---
name: gitlab-implement
description: End-to-end feature implementation workflow for a GitLab issue or epic — scopes it, asks clarifying questions, writes and adversarially reviews a plan, posts the plan on the issue and waits for approval, then implements, verifies, commits, and opens an MR. Use when asked to build or implement a GitLab feature end-to-end, from issue or epic to open MR.
version: 1.0.0
category: Development Workflow
license: MIT
compatibility: opencode
argument-hint: "<issue-or-epic-url> [--frontend-e2e]"
metadata:
  audience: developers
  workflow: gitlab
---

# GitLab Implement

fetch → scope → clarify → plan → grill the plan → post it and wait for
approval → implement → verify → commit → MR, for a feature-sized GitLab
issue or epic. `--frontend-e2e` (off by default) adds a live browser-driven
UI check.

This is the bigger, slower sibling of a bug-fix workflow: use this for
"build this" asks that need scoping and design decisions before any code
gets written, not for a bug report with known repro steps.

## 0. Before you start

Parse the project path and IID from the URL:
`gitlab.com/<namespace>/<project>/-/issues/<iid>` or `.../-/epics/<iid>`.
Use whatever GitLab access you have — an MCP server, the `glab` CLI
(https://gitlab.com/gitlab-org/cli), or the REST/GraphQL API directly — to
fetch and later comment on the issue/epic. For an epic, also fetch its child
issues (GraphQL `epic.children`, `glab api` against the linked-items
endpoint, or the equivalent MCP tool) — the epic states intent, the linked
issues carry the detail; scoping from the epic description alone
under-scopes.

If the target checkout has `doc/development/*` distilled into an agent
skill or `.ai/` conventions directory, load the relevant ones before
touching code.

## 1. Fetch

Get the issue or epic, plus child issues per step 0.

**Security-fix check** — if the issue is confidential AND carries the
`~security` label AND does NOT carry `~security-fix-in-public`: stop and
follow this project's security-fix process instead (see
`references/implement-verify-ship.md`). Do not push a fix for it to the
canonical repository, and do not summarise or paraphrase the issue's
contents in your report.

## 2. Scope — what needs to be done

Dispatch a subagent to read the issue/epic and map it onto the real
codebase: which layers it touches (backend/GraphQL/frontend/database),
existing patterns to follow instead of inventing new ones, the files likely
to change, and — critically — the open questions it can't resolve just by
reading. If more than one model tier is available, use the more capable one
here: getting the scope wrong costs a wasted implementation pass.

## 3. Ask clarifying questions, 4. Write the plan, 5. Grill it, post it, and stop

Full detail, plan template, and approval protocol:
[`references/plan-and-approval.md`](references/plan-and-approval.md). Do not
skip ahead to implementation before the plan is posted and explicitly
approved — silence is not approval.

**Resuming in a later session** on the same issue: look for the newest
agent-written plan comment before doing anything else. If it is approved,
skip straight to step 6. If it has unanswered change requests, revise it and
stop. If it is unapproved with no replies, ask in this session; do not
re-plan from scratch.

## 6. Implement

Work from the approved plan comment, not from memory of this conversation;
if they differ, the comment wins and the difference is a new revision, not a
silent deviation. Tasks with no shared state can be dispatched to parallel
subagents; tasks that depend on each other run in sequence, following the
plan's dependency graph. Within a feature, implement backend → GraphQL →
frontend → tests, unless the dependency graph says otherwise.

## 7. Verify, 8. Commit, 9. Review, push, and open the MR

Full detail: [`references/implement-verify-ship.md`](references/implement-verify-ship.md).
Every acceptance criterion from the plan needs a passing spec, the diff
needs a fresh-context review pass before it is pushed, and the MR
description carries the plan's context forward for the next reader.

## 10. Report

One report in this shape, nothing before or after it:

```
ISSUE:    <url> · plan comment <url>
BUILT:    <acceptance criterion → file:line>, one line each
EVIDENCE: <spec files> green · <live check, one line> · suite <n> examples, <f> failures · E2E <run | not run>
MR:       <url>
SKIPPED:  <what> — <why>, or none
```
