# Commit, self-review, and MR

Full detail for [SKILL.md](../SKILL.md) step 8.

## Commit

Check the current branch first. If it already has unrelated commits or an
open MR, don't add to it: stash your changes, branch fresh off the
up-to-date default branch as `<iid>-<short-slug>`, then reapply.

One commit for the fix and its specs: imperative subject; a body explaining
*why* the bug happened, not a restatement of the diff; `Resolves <full
issue URL>` (full URLs only — short references like `#1234` render as plain
text on some GitLab versions and are rejected by some repos' conventions);
a `Changelog:` trailer and `EE: true` (if the diff touches `ee/`) when the
target repo uses those conventions. No AI-attribution trailers unless the
target repo asks for them.

If a pre-commit hook fails on something your diff didn't cause (stale
gems, pending migrations), fix that cause and recommit — don't bypass the
hook.

## Self-review before pushing

There is no substitute here for a second pair of eyes, but before pushing,
run this checklist yourself (or dispatch it to a fresh subagent with no
prior context — a clean read catches things a self-review misses):

- **BLOCKER-level**: the diff actually fixes the issue's acceptance
  criteria; no unrelated refactors are mixed in; no secrets, debug prints,
  or scratch scripts leaked into the diff; every new/changed spec passes.
- **WARN-level**: naming and style match surrounding code; error handling
  covers the edge cases the root-cause research surfaced; the commit
  message explains *why*, not just *what*.
- Fix every BLOCKER before pushing. Treat WARN as judgment calls.

## Push and open the MR

Push with `-u`. Pre-push hooks on large repos can run for several minutes —
don't treat a long-running push as failure; confirm it landed with
`git ls-remote origin <branch>` before opening the MR.

Use the most specific MR template the target repo ships (usually under
`.gitlab/merge_request_templates/Default.md`); keep every section, filling
each in or stating briefly why it doesn't apply. Mirror the issue's labels
onto the MR (type, group/section, and similar) and assign it to yourself.

Beyond the template, give the next reader — human or a follow-up agent in a
fresh session — three things:

- A reviewable line-count line for the diff (e.g. `Reviewable LOC: N (plus
  M in tests)`), as its own plain paragraph so a script can find it later.
  Over roughly 500 reviewable lines, add one sentence on why it cannot be
  split.
- A `<details><summary>Context for LLM agents</summary>` block: the
  alternatives you rejected and why, and any invariant a follow-up must
  keep. Rationale only; the diff already shows what changed.
- **`Owed elsewhere`**: each deliberately deferred item with its follow-up
  issue link. Omit the section when nothing is owed. Squash merges drop
  commit bodies, so an obligation recorded only there is lost.
