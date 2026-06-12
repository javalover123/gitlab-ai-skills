---
name: gitlab-mr-description
description: Write or update a GitLab MR description. Reads the branch diff, drafts structured markdown using GitLab's standard sections, and applies conventions for feature flags, database queries, and local testing matrices. Use when opening a new MR or refreshing an existing description.
version: 1.0.0
license: MIT
---

# GitLab MR Description

When invoked, read the branch diff, infer the change's intent and shape, then produce a complete MR description using the structure below. Fill every section you have evidence for; omit sections that genuinely don't apply (e.g. no Database section for a pure-Ruby-no-query change). Never leave placeholder text in the final output.

## Step 1 — Gather context

Run these before writing anything:

```bash
git diff origin/master..HEAD --stat          # what files changed
git log --oneline origin/master..HEAD        # commit subjects
git diff origin/master..HEAD                 # full diff (read key files)
```

Also read the MR's existing description if one exists:

```bash
glab mr view <number>
```

Use the diff and commit messages to answer: *What does this MR add or fix? Why? What surfaces does it touch?*

## Step 2 — Write the description

Use this skeleton. Wrap long sections in `<details><summary>` so reviewers can skip them.

```markdown
## Summary

Part of #<issue>. Split from !<parent-mr-url> (if applicable).

<One sentence: what the MR adds or fixes, and why.>

<Optional: table of surfaces touched.>

<If gated: Gated behind the `<flag_name>` WIP feature flag (off by default in production).>

## Approach

### <Business logic / Detection / Core change>

<Short prose on what the code does and why it's structured that way. Explain
non-obvious decisions. Reference rejected alternatives if they came up during
implementation.>

### <Field / response shape> (omit if not a data-shape change)

| Value | Meaning |
|-------|---------|
| `true` | … |
| `false` | … |
| `null` | … |

### Preloading (omit if no N+1 risk)

<Show the preload tree. One line per association, explaining what each avoids.>

### Feature flag gating (omit if no FF)

<Per-surface table: method name, what it checks, what it returns when the FF is disabled.>

## Database (omit if no queries added or changed)

<details>
<summary>Queries and query plans</summary>

For each new or changed query:

- SQL in subquery form (safe to paste into postgres.ai without needing real IDs).
- Note if Rails emits a flat `IN (id1, id2, …)` at runtime rather than the
  subquery form shown above.
- The **exact** index name backing the query (verify with `pg_indexes` — do not
  guess from memory).
- Link to the postgres.ai query plan.

</details>

<details>
<summary>Considered and rejected alternatives</summary>

For each alternative tried and rejected:

- The query or code form attempted.
- Link to the postgres.ai plan with concrete numbers (loop count, buffer hits, ms).
- One-line conclusion: why it lost.
- Follow-up path if rollout data later changes the calculus.

</details>

## Feature flag (omit if no FF introduced)

| Flag | Type | Scope | Default | Purpose |
|------|------|-------|---------|---------|
| `<flag_name>` | `wip` | … | off | … |

## Local testing

<details>
<summary>Setup and verification</summary>

1. <How to get test data: import project / seed via console / run factory>
2. <Enable required feature flags. WIP flags are **off by default** — call them out explicitly.>

**Value matrix** — walk every combination of flag state × data state:

| Data present | `<flag_name>` enabled | Expected result |
|---|---|---|
| yes | yes | … |
| yes | no | … |
| no | yes | … |

</details>

## Related

- <Companion MRs with full URLs>
- <Parent or split-from MR with full URL>
- <Issue / epic with full URL>
```

## Section-by-section rules

### Summary

- One sentence. Imperative ("Adds …", not "This MR adds …").
- Include the parent issue number as `#NNN` only in the prose — use a full URL when linking anywhere that renders outside GitLab (related section, commit body).
- If the MR is gated behind a WIP feature flag, say so explicitly and note it is **off by default in production**.

### Approach

- Explain the *why*, not just the *what* — the diff already shows what changed.
- If the implementation made a non-obvious choice (e.g. reusing an existing table instead of adding one, a specific enum value ordering, a performance trade-off), explain it here so reviewers don't re-raise the same alternatives.
- Keep paragraphs to 3–5 sentences. Use subsections only when the change spans multiple distinct concerns.

### Database

Only include this section if the MR adds or changes queries. When you do:

- Write SQL in subquery form so it can be pasted into postgres.ai without real IDs. Add a one-liner noting that Rails emits flat `IN (id1, id2, …)` at runtime — this prevents the reviewer from thinking the runtime does something more expensive.
- Verify index names against the actual schema (`pg_indexes`) — never write them from memory.
- If alternatives were tested, document them with postgres.ai plan links and concrete numbers. Reviewers reliably re-suggest alternatives that weren't documented as already tried.

### Feature flag

- WIP flags are **off by default in production** and **on by default in the test environment**. Both facts should be visible somewhere in the description.
- The local testing matrix must cover the disabled state explicitly, because the disabled path is the production default before rollout.

### Local testing matrix conventions

- Vary **only the flags this MR introduces**. Pre-existing flags are prerequisites, not matrix axes.
- Always include the disabled-FF row — that is the production default.
- Label the disabled-state context `'when the feature flag is disabled'`, not a compound description like `'when the flag is disabled and no data is present'` — the data state is irrelevant when the gate is closed.

### Related

- Use full URLs everywhere: `https://gitlab.com/gitlab-org/gitlab/-/merge_requests/NNN`. Short refs (`!NNN`) render as plain text outside GitLab and can trip the commit-message linter.

## What to skip

Omit a section entirely (don't leave it empty or with placeholder text) when:

- **Database** — the MR adds no queries and changes no schema.
- **Feature flag** — no FF is introduced or changed.
- **Preloading** — the change touches no association loading path.
- **Field / response shape** — the change is not a data-shape change visible to callers.

A shorter, accurate description is better than a long one with empty tables.
