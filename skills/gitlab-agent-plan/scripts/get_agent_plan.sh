#!/usr/bin/env bash
# Fetch (read) a GitLab work item's Agent Plan / Workplan widget as Markdown,
# via a GraphQL query using `glab`.
#
# The Agent Plan widget is a first-class *property* of the work item — distinct
# from its description or its notes/comments. The write counterpart is
# ./set_agent_plan.sh.
#
# Usage:
#   get_agent_plan.sh <work_item_url> [out_file.md]
#   get_agent_plan.sh <project/full/path> <iid> [out_file.md]
#
# Without an out file the plan Markdown goes to stdout and all diagnostics go to
# stderr, so stdout stays clean and pipeable.
#
# Exit codes:
#   0  plan returned
#   3  no agent plan set on the item (widget absent or content empty)
#   1  failure (work item not found, auth/network error, GraphQL errors)
#
# Examples:
#   get_agent_plan.sh https://gitlab.com/gitlab-org/build/CNG/-/work_items/2332
#   get_agent_plan.sh gitlab-org/build/CNG 2332 plan.md
set -Eeuo pipefail

die() { echo "error: $*" >&2; exit 1; }
command -v glab >/dev/null || die "glab not found on PATH"
command -v python3 >/dev/null || die "python3 not found on PATH"

if [[ "${1:-}" == http* ]]; then
  url="$1"; out_file="${2:-}"
  # https://HOST/<project/path>/-/work_items/<iid>
  rest="${url#*://}"; rest="${rest#*/}"           # strip host
  project="${rest%%/-/work_items/*}"
  iid="${rest##*/-/work_items/}"; iid="${iid%%[/?#]*}"
else
  project="${1:-}"; iid="${2:-}"; out_file="${3:-}"
fi

[[ -n "${project:-}" && -n "${iid:-}" ]] || die "could not determine project/iid; see usage"

# 1. Fetch the work item and its Agent Plan widget in a single query.
#    Pass project and iid as GraphQL variables. Do not put them in the query
#    text. A quote in either value must not change the query.
#    Use -f (--raw-field). Do not use -F (--field): -F sends an integer-like
#    value as a JSON number, and GitLab rejects a number for a String!
#    variable ("Could not coerce value 2332 to String").
# shellcheck disable=SC2016  # $fullPath/$iid are GraphQL variables, not shell vars
resp=$(glab api graphql \
  -f query='query($fullPath: ID!, $iid: String!) { project(fullPath: $fullPath) { workItems(iid: $iid) { nodes { id iid title widgets { type ... on WorkItemWidgetAgentPlan { content } } } } } }' \
  -f fullPath="$project" \
  -f iid="$iid")

# 2. Parse, report to stderr, emit the plan to stdout or the out file.
printf '%s' "$resp" | python3 -c '
import sys, json

out_file = sys.argv[1] if len(sys.argv) > 1 else ""
ref = sys.argv[2]

def die(msg):
    print("error:", msg, file=sys.stderr); sys.exit(1)

raw = sys.stdin.read()
try:
    doc = json.loads(raw)
except ValueError:
    die("unexpected non-JSON response from glab (auth/network?): " + raw[:200].strip())

errs = doc.get("errors") or []
if errs:
    print("GRAPHQL ERRORS:", errs, file=sys.stderr); sys.exit(1)

project = (doc.get("data") or {}).get("project") or {}
nodes = (project.get("workItems") or {}).get("nodes") or []
if not nodes:
    die("work item not found: " + ref)
n = nodes[0]

print("Work item: %s  %s#%s  %s" % (n["id"], ref.split("#")[0], n.get("iid"), n.get("title") or ""),
      file=sys.stderr)

ap = next((w for w in n.get("widgets", []) if w.get("type") == "AGENT_PLAN"), None)
content = (ap or {}).get("content") or ""
if not content.strip():
    print("note: no agent plan set on " + ref, file=sys.stderr); sys.exit(3)

if out_file:
    try:
        with open(out_file, "w", encoding="utf-8", newline="") as fh:
            fh.write(content)
    except OSError as exc:
        die("could not write %s: %s" % (out_file, exc.strerror or exc))
    print("OK: agent plan fetched, %d bytes -> %s"
          % (len(content.encode("utf-8")), out_file), file=sys.stderr)
else:
    sys.stdout.write(content)
' "$out_file" "${project}#${iid}"
