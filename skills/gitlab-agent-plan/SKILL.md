---
name: gitlab-agent-plan
description: "Read or write a GitLab work item's Workplan / Agent Plan widget — the AI work plan property — via GraphQL. Use when asked to get/show/pull or attach/set/update a work item's workplan or agent plan, as opposed to its description or comments."
version: 0.1.0
license: MIT
category: Development Workflow
compatibility: opencode
user-invocable: true
argument-hint: "<work item URL or project/path + iid> [plan file to write]"
metadata:
  audience: developers
  workflow: gitlab
  keywords: work item, workplan, agent plan, graphql, widget
allowed-tools:
  - Read
  - Write
  - Bash(glab api graphql *)
  - Bash(bash *get_agent_plan.sh *)
  - Bash(bash *set_agent_plan.sh *)
  - Bash(python3 *)
---

# gitlab-agent-plan — read and write a work item's Agent Plan (Workplan) widget

GitLab work items have a dedicated **Workplan / Agent Plan** widget
(https://docs.gitlab.com/user/work_items/workplan/): a structured Markdown
property for an AI/agent work plan, kept separate from the description so the
original intent is never overwritten. It is exposed via GraphQL even though the
docs don't describe the API.

**This is a first-class property.** It is NOT the description and NOT a
note/comment. If an item has no agent plan, say so plainly — do not read the
description or comments instead and present that as the plan. If a write is
rejected, do not fall back to posting a comment or editing the description.

## Inputs

- A work item reference: a full URL
  (`https://HOST/<project/path>/-/work_items/<iid>`) or `<project/path>` + `<iid>`.
- For writes, the plan content as a Markdown file. For reads, optionally a path
  to write the plan Markdown to.

## Fast path (helper scripts)

Read — plan Markdown goes to **stdout**, every diagnostic to **stderr**, so
stdout stays clean and pipeable. With an out-file argument the plan is written
there instead and stderr gets `OK: agent plan fetched, <n> bytes -> <path>`:

```
bash scripts/get_agent_plan.sh https://gitlab.com/gitlab-org/build/CNG/-/work_items/2332
bash scripts/get_agent_plan.sh gitlab-org/build/CNG 2332 /path/to/plan.md
```

Write — resolves the global ID, runs the availability preflight below, sets the
content, and verifies the read-back, printing `OK: agent plan set, <n> bytes`:

```
bash scripts/set_agent_plan.sh \
  https://gitlab.com/gitlab-org/build/CNG/-/work_items/2332 /path/to/plan.md
bash scripts/set_agent_plan.sh gitlab-org/build/CNG 2332 /path/to/plan.md
```

Both paths are relative to this skill's own directory.

Exit codes: `0` success; `1` failure (bad arguments, work item not found,
auth/network, GraphQL or mutation `errors`, or a write that didn't take effect);
`3` **read only** — no agent plan set, nothing on stdout; `4` **write only** —
the widget is unavailable here, nothing was attempted.

## Availability: two different kinds of "missing"

`AGENT_PLAN` missing from an item's `widgets { type }` has two very different
causes, and they must not be conflated:

| Situation | Meaning | Behaviour |
|---|---|---|
| Absent from the **type's** `widgetDefinitions` | The feature is not enabled for this namespace. A write **will** be rejected. | Write: hard fail, exit `4`, mutation never sent |
| Present for the type, absent from **this item** | Writable; the item just has no plan yet | Write: `warning:`, then write |

The gate is **per namespace, not per work item type**: an `Issue` in
`gitlab-org/build/CNG` exposes `AGENT_PLAN`, an identical `Issue` in a personal
namespace does not. Attempting the write there fails with:

```
Following widget keys are not supported by Issue type: [:agent_plan_widget]
```

When the feature is unavailable, report the namespace gate — do not report it as
an ordinary write failure, and do not retry. `AGENT_PLAN_FORCE=1` overrides the
preflight on the write path. On the read path, exit `3` cannot by itself tell
"no plan set" from "feature not available here"; use the `widgetDefinitions`
probe to distinguish them.

For the raw queries, the mutation, the availability probe, and the `createNote` /
description alternatives, see [references/graphql.md](references/graphql.md).

## Notes

- Both paths use the authenticated `glab` user's token and `glab`'s configured
  default host. A reference's host is discarded, so a self-managed URL only
  resolves if `glab` is authenticated against that host. Writes are attributed
  to that user.
- Fetch → edit → set preserves content byte-for-byte **except trailing
  newlines**, which the write path's `-f content="$(cat file)"` strips. Unicode
  and shell/GraphQL metacharacters survive — `glab` does the JSON escaping.

## Tests

Offline, no network or credentials needed — each stubs `glab` on `PATH`. In this
repo they are discovered and run by `scripts/run_skill_tests.sh` (wired into
`bin/ci-checks`, pre-push, and CI); to run one directly:

```
bash tests/test_get_agent_plan.sh    # 51 cases
bash tests/test_set_agent_plan.sh    # 54 cases
bash tests/test_roundtrip_mock.sh    #  7 cases
```

The first two cover argument parsing (asserting the exact GraphQL built for each
URL shape), byte-exact output, stdout/stderr separation, the availability
preflight in both directions, and every failure mode. The round-trip drives both
scripts against one shared stub endpoint, so the write→read contract is verified
even where the feature flag is off.
