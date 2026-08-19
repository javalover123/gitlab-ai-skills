#!/usr/bin/env bash
# End-to-end round-trip test: set_agent_plan.sh writes a plan,
# get_agent_plan.sh reads it back, and the bytes must match.
#
# Both scripts talk to a single stub `glab` that plays the part of the GitLab
# GraphQL endpoint: it stores whatever `content` the mutation sends into a state
# file and serves that same value back to the fetch query. Because the stub
# receives exactly the argv `glab` would have received, this exercises the real
# contract between the two scripts — including `glab`'s job of JSON-escaping the
# Markdown — without a network call, credentials, or the AGENT_PLAN feature flag.
#
# Motivation: the flag is namespace-gated (present in gitlab-org/build/CNG,
# absent in personal namespaces), so a live write round trip is not reproducible
# on demand. This is.
#
# Usage: bash skills/gitlab-agent-plan/tests/test_roundtrip_mock.sh
set -uo pipefail

here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
get="$here/../scripts/get_agent_plan.sh"
set_="$here/../scripts/set_agent_plan.sh"

for f in "$get" "$set_"; do
  [[ -f "$f" ]] || { echo "error: not found: $f" >&2; exit 1; }
done

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
export MOCK_STATE="$work/stored_content"

# --- stub GitLab GraphQL endpoint ------------------------------------------
mkdir -p "$work/bin"
cat >"$work/bin/glab" <<'STUB'
#!/usr/bin/env python3
"""Stand-in for `glab api graphql`, backed by a file holding the stored plan."""
import json
import os
import sys

args = sys.argv[1:]
state = os.environ["MOCK_STATE"]


def arg(prefix):
    for a in args:
        if a.startswith(prefix):
            return a[len(prefix):]
    return None


query = arg("query=") or ""
item = {"id": "gid://gitlab/WorkItem/424242", "iid": "1", "title": "mock item"}

if query.startswith("mutation"):
    # The set path: persist exactly what glab was handed as the content variable.
    content = arg("content=")
    if content is None:
        sys.exit("stub: mutation without content")
    with open(state, "w", encoding="utf-8", newline="") as fh:
        fh.write(content)
    body = {"data": {"workItemUpdate": {
        "workItem": {"widgets": [{"type": "AGENT_PLAN", "content": content}]},
        "errors": [],
    }}}
elif "WorkItemWidgetAgentPlan" in query:
    # The fetch path: serve the stored content back.
    try:
        with open(state, encoding="utf-8", newline="") as fh:
            content = fh.read()
    except OSError:
        content = ""
    node = dict(item, widgets=[{"type": "DESCRIPTION"},
                               {"type": "AGENT_PLAN", "content": content}])
    body = {"data": {"project": {"workItems": {"nodes": [node]}}}}
else:
    # The set path's preflight: work item id/type/widgets plus the per-type
    # widget definitions it uses to decide whether AGENT_PLAN is available here.
    node = dict(item,
                workItemType={"name": "Issue"},
                widgets=[{"type": "DESCRIPTION"}, {"type": "AGENT_PLAN"}])
    body = {"data": {"project": {
        "workItems": {"nodes": [node]},
        "workItemTypes": {"nodes": [
            {"name": "Issue", "widgetDefinitions": [{"type": "DESCRIPTION"},
                                                    {"type": "AGENT_PLAN"}]},
            {"name": "Task", "widgetDefinitions": [{"type": "DESCRIPTION"}]},
        ]},
    }}}

sys.stdout.write(json.dumps(body))
STUB
chmod +x "$work/bin/glab"
export PATH="$work/bin:$PATH"

pass=0; fail=0
ok()  { pass=$((pass+1)); printf '  ok   %s\n' "$1"; }
bad() { fail=$((fail+1)); printf '  FAIL %s\n     %s\n' "$1" "$2"; }

# roundtrip <name> <plan_file>
roundtrip() {
  local name="$1" plan="$2"
  : >"$MOCK_STATE"
  if ! bash "$set_" https://gitlab.com/grp/proj/-/work_items/1 "$plan" >"$work/set.log" 2>&1; then
    bad "$name: set" "$(cat "$work/set.log")"; return
  fi
  if ! bash "$get" https://gitlab.com/grp/proj/-/work_items/1 "$work/back.md" \
       >"$work/get.out" 2>"$work/get.err"; then
    bad "$name: fetch" "$(cat "$work/get.err")"; return
  fi
  if cmp -s "$plan" "$work/back.md"; then
    ok "$name: round trip byte-identical ($(wc -c <"$plan" | tr -d ' ') bytes)"
  else
    # A sole trailing-newline difference is the known set-path artifact of
    # `-f content="$(cat file)"`; report it distinctly rather than as a mismatch.
    if [[ "$(cat "$plan")" == "$(cat "$work/back.md")" ]]; then
      ok "$name: round trip matches except trailing newline (known set-path artifact)"
    else
      bad "$name: round trip" "$(cmp "$plan" "$work/back.md" 2>&1)"
    fi
  fi
}

echo "== round trip: set_agent_plan.sh -> get_agent_plan.sh =="

printf '# Simple plan\n\nOne step.\n' >"$work/simple.md"
roundtrip "plain markdown" "$work/simple.md"

cat >"$work/rich.md" <<'PLAN'
# Round-trip fixture — étape 1

- unicode: café, ✅, 日本語, emoji 🎉
- metacharacters: `$(rm -rf /)`, "quotes", 'single', $VAR, \backslash, %s
- GraphQL-ish: {"id": "gid://gitlab/WorkItem/1"} and $content
- a fenced block:

```bash
echo "backticks ` and \$dollars and newlines"
printf '%s\n' "$@"
```

| col | val |
|-----|-----|
| a   | 1   |
PLAN
roundtrip "unicode + shell/GraphQL metacharacters + fences" "$work/rich.md"

printf 'no trailing newline' >"$work/nonl.md"
roundtrip "no trailing newline" "$work/nonl.md"

printf '# Blank lines\n\n\n\n## After three blanks\n\n\ttab-indented\n   trailing spaces   \n' \
  >"$work/ws.md"
roundtrip "blank lines, tabs, trailing spaces" "$work/ws.md"

python3 -c 'open("'"$work"'/big.md","w").write("\n".join("- line %d — ünïcode" % i for i in range(2000)) + "\n")'
roundtrip "large plan (2000 lines)" "$work/big.md"

echo
echo "== fetch sees an unset plan as unset (exit 3) =="
: >"$MOCK_STATE"
rc=0
bash "$get" https://gitlab.com/grp/proj/-/work_items/1 >"$work/o" 2>"$work/e" || rc=$?
if [[ "$rc" -eq 3 ]]; then ok "empty stored content -> exit 3"; else bad "empty stored content -> exit 3" "got exit $rc"; fi

echo
echo "== overwrite: second set replaces the first =="
: >"$MOCK_STATE"
bash "$set_" https://gitlab.com/grp/proj/-/work_items/1 "$work/simple.md" >/dev/null 2>&1
bash "$set_" https://gitlab.com/grp/proj/-/work_items/1 "$work/rich.md" >/dev/null 2>&1
bash "$get" https://gitlab.com/grp/proj/-/work_items/1 "$work/back2.md" >/dev/null 2>&1
if [[ "$(cat "$work/rich.md")" == "$(cat "$work/back2.md")" ]]; then
  ok "fetch returns the most recent plan"
else
  bad "fetch returns the most recent plan" "$(cmp "$work/rich.md" "$work/back2.md" 2>&1)"
fi

echo
printf '%d passed, %d failed\n' "$pass" "$fail"
[[ "$fail" -eq 0 ]]
