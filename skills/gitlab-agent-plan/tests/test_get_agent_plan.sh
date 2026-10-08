#!/usr/bin/env bash
# Offline test suite for get_agent_plan.sh.
#
# Stubs `glab` on PATH so no network or GitLab auth is needed: the stub echoes a
# fixture body (built by mkfixture_get.py) and records the arguments it was called
# with, letting us assert both the parsing/output behaviour and the exact
# GraphQL query the script builds from its arguments.
#
# Usage: bash skills/gitlab-agent-plan/tests/test_get_agent_plan.sh
# Exit 0 if every case passes.
set -uo pipefail

here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
script="$here/../scripts/get_agent_plan.sh"
mkfixture="$here/mkfixture_get.py"
[[ -f "$script" ]] || { echo "error: script not found: $script" >&2; exit 1; }

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

# --- glab stub -------------------------------------------------------------
# Prints $MOCK_BODY_FILE to stdout, appends its own argv to $MOCK_ARGS_FILE,
# exits with $MOCK_EXIT (default 0).
mkdir -p "$work/bin"
cat >"$work/bin/glab" <<'STUB'
#!/usr/bin/env bash
printf '%s\n' "$@" >>"$MOCK_ARGS_FILE"
[[ -n "${MOCK_BODY_FILE:-}" ]] && cat "$MOCK_BODY_FILE"
exit "${MOCK_EXIT:-0}"
STUB
chmod +x "$work/bin/glab"
export PATH="$work/bin:$PATH"
export MOCK_ARGS_FILE="$work/args.txt"

# --- assertions ------------------------------------------------------------
pass=0; fail=0
ok()  { pass=$((pass+1)); printf '  ok   %s\n' "$1"; }
bad() { fail=$((fail+1)); printf '  FAIL %s\n     %s\n' "$1" "$2"; }

check() { # check <name> <expected> <actual>
  if [[ "$2" == "$3" ]]; then ok "$1"; else bad "$1" "expected [$2] got [$3]"; fi
}
has() { # has <name> <pattern> <file>
  if grep -q "$2" "$3"; then ok "$1"; else bad "$1" "no match for [$2] in: $(cat "$3")"; fi
}
hasnt() { # hasnt <name> <pattern> <file>
  if grep -q "$2" "$3"; then bad "$1" "unexpected match for [$2] in: $(cat "$3")"; else ok "$1"; fi
}
same() { # same <name> <expected_file> <actual_file>
  if cmp -s "$2" "$3"; then ok "$1"; else bad "$1" "$(cmp "$2" "$3" 2>&1)"; fi
}
bytes() { wc -c <"$1" | tr -d ' '; }

# run <body_kind|raw:BODY|none> [content_file] -- <script args...>
# Sets: rc, out (stdout file), err (stderr file)
run() {
  local kind="$1"; shift
  local content=""
  if [[ "${1:-}" != "--" ]]; then content="$1"; shift; fi
  [[ "${1:-}" == "--" ]] && shift
  : >"$MOCK_ARGS_FILE"
  if [[ "$kind" == "raw:"* ]]; then
    printf '%s' "${kind#raw:}" >"$work/body.json"
  elif [[ "$kind" == "none" ]]; then
    : >"$work/body.json"
  else
    python3 "$mkfixture" "$kind" ${content:+"$content"} >"$work/body.json"
  fi
  export MOCK_BODY_FILE="$work/body.json"
  out="$work/out"; err="$work/err"
  bash "$script" "$@" >"$out" 2>"$err"
  rc=$?
}

# project and iid go to glab as GraphQL variables. Each one is its own argv
# line, for example `fullPath=grp/proj`. Read the value that glab receives.
field_of() { grep -m1 "^$1=" "$MOCK_ARGS_FILE" | cut -d= -f2-; }
query_of() { grep -m1 '^query=' "$MOCK_ARGS_FILE"; }

echo "== fixtures =="
# A plan with unicode, a trailing newline, and shell/GraphQL metacharacters that
# must survive untouched.
# shellcheck disable=SC2016  # the literal $(...)/$VAR text is the point of the fixture
printf '# Plan — étape 1\n\n- `$(rm -rf /)` and "quotes" and $VAR\n- backslash \\ and %%s\n' \
  >"$work/plan.md"
printf 'no trailing newline' >"$work/plan-nonl.md"
echo "  built $(bytes "$work/plan.md") byte plan fixture"

echo
echo "== happy path =="
run plan "$work/plan.md" -- https://gitlab.com/grp/sub/proj/-/work_items/7
check "exit 0" 0 "$rc"
same  "stdout byte-identical to plan (unicode, metachars, trailing newline)" "$work/plan.md" "$out"
has   "diagnostics on stderr" 'Work item: gid://gitlab/WorkItem/424242' "$err"
hasnt "stdout free of diagnostics" 'Work item:' "$out"

run plan "$work/plan-nonl.md" -- grp/proj 7 "$work/written.md"
check "out-file exit 0" 0 "$rc"
same  "out-file byte-identical (no trailing newline added)" "$work/plan-nonl.md" "$work/written.md"
check "out-file mode: stdout empty" 0 "$(bytes "$out")"
has   "OK summary on stderr with byte count and path" "OK: agent plan fetched, 19 bytes -> $work/written.md" "$err"

# The count must be real UTF-8 bytes, not characters: this fixture is 80 bytes
# but only 78 characters (é and — are multi-byte).
run plan "$work/plan.md" -- grp/proj 7 "$work/written-utf8.md"
has   "byte count is UTF-8 bytes, not characters" \
      "OK: agent plan fetched, $(wc -c <"$work/plan.md" | tr -d ' ') bytes" "$err"

echo
echo "== argument parsing (assert the query glab receives) =="
run plan "$work/plan.md" -- https://gitlab.com/grp/sub/proj/-/work_items/7
check "url: nested subgroup fullPath" 'grp/sub/proj' "$(field_of fullPath)"
check "url: iid"                      '7'            "$(field_of iid)"
q_baseline=$(query_of)

run plan "$work/plan.md" -- 'https://gitlab.com/grp/proj/-/work_items/12/'
check "url: trailing slash trimmed" '12' "$(field_of iid)"

run plan "$work/plan.md" -- 'https://gitlab.com/grp/proj/-/work_items/13?work_item_iid=99'
check "url: query string trimmed" '13' "$(field_of iid)"

run plan "$work/plan.md" -- 'https://gitlab.com/grp/proj/-/work_items/14#note_1'
check "url: fragment trimmed" '14' "$(field_of iid)"

run plan "$work/plan.md" -- 'http://self.managed.example/grp/proj/-/work_items/15'
check "url: http scheme + self-managed host discarded" 'grp/proj' "$(field_of fullPath)"

run plan "$work/plan.md" -- grp/sub/proj 21
check "explicit: fullPath" 'grp/sub/proj' "$(field_of fullPath)"
check "explicit: iid"      '21'           "$(field_of iid)"

# A quote in an argument must not change the query.
run plan "$work/plan.md" -- 'grp/proj" ) { evil }' 99
check "injection: hostile fullPath stays a variable value" 'grp/proj" ) { evil }' "$(field_of fullPath)"
check "injection: query text does not change"              "$q_baseline"          "$(query_of)"
has   "query uses AgentPlan inline fragment" 'on WorkItemWidgetAgentPlan' "$MOCK_ARGS_FILE"
if grep -qi 'mutation' "$MOCK_ARGS_FILE"; then
  bad "read-only: no mutation in query" "query contains a mutation"
else
  ok "read-only: no mutation in query"
fi

run plan "$work/plan.md" -- grp/proj
check "missing iid rejected" 1 "$rc"
has   "missing iid message" 'could not determine project/iid' "$err"

run plan "$work/plan.md" --
check "no args rejected" 1 "$rc"

echo
echo "== no plan set (exit 3) =="
for kind in empty whitespace null-content no-widget; do
  run "$kind" -- grp/proj 7
  check "$kind: exit 3" 3 "$rc"
  check "$kind: stdout empty" 0 "$(bytes "$out")"
  has   "$kind: note on stderr" 'note: no agent plan set on grp/proj#7' "$err"
done

echo
echo "== failures (exit 1) =="
run no-nodes -- grp/proj 7
check "no-nodes: exit 1" 1 "$rc"
has   "no-nodes: message" 'error: work item not found: grp/proj#7' "$err"

run null-project -- grp/proj 7
check "null-project: exit 1" 1 "$rc"
has   "null-project: message" 'error: work item not found' "$err"

run gql-errors -- grp/proj 7
check "gql-errors: exit 1" 1 "$rc"
has   "gql-errors: surfaced verbatim" 'GRAPHQL ERRORS' "$err"

run 'raw:<html>502 Bad Gateway</html>' -- grp/proj 7
check "non-JSON: exit 1" 1 "$rc"
has   "non-JSON: guarded with a clear message" 'error: unexpected non-JSON response from glab' "$err"
hasnt "non-JSON: no traceback leaked" 'Traceback' "$err"

run none -- grp/proj 7
check "empty body: exit 1" 1 "$rc"
has   "empty body: guarded" 'error: unexpected non-JSON response' "$err"

MOCK_EXIT=1 run plan "$work/plan.md" -- grp/proj 7
check "glab non-zero exit propagates as 1" 1 "$rc"
unset MOCK_EXIT

run plan "$work/plan.md" -- grp/proj 7 /nonexistent-dir/out.md
check "unwritable out-file: exit 1" 1 "$rc"
has   "unwritable out-file: clean error" 'error: could not write' "$err"
hasnt "unwritable out-file: no traceback leaked" 'Traceback' "$err"

echo
echo "== preflight =="
mkdir -p "$work/nobin"
rc=0
# PATH holds only the empty nobin dir, so a glab installed in /usr/bin or /bin
# is not found. Run bash by its full path ($BASH) since PATH cannot find it.
PATH="$work/nobin" "$BASH" "$script" grp/proj 7 >"$work/o" 2>"$work/e" || rc=$?
check "glab missing: exit 1" 1 "$rc"
has   "glab missing message" 'error: glab not found on PATH' "$work/e"

echo
printf '%d passed, %d failed\n' "$pass" "$fail"
[[ "$fail" -eq 0 ]]
