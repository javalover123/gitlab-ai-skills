---
name: mr-guided-review
description: Use when you want to understand and review a GitLab MR as a reasoning companion rather than an automated reviewer. Phase 1 explains the MR's goal with a concrete example, Phase 2 reports genuine issues (not nitpicks) as a terse findings index, and Phase 3 drafts review comments in your voice and stages them as unpublished draft notes. Each phase gates on your confirmation, and it never publishes a review, posts a plain comment, or approves. Triggers when you want to review, understand, walk through, or draft review comments on an MR.
version: 0.2.0
license: MIT
compatibility: opencode
category: Development Workflow
argument-hint: "[MR ID, URL, or blank to auto-detect from current branch]"
metadata:
  audience: developers
  workflow: gitlab
  keywords: merge request, code review, walkthrough, review companion, draft notes
allowed-tools: Bash(glab mr view:*), Bash(glab mr diff:*), Bash(glab mr note list:*), Bash(glab api:*), Bash(git diff:*), Bash(git log:*), Bash(git show:*), Bash(git merge-base:*), Bash(git fetch:*), Bash(jq:*), Bash(mkdir:*), Bash(cat:*), Read, Write, Grep, Glob
---

# MR Guided Review

A three-phase walkthrough for an MR you've been asked to review. **Understand first, critique second, draft third** — and never publish on your behalf. This skill augments human review; it does not replace it.

## Hard rules

- **Never publish a review.** Phase 3 may create *unpublished draft notes* and nothing else. Never call the publish endpoints (`PUT .../draft_notes/:id/publish`, `POST .../draft_notes/bulk_publish`), never `glab mr approve`, never `glab mr note`, `glab mr comment`, `glab mr update`, `glab mr merge`, never post through `POST .../notes` or `POST .../discussions`, never resolve a thread, never touch labels or reviewer state. Reading the staged drafts on the MR and publishing them is the reviewer's, always.
- **Draft notes only on an explicit go-ahead.** Phases 1 and 2 are strictly read-only. Nothing is written to the MR until the reviewer says so plainly. A "yes" to the Phase 2 gate is not a go-ahead for Phase 3.
- **Be concise.** Lead with substance. No filler, no restating the diff line by line, no walls of text. The goal is to save review time, not to produce an essay.
- **Gate between phases.** Do not start the code review until the reviewer confirms. Do not draft or post comments until they confirm again.

## Phase 1 — Understand the goal and purpose

Goal: build a solid mental model of *what this MR is for and why*, fast.

1. Load the MR (read-only):
   - If given an ID/URL, use it. Otherwise auto-detect from the current branch: `glab mr view`.
   - `glab mr view <id>` for title, description, author, target branch, linked issues.
   - `glab mr diff <id>` and/or `git diff <target>...<source> --stat` for the shape of the change.
   - Skim the linked issue/description for the motivating problem, not just the "what".
2. Explain it back concisely:
   - **Problem** — what was broken/missing (1–2 sentences).
   - **Change** — what this MR does about it (1–2 sentences).
   - **How it works** — the mechanism, only as deep as needed to grasp it.
   - **Simple example** — a concrete before/after: a sample input→output, a user-visible scenario, or a tiny code walkthrough. Make the abstract tangible. This is required, not optional.
   - **Scope** — the main files/areas touched, grouped by concern (not a full file list).
3. Keep it tight. Prefer short paragraphs or a few bullets over long prose. If something is genuinely unclear from the MR itself, say so rather than guessing.

**Then stop and ask:** *"Ready to review the code changes thoroughly?"* Wait for the answer. Do not proceed to Phase 2 until the reviewer says yes. If they have questions about the goal/purpose first, stay in Phase 1 and answer them.

## Phase 2 — Thorough code review

Only after the reviewer confirms.

**Before reviewing, if the project provides a `gitlab-coding-principles` skill or a `.ai/code-review.md` methodology, load and apply them** — they govern how GitLab code is planned, implemented, and reviewed. Otherwise apply general GitLab review conventions.

Look for **genuine issues that matter**:

- **Correctness** — bugs, wrong logic, edge cases, nil/None handling, race conditions, off-by-one, incorrect queries.
- **Regressions & safety** — behavior changes, security holes, missing error handling, N+1s and performance cliffs, migration/data risks.
- **Coverage gaps** — untested branches or new behavior with no test.
- **Architecture fit** — does it follow established patterns? Does it add avoidable debt or scope creep? (Minimal-change principle: flag layers touched that aren't load-bearing.)

**Do not nitpick.** Skip style, naming preferences, formatting, and micro-optimizations unless they cause a real bug or genuinely block comprehension.

Do the analysis thoroughly — Read/Grep the surrounding context and verify every claim against the actual code before asserting it, no speculative findings. But **report it tersely**: deep work, shallow output.

### Output format — a scannable index, not a report

Default to the *shortest useful summary*; the reviewer asks for detail on the findings they care about. Emit exactly this, nothing else:

1. **One line** on overall state (e.g. `Reviewed 12 files. 1 blocker, 2 worth fixing, 1 nit.`).
2. **A numbered list of findings**, most-serious first, **one line each**: `N. [SEVERITY] file.rb:123 — <the problem in ≤15 words>`, where `SEVERITY` is `BLOCKER` / `SHOULD-FIX` / `NIT`. One line means one line: no sub-bullets, no code blocks, no "why it matters".
3. **Verdict** — one line: blockers to resolve, or good to approve.
4. **Closing pointer** — one line: `Say "expand 2" (or "expand all") for the failure scenario and fix.`

No preamble, no restating what the MR does (that was Phase 1), no per-file walkthrough, no diff summary table, no "things done well" section. Cap at 7 findings; if there are more, list the top 7 and note the remaining count on the state line. With no real issues, say so in one line plus the verdict and stop.

### Expansion, on request

When asked to expand a finding (by number, severity, or "all"), give **only those** findings in full: the relevant code quoted minimally, the concrete failure scenario (inputs/state → wrong outcome), and the fix or the specific question for the author. A short paragraph or a few bullets each. Do not re-list the other findings or re-run Phase 2.

## Phase 3 — Draft review comments and stage them on the MR

Only after the reviewer confirms. Two sub-gates: draft in chat, then post on an explicit go-ahead.

### 3a. Write the drafts in chat first

Take the findings the reviewer names (default: everything above `NIT`) and show each as `<file>:<line>` followed by the comment body. Start every body with exactly one of these three labels, bold:

- `**Suggestion (blocking):**` — a real defect: correctness bug, regression, security hole, data risk. Something worth holding the MR on.
- `**Suggestion (non-blocking):**` — worth changing but the author's call: missing test, pattern drift, avoidable complexity.
- `**Question:**` — not enough is known to assert a problem and the author should answer. Prefer this over a hedged suggestion whenever the answer could reasonably be "it's fine, because X".

Nothing else. No `Nit:`, no `Praise:`, no severity tags, no emoji, and no AI-authorship marker — these go out under the reviewer's name, in their voice.

**Voice.** Short and to the point, but human, not analyzer register:

- First person and conversational: "I think", "I'm curious whether", "I noticed".
- "We"/"our" about the codebase. Never "you".
- Two or three sentences. Name the problem, say why it matters, and for a blocking one say what you'd do instead. Stop there.
- Hand the decision back on non-blocking findings and questions: "but I'll let you decide", "unless I'm missing something". Do not tack that onto a blocking finding; it undercuts it.
- No em dashes. Use commas, colons, or a second sentence.
- No clause-stacking, no compressed labels, no "lacks X" / "fails to Y", no restating the diff back at the author.
- If the fix is a one-liner, use a GitLab `suggestion` block instead of describing the change in prose.

**Then stop.** Ask: *"Post these as draft notes?"* Wait for an explicit go-ahead. If the reviewer edits the wording, use their version verbatim.

### 3b. Post them as unpublished draft notes

See [references/draft-notes.md](references/draft-notes.md) for the API recipe, the line-positioning rules, and how to fix or delete a draft afterwards. Report one line per staged draft (id, `file:line`, label) plus the MR URL, and say plainly that they are unpublished and that publishing is the reviewer's.
