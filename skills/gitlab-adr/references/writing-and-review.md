# Writing and review detail

## Writing the ADR

Follow the repo template. Beyond it:

- **Context** carries a readiness or facts table with a source and an as-of
  date per row, and a list of what already exists (ADRs, drafts, open
  threads) with their true status. Use the status words the repo's rule
  gives; a merged ADR with `Status: proposed` is not "in force".
- **Options**, when comparing: each gets a diagram, feasibility, delivery
  cost in words against work already on the board, and risks. Charge the
  same risk class (latency, availability, fail-open) to every option it
  applies to. A comparison table row that reads the same in every column is
  deleted.
- **Diagrams** mark what exists today versus what is hypothesized; solid for
  existing, dotted for hypothesized, and say so in the caption.
- **Decision** names criteria that are observable: a threshold, a
  measurement source, or an event. A criterion that fires on inaction
  ("stable for two releases" alone) is a loophole. Sequencing decisions need
  criteria in both directions (when to move, when to adopt the next thing).
  Anything the decision assumes but does not control is a named dependency
  with an accepted fallback and an owner.
- **Consequences** list the files that change on acceptance and the exact
  terms a glossary gains, instead of editing them in this MR when the repo
  rule says acceptance.
- **Alternatives considered** include anything the interview or review
  rejected, with the reason.
- Use the repo's identifiers exactly (case, terminology); check the glossary
  before naming anything.

## Grilling

Dispatch one **fresh** subagent per ADR with the artifact and the contract
(the confirmed restate from the interview) and an adversarial prompt: find
what is wrong, assume the author is overconfident, do not validate or
summarize. Do not pass your own conclusion or reasoning.

Classify every finding against the text, in this order: contract misread,
actionable, trade-off to document, noise. Findings that need the author's
call go back through the interview format, one question at a time.

Run a second pass for over-engineering: every commitment, field, and
criterion is asked "does the first consumer need this?"; the ADR should get
shorter. Stop after the findings turn trivial or after three cycles.
