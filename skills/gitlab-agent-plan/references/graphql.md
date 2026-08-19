# Agent Plan widget — the raw GraphQL

Everything the helper scripts do, for when you'd rather issue the calls yourself
or need to adapt them. Run queries with `glab api graphql -f query='…'`.

## Read: item + widget content in one query

```graphql
query {
  project(fullPath: "<project/path>") {
    workItems(iid: "<iid>") {
      nodes { id iid title
        widgets { type ... on WorkItemWidgetAgentPlan { content } } }
    }
  }
}
```

Pick the widget whose `type` is `AGENT_PLAN` and read its `content`. The widget
also exposes `contentHtml` if rendered HTML is wanted instead of Markdown. If
the response's `errors` is non-empty, surface it verbatim and stop.

## Availability probe

The widget is **namespace-gated**, not type-gated. To tell "no plan set" apart
from "feature not available here" without touching any item, query the type's
widget definitions:

```graphql
query {
  project(fullPath: "<project/path>") {
    workItemTypes(name: ISSUE) { nodes { name widgetDefinitions { type } } }
  }
}
```

If `AGENT_PLAN` is absent from `widgetDefinitions`, no item in that project can
carry an agent plan — say so rather than reporting the item as merely unset.

The write path's preflight combines both lookups so nothing is modified:

```graphql
query {
  project(fullPath: "<project/path>") {
    workItems(iid: "<iid>") { nodes { id workItemType { name } widgets { type } } }
    workItemTypes { nodes { name widgetDefinitions { type } } }
  }
}
```

Match the item's `workItemType.name` against `workItemTypes.nodes[].name` and
check that node's `widgetDefinitions` for `AGENT_PLAN`. Proceed only when it is
present; otherwise stop and report the namespace gate rather than sending a
mutation that is certain to be rejected.

## Write: set the widget

The input's only field is `content: String!`.

```graphql
mutation($id: WorkItemID!, $content: String!) {
  workItemUpdate(input: {id: $id, agentPlanWidget: {content: $content}}) {
    workItem { widgets { ... on WorkItemWidgetAgentPlan { type content } } }
    errors
  }
}
```

Pass content from a file to avoid shell escaping:

```
glab api graphql -f query='…' \
  -f id='gid://gitlab/WorkItem/<n>' \
  -f content="$(cat plan.md)"
```

Then verify: re-query `... on WorkItemWidgetAgentPlan { content }` and confirm it
matches. If `errors` is non-empty, surface it verbatim and stop — do not post a
comment or edit the description as a workaround.

Note that `"$(cat plan.md)"` strips trailing newlines; content is otherwise
preserved byte-for-byte, including unicode and shell/GraphQL metacharacters,
because `glab` does the JSON escaping.

## Neighbouring operations, for reference

These are **different** properties — reach for them only when the request is
actually about them, not as a fallback when an agent-plan write is rejected:

- a note/comment → `createNote`
- the description → `workItemUpdate { descriptionWidget { description } }`
