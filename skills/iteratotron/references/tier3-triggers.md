# Tier-3 escalation triggers

Tier-3 verification (chaos / deterministic-simulation / multi-VM /
formal methods) is the differentiator between iteratotron and every public
spec-driven implementation platform. Most platforms (Devin, OpenHands,
GPT-Engineer, Aider, Spec Kit) stop at "tests pass." The SWE-ABS
adversarial study (arXiv 2603.00520, March 2026) found 19.78% of
"solved" cases on the top-30 SWE-Bench Verified agents fail under
strengthened test suites — empirical confirmation that benchmark-pass
is necessary but not sufficient.

But Tier-3 is **expensive**. A madsim sweep of 1000 seeds on a
17-agent ZMQ topology runs for hours. Wycheproof on non-crypto code is
pure waste. So iteratotron fires Tier-3 only when the scope's spec content,
threat model, ADR, or constitution gives a concrete reason to.

This reference is the taxonomy of triggers and the sampling strategy
for each. The composition logic lives in
`references/harness-vector.md`; this reference is the canonical
trigger → tool mapping.

## The trigger taxonomy

| Trigger phrase (or pattern) in spec / threat model / ADR / constitution | Tier-3 tool | Scope-completion sample | Project-complete full sweep |
|---|---|---|---|
| "leader election", "consensus", "transaction commit protocol", "Paxos", "Raft" | TLA+ / P + `tlc` | 1 model check, no liveness | + liveness checks |
| "hand-rolled sync primitive", "custom Mutex", "lock-free queue", "atomic ordering" | loom (exhaustive C11) | 1 loom run per primitive | same — loom is exhaustive |
| "`tokio::spawn` in multi-agent path", "async fn" + "race", "task interleaving" | shuttle (PCT randomized) | 50 seeds | 1000 seeds |
| "distributed", "ZMQ DEALER/ROUTER", "message bus", "saga", "two-phase commit" | madsim deterministic simulation | 50 seeds | 1000 seeds |
| "multi-host", "VLAN", "BitTorrent topology", "deploy verification" | nixosTest multi-VM + tc-netem in guests | 1 topology run | same |
| "network partition", "latency injection", "packet loss", "node failure" | Toxiproxy in front of sockets | 1 chaos scenario | full scenario matrix |
| "FIPS", "AEAD", "signature scheme", "key exchange", "AES-GCM", "ChaCha20-Poly1305" | Wycheproof vectors + differential vs. ring / RustCrypto / openssl-sys | full vector set | same |
| "OpenAPI", "REST contract", "GraphQL schema", "gRPC proto" | schemathesis conformance fuzz | full link-derived state machine | + longer fuzz time |
| "parser", "decoder", "deserializer", "codec" | bolero + Kani (when feasible) | 50 fuzz seeds + 1 Kani proof | 10k fuzz seeds + Kani exhaustive |
| "production memory limit", "OOM", "RSS bound" | criterion-rs + heaptrack | 1 benchmark run | + regression baseline |

## Sampling strategy

The "scope-completion sample" column is what runs when a single scope
completes (Phase 7 review). The "project-complete full sweep" is what
runs at Phase 4 done-predicate check. The gap is intentional: scope-
completion samples are fast enough to fit per-scope budgets; full
sweeps justify their cost only once per project at the very end.

For randomized tools (shuttle, madsim), the seed range matters:

- **Sample**: 50 random seeds + the 3 "interesting" pre-recorded
  failure seeds (if any exist in `.iteratotron/tier3/<tool>/known-seeds.jsonl`).
- **Full sweep**: 1000 random seeds, plus a hash-partition strategy
  so seeds are deterministic across runs.

For exhaustive tools (loom, TLA+ TLC), no sampling — one run is
authoritative. Budget caps come from the harness vector
(`references/harness-vector.md` § "Budget partitioning").

## Trigger composition

A single scope can fire multiple triggers. The composition rule:

- **Union of triggered tools.** A scope mentioning both "ZMQ
  DEALER" and "AES-GCM" gets madsim + Wycheproof, not "pick one".
- **Sequential sampling at scope completion.** Don't parallelize
  Tier-3 within a single scope review; the failures need clean
  attribution to the specific tool.
- **Skip triggers that are out-of-language.** loom is Rust-only; if
  the scope is Go code, skip even though it mentions sync primitives
  (use Go's race detector + rapid state machines instead).

## When triggers are absent

A scope that doesn't match any trigger genuinely doesn't need Tier-3
at scope-completion. Don't run Tier-3 "to be thorough" — that's the
mistake that makes iteratotron 10× more expensive than it should be.

The deterministic sample at Phase 4 (done predicate) is the
project-level safety net for "did we miss a trigger?". It re-runs the
full sample on every scope, even ones that didn't trigger at
scope-completion. Surprises at this stage are flagged as
`tier3-trigger-missed` findings and trigger a constitution-amendment
discussion (the constitution should have caught the missing trigger;
its absence is the underlying issue).

## Building the trigger detector

Phase 1 of iteratotron runs a one-shot Haiku scan across all spec / ADR /
threat-model / story files:

```bash
claude -p "$(cat <<EOF
Scan these files for Tier-3 triggers. Triggers are listed in the
table below. For each file, list the triggers that match (with
file:line evidence) and the implied tools.

Trigger → tool table:
$(cat ~/.claude/skills/iteratotron/references/tier3-triggers.md \\
  | awk '/^## The trigger taxonomy/,/^## Sampling strategy/' )

Files to scan:
$(find specs/ adrs/ threat-models/ stories/ .specify/ -name '*.md')

Output JSON:
{
  "triggers_detected": [
    {
      "file": "...",
      "line": 42,
      "phrase": "...",
      "tools_implied": ["..."]
    }
  ],
  "scopes_affected": {
    "<scope-id>": ["tool1", "tool2"]
  }
}
EOF
)" --model haiku --max-turns 1 --output-format json
```

The output goes into `harness_vector#tier3_from_spec`.

## False-positive handling

Pattern-matching triggers will occasionally fire on text that mentions
the keyword without the meaning — a spec that says "this is NOT a
distributed system" still mentions "distributed". The detector's prompt
asks Haiku to read context, not just match keywords, so most false
positives get filtered there.

Remaining false positives surface at the Phase 7 adversarial reviewer:
when a Tier-3 tool runs against code that doesn't actually exercise its
test surface (madsim against code that doesn't use Tokio, Wycheproof
against code that doesn't call crypto), the reviewer flags
`tier3-trigger-false-positive` and the harness vector is amended for
the rest of the session. The Tier-3 run for that scope is treated as
"vacuously passed" — no signal but no failure.

## Constitution-driven triggers

When `.specify/memory/constitution.md` includes principles like "all
cryptographic primitives must pass Wycheproof vectors", those imply
project-wide triggers regardless of per-scope content. The trigger
detector includes the constitution in its scan; matched constitution-
level triggers go into `harness_vector#tier3_from_constitution` and
are applied to every scope whose code matches the constitution's
predicate.

This is how iteratotron enforces project-wide invariants (FIPS compliance,
distributed-state correctness) without requiring every spec to repeat
the trigger phrase.

## Verification time regression detection

The `iteratotron` stop-bias-pattern catalogue Family 12 (verification
time regression) fires when bolero / Kani / shuttle / madsim wall-clock
on the same harness grows > 50% session-over-session. Genesis tracks
this:

- Each Tier-3 run records `(tool, harness, seeds, wall_clock_s,
  session_id)` to `.iteratotron/tier3/timing.jsonl`.
- Before each Tier-3 run, look up the prior wall-clock for the same
  `(tool, harness, seed_count)` triple.
- Growth > 50% → emit Family 12 finding to bug_queue.
- Growth > 100% OR exceeds budget → P0 finding; the iterate prompt for
  the resolution must decompose the harness or simplify the property
  (not raise the timeout).

## Tier-3 budget caps

The full Tier-3 sweep at Phase 4 has a global wall-clock cap and a
USD cap (see `references/harness-vector.md` § "Budget partitioning").
When the cap is hit before all scopes' full sweeps complete:

1. Sample the remaining scopes at sample-density (50 seeds) instead
   of full density.
2. Record `tier3_budget_capped: true` in the done predicate output.
3. Surface to the operator as a one-line warning — the project is
   declared done with a budget-capped Tier-3 verification, not a full
   one. The human decides whether to extend the budget or accept the
   reduced verification.

The Antithesis commercial alternative (hypervisor-level DST with
autonomous bug-search) is out of personal-project budget but worth
knowing about when Tier-3 cost becomes a serious blocker.
