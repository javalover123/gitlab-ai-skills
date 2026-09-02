#!/usr/bin/env python3
"""Emit a mock `glab api graphql` response body for get_agent_plan.sh tests.

Usage: mkfixture_get.py <kind> [content_file]

Kinds:
  plan          project + work item + AGENT_PLAN widget whose content is the
                verbatim bytes of content_file
  empty         AGENT_PLAN widget present, content ""
  whitespace    AGENT_PLAN widget present, content " \n\t\n "
  null-content  AGENT_PLAN widget present, content null
  no-widget     work item found, but no AGENT_PLAN in the widget list
  no-nodes      project found, workItems.nodes == []
  null-project  data.project == null
  gql-errors    top-level GraphQL errors array
"""
import json
import sys

kind = sys.argv[1]


def item(widgets):
    return {
        "data": {
            "project": {
                "workItems": {
                    "nodes": [
                        {
                            "id": "gid://gitlab/WorkItem/424242",
                            "iid": "7",
                            "title": "mock item",
                            "widgets": widgets,
                        }
                    ]
                }
            }
        }
    }


other = [{"type": "DESCRIPTION"}, {"type": "NOTES"}]

if kind == "plan":
    with open(sys.argv[2], "rb") as fh:
        content = fh.read().decode("utf-8")
    doc = item(other + [{"type": "AGENT_PLAN", "content": content}])
elif kind == "empty":
    doc = item(other + [{"type": "AGENT_PLAN", "content": ""}])
elif kind == "whitespace":
    doc = item(other + [{"type": "AGENT_PLAN", "content": " \n\t\n "}])
elif kind == "null-content":
    doc = item(other + [{"type": "AGENT_PLAN", "content": None}])
elif kind == "no-widget":
    doc = item(other)
elif kind == "no-nodes":
    doc = {"data": {"project": {"workItems": {"nodes": []}}}}
elif kind == "null-project":
    doc = {"data": {"project": None}}
elif kind == "gql-errors":
    doc = {
        "errors": [{"message": "Field 'agentPlanWidget' doesn't exist"}],
        "data": {"project": None},
    }
else:
    sys.exit("unknown fixture kind: " + kind)

sys.stdout.write(json.dumps(doc))
