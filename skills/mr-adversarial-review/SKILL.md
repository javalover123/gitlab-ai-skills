---
name: mr-adversarial-review
description: Use when running a critical, skeptical pass over a GitLab MR — either as the author before requesting human review, or as a reviewer wanting a structured first cut — produces a severity-bucketed findings report (High / Medium / Low / Done well) and posts it as a single comment on the MR.
version: 0.1.0
category: Development Workflow
license: MIT
compatibility: opencode
argument-hint: <URL of the MR to review>
metadata:
  audience: developers
  workflow: gitlab
---

# MR Adversarial Review

Skeptical, reviewer-mode pass over a GitLab merge request. Posts a single comment with findings bucketed by severity, in a standardized format so authors, reviewers, and downstream tooling can scan reviews consistently.

## Inputs

MR URL or IID. If omitted, resolve from the current branch via `glab mr view`.

## Workflow

1. Resolve MR: `glab mr view <iid-or-url>`.
2. Read the diff: `glab mr diff <iid-or-url>`. For large MRs, read surrounding files for context the diff lacks.
3. Read prior discussion: `glab mr note list <iid-or-url> -F json`. Don't re-raise points others already made or the author addressed.
4. Run the review (see [stance](#stance) and [coverage](#coverage)).
5. Format the output per [Output format](#output-format) — non-negotiable; tooling depends on it.
6. Post the comment: write the body to a file (backticks/`$`/code fences will be mangled inline — see the [`glab` skill](../glab/SKILL.md) for the heredoc pattern), then `glab mr note create <iid-or-url> -m "$(cat "$REPORT")"`.

Do not fix, approve, or resolve threads. One pass per invocation.

## Stance

- Skeptical, not theatrical — flag real issues, no filler.
- Evidence over speculation — name the line, the failure mode. If uncertain, say so.
- Don't repeat existing review comments.
- Acknowledge what's done well — tells the author which decisions you considered and endorsed.
- No moralizing ("be careful", "make sure to"). State the issue.

## Coverage

Run through these explicitly. Say nothing rather than inventing a finding to fill a bucket.

- **Correctness** — off-by-one, nil/empty cases, races, wrong defaults.
- **Security** — input validation, auth/authz, injection, secrets, sensitive data in responses.
- **Performance** — N+1, unbounded loops, missing indexes, blocking I/O on hot paths.
- **API design** — backwards compatibility, naming consistency, error shapes, public surface.
- **Error handling** — swallowed exceptions, leaky messages, non-idempotent retries.
- **Testing** — coverage, edge cases, tautological tests, flaky patterns.
- **Maintainability** — lying comments, dead code, premature abstraction, misleading names.
- **CI / build** — pinned versions that drift, cache keys, missing `retry`/`timeout`.
- **Docs** — required docs / changelog / migration updates.

## Output format

See [references/output-format.md](references/output-format.md) for the canonical worked example.

```markdown
## Adversarial Review: <MR title>

<One short framing paragraph: mergeable as-is? main takeaway? 2–3 sentences.>

---

### 🔴 High

**<Short noun-phrase heading>**

<Body: what, why, where (file:line), suggestion.>

---

### 🟠 Medium

...

---

### 🟡 Low / Nitpicks

...

---

### ✅ What is done well

- <Specific decision worth endorsing, not generic praise>
- ...

---

**Summary:** <One sentence. Mergeable? One thing worth doing before merge, if anything?>
```

### Rules

- Severity buckets are fixed: 🔴 High → 🟠 Medium → 🟡 Low / Nitpicks → ✅ What is done well. Always this order, these labels, these emoji.
- **Omit empty buckets.** Absence is the signal — never write "No high-severity issues found."
- Always include `✅ What is done well` unless the MR is genuinely a wreck. 3–5 bullets.
- Always end with `**Summary:**` — one sentence, plain prose.
- Each finding: bold heading + body paragraph. Headings are short noun phrases, not questions/imperatives.
- `---` separators between buckets and before the Summary, not between findings within a bucket.

### Severity

- **🔴 High** — incorrect behavior in production, security, data loss, broken contract. Don't merge without addressing.
- **🟠 Medium** — friction (performance, maintainability, fragile patterns) but not strictly wrong. Fix here or follow-up.
- **🟡 Low / Nitpicks** — style, docs, minor improvements. Author may ignore.

When in doubt between two levels, pick the lower one. Inflated severity makes this skill useless.
