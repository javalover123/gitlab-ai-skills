---
name: mr-adversarial-review
description: Use when an author wants a critical, skeptical review of their own merge request before bringing in a human reviewer — produces a severity-bucketed findings report (High / Medium / Low / Done well) and posts it as a single comment on the MR.
version: 0.1.0
category: Development Workflow
license: MIT
compatibility: opencode
argument-hint: <URL of the MR to review>
metadata:
  audience: developers
  workflow: gitlab
---

# Adversarial Review

Run a skeptical, reviewer-mode pass over a GitLab merge request. The goal is to surface issues the author may have missed so they can address (or consciously dismiss) them **before** human reviewers are pulled in.

The output is a single MR comment in a standardized format so authors, reviewers, and downstream tooling can scan it consistently.

## When to use

- Author wants a self-check before requesting human review.
- A reviewer wants a structured first pass they can iterate on before posting their own notes.
- Anyone wants a consistent format for "AI-generated adversarial review" comments across projects.

## Inputs

- **MR URL or IID** (required). If omitted, resolve from the current branch via `glab mr view`.

## Workflow

1. **Resolve the MR.** Use `glab mr view <iid-or-url>` to get title, description, target branch, author, and pipeline status.
2. **Read the diff.** `glab mr diff <iid-or-url>` for the full diff. For large MRs, also fetch the file list and read individual files in the repo for context the diff lacks (callers, surrounding functions, tests).
3. **Read prior discussion.** `glab mr note list <iid-or-url> -F json`. Don't re-raise points another reviewer already made or that the author has explicitly addressed.
4. **Run the review** (see [Review stance](#review-stance) and [Coverage checklist](#coverage-checklist) below). Adopt a skeptical mindset: assume something is wrong and look for it.
5. **Format the output** exactly as specified in [Output format](#output-format). The format is non-negotiable — downstream tooling and humans both rely on it.
6. **Post the comment.** `glab mr note create <iid-or-url> -m "$(cat "$REPORT")"`. Write the body to a file first (backticks, code fences, and `$` in the report would otherwise be mangled — see the `glab` skill for the safe heredoc pattern).
7. **Stop.** Do not iterate, do not "fix" issues, do not push code. The author decides what to act on.

## Review stance

- **Be skeptical, not theatrical.** Flag real issues. Don't pad with "consider renaming this variable" filler — nitpicks belong in the Low bucket and should be genuinely worth a 10-second glance.
- **Prefer evidence over speculation.** If you claim a bug, point at the line and explain the failure mode concretely. If you're uncertain, say so ("I couldn't verify X without running the tests") rather than asserting.
- **Don't repeat existing review comments.** Read the discussion first; if Duo or another reviewer already raised a point, skip it unless you have something materially new to add.
- **Acknowledge what's done well.** This isn't politeness padding — it tells the author which decisions you considered and endorsed, which is information they can't get from silence.
- **No moralizing.** No "be careful", "make sure to", "remember to" language. State the issue; trust the reader.

## Coverage checklist

Run through these dimensions explicitly. Not every MR has issues in every dimension — say nothing rather than inventing a finding to fill a bucket.

- **Correctness** — does the change do what the description claims? Off-by-one, missing nil/empty cases, race conditions, wrong default values.
- **Security** — input validation, auth/authz, SQL/command injection, secrets in logs or commits, sensitive data in responses.
- **Performance** — N+1 queries, unbounded loops, missing indexes, blocking I/O on hot paths, accidental large payloads.
- **API / interface design** — backwards compatibility, naming consistency with surrounding code, error response shapes, public surface area.
- **Error handling** — swallowed exceptions, error messages that leak internals, retries without idempotency.
- **Testing** — coverage of the change, missing edge cases, tests that pass tautologically (mocking the thing under test), flaky patterns.
- **Maintainability** — comments that lie, dead code, abstractions that don't pay rent, magic numbers, names that mislead.
- **CI / build / tooling** — pinned versions that drift, cache keys, hardcoded values that should be derived, missing `retry` / `timeout`.
- **Documentation** — does the change require a docs update, changelog entry, or migration note?

## Output format

The comment **must** follow this structure exactly. See [references/output-format.md](references/output-format.md) for a fully worked example.

```markdown
## Adversarial Review: <MR title>

<One short paragraph: overall framing. Is the MR mergeable as-is? What's the single most important takeaway? Two sentences, three at most.>

---

### 🔴 High

**<Short heading for the finding>**

<Body: what the issue is, why it matters, where it lives (file:line if useful), and a concrete suggestion. One paragraph, optionally followed by a small code block.>

**<Next high-severity finding>**

<...>

---

### 🟠 Medium

**<Heading>**

<Body>

---

### 🟡 Low / Nitpicks

**<Heading>**

<Body>

---

### ✅ What is done well

- <Bullet — a specific decision worth endorsing, not generic praise>
- <Bullet>
- <Bullet>

---

**Summary:** <One sentence. Is it mergeable? What's the one thing worth doing before merge, if anything?>
```

### Format rules

- **Severity buckets are fixed**: 🔴 High, 🟠 Medium, 🟡 Low / Nitpicks, ✅ What is done well. Use these labels, these emoji, this order.
- **Omit empty buckets**. If there are no High findings, drop the `### 🔴 High` section entirely. Do not write "No high-severity issues found." — the absence is the signal.
- **Always include `✅ What is done well`** unless the MR is genuinely a wreck. Three to five bullets is the sweet spot.
- **Always end with `**Summary:**`** — one sentence, plain prose, no bullets.
- **Each finding has a bold heading** (the `**...**` line) followed by a body paragraph. Headings are short noun phrases ("Ruby version is hard-coded and will silently go stale"), not questions or imperatives.
- **`---` separators** between major sections (between buckets, before the Summary). Not between individual findings within a bucket.

### Severity guide

- **🔴 High** — would cause incorrect behavior in production, a security issue, data loss, or break the contract the MR claims to uphold. The author should not merge without addressing.
- **🟠 Medium** — likely to cause friction (performance, maintainability, fragile patterns) but not strictly wrong. Worth fixing in this MR or as a follow-up.
- **🟡 Low / Nitpicks** — style, documentation, minor improvements. Author may justifiably ignore.

When in doubt between two levels, pick the lower one. Inflated severity is the fastest way to make this skill useless.

## Posting

```bash
# Write the report to a file (NOT inline -m, backticks in the body will be mangled)
REPORT=$(mktemp)
cat > "$REPORT" << 'EOF'
## Adversarial Review: ...
EOF

glab mr note create <iid> -m "$(cat "$REPORT")"
```

See the [`glab` skill](../glab/SKILL.md) for the full message-escaping rationale.

## What this skill does NOT do

- **Does not fix issues.** The author decides what to act on.
- **Does not approve or unapprove the MR.** Approval is a human decision.
- **Does not resolve threads.** Findings are posted as a single discussion; the author resolves it after triage.
- **Does not loop or re-review.** One pass per invocation. If the author pushes changes and wants another pass, they invoke the skill again.
