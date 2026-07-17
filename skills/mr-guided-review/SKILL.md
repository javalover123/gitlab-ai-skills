---
name: mr-guided-review
description: Use when you want to understand and review a GitLab MR as a reasoning companion rather than an automated reviewer. Phase 1 explains the MR's goal and purpose concisely with a concrete example, then gates on your confirmation before Phase 2 does a thorough code review that surfaces genuine issues, not nitpicks. Read-only — never posts anything to the MR; you post any feedback yourself. Triggers when you want to review, understand, or walk through an MR.
version: 0.1.0
license: MIT
compatibility: opencode
category: Development Workflow
argument-hint: "[MR ID, URL, or blank to auto-detect from current branch]"
metadata:
  audience: developers
  workflow: gitlab
  keywords: merge request, code review, walkthrough, review companion
allowed-tools: Bash(glab mr view:*), Bash(glab mr diff:*), Bash(glab mr note list:*), Bash(glab api:*), Bash(git diff:*), Bash(git log:*), Bash(git show:*), Bash(git merge-base:*), Bash(git fetch:*), Read, Grep, Glob
---

# MR Guided Review

A two-phase walkthrough for an MR you've been asked to review. **Understand first, critique second** — and never on your behalf. This skill augments human review; it does not replace it.

## Hard rules

- **Never post anything to the MR.** No comments, notes, replies, approvals, suggestions, thread resolutions, or label/status changes — not with `glab mr note`, not with `glab api`, not by any other path. The reviewer posts everything themselves. Only read from the MR. If asked to draft comment text, print it in the chat to copy — do not send it.
- **Be concise.** Lead with substance. No filler, no restating the diff line by line, no walls of text. The goal is to save review time, not to produce an essay.
- **Gate between phases.** Do not start the code review until the reviewer confirms. See below.

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

Focus on **genuine issues that matter**, ranked most-serious first:

- **Correctness** — bugs, wrong logic, edge cases, nil/None handling, race conditions, off-by-one, incorrect queries.
- **Regressions & safety** — behavior changes, security holes, missing error handling, N+1s and performance cliffs, migration/data risks.
- **Coverage gaps** — untested branches or new behavior with no test.
- **Architecture fit** — does it follow established patterns? Does it add avoidable debt or scope creep? (Minimal-change principle: flag layers touched that aren't load-bearing.)

**Do not nitpick.** Skip style, naming preferences, formatting, and micro-optimizations unless they cause a real bug or genuinely block comprehension. When a point is minor but still worth a mention, label it explicitly as a nit and keep it to one line so it's obviously not a blocker.

For each real issue: **`file:line` — what's wrong, why it matters, and the concrete failure scenario or fix.** Verify claims against the actual code (Read/Grep the surrounding context) before asserting them — no speculative findings.

Close with a short, actionable verdict: are there blockers, or is it good to approve? The reviewer takes it from there and posts any feedback themselves.
