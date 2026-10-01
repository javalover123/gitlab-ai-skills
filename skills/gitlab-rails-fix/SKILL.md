---
name: gitlab-rails-fix
description: "End-to-end bug-fix workflow for a reported GitLab issue or work item: fetches it, researches the root cause, reproduces it with a failing spec, confirms it live, applies the minimal fix, verifies downstream, commits, and opens an MR. Use when asked to fix a reported GitLab bug end-to-end, from issue to open MR, in a gitlab-org/gitlab (or similarly structured Rails) checkout."
version: 1.0.0
category: Development Workflow
license: MIT
compatibility: opencode
argument-hint: "<issue-or-work-item-url> [--e2e]"
metadata:
  audience: developers
  workflow: gitlab
---

# GitLab Rails Fix

fetch → research → reproduce → fix → verify → commit → MR, for one GitLab
issue or work-item URL. Append `--e2e` to also drive a live before/after
browser reproduction (off by default — slow, only worth it when asked
for).

## 0. Before you start

Orientation, for a checkout structured like `gitlab-org/gitlab`:

- `app/`, `lib/` — Community Edition (CE) code. `ee/app/`, `ee/lib/` —
  Enterprise Edition (EE) code, mirroring the CE directory structure.
- `spec/`, `ee/spec/` — tests, mirroring the source paths above (a file at
  `ee/app/models/foo.rb` is typically tested by `ee/spec/models/foo_spec.rb`).
- `doc/` — user- and developer-facing docs, published to docs.gitlab.com.
- `.ai/` — this repo's own distilled conventions for AI agents, if it has
  one: `git.md` (branch/commit rules), `merge-requests.md` (MR checklist),
  `code-review.md`, `ci-cd.md`, `security-fixes.md`. Read the relevant one
  before each step below that names it; if the checkout has no `.ai/`, fall
  back to the project's own developer docs — `doc/development/` in
  gitlab-org/gitlab, `docs/developer/*.md` or `docs/development_process.md`
  in others — and this skill's own defaults.
- If a coding-principles or conventions skill is installed for this
  checkout, invoke it before touching code.
- The [GitLab Development Kit (GDK)](https://gitlab.com/gitlab-org/gitlab-development-kit)
  is the standard way to run Rails/specs locally.

Parse the project path and IID from the URL:
`gitlab.com/<namespace>/<project>/-/issues/<iid>` or `.../-/work_items/<iid>`.
Use whatever GitLab access you have — an MCP server, the `glab` CLI, or the
REST/GraphQL API directly — to fetch the issue and later to comment/create
the MR.

## 1. Fetch

Read the full issue description, not just the title — bug reports usually
include the reporter's own repro steps and sometimes a "possible fix"
pointer. Treat that pointer as an unverified hypothesis, not a confirmed
root cause. If the expected/correct behavior itself is ambiguous, ask a
specific question with your best-guess options rather than assuming.

**Security-fix check** — if the issue is confidential AND carries the
`~security` label AND does NOT carry `~security-fix-in-public`: stop this
workflow and follow the repo's own security-fix process instead (`.ai/security-fixes.md`
if present). Do not push a fix for it to the canonical repository. Say only
that you stopped and where to go next; do not summarise or paraphrase the
issue's contents, since your report lands in a transcript the issue's
confidentiality does not cover.

## 2. Research → 3. Reproduce → 4. Confirm live

Find the shared root cause, prove it with a failing spec, then confirm it
outside the spec's mocks. See
[references/root-cause-research.md](references/root-cause-research.md) for
the full method (subagent dispatch for unfamiliar code, the "dig one layer
deeper" heuristic, spec placement, and the live-check pattern).

## 5. Fix — minimal, at the root

Grep every caller of the method before editing. Fix it once at the shared
point they all route through, not in whichever caller the issue happened to
name — a guard added only on the reported path leaves every sibling caller
still broken. Smallest change that removes the cause; no unrelated
refactors in the same commit.

## 6. Verify

- Turn the new spec green; re-run the step-4 live check.
- Other specs may assert the *old* buggy behavior as correct and go red —
  that's expected. Update their expectations; never loosen the fix just to
  keep a stale expectation passing.
- Run the full spec suite for every file the fix and its callers/
  collaborators live in, and the project's linter, on every changed file.
- Show the actual command output before claiming anything passes.

## 7. Optional end-to-end check (only with `--e2e`)

Drive the issue's own repro steps through the real UI or API, before the fix
(stash, worktree, or previous commit) and after, so the before/after is a
genuine comparison. Without `--e2e`, skip silently; mention in the report
that it's available on request.

## 8. Commit, review, and open the MR

One commit for the fix and its specs, an imperative subject, a body
explaining *why* the bug happened, and a link back to the issue. Follow the
target project's own commit and code-review conventions where it has them.
Before pushing, write the MR description per
[references/commit-and-mr.md](references/commit-and-mr.md) — it covers a
fallback commit/self-review process for a checkout with no conventions of
its own, plus the description sections a human or follow-up agent needs.

## 9. Report

One report in the shape defined in
[references/output-format.md](references/output-format.md), nothing before
or after it.
