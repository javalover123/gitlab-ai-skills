---
name: pushify
version: 1.0.0
category: Development Workflow
license: MIT
description: Run pre-push lefthook checks and fix any failures before pushing. Use this skill whenever the user asks to run pre-push checks, prepare for push, or wants to ensure code passes all pre-push hooks. Trigger proactively when the user asks if code is ready to push or wants to clean up before a git push.
metadata:
  author: pshutsin
  audience: developers
---

# Pushify

Run all pre-push lefthook hooks and fix failures iteratively until everything passes. All prepush hooks must pass.

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
