---
name: gitlab-adr
description: "Use when asked to write, draft, propose, or revise an Architecture Decision Record (ADR) in a design-doc repository (a repo with a decisions/ directory and an ADR template), or when asked to compare architecture options and recommend one for a deciding reader. Also use when an existing draft ADR overlaps a new decision and needs narrowing."
version: 1.0.0
category: Development Workflow
license: MIT
compatibility: opencode
argument-hint: "<decision topic or issue/MR url> [--repo <path-to-design-doc-checkout>]"
metadata:
  audience: developers
  workflow: gitlab
---

# GitLab ADR

orient → interview → research → write → grill → lint → MR, for one
architecture decision in a design-doc repo. The deliverable is a proposed ADR
plus an MR whose description a reviewer can act on without reading the ADR
first.

**The ADR is written after the interview, never before it.** A prompt that
says "write the ADR" is a request to start this workflow, not permission to
skip step 2 — agents that skip the interview invent numbering, terminology,
and infrastructure facts.

## 1. Orient in the target repo

Read, in this order: `AGENTS.md`/`CLAUDE.md`, `README.md`, the decisions
index, the ADR template, the glossary, `design.md`. Then list **open merge
requests**; draft ADRs live there and claim numbers. Record the next free
number, the status vocabulary (`proposed`, `accepted`, `superseded by`), and
which files change only on acceptance. Note the CI lint jobs; step 6 runs them
locally.

A numbering collision resolves in favor of the older MR. An overlapping draft
is narrowed and cross-linked, not replaced — two ADRs deciding different
things stay two ADRs.

## 2. Interview

One question per message, each with your own guess attached, until you can
predict the answers to the next three. Then restate outcome, readers, why now,
success, constraint, and out of scope, and wait for an explicit yes. Format
and probing technique: [references/interview-and-research.md](references/interview-and-research.md#interview).

## 3. Research, delegated

Fan out to subagents for this repo's MRs/discussions, sibling initiatives the
decision depends on, and current-state facts in the code — keep only
conclusions, every claim sourced. Details:
[references/interview-and-research.md](references/interview-and-research.md#research).

## 4. Write the ADR

Follow the repo's own template. What to add beyond it — a sourced facts table
in Context, one diagram/feasibility/cost/risk per Option, solid-vs-dotted
diagram convention, observable Decision criteria, and a Consequences list of
what changes on acceptance: [references/writing-and-review.md](references/writing-and-review.md#writing-the-adr).

## 5. Grill it

Dispatch one fresh subagent per ADR with the artifact and the confirmed
contract from step 2, told to find what's wrong and not validate or summarize.
Classify findings, route anything needing the author's call back through the
interview format, then run a second over-engineering pass. Stop when findings
turn trivial or after three cycles. Details:
[references/writing-and-review.md](references/writing-and-review.md#grilling).

## 6. Lint

Run the repo's CI lint jobs locally before pushing (typically spell-check plus
a link checker in offline mode). A link to a sibling MR's file fails until
that MR merges — state the merge order instead of removing the link.

## 7. Branch, commit, MR

Never commit on the default branch; branch first, and follow the target
repo's own commit-message and attribution conventions. Push, then open the MR
with `glab mr create --description-file <path>` (or update one with
`glab mr update --description-file <path>`) so the drafted description never
has to be re-typed into your context. The MR description is for reviewers who
have not read the ADR: why it exists, the question in one sentence, the
proposal in the reader's framing, why not the alternatives now, relationship
to other MRs and merge order, feedback asks split by reader, checks run.

## 8. Report and follow through

One report, nothing before or after it:

```
MR:         <url>
DECIDES:    <three lines>
GRILL:      <what the fresh-context reviewers changed, one line each>
UNVERIFIED: <diagram rendering | unsourced fact …>, or none
NEXT:       <reviewers, merge order>
```

Answer bot review threads on your own MR. For comments on other people's MRs,
issues, or channels, propose them and wait — don't post.

## Red flags

- Writing any ADR text before the restate has an explicit yes
- A number chosen without listing open drafts
- A fact about another team's system with no URL
- A criterion with no threshold, source, or event
- "Stays in force" or "already decided" about a `proposed` ADR
- Editing acceptance-only files (e.g. `design.md`, `glossary.md`) in the
  proposing MR
- Passing your conclusion to the fresh-context reviewer in step 5
- Renaming a wire-level term to fix a documentation collision

## References

- [references/interview-and-research.md](references/interview-and-research.md) — interview question format and the three research streams
- [references/writing-and-review.md](references/writing-and-review.md) — what each ADR section needs beyond the template, and the grilling protocol
