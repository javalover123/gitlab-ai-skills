---
name: pushify
version: 1.1.0
category: Development Workflow
license: MIT
description: "Run pre-push lefthook checks and iteratively fix failures. Primary trigger: invoke after `git push` fails on the lefthook pre-push hook, to drive the fix loop until checks pass. Secondary trigger: pre-validate without pushing — e.g., before opening a Draft MR for early review, or when explicitly preparing a clean working tree. If lefthook is installed as a git hook (`lefthook install`), `git push` already runs the same checks; the unique value of this skill is the structured fix-and-retry loop, not the hook execution itself."
metadata:
  author: pshutsin
  audience: developers
---

# Pushify

Run all pre-push lefthook hooks and fix failures iteratively until everything passes. All pre-push hooks must pass.

When lefthook is installed as a git hook (`lefthook install` — see [`doc/contributing.md`](../../doc/contributing.md)), `git push` already triggers the same hook set. The unique value of this skill is the **structured fix-and-retry loop** below, not running the hooks. Prefer letting `git push` enforce the checks; invoke this skill when push fails (to drive recovery) or when you explicitly want to pre-validate without pushing (e.g. before opening a Draft MR for early review).

## Workflow

### Step 1: Run lefthook

```bash
mise exec -- lefthook run pre-push
```

If all pass → done, tell user "All pre-push checks pass. Ready to push."

### Step 2: Identify failures

Read the output and identify which hooks failed. Each failed hook has a fix strategy below.

### Step 3: Fix each failure

Apply fixes in the order below (some fixes create conditions that help later ones).

---

## Iteration loop

After applying all fixes:

1. Re-run `mise exec -- lefthook run pre-push`
2. If still failing, apply fixes again for remaining failures
3. Repeat up to 3 times

If after 3 iterations something still fails, **stop and explain** to the user:
- Which hook is still failing
- What the exact error is
- What you tried
- What you think needs to happen next (and whether it needs a human decision)

## Important constraints

- Never modify test files to make them pass (unless user explicitly asks)
- Never use linter inline suppressions (e.g. `rubocop:disable`) unless the rule is genuinely inapplicable and you explain it
