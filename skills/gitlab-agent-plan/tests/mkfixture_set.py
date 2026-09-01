#!/usr/bin/env python3
"""Emit mock `glab api graphql` bodies for set_agent_plan.sh tests.

Usage: mkfixture_set.py <kind>

Lookup-response kinds (the preflight query), named <on_type>-<on_item>:
  avail-set      AGENT_PLAN in the type's widgetDefinitions and on the item
  avail-unset    AGENT_PLAN defined for the type but absent from the item
  unavail        AGENT_PLAN absent from both -> feature gated off here
  other-type     type's definitions list AGENT_PLAN for a *different* type only
  no-nodes       project found, workItems.nodes == []
  null-project   data.project == null
  gql-errors     top-level GraphQL errors

Mutation-response kinds:
  ok             workItemUpdate returns AGENT_PLAN content
  mut-errors     workItemUpdate.errors is non-empty (the flag-gated rejection)
  empty-after    workItemUpdate returns AGENT_PLAN with empty content
  no-payload     data.workItemUpdate == null
"""
import json
import sys

kind = sys.argv[1]
AP = {"type": "AGENT_PLAN"}
OTHER = [{"type": "DESCRIPTION"}, {"type": "NOTES"}]


def lookup(item_widgets, type_defs):
    return {
        "data": {
            "project": {
                "workItems": {"nodes": [{
                    "id": "gid://gitlab/WorkItem/424242",
                    "workItemType": {"name": "Issue"},
                    "widgets": item_widgets,
                }]},
                "workItemTypes": {"nodes": type_defs},
            }
        }
    }


def wtype(name, defs):
    return {"name": name, "widgetDefinitions": defs}


if kind == "avail-set":
    doc = lookup(OTHER + [AP], [wtype("Issue", OTHER + [AP]), wtype("Task", OTHER)])
elif kind == "avail-unset":
    doc = lookup(OTHER, [wtype("Issue", OTHER + [AP]), wtype("Task", OTHER)])
elif kind == "unavail":
    doc = lookup(OTHER, [wtype("Issue", OTHER), wtype("Task", OTHER)])
elif kind == "other-type":
    doc = lookup(OTHER, [wtype("Issue", OTHER), wtype("Task", OTHER + [AP])])
elif kind == "no-nodes":
    doc = {"data": {"project": {"workItems": {"nodes": []},
                                "workItemTypes": {"nodes": []}}}}
elif kind == "null-project":
    doc = {"data": {"project": None}}
elif kind == "gql-errors":
    doc = {"errors": [{"message": "Field 'widgetDefinitions' doesn't exist"}],
           "data": {"project": None}}
elif kind == "ok":
    doc = {"data": {"workItemUpdate": {
        "workItem": {"widgets": [{"type": "AGENT_PLAN", "content": "stored plan"}]},
        "errors": []}}}
elif kind == "ok-utf8":
    # 11 characters, 14 UTF-8 bytes — pins the "bytes" label to real bytes.
    doc = {"data": {"workItemUpdate": {
        "workItem": {"widgets": [{"type": "AGENT_PLAN", "content": "plan — étape"[:11]}]},
        "errors": []}}}
elif kind == "mut-errors":
    doc = {"data": {"workItemUpdate": {
        "workItem": None,
        "errors": ["Following widget keys are not supported by Issue type: [:agent_plan_widget]"]}}}
elif kind == "empty-after":
    doc = {"data": {"workItemUpdate": {
        "workItem": {"widgets": [{"type": "AGENT_PLAN", "content": ""}]},
        "errors": []}}}
elif kind == "no-payload":
    doc = {"data": {"workItemUpdate": None}}
else:
    sys.exit("unknown fixture kind: " + kind)

sys.stdout.write(json.dumps(doc))
