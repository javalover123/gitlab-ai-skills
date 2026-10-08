# Interview and research detail

## Interview

Open with a hypothesis and a confidence number with the missing pieces named:

```
HYPOTHESIS: <one sentence: what the decision is and who it is for>
CONFIDENCE: ~40% — missing: <readers>, <success>, <binding constraint>

Q: <one question>
GUESS: <your answer and why; be willing to be wrong>
```

Keep going until you can predict the answers to the next three questions. Then
restate and wait for an explicit yes:

- **Outcome** — the decision in one line.
- **Readers** — who decides the architecture, and who must accept its
  schedule or product consequence. These are usually two different people
  with different vetoes; an ADR that satisfies one and surprises the other
  fails.
- **Why now** — what changed.
- **Success** — how the author will know the ADR landed.
- **Constraint** — the binding limit (a ship date, a deployment target, a
  platform mandate).
- **Out of scope** — what this ADR does not decide.

Probe convention-shaped answers ("scalable", "modular", "best practice") with:
*if you didn't have to justify this to anyone, what would you actually want?*
Ask explicitly how the author wants the recommendation to read to the
deciding reader; wording that reads as hedging loses the argument even when
the reasoning is right.

## Research

Fan out to subagents and keep only conclusions. Three streams, in parallel:

- **This repo's MRs and discussions**: every open and merged MR, the
  contested points with author and verbatim quote, open threads on merged
  ADRs. The new ADR must answer or cite those threads.
- **Sibling initiatives** the decision depends on: their design-doc repos,
  status (design, draft, shipping), deployment model, and what they serve
  today versus plan to. Every claim with a URL; "not found" stated
  explicitly.
- **Current-state facts** in the code: what actually shipped (enum values,
  table names, dependency versions), because ADRs describe intent and code
  describes reality.

If the user pasted a memo or meeting notes, treat them as a hypothesis to
reconcile with the research, and say so in the ADR where they differ.
