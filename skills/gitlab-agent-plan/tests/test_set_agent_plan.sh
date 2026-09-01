#!/usr/bin/env bash
# Offline test suite for set_agent_plan.sh, focused on the availability
# preflight: telling "the Agent Plan widget is not available in this namespace"
# (exit 4, nothing written) apart from "available but not yet set on this item"
# (warn, write anyway).
#
# A stub `glab` on PATH answers the preflight query from one fixture and the
# mutation from another, and records whether the mutation was ever attempted —
# which is the property that matters for exit 4.
#
# Usage: bash skills/gitlab-agent-plan/tests/test_set_agent_plan.sh
set -uo pipefail

here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
script="$here/../scripts/set_agent_plan.sh"
mkfixture="$here/mkfixture_set.py"
[[ -f "$script" ]] || { echo "error: script not found: $script" >&2; exit 1; }

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
plan="$work/plan.md"
printf '# Plan\n\nStep one.\n' >"$plan"

# --- glab stub -------------------------------------------------------------
# Serves $MOCK_LOOKUP for the preflight query and $MOCK_MUTATION for the
# mutation, touching $MOCK_MUTATED when a mutation is attempted.
mkdir -p "$work/bin"
cat >"$work/bin/glab" <<'STUB'
#!/usr/bin/env bash
q=""
for a in "$@"; do
  case "$a" in query=*) q="${a#query=}" ;; esac
done
if [[ "$q" == mutation* ]]; then
  echo "mutation attempted" >>"$MOCK_MUTATED"
  cat "$MOCK_MUTATION"
else
  cat "$MOCK_LOOKUP"
fi
exit "${MOCK_EXIT:-0}"
STUB
chmod +x "$work/bin/glab"
export PATH="$work/bin:$PATH"
export MOCK_MUTATED="$work/mutated.log"

pass=0; fail=0
ok()  { pass=$((pass+1)); printf '  ok   %s\n' "$1"; }
bad() { fail=$((fail+1)); printf '  FAIL %s\n     %s\n' "$1" "$2"; }
check() { if [[ "$2" == "$3" ]]; then ok "$1"; else bad "$1" "expected [$2] got [$3]"; fi }
has()   { if grep -q "$2" "$3"; then ok "$1"; else bad "$1" "no match for [$2] in: $(cat "$3")"; fi }
hasnt() { if grep -q "$2" "$3"; then bad "$1" "unexpected match for [$2]"; else ok "$1"; fi }
mutated()     { if [[ -s "$MOCK_MUTATED" ]]; then ok "$1"; else bad "$1" "mutation was NOT attempted"; fi }
not_mutated() { if [[ -s "$MOCK_MUTATED" ]]; then bad "$1" "mutation WAS attempted"; else ok "$1"; fi }

# run <lookup_kind> <mutation_kind> [extra env assignments...]
run() {
  python3 "$mkfixture" "$1" >"$work/lookup.json"
  python3 "$mkfixture" "$2" >"$work/mutation.json"
  export MOCK_LOOKUP="$work/lookup.json" MOCK_MUTATION="$work/mutation.json"
  : >"$MOCK_MUTATED"
  out="$work/out"; err="$work/err"
  bash "$script" https://gitlab.com/grp/proj/-/work_items/1 "$plan" >"$out" 2>"$err"
  rc=$?
}

echo "== widget available and already on the item =="
run avail-set ok
check "exit 0" 0 "$rc"
mutated "mutation attempted"
has   "OK line on stdout" 'OK: agent plan set, 11 bytes' "$out"
hasnt "no warning" 'warning:' "$err"
hasnt "no availability error" 'not available for' "$err"
has   "work item type reported" 'Work item: gid://gitlab/WorkItem/424242 (Issue)' "$err"
hasnt "stdout free of diagnostics" 'Work item:' "$out"

# The reported count must be real UTF-8 bytes, not characters: this fixture's
# content is 11 characters but 14 bytes.
run avail-set ok-utf8
check "utf-8 fixture exit 0" 0 "$rc"
has   "byte count is UTF-8 bytes, not characters" 'OK: agent plan set, 14 bytes' "$out"

echo
echo "== widget defined for the type but not listed on the item: warn, write anyway =="
run avail-unset ok
check "exit 0" 0 "$rc"
mutated "mutation still attempted"
has   "warns about the item, not the namespace" 'warning: AGENT_PLAN is defined for Issue in grp/proj but is not listed on this item' "$err"
hasnt "does not claim the feature is unavailable" 'not available for' "$err"

echo
echo "== widget absent from the type's definitions: exit 4, nothing written =="
run unavail ok
check "exit 4" 4 "$rc"
not_mutated "mutation NOT attempted"
has   "names the type and project" 'error: the Agent Plan widget is not available for Issue in grp/proj' "$err"
has   "predicts the exact GitLab rejection" 'not supported by Issue type: \[:agent_plan_widget\]' "$err"
has   "explains namespace gating" 'gated per namespace' "$err"
has   "states nothing was written" 'Nothing was written' "$err"
has   "offers the override" 'AGENT_PLAN_FORCE=1 to attempt it anyway' "$err"
check "stdout empty" 0 "$(wc -c <"$out" | tr -d ' ')"

echo
echo "== availability is judged per type, not per project =="
run other-type ok
check "AGENT_PLAN on Task only -> Issue still exit 4" 4 "$rc"
not_mutated "mutation NOT attempted for the wrong type"

echo
echo "== AGENT_PLAN_FORCE=1 overrides the preflight =="
python3 "$mkfixture" unavail >"$work/lookup.json"
python3 "$mkfixture" mut-errors >"$work/mutation.json"
export MOCK_LOOKUP="$work/lookup.json" MOCK_MUTATION="$work/mutation.json"
: >"$MOCK_MUTATED"
rc=0
AGENT_PLAN_FORCE=1 bash "$script" https://gitlab.com/grp/proj/-/work_items/1 "$plan" \
  >"$work/out" 2>"$work/err" || rc=$?
check "forced run reaches the mutation and fails on the real error" 1 "$rc"
mutated "forced mutation attempted"
has   "force is announced" 'AGENT_PLAN_FORCE=1 set; attempting the write anyway' "$work/err"
hasnt "forced run does not claim nothing was written" 'Nothing was written' "$work/err"
has   "server rejection surfaced verbatim" 'MUTATION ERRORS' "$work/err"
has   "rejection text preserved" 'not supported by Issue type' "$work/err"

echo
echo "== mutation-stage failures (exit 1) =="
run avail-set mut-errors
check "mutation errors: exit 1" 1 "$rc"
has   "mutation errors surfaced" 'MUTATION ERRORS' "$err"

run avail-set empty-after
check "empty content after write: exit 1" 1 "$rc"
has   "empty-after message" 'no AGENT_PLAN content after update' "$err"

run avail-set no-payload
check "null payload: exit 1" 1 "$rc"
has   "null payload message" 'no workItemUpdate payload' "$err"

echo
echo "== preflight-stage failures (exit 1) =="
run no-nodes ok
check "work item not found: exit 1" 1 "$rc"
not_mutated "not found -> no mutation"
has   "not found message" 'error: work item not found: grp/proj#1' "$err"

run null-project ok
check "null project: exit 1" 1 "$rc"
has   "null project message" 'error: work item not found' "$err"

run gql-errors ok
check "graphql errors: exit 1" 1 "$rc"
not_mutated "graphql errors -> no mutation"
has   "graphql errors surfaced" 'GRAPHQL ERRORS' "$err"

echo
echo "== non-JSON / auth guards (no tracebacks) =="
python3 "$mkfixture" avail-set >"$work/lookup.json"
printf '<html>502 Bad Gateway</html>' >"$work/lookup.json"
python3 "$mkfixture" ok >"$work/mutation.json"
export MOCK_LOOKUP="$work/lookup.json" MOCK_MUTATION="$work/mutation.json"
: >"$MOCK_MUTATED"
rc=0
bash "$script" https://gitlab.com/grp/proj/-/work_items/1 "$plan" >"$work/out" 2>"$work/err" || rc=$?
check "non-JSON preflight: exit 1" 1 "$rc"
has   "non-JSON preflight guarded" 'error: unexpected non-JSON response from glab' "$work/err"
hasnt "no traceback from preflight" 'Traceback' "$work/err"
not_mutated "non-JSON preflight -> no mutation"

python3 "$mkfixture" avail-set >"$work/lookup.json"
printf '<html>502</html>' >"$work/mutation.json"
: >"$MOCK_MUTATED"
rc=0
bash "$script" https://gitlab.com/grp/proj/-/work_items/1 "$plan" >"$work/out" 2>"$work/err" || rc=$?
check "non-JSON mutation response: exit 1" 1 "$rc"
has   "non-JSON mutation guarded" 'error: unexpected non-JSON response from glab' "$work/err"
hasnt "no traceback from mutation stage" 'Traceback' "$work/err"

echo
echo "== argument validation =="
python3 "$mkfixture" avail-set >"$work/lookup.json"
python3 "$mkfixture" ok >"$work/mutation.json"
for args in "grp/proj" "grp/proj 1"; do
  rc=0
  # shellcheck disable=SC2086  # deliberate word splitting of the arg fixture
  bash "$script" $args >"$work/out" 2>"$work/err" || rc=$?
  check "rejects incomplete args [$args]" 1 "$rc"
done
rc=0
bash "$script" https://gitlab.com/grp/proj/-/work_items/1 /no/such/plan.md >"$work/out" 2>"$work/err" || rc=$?
check "missing plan file: exit 1" 1 "$rc"
has   "missing plan file message" 'plan file not found' "$work/err"

echo
printf '%d passed, %d failed\n' "$pass" "$fail"
[[ "$fail" -eq 0 ]]
