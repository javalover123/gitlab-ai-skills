---
name: gdk-predictive
description: Run GDK predictive checks (tests, linters, coverage) for local changes before pushing. Runs relevant RSpec, Jest, RuboCop, ESLint, HAML Lint, and Stylelint based on changed files. Use before pushing commits, or invoke with /gdk-predictive [flags].
argument-hint: "[--rspec|--jest|--rubocop|--eslint|--haml-lint|--stylelint|--simplecov|--yes|--skip-<tool>]"
disable-model-invocation: false
allowed-tools: Bash(gdk predictive:*), Bash(git diff:*), Bash(git status:*)
---

# GDK Predictive Checks

Run `gdk predictive` to execute relevant tests, linters, and coverage checks for local changes before pushing.

## Step 1: Check What Has Changed

Run `git status` and `git diff --stat HEAD` to understand what files are changed (staged, unstaged, or committed but not pushed).

## Step 2: Run gdk predictive

Run the following command with any flags provided by the user (`$0`):

```
gdk predictive $0
```

If no flags are given, all tools run by default (RSpec, Jest, RuboCop, ESLint, HAML Lint, Stylelint).

Common flag combinations:
- `--rspec --rubocop` — backend-only changes
- `--jest --eslint` — frontend-only changes
- `--yes` — skip the RSpec confirmation prompt

## Step 3: Report Results

After the command completes, summarize:

- Which tools ran
- Which passed and which failed
- Any specific test failures or lint errors, with file and line references
- Whether the changes are safe to push

If any checks fail, highlight the errors clearly and suggest fixes where obvious.
