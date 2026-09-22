# Clarify, plan, review, and get approval

Detail for steps 3–5 of `gitlab-implement`.

## 3. Ask clarifying questions

Take the scoping pass's open questions back to whoever filed or is driving
the issue/epic. Ask one question at a time rather than a long list, and
where you can, offer concrete options with a recommendation instead of an
open-ended "what do you want here?" Keep going until you're confident about:

- The exact expected behavior — not just "it's broken/missing," but what
  "done" looks like.
- What's explicitly out of scope for this pass.
- Which existing pattern to follow, when more than one plausibly fits.
- Whether this needs a feature flag (check this repo's own feature-flag
  conventions, e.g. `doc/development/feature_flags/` in gitlab-org/gitlab).

## 4. Write the plan

Before writing any code, write down:

- An ordered list of tasks, each tagged with its layer (migration / backend
  / GraphQL / frontend / tests).
- Acceptance criteria per task, ideally as Given/When/Then.
- The file paths each task is expected to touch.
- A dependency graph — which tasks must happen in order, and which are
  independent of each other. This drives implementation and review order.

The plan is written to be posted on the issue in step 5, so a later
session or a human reviewer can read it without this conversation. Use this
shape (wrap it however this repo's own conventions require for
agent-written comments, if it has any):

```
## Implementation plan (revision 1)

**Scope:** what "done" looks like, in the requester's words where possible.
**Out of scope:** what this pass deliberately leaves, each with an issue link.
**Approach:** why this shape; the alternatives considered and why rejected.
**Feature flag:** name and rollout, or "none, because …".

### Tasks
1. [backend] <title>. Files: … Acceptance: Given … When … Then … Tests: … Depends on: —
2. [graphql] …

**Open questions:** none
```

`Open questions` must read `none` before the plan is posted; anything still
open goes back to step 3.

## 5. Grill the plan, post it, and stop

Read back over your own plan adversarially, the way a skeptical senior
reviewer would, before any code exists:

- For every task: does this need to exist at all? Is there already
  something in this codebase that does it (a helper, a pattern, a gem)? Is
  this the smallest shape that solves the actual requirement, or does it
  add flexibility nobody asked for?
- For anything non-trivial, high-risk, or hard to reverse (a new public
  API, a schema change, an authorization boundary), dispatch a *fresh*
  subagent with no prior context on the decision and ask it to argue
  against your approach — a model that hasn't already committed to the
  plan is much better at finding its holes than you re-reading your own
  reasoning.

Once every open question from step 3 has an answer and the plan survives
this adversarial pass without an objection you can't answer, **post the
plan as a comment on the issue and stop.** No code before approval. This
turns "did we agree on the approach" into an artifact on the issue that a
reviewer can read and a later session can resume from, instead of consensus
that lives only in this conversation.

- The comment ends with one line telling the requester how to answer:
  reply `approved` (or add a 👍 reaction to the comment) to start, or reply
  with the changes wanted.
- Approval is an explicit signal from the requester: `approved` said in
  this session, an `approved` reply on the issue, or their 👍 on the plan
  comment. Silence is not approval; do not proceed on a timeout.
- Changes requested: revise the **same** comment (edit it, bump the
  revision number, keep the old revision's changes visible as a short
  "Changed since revision N" list), reply briefly that it is revised, and
  stop again. One plan comment per issue; the thread stays readable.
- A genuinely new fork in approach surfaced by the requester's reply goes
  back to step 3 — ask, don't pick.
