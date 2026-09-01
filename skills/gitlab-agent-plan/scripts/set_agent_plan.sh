#!/usr/bin/env bash
# Set (or update) a GitLab work item's Agent Plan / Workplan widget from a
# Markdown file, via the GraphQL workItemUpdate mutation using `glab`.
#
# The Agent Plan widget is a first-class *property* of the work item — distinct
# from posting a note/comment or editing the description.
#
# Usage:
#   set_agent_plan.sh <work_item_url> <plan_file.md>
#   set_agent_plan.sh <project/full/path> <iid> <plan_file.md>
#
# Exit codes:
#   0  plan written and verified
#   4  the Agent Plan widget is not available for this work item type in this
#      project (namespace feature gate) — nothing was attempted
#   1  failure (bad arguments, work item not found, auth/network, GraphQL errors,
#      or the write did not take effect)
#
# Set AGENT_PLAN_FORCE=1 to attempt the write even when the preflight says the
# widget is unavailable.
#
# Examples:
#   set_agent_plan.sh https://gitlab.com/gitlab-org/build/CNG/-/work_items/2332 plan.md
#   set_agent_plan.sh gitlab-org/build/CNG 2332 plan.md
set -Eeuo pipefail

die() { echo "error: $*" >&2; exit 1; }
command -v glab >/dev/null || die "glab not found on PATH"
command -v python3 >/dev/null || die "python3 not found on PATH"

if [[ "${1:-}" == http* ]]; then
  url="$1"; plan_file="${2:-}"
  # https://HOST/<project/path>/-/work_items/<iid>
  rest="${url#*://}"; rest="${rest#*/}"           # strip host
  project="${rest%%/-/work_items/*}"
  iid="${rest##*/-/work_items/}"; iid="${iid%%[/?#]*}"
else
  project="${1:-}"; iid="${2:-}"; plan_file="${3:-}"
fi

[[ -n "${project:-}" && -n "${iid:-}" ]] || die "could not determine project/iid; see usage"
[[ -n "${plan_file:-}" ]] || die "missing plan file argument"
[[ -f "$plan_file" ]] || die "plan file not found: $plan_file"

echo "Project: ${project}  iid: ${iid}  plan: ${plan_file}" >&2

# 1. Resolve the work item and determine whether the Agent Plan widget is
#    actually available here.
#
#    Two different "AGENT_PLAN is missing" situations must not be conflated:
#      - missing from the *type's* widgetDefinitions -> the feature is not
#        enabled for this namespace, GitLab will reject the write outright
#        ("widget keys are not supported by <Type> type"). Fail before writing.
#      - present for the type but missing from *this item's* widgets -> odd but
#        writable; warn and proceed.
#    Use GraphQL variables, as the mutation below does. For the -f/-F rule, see
#    the comment in get_agent_plan.sh.
# shellcheck disable=SC2016  # $fullPath/$iid are GraphQL variables, not shell vars
lookup=$(glab api graphql \
  -f query='query($fullPath: ID!, $iid: String!) { project(fullPath: $fullPath) { workItems(iid: $iid) { nodes { id workItemType { name } widgets { type } } } workItemTypes { nodes { name widgetDefinitions { type } } } } }' \
  -f fullPath="$project" \
  -f iid="$iid")

set +e
meta=$(printf '%s' "$lookup" | python3 -c '
import sys, json

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

proj = (doc.get("data") or {}).get("project") or {}
nodes = (proj.get("workItems") or {}).get("nodes") or []
if not nodes:
    sys.exit(2)                      # caller reports "work item not found"
n = nodes[0]

tname = (n.get("workItemType") or {}).get("name") or "(unknown type)"
on_item = "AGENT_PLAN" in [w.get("type") for w in n.get("widgets", [])]
on_type = False
for t in (proj.get("workItemTypes") or {}).get("nodes") or []:
    if t.get("name") == tname:
        on_type = "AGENT_PLAN" in [w.get("type") for w in (t.get("widgetDefinitions") or [])]
        break

print("\t".join([n["id"], tname, "1" if on_item else "0", "1" if on_type else "0"]))
')
probe_rc=$?
set -e

case "$probe_rc" in
  0) ;;
  2) die "work item not found: ${project}#${iid}" ;;
  *) exit 1 ;;   # the probe already explained itself on stderr
esac

IFS=$'\t' read -r gid type_name on_item on_type <<<"$meta"
echo "Work item: ${gid} (${type_name})" >&2

if [[ "$on_type" != "1" && "$on_item" != "1" ]]; then
  {
    echo "error: the Agent Plan widget is not available for ${type_name} in ${project}."
    echo "       AGENT_PLAN is absent from that type's widgetDefinitions, so GitLab will"
    echo "       reject the write with:"
    echo "         Following widget keys are not supported by ${type_name} type: [:agent_plan_widget]"
    echo "       The feature is experimental and gated per namespace — it must be enabled"
    echo "       for ${project%%/*}."
  } >&2
  if [[ "${AGENT_PLAN_FORCE:-}" != "1" ]]; then
    echo "       Nothing was written. Re-run with AGENT_PLAN_FORCE=1 to attempt it anyway." >&2
    exit 4
  fi
  echo "       AGENT_PLAN_FORCE=1 set; attempting the write anyway." >&2
elif [[ "$on_item" != "1" ]]; then
  echo "warning: AGENT_PLAN is defined for ${type_name} in ${project} but is not listed on this item; attempting the write" >&2
fi

# 2. Set the Agent Plan widget content.
# shellcheck disable=SC2016  # $id/$content are GraphQL variables, not shell vars
resp=$(glab api graphql \
  -f query='mutation($id: WorkItemID!, $content: String!) { workItemUpdate(input: {id: $id, agentPlanWidget: {content: $content}}) { workItem { widgets { ... on WorkItemWidgetAgentPlan { type content } } } errors } }' \
  -f id="$gid" \
  -f content="$(cat "$plan_file")")

# 3. Report + verify.
printf '%s' "$resp" | python3 -c '
import sys, json

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

u = (doc.get("data") or {}).get("workItemUpdate")
if not u:
    die("no workItemUpdate payload in response")
errs = u.get("errors") or []
if errs:
    print("MUTATION ERRORS:", errs, file=sys.stderr); sys.exit(1)
ap = next((w for w in u["workItem"]["widgets"] if w.get("type") == "AGENT_PLAN"), None)
if not ap or not (ap.get("content") or ""):
    die("no AGENT_PLAN content after update")
print("OK: agent plan set,", len(ap["content"].encode("utf-8")), "bytes")
'
