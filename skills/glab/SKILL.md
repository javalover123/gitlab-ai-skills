---
name: glab
description: GitLab workflow automation using glab CLI
license: MIT
compatibility: opencode
metadata:
  audience: developers
  workflow: gitlab
---

# GitLab Workflow Skill

GitLab workflow management using `glab` CLI for merge requests, issues, and Git best practices.

## Creating Merge Requests

```bash
# Simple MR
glab mr create --title "feat: add feature" --description "Brief description"

# Complex MR - write description to file first
glab mr create --title "feat: add feature" --description "$(cat /tmp/mr-description.md)"
```

**Templates:** Check `.gitlab/merge_request_templates/` for project-specific templates and follow their structure.

## Updating Merge Requests

```bash
# Update description from file
glab mr update <number> --description "$(cat /tmp/description.md)"

# View MR details
glab mr view <number> -R <owner>/<repo>
```

## Issue Management

```bash
# View issue details
glab issue view <number>

# View issue with comments
glab issue view <number> --comments -R <owner>/<repo>

# Post a comment on an issue
glab issue note <number> -m "comment text" -R <owner>/<repo>
# For multiline comments, use a file:
glab issue note <number> -m "$(cat /tmp/comment.md)" -R <owner>/<repo>

# List issues with filters
glab issue list --label "priority::P1,status::doing"

# Create issue - write description to file first
glab issue create --title "Bug: issue title" --description "$(cat /tmp/issue-description.md)"

# Update issue labels (IMPORTANT: Use separate flags, NOT +/- prefixes)
glab issue update 123 --label "new-label"           # Add label
glab issue update 123 --unlabel "old-label"         # Remove label
glab issue update 123 --label "label1" --unlabel "label2"  # Add and remove in one command

# Scoped labels (key::value) — auto-replace within the same scope
# Adding "status::doing" automatically removes "status::today" — no --unlabel needed
glab issue update 123 --label "status::doing"       # Replaces any existing status:: label
glab issue update 123 --label "priority::P1"        # Replaces any existing priority:: label
```

### Issue State Transitions and Notes

```bash
# Close an issue
glab api --method PUT "projects/<project_id>/issues/<iid>" -f state_event=close

# Reopen an issue
glab api --method PUT "projects/<project_id>/issues/<iid>" -f state_event=reopen

# Post a comment via API (the `note` field on PUT is silently ignored — always use this)
glab api --method POST "projects/<project_id>/issues/<iid>/notes" -f "body=Your comment here"

# Multiline comment from file
glab api --method POST "projects/<project_id>/issues/<iid>/notes" \
  -f "body=$(cat /tmp/comment.md)"
```

**Templates:** Check `.gitlab/issue_templates/` for project-specific templates and follow their structure.
**References:** Link related issues using `#123` syntax and use appropriate labels/milestones.

## Issue Links and Epics

For **issue links** (blocked_by, related) and **epics** (group-level work items), use `glab api` with the REST API. Load the reference docs for full details:

- **Issue links:** [references/issue-links.md](references/issue-links.md) — create/list/remove `is_blocked_by`, `blocks`, `relates_to` links
- **Epics:** [references/epics.md](references/epics.md) — create epics (with parent), add issues to epics, update descriptions

## GLQL Queries

To query issues, MRs, or epics across projects or groups, load the **`glab-glql`** skill.
It covers the full query syntax, all filter fields, `jq` output patterns, and pagination.

## Git Best Practices

**Branch naming:**
```bash
git checkout -b feat/description
git checkout -b fix/description
git checkout -b refactor/description
```

**Commit messages:**
- Format: `type: description` (conventional commits)
- Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`
- Explain the "why" not just the "what"
- Reference: Use full URLs like `Closes https://gitlab.com/org/project/-/issues/123`
- Use single quotes for special characters: `git commit -m 'fix: resolve issue'`

## Quick Reference

```bash
# List issues/MRs
glab issue list --label "bug,P1"
glab mr list --author @me

# View details
glab issue view 123
glab mr view 456

# Update MR
glab mr update 456 --description "$(cat /tmp/new-description.md)"
```

## Agent Guidelines

1. **Read context first** - Use `glab issue view` or `glab mr view` before implementing
2. **Use project templates** - Check `.gitlab/issue_templates/` and `.gitlab/merge_request_templates/` for project-specific formats
3. **Write descriptions to files** - Create markdown in `/tmp/` then use `$(cat /tmp/description.md)`
4. **Reference properly** - Link issues/MRs with full URLs in commits: `Closes https://gitlab.com/org/project/-/issues/123`
5. **Descriptive commits** - Focus on the "why" behind changes
6. **Quote special characters** - Use single quotes: `git commit -m 'fix: from MR !123'`
7. **Label syntax** - Use `--label` to add and `--unlabel` to remove. **NEVER** use `+label` or `-label` syntax - that creates literal label names with +/- characters
8. **Scoped labels** - For scoped labels (`key::value`), just use `--label` — the new value auto-replaces the old one in the same scope. No need for `--unlabel` (e.g., `--label "status::doing"` automatically removes `status::today`)
