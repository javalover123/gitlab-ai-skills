---
name: writing-commit-messages
description: Use when creating git commits, writing commit messages, or when about to run git commit — enforces structured commit message format with imperative mood, capitalized subjects, 72-char wrapping, and atomic commits
version: 1.0.0
license: MIT
compatibility: opencode
metadata:
  audience: developers
  workflow: git
---

# Writing Commit Messages

## Overview

Every commit message follows a consistent format. The subject line completes the sentence: **"If applied, this commit will _\<your subject line\>_"**. When present, the body explains **why**, not what.

## Detect Project Convention First

Before writing a commit, check what style the project already uses:

1. Check for documented commit conventions in the repo
2. Run `git log --oneline -20` to see recent patterns
3. Match the existing style

**Project convention always wins.** The rules below are the default when no convention is detected.

## The Format

```
Short (72 chars or less) summary

Body wraps at 72 chars. Blank line after subject is critical.
Explain WHY, not what. Bullet points okay with hanging indent.
```

| Rule | Good | Bad |
|------|------|-----|
| Capitalize | `Add CPU arch filter` | `add CPU arch filter` |
| Imperative | `Fix null pointer` | `Fixed null pointer` |
| No period | `Add user auth` | `Add user auth.` |

**Subject line rules, body format, URLs, issue references**: [references/COMMIT_FORMAT.md](references/COMMIT_FORMAT.md)

## Atomic Commits

Each commit does **ONE logical thing**. If your subject contains "and", split into separate commits.

**When asked to commit mixed changes, ALWAYS recommend splitting:**
- Refactoring → one commit
- Bug fix → one commit  
- New feature → one commit
- Dependency updates → one commit

**Split strategies, anti-rationalizations, and refactoring patterns**: [references/ATOMIC_COMMITS.md](references/ATOMIC_COMMITS.md)

## Common Issues

```bash
# ✅ Correct
Add user authentication

# ❌ Wrong
fix: auth stuff              # vague, lowercase (unless Conventional Commits)
Fixed the bug               # past tense
Update stuff                # vague
```

**Complete red flags checklist and mistake patterns**: [references/COMMON_MISTAKES.md](references/COMMON_MISTAKES.md)

## Issue References

**Only add if the project already uses them** (check `git log --oneline -20`).

Put references in the **body** on their **own line** at the end:

```
Add CPU arch filter scheduler support

[explanation of why]

Fixes #847
```

## Conventional Commits

The default style is **plain English imperative**, NOT Conventional Commits. However, if the project uses Conventional Commits (detected via config files or `git log`), follow that convention. All other rules still apply.

## Attribution

**Author:** Andrew Fontaine ([@afontaine](https://gitlab.com/afontaine))

This skill is based on widely-accepted git commit message conventions, with inspiration from:

- [Commit Message Guidelines](https://gist.github.com/robertpainsi/b632364184e70900af4ab688decf6f53) by Robert Painsi
- [OpenStack GitCommitMessages](https://wiki.openstack.org/wiki/GitCommitMessages)
- [A Note About Git Commit Messages](http://tbaggery.com/2008/04/19/a-note-about-git-commit-messages.html) by Tim Pope
- [How to Write a Git Commit Message](http://chris.beams.io/posts/git-commit/) by Chris Beams
