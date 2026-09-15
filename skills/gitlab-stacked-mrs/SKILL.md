---
name: gitlab-stacked-mrs
description: "Manages stacked GitLab merge requests end-to-end: decomposing a feature branch into logical, independently-reviewable MRs; maintaining a suppression ledger for early-stack dead code; re-syncing the stack after merges (GitLab only auto-retargets 4 MRs, not the full 20-entry limit); triaging reviewer feedback back to the owning entry; and verifying parity with the feature branch throughout. Triggers: stacked MRs, stacked diffs, glab stack, split MR, decompose change, chain merge requests, stack workflow, stacked review, retarget stack, mid-stack rebase."
version: 1.0.0
category: Development Workflow
license: MIT
compatibility: opencode
metadata:
  audience: developers
  workflow: gitlab
---

# GitLab Stacked MRs

Stacked MRs let you ship a large feature as a sequence of small, focused
changes that reviewers can actually read. GitLab 19.1+ detects stacks
automatically from target-branch chaining and retargets the next MR when one
merges — but only 4 deep. This skill manages the rest: decomposition, the
suppression ledger, re-syncing, feedback routing, and parity verification.

Uses `glab stack` (experimental, with a pure-git fallback), the GitLab MCP for
MR/review writes, and `glab api` for dependency edges and retargeting.

**vs. `stack-changes`:** that skill does the one-shot local split — turn an
existing uncommitted or committed diff into a `glab stack` and hand off the
sync to you. This skill picks up from there (or from a stack built any other
way) and owns the ongoing MR lifecycle: opening MRs, triaging reviewer
feedback, re-syncing after merges over days or weeks, and merging bottom-up.
Use `stack-changes` to create the split; use this skill to run it afterward.

## Quick Start

1. **Decompose by logic, not lines.** Split on def-use independence, then check
   size: target ≤200 changed LOC per MR, warn at 300, refuse at 400. Machine-
   generated codemods are exempt — flag them as such.
2. **Keep a suppression ledger.** Every `#[allow(dead_code)]`, `var _ =`, or
   build-tag added to make an early-stack MR compile is a debt entry. The
   consuming MR must clear it; verify that on every re-sync.
3. **Never trust auto-retarget past 4 MRs.** After any merge, re-sync the
   whole stack explicitly, verify parity, and update "part N of M" in every
   description.
4. **Parity is the invariant.** `git diff <stack-tip> <feature-branch>` must
   be empty throughout — check it at the end of every phase.

## When to Use This Skill

- Splitting a too-large feature into a reviewable chain before opening anything
- A reviewer or Danger bot flagged an open MR as too large
- Mid-stack MRs merged and children need retargeting and rebasing
- Triaging reviewer feedback and routing fixes to the right stack entry
- `glab stack` left `.git/stacked` inconsistent and needs recovery
- Verifying the composed stack still matches the feature branch after fixups

**Tooling discovery:** `glab stack` is experimental — check `glab stack --help`
before relying on it, and keep the pure-git fallback ready. Discover GitLab MCP
tools at runtime rather than assuming a fixed set. MR dependency gates
(`/blocks`) are Premium-tier on the dependent side — check
`glab api "projects/:fullpath" --jq '.namespace.plan'` before adding them.

## Phase 1: Decompose

Map the feature branch from its merge-base with the default branch, then split
by priority order: def-use independence, machine-generated code, pure-refactor-
before-behaviour-change, layer order, module boundary, one bugfix/feature atom,
test-only. Never split into something that isn't independently reviewable.

Run the sizing gate (LOC diff excluding generated/vendored paths) against the
≤200/300/400 thresholds, then use `AskUserQuestion` to confirm the proposed
stack order, entry count (warn above 15; UI caps at 20), and any codemods
before creating branches. See
[references/workflow-phases.md](references/workflow-phases.md#phase-1-decompose)
for the sizing table and branch-creation commands, and
[references/sizing-evidence.md](references/sizing-evidence.md) for how solid
the LOC thresholds actually are (short version: the 200/400 numbers trace to
one unrefereed vendor case study — treat them as adjustable policy).

## Phase 2: Open MRs

Each MR targets the branch below it; the bottom MR targets the default branch.
Title as `feat(scope): description [part N of M]` and paste the standard
stack-context block (table of parts, parity statement, suppression-ledger
entries introduced) into the description. See
[references/workflow-phases.md](references/workflow-phases.md#phase-2-open-mrs)
for the template and dependency-gate commands.

## Phase 3: Handle Feedback

Enumerate open discussions via the GitLab MCP and classify each item (blocking
correctness, style, scope creep, "too big", test coverage, docs, design
disagreement, Duo false positive) to decide whether it's fixed in place, routed
to a different stack entry, or escalated with `AskUserQuestion`. Full
classification table in
[references/workflow-phases.md](references/workflow-phases.md#phase-3-handle-feedback).

## Phase 4: Re-sync After Merges

GitLab auto-retargets only the 4 MRs immediately below a merge and doesn't
rebase — re-sync every remaining branch from the bottom up after every merge,
verify parity, update "part N of M" counts, and re-verify the suppression
ledger. A squashed merge desynchronises children at the squash SHA; always
rebase, never just retarget. Commands in
[references/workflow-phases.md](references/workflow-phases.md#phase-4-re-sync-after-merges).

## Phase 5: Merge

Merge bottom-up, one at a time, re-syncing after each — `accept_merge_request`
with `strategy: merge_when_checks_pass`, or `glab mr merge --auto-merge`. After
the last MR merges, delete the feature branch and archive `STACK.md`.

## Suppression Ledger

Keep the ledger in the feature branch's `STACK.md` (never committed to the
default branch): suppression, file:line, which part introduced it, which part
clears it. Verify counts against the working tree on every re-sync — see
[references/git-recipes.md](references/git-recipes.md) for per-language
suppression patterns (Rust, Go, Ruby, Nix) and the exact grep commands.

## Known Failure Modes

- `glab stack` is an experiment and can change or break without notice.
- Auto-retarget is 4 MRs deep, not 20 — always re-sync manually.
- Squash merges desynchronise children; rebase them, don't just retarget.
- A closed-without-merge MR still blocks its dependents until removed.
- Circular `/blocks` dependencies are constructible — validate before writing.

## Writing Style

Apply `natural-writing-style` to MR descriptions, stack-context blocks, and
review replies. Be concrete: "Introduces the `Attestation` type used by part 3"
beats "This MR makes some foundational changes."

## References

- [references/workflow-phases.md](references/workflow-phases.md) — full
  per-phase commands, MR description template, and feedback-routing table
- [references/git-recipes.md](references/git-recipes.md) — splitting
  mechanics, per-language suppression patterns, `--update-refs` and
  `git absorb` usage
- [references/sizing-evidence.md](references/sizing-evidence.md) — evidence
  grades for the LOC thresholds
</content>
