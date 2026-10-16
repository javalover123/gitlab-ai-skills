# Verify, commit, review, and open the MR

Detail for steps 7–9 of `gitlab-implement`.

## Security-fix bail-out (referenced from step 1)

If the issue is confidential, carries `~security`, and does NOT carry
`~security-fix-in-public`: stop this workflow entirely. Follow this
project's own security-fix process instead of pushing anywhere public. Say
only that you stopped and where to go next — do not summarise or
paraphrase the issue's contents in your report, since the report may land
in a transcript the issue's confidentiality does not cover.

## 7. Verify

- Every acceptance criterion from the plan has a passing spec — confirming
  the behavior that was asked for, not just that the code runs.
- Confirm backend-observable behavior live: with local services running,
  write a small **read-only** script (e.g. `bin/rails runner` on a Rails
  codebase) that exercises the real classes in memory — most service/policy
  bugs need no database writes, so prefer constructing objects directly
  over factories plus real records. Keep scratch scripts out of your diff.
- Run the full downstream spec suite for every file the change and its
  callers/collaborators live in, plus the project's linter, on every
  changed file. Show the actual command output before claiming anything
  passes.
- Browser end-to-end check only with `--frontend-e2e`: drive the real UI
  flow. Off by default; if the change touches the frontend, mention in the
  report that this is available on request.

## 8. Commit

Feature-sized work usually needs more than one commit. Split along concern
boundaries instead of one giant commit: migrations isolated, implementation
on its own, wiring/integration (routes, feature-flag checks, initializers)
separate, and tests traveling with the implementation they cover.

Check the current branch first. If it already has unrelated commits or an
open MR, don't add to it: stash your changes, branch fresh off the
up-to-date default branch, then reapply. Follow this repo's own
branch-naming and commit-message conventions (imperative subject; a body
explaining *why*, not a restatement of the diff; `Resolves <full issue URL>`
using the full URL, not a short `#1234` reference which renders as plain
text in some contexts). No AI-attribution trailers unless the repo asks for
them.

If a pre-commit hook fails on something your diff didn't cause (stale
gems, pending migrations), fix that cause and recommit — don't bypass the
hook.

## 9. Review, push, and open the MR

Before pushing, run a fresh-context, read-only review pass over the diff —
ideally as a separate subagent with no prior context on the change, given
only the branch name and the plan's acceptance criteria — checking the diff
against those criteria, the repo's own conventions, test coverage, and the
draft MR description's claims. Fix every blocking issue it raises, then run
a new fresh pass; don't re-review in a session that already agrees with
itself.

Push with `-u`. Some repos have slow pre-push hooks — don't treat a
long-running push as failure; confirm it landed (e.g.
`git ls-remote origin <branch>`) before opening the MR.

Use the most specific merge request template the repo ships (check
`.gitlab/merge_request_templates/`); keep every section, filling each in or
stating briefly why it doesn't apply. Mirror the issue's labels onto the MR
where the repo's conventions expect that, set the milestone if the repo
uses one, and assign it to yourself.

The next reader of this description may be a human reviewer or a
follow-up agent session days later. Beyond the template, give them three
things:

- **Reviewable size**: a one-line note on the diff's reviewable size (e.g.
  from `git diff --stat` on non-test files), and if it's large, one
  sentence on why it can't be split.
- **A `<details><summary>Context for LLM agents</summary>` block**: the
  alternatives you rejected and why, and any invariant a follow-up must
  keep. Rationale only; the diff already shows what changed.
- **`Owed elsewhere`**: each deliberately deferred item with its follow-up
  issue link. Omit the section when nothing is owed — squash merges drop
  commit bodies, so an obligation recorded only there is lost.
