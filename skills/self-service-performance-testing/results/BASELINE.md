# Eval baseline — self-service-performance-testing

Established for [team-tasks#4421](https://gitlab.com/gitlab-org/quality/quality-engineering/team-tasks/-/work_items/4421).

- **Date:** 2026-07-15
- **Skill version:** 0.4.1
- **Model (executor + grader):** Claude Opus 4.8 (`claude-opus-4-8[1m]`) — the model powering the session that ran the evals
- **Runs:** 1 per configuration per eval (16 executor runs total: 8 evals x with-skill / without-skill)
- **Raw data:** [`iteration-1/benchmark.json`](iteration-1/benchmark.json), [`iteration-1/benchmark.md`](iteration-1/benchmark.md), per-run `iteration-1/eval-<id>/<config>/run-1/grading.json`

## Headline result

| Configuration | Pass rate (all 8 evals) |
|---|---|
| **With skill** | **92.7%** |
| Without skill (baseline) | 79.2% |
| **Delta** | **+13.5 pp** |

"With skill" = an agent that loaded `SKILL.md` and its references before answering. "Without skill" = the same model answering cold. The gap is what the skill adds on top of the model's own knowledge.

## What the issue asked for, and where it landed

1. **Baseline pass rate for the existing 6 evals** — recorded (see split below).
2. **New eval cases for tools added during skill expansion** — added evals #6 (rspec-benchmark) and #7 (Ruby profilers), the two tool families introduced by [MR !53](https://gitlab.com/gitlab-org/ai/skills/-/merge_requests/53).
3. **Updated pass rate after the additions** — recorded (all-8 numbers above).

### Original 6 vs. the 2 new evals

| Eval set | With skill | Without skill | Delta |
|---|---|---|---|
| Original 6 (ids 0–5) | 93.1% | 88.9% | +4.2 pp |
| New 2 (ids 6–7) | 91.7% | 50.0% | **+41.7 pp** |

The original 6 show a modest gap because much of this GitLab-specific knowledge (CPT wiring, Sitespeed Runway, CWV targets) is already strong in Opus 4.8. The **new evals are where the skill earns its keep**: routing an allocation-regression guard to rspec-benchmark and a "why is this slow?" question to the right profiler is knowledge the cold model largely lacks — the baseline agent scored only 50%. This validates that MR !53's additions genuinely needed eval coverage.

## Per-eval pass rates

| Eval | Scenario | With skill | Without skill |
|---|---|---|---|
| 0 | SQL JOIN on hot MR-list endpoint | 83% (5/6) | 67% (4/6) |
| 1 | CPT for containerized service | 100% (6/6) | 100% (6/6) |
| 2 | Frontend CWV → Sitespeed Runway | 100% (5/5) | 100% (5/5) |
| 3 | Proactive nudge on an MR-review ask | 100% (6/6) | 67% (4/6) |
| 4 | Existing CPT test already present | 100% (4/4) | 100% (4/4) |
| 5 | Docs/config-only → clear "no" | 75% (3/4) | 100% (4/4) |
| 6 | rspec-benchmark unit guard *(new)* | 100% (6/6) | 33% (2/6) |
| 7 | Ruby profiler investigation *(new)* | 83% (5/6) | 67% (4/6) |

## Where the skill clearly helps (biggest gaps)

- **Eval 6 — rspec-benchmark (+67 pp).** With the skill, the agent named rspec-benchmark and wrote a `perform_allocation` matcher stub. Without it, the agent reached for a hand-rolled `GC.stat(:total_allocated_objects)` delta and `QueryRecorder` — a workable answer, but it never surfaced the purpose-built gem. (Two independent baseline runs produced the same miss, so this is a stable signal, not noise.)
- **Eval 3 — proactive nudge (+33 pp).** With the skill, the agent gave a brief, opt-out-friendly nudge ("if you've already accounted for this… no action needed"). Without it, the agent delivered a full advisory wall of text with no easy dismiss — failing the `keeps-it-brief` and `easy-opt-out` assertions. This is a behavioral capability, not just facts.

## Honest anti-signals (worth fixing in Q3)

- **Eval 5 — with-skill (75%) scored *below* baseline (100%).** The skill-loaded agent tacked on a conditional GPT recommendation for a hypothetical pool-value change, tripping the `no-tool-suggestions` assertion on what should be a clean "no." The skill's advisory flow may be nudging toward tool-mentions even in the negative case. Candidate for a skill tweak.
- **Eval 0 — with-skill led with CPT** where the assertion wanted GPT or custom k6 (and explicitly not CPT), costing the `suggests-tool` point. The skill's tool-routing for a hot backend endpoint over-favours CPT.
- **Eval 7 — `notes-ruby-only` failed in both configs.** Neither agent stated profilers are Ruby-specific or offered a non-Ruby fallback (e.g. `pprof`). The skill body says this, but it isn't surfacing when the prompt is already Ruby-framed. The assertion is doing its job (flagging a real gap); the skill could make the Ruby-only caveat more prominent.

## Non-discriminating evals (this run)

Evals 1, 2, and 4 scored 100% in both configurations. On Opus 4.8 these don't distinguish skill value — the model already handles CPT setup, Sitespeed routing, and "existing test found" well cold. They remain useful as regression guards (they'd catch a *drop*), but they don't demonstrate uplift. Worth revisiting in Q3, possibly with a cheaper/less-capable executor model where the skill's contribution would show more.

## Method notes / caveats

- **Single run per configuration.** This is a first baseline, not a variance study. Per-eval numbers can move ±1 assertion on a re-run; the ~13 pp aggregate gap and the large eval-6/eval-7 gaps are the robust findings. A multi-run (3x) pass is the natural Q3 follow-up for stddev.
- **Grading** was done by close reading of each response against the eval's assertions; evidence quotes are stored per assertion in each `grading.json`.
- The generated `benchmark.md` header says "3 runs each" (the aggregator's default label) and shows Tokens as 0 — both are cosmetic artifacts of the shared aggregation script; the pass-rate figures are correct. Actual runs per configuration: **1**.
