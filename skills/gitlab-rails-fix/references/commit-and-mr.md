# Commit, self-review, and MR

Full detail for [SKILL.md](../SKILL.md) step 8.

## Commit and self-review

Follow the target project's own commit-message, branching, and review
conventions — its `AGENTS.md`/`CLAUDE.md`, a coding-principles skill, or
equivalent, if it has one. Most of what a generic checklist would tell you
to do (branch hygiene, commit-message shape, a pre-push review pass)
belongs there, not repeated here.

If the checkout has none of the above, fall back to: check the current
branch first — if it already has unrelated commits or an open MR, branch
fresh off the up-to-date default branch instead of adding to it; one
commit for the fix and its specs with an imperative subject and a body
explaining *why* the bug happened; and a self-review pass (yourself, or a
fresh subagent with no prior context) before pushing, checking at minimum
that the diff fixes the issue's acceptance criteria with no unrelated
changes and no leaked debug output.

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
