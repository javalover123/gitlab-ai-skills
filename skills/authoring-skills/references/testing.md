# Testing and iterating on a skill

Lightweight, tool-agnostic methodology distilled from Anthropic's testing
guidance. Anthropic's own docs note there is no built-in eval runner: build the
smallest harness that gives you signal (`opencode run`, `claude -p`, a manual
transcript).

## Contents

- Evaluation-first loop
- Three kinds of test
- Success metrics
- Iterate with two agents
- Read the signals
- Models

## Evaluation-first loop

1. Run the agent on representative tasks **without** the skill; note concrete
   failures and missing context.
2. Write at least three scenarios that exercise those gaps. Each: the query,
   input files if any, and expected behaviours (observable, checkable).
3. Record the baseline.
4. Write the minimum instructions that close the gaps.
5. Re-run, compare to baseline, refine. Don't document problems you never saw.

Tip: iterate on one hard task until it succeeds, then extract the winning
approach into the skill; widen to more cases afterwards.

## Three kinds of test

- **Triggering:** fires on obvious requests and on paraphrases; stays silent on
  unrelated ones. Debug probe: ask "when would you use the `<name>` skill?" and
  read back the description it quotes.
- **Functional:** correct outputs, tool calls succeed, error paths and edge
  cases behave.
- **Comparison:** same task with and without the skill; compare messages,
  tool calls, failures, and tokens.

## Success metrics

Rough targets, not precise thresholds:

- Fires on ~90% of relevant queries (try 10–20; count automatic vs manual loads).
- Fewer tool calls / tokens than baseline; zero failed calls per workflow.
- Qualitative: no redirection needed, same request run 3–5 times gives
  structurally consistent output, a new user succeeds first try.

## Iterate with two agents

Use one agent session to author/refine the skill and a fresh session with the
skill loaded to do real work. Bring observed failures back verbatim ("it forgot
to filter test accounts") and adjust prominence, wording, or structure. Repeat
on real tasks, not synthetic ones. `opencode-refine` automates this in opencode.

## Read the signals

| Signal | Likely fix |
|---|---|
| Never loads / users invoke manually | Add literal trigger phrases, file types, jargon to `description` |
| Loads for unrelated requests | Add "do not use for…" boundary, narrow scope |
| Loads but rules ignored | See *Making rules stick* in `body-patterns.md` |
| Agent reads files in odd order | Structure isn't intuitive; make links explicit |
| Agent never opens a bundled file | Unneeded or poorly signalled; delete or link better |
| Agent re-reads the same reference | Move that content into `SKILL.md` |
| Slow or degraded with many skills | Trim `SKILL.md`, shrink descriptions, enable fewer skills |

## Models

Skills add to a model, so behaviour varies by model. If the skill will be used
across tiers, spot-check small, mid, and large models: small ones need enough
guidance, large ones should not be over-explained to. Adding "take your time,
don't skip validation" to the *user prompt* works better than in the skill.
