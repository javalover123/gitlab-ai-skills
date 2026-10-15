# Modes and guardrails

Contents:

- [Choosing a mode](#choosing-a-mode)
- [Every mode](#every-mode)
- [Interactive mode](#interactive-mode)
- [Silent](#silent)
- [Dry run](#dry-run)
- [Auto mode and CI](#auto-mode-and-ci)

## Choosing a mode

The first match wins:

1. `--mode interactive`, `--mode auto`, `--silent`, or `--dry-run` in the request.
1. The `DOCS_REVIEW_MODE` environment variable (`interactive` or `auto`).
1. `CI=true` and `auto_mode: true` in `.docs-review.yml`: auto.
1. Otherwise: interactive.

`--dry-run` combines with either mode. It always wins over posting. On a test
copy of someone else's MR, pass `post_review.py --no-mentions` so nobody is
notified.

## Every mode

Every mode runs the same reviewers (mechanical, editor, facts, reader).
Two behaviors apply in every mode:

- A first-time docs writer gets [coaching](triage.md#first-time-docs-writer).
- The summary note lists findings by importance and ends with a "For the
  final human pass" section: importance 4 and 5 items, unverified facts,
  questions for experts, the reader's task walk-through, and what was left
  alone on purpose.

## Interactive mode

- Run every phase, then show the report from phase 4.
- Show each drafted comment and each fix as a diff.
- Post only after the user approves. Pass `--yes` to `post_review.py` only
  then.
- Ask before you mention anyone. Show who and why.

## Silent

Review and fix with no comments on the MR: for an author who wants a
cleaned-up branch, not a review thread.

- Run phases 0-4, then the [fix loop](writer.md#fix-loop) with `--policy
  auto` (only `auto` findings and high-confidence suggestions), without
  pausing.
- Never run `post_review.py`. Commit each cycle locally; push only if asked.
- End with `<out-dir>/report.md`, the commits, and what was left for the
  author.

## Dry run

- No write API calls. `post_review.py --dry-run` writes the payloads and a
  `preview.md` to the output directory.
- Fixes are applied in a scratch worktree, and the patch is written to the
  output directory. Nothing is committed to the user's branch.

## Auto mode and CI

Auto mode guardrails and the CI setup are in [auto-mode.md](auto-mode.md).
Read it only for an auto or CI run.
