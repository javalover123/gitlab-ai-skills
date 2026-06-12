---
name: gitlab-mr-description
description: Write or update a GitLab MR description. Reads the branch diff, drafts structured markdown using GitLab's standard sections, and applies conventions for feature flags, database queries, and local testing matrices. Use when opening a new MR or refreshing an existing description.
version: 1.1.0
license: MIT
---

# GitLab MR Description

When invoked, read the branch diff, infer the change's intent and shape, then produce a complete MR description. Fill every section you have evidence for; omit sections that genuinely don't apply. Never leave placeholder text in the final output.

## Step 1 — Gather context

```bash
git diff "$(git remote show origin | awk '/HEAD branch/ {print $NF}')"..HEAD --stat
git log --oneline "$(git remote show origin | awk '/HEAD branch/ {print $NF}')"..HEAD
git diff "$(git remote show origin | awk '/HEAD branch/ {print $NF}')"..HEAD
glab mr view <number>   # read existing description if one exists
```

Answer: *What does this MR add or fix? Why? What surfaces does it touch?*

## Step 2 — Write the description

Use the template in [references/TEMPLATE.md](references/TEMPLATE.md).

## References

- **Full section template**: [references/TEMPLATE.md](references/TEMPLATE.md)
- **Per-section writing rules and what to omit**: [references/SECTION_RULES.md](references/SECTION_RULES.md)
