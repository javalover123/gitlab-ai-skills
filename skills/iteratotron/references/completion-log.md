# Completion log + adversarial completion review

This reference is loaded on demand from the `iteratotron` skill during
Phases 1 (load log), 4b (recurrence detection), 7 (adversarial review),
and 8c (write log update). It defines the persistent completion-log
schema, the recurrence-detection protocol for completion claims, and
the adversarial completion reviewer's full subsection contract.

The completion log is iteratotron's analogue to bug-burndown's bugfix
log. It captures every scope-level completion attempt across sessions,
making "we said this was done before" first-class data. Combined with
the stop-bias-pattern catalogue, it answers the question: **is this
scope's `complete` claim trustworthy, or is it a stale claim, a
hallucination claim, or a once-true claim that has regressed?**

## The completion-log directory layout

```
.iteratotron/completion-log/
├── index.jsonl                  # append-only structured index
├── embeddings/
│   ├── SCOPE-7f3a9c1e.bin       # float32 vector, scope-claim embedding
│   ├── SCOPE-9b2e1a04.bin
│   └── ...
├── SCOPE-7f3a9c1e.md            # full scope record (markdown)
├── SCOPE-9b2e1a04.md
└── patterns/
    ├── STOP-PAT-001.md          # promoted stop-bias patterns
    └── STOP-PAT-002.md
```

The structure mirrors the bugfix log's, with a key difference:
**iteratotron promotes stop-bias patterns**, not bugs. A
stop-bias-pattern that recurs across scopes becomes a `STOP-PAT-NNN`
entry, which feeds future Phase 3c scans across all sessions.

## The `index.jsonl` schema

One JSON object per line, append-only:

```json
{
  "id": "SCOPE-7f3a9c1e",
  "schema_version": 1,
  "logged_at": "2026-05-16T18:42:11Z",
  "session_id": "20260516-152217-bf2a",
  "iterate_skill_version": "1.0.0",

  "scope_kind": "cargo-crate",
  "scope_name": "agent-compiler",
  "scope_primary_path": "crates/agent-compiler",

  "outcome": "complete",
  "completion_sha": "a3f8e2d1b9c4...",
  "merge_sha_in_integration": "b9c4d8e7...",
  "branch_merged_into": "main",

  "stop_hook_verdict": "passed",
  "adversarial_review_verdict": "APPROVED",

  "fingerprint": {
    "scope_kind_hash": "rust-cargo-crate",
    "scope_canonical_path": "crates/agent-compiler",
    "linked_artefacts_hash": "f8e2d1a3"
  },
  "embedding_ref": "embeddings/SCOPE-7f3a9c1e.bin",

  "manifest": {
    "files_changed": 12,
    "tests_added": 18,
    "test_coverage_before": 64.2,
    "test_coverage_after": 87.5,
    "gaps_closed": {"P0": 4, "P1": 12, "P2": 6, "P3": 2},
    "stop_bias_eliminated": {"stub": 3, "placeholder": 2, "partial": 1},
    "doc_artefacts_created": ["docs/adr/0061-..."],
    "doc_artefacts_updated": ["docs/specs/agent-compiler.md"]
  },

  "linked_artefacts_at_completion": {
    "spec": "docs/specs/agent-compiler.md@a3f8e2d1",
    "adrs": ["docs/adr/0042-agent-trait-design.md@a3f8e2d1",
             "docs/adr/0061-...@a3f8e2d1"],
    "threat_model": "docs/threat-models/agents.md@a3f8e2d1",
    "stories": ["docs/stories/STORY-187.md@a3f8e2d1"]
  },

  "iteration_log_tail": [
    "compiler-dispatch-real-impl (2026-05-16): replaced Ok(vec![]) stub with real dispatch logic; +6 tests; clippy/fmt clean.",
    "compiler-trait-impl-completion (2026-05-16): added 3 unimplemented! methods; updated ADR-0042 Confirmation; +12 tests.",
    "complete (2026-05-16): all Step 6 criteria passed, stop hook confirmed, adversarial review APPROVED."
  ],

  "lessons_learned": [
    "Stub implementations in trait impls were paired with doc comments claiming retry logic; both had to be fixed.",
    "ADR-0042 'Confirmation' section referenced tests that did not exist; iterate created them as part of completion."
  ],

  "stop_bias_patterns_in_history": ["STOP-PAT-001", "STOP-PAT-003"],
  "prior_completion_chain": []
}
```

### Outcome values

- `complete` — Phase 7 APPROVED, merged, stop hook passed.
- `blocked` — subagent hit a genuine blocker; user input needed.
- `needs_human` — Phase 7 NEEDS_HUMAN verdict.
- `insufficient` — Phase 7 INSUFFICIENT; archived after max attempts.
- `regressed` — was `complete`, observed gaps in a later session.
- `superseded` — completed differently in a later session.
- `wontfix` — explicit decision not to complete (rare; usually means
  scope was deprecated).

### State transitions

Append-only. Status changes write a new line with same `id` and
updated fields. The latest line wins on read.

### `prior_completion_chain`

When a scope is `regressed`, the chain records the trail:

```
prior_completion_chain: [
  "SCOPE-7f3a9c1e@a3f8e2d1 (20260415-091422-c1d4)",
  "SCOPE-7f3a9c1e@cd1234ab (20260516-152217-bf2a)"
]
```

This makes "how many times have we tried to drive this scope to
completion?" answerable, and supports the recurrence-detection
"prior_fix_did_not_take" lift.

## The `<scope_id>.md` schema

Human-readable record an engineer reads when investigating "has this
scope been done before?":

```markdown
---
id: SCOPE-7f3a9c1e
outcome: complete
scope_kind: cargo-crate
scope_name: agent-compiler
session_id: 20260516-152217-bf2a
logged_at: 2026-05-16T18:42:11Z
completion_sha: a3f8e2d1b9c4...
stop_hook_verdict: passed
adversarial_review_verdict: APPROVED
---

# SCOPE-7f3a9c1e — agent-compiler driven to completion

## Scope

Cargo crate at `crates/agent-compiler`. Implements the `AgentCompiler`
trait that translates higher-level task specs into ZMQ message
sequences for downstream agent dispatch.

## Starting state (at session start)

- 4 P0 gaps (severity-lifted from stop-bias-pattern findings):
  - FR-014 (spec marked Implemented) was a stub: `Ok(vec![])`.
  - 3 trait methods in `impl AgentCompiler for DefaultCompiler` were
    `unimplemented!()`.
- 12 P1 correctness gaps (`unwrap()` calls, missing error handling).
- 8 P2 quality (clippy warnings, missing docs).
- 3 P3 coverage (untested error paths).
- iteration-log last entry: "Partial — FR-014 stub remaining".
- Previous session: 20260415-091422-c1d4 (claimed complete; was
  hallucinated — see lessons below).

## What the iterate subagent did

The subagent ran through ~7 internal cycles (iterate banned numbering,
so the iteration log uses descriptive names). High-level:

1. Replaced the FR-014 stub with real dispatch logic. Wrote 6 unit
   tests against the spec's acceptance criteria.
2. Implemented the 3 `unimplemented!()` trait methods, each with
   tests. One required clarifying the contract — invoked
   `/adr-review` on ADR-0042 and added a new Confirmation row
   referencing the new tests.
3. Audited `unwrap()` calls; replaced with `?`-propagated errors or
   `expect()` with documented invariants.
4. Brought coverage from 64.2% → 87.5%.

Files changed: 12. Tests added: 18. Doc artefacts: 1 created
(`docs/adr/0061-compiler-error-propagation.md`), 1 updated
(`docs/specs/agent-compiler.md` — FR-014 row moved from `Partial` →
`Implemented` with a test reference).

## Adversarial review verdict

APPROVED. Reviewer subagent's notes:

- **Restate intent**: spec says compiler must dispatch tasks
  preserving order; tests confirm.
- **Three-way diff**: Desired = spec FR-014 "ordered dispatch";
  Documented (iteration log) = "real dispatch logic, ordered";
  Implemented (diff) = `Vec<Message>` returned in input order with
  test coverage of ordering. ✓
- **Stop-bias re-scan**: 0 new stop-bias patterns introduced in the
  worktree. Original 4 severity-lifted findings eliminated.
- **Hallucination spot-check**: ran on the new dispatch logic — body
  does substantive work (constructs ZMQ envelopes from task spec),
  tests exercise the real function (not tautological), doc comments
  match behaviour.
- **Doc-vs-code three-way diff**: FR-014 row now correctly says
  `Implemented` with a real test reference. ✓
- **Cross-scope contract preservation**: `AgentCompiler` trait
  signature unchanged; one new associated type added (additive, no
  break).

## Lessons learned

- The prior session (20260415-091422-c1d4) marked this scope complete
  but the implementation was a stub. The stop hook at that time did
  not detect the stub because the file had non-zero LoC and tests
  passed (tests were tautological). This session's adversarial-review
  hallucination spot-check is what caught it. Pattern: tautological
  tests + stub implementation + doc claiming complete = high-risk
  trio.
- ADR-0042's Confirmation row was missing; the prior session did not
  enforce it. iteratotron's adversarial-review doc-vs-code check
  surfaces this as a gap now.

## Recurrence indicators added

This scope's embedding is added to the corpus. Its stop-bias-pattern
findings (3 stubs + 3 unimplemented in trait impls) are tagged with
embeddings to support future recurrence detection — if any of these
patterns reappear in `agent-compiler` or a sibling crate, the next
session will surface them as `recurring`.

The pair "stub + spec FR Implemented" was observed twice now (once in
this scope, once in `agent-graph` last week) — consider promoting to
STOP-PAT-NNN. See `## Pattern promotion suggestion` below.

## Pattern promotion suggestion

Two scopes have now exhibited "spec FR marked Implemented, but
implementation is a stub" within a 30-day window. Consider:

```
/iteratotron promote-pattern STOP-7f3a9c1e,STOP-cd1234ab
```

Promotion would create `STOP-PAT-001` with the doctrine: "before
marking an FR row Implemented, the implementation must do substantive
work AND have a non-tautological test". Future stop-bias scans would
then auto-flag this combination across all scopes.
```

The frontmatter is machine-parseable; the body is for humans.

## The `patterns/<pat_id>.md` schema

```markdown
---
pattern_id: STOP-PAT-001
promoted_at: 2026-05-16T19:05:11Z
promoted_from: [SCOPE-7f3a9c1e, SCOPE-cd1234ab]
status: active
pattern_kind: hallucination | stub | placeholder | tautological-test | partial-spec-claim
pattern_signature_kind: composite  # composite signatures use multiple scans
pattern_signature: |
  # Composite scan:
  # 1. Find spec FRs marked Implemented (status column = Implemented)
  # 2. For each, find the implementation file(s) (via traceability or rg)
  # 3. Scan the implementation for stub patterns (Family 1 of stop-bias-patterns.md)
  # 4. Scan the tests for tautological-test patterns (Family 6d)
  # Pattern matches when both 3 and 4 fire for the same FR.
severity_floor: P0
---

# STOP-PAT-001 — Spec-implemented-but-implementation-is-stub

## What

A spec FR row is marked `Implemented`, but the implementation is a
stub returning a default/empty value, AND the tests for that FR are
tautological (assert on test setup, not on code under test).

## Why it's a pattern (not just one finding)

Observed in two distinct scopes within 30 days. The mechanism
underlying both occurrences was the same: a long AI-assisted coding
session was prompted to "finish the feature", produced
implementation-shaped code plus implementation-shaped tests plus a
spec update — all three syntactically correct but semantically empty.

The combination is dangerous because:
- The stop hook passes (tests exist and pass).
- A casual code review passes (the file is non-trivial in size).
- The completion claim is technically true at every individual layer
  but false as a whole.

## Doctrine: how to detect (Phase 3c usage)

When iteratotron's stop-bias scan finds a stub in `crates/<x>/`:
1. Find the spec FR that cites `crates/<x>/`.
2. If that FR's status is `Implemented`, severity-lift to P0.
3. Additionally scan the tests for that FR for tautological-test
   patterns (Family 6d). If positive, surface as a high-confidence
   STOP-PAT-001 finding.

## Doctrine: how to fix

1. Replace the stub with real implementation logic that satisfies the
   spec FR's acceptance criteria.
2. Replace tautological tests with tests that call the function under
   test and assert on its return value.
3. Ensure ADR Confirmation rows reference the new tests by name.
4. Only after all three are done, update the spec FR row to
   `Implemented` with a test reference.

## Detection signature (composite)

This pattern uses a composite signature because no single regex finds
it. The Phase 3c collector runs three sub-scans and joins their
output:

```bash
# Sub-scan A: spec FRs marked Implemented
rg -P '^\|\s*(FR-\d+)\s*\|.*\|\s*Implemented\s*\|' docs/specs/ \
  --no-filename | awk -F'|' '{gsub(/\s+/,"",$2); print $2}' > /tmp/implemented-frs

# Sub-scan B: for each, find the implementation files (cite or rg)
# ... (skill-implementation-specific)

# Sub-scan C: stop-bias Family 1 + Family 6d scans on those files
# Pattern matches when A∩B∩C is non-empty
```

## Promotion criteria (how this got here)

Two distinct scopes (SCOPE-7f3a9c1e, SCOPE-cd1234ab) exhibited the
same combination within a 30-day window. The first occurrence was
discovered post-hoc by iteratotron's adversarial-review; the second
was prevented from completing by the same review. After two
occurrences, the pattern was promoted manually by the user.

## Active in scans

This pattern is active. iteratotron's Phase 3c scan runs the composite
signature against every audited scope. Findings produce
`stop-bias-pattern: STOP-PAT-001` records.
```

## Embedding pipeline

Same model and approach as bug-burndown's recurrence-detection
reference. Brief summary:

- Local model: `all-MiniLM-L6-v2` (384-dim, 80MB).
- API alternative: Voyage / OpenAI / Cohere.
- Embed: `f"{scope_name}\n{summary}\n{key gap categories}\n{primary
  artefacts}"`.
- Cosine similarity for match; thresholds:

| Threshold | Action                                                              |
|-----------|---------------------------------------------------------------------|
| ≥ 0.90    | Strong match. Auto-tag `recurring: true`. Add prior context.        |
| 0.85-0.90 | Probable match. Auto-tag, flag for human verification in report.    |
| 0.80-0.85 | Borderline. AskUserQuestion at end of Phase 4 with the pair.        |
| < 0.80    | Not a match.                                                        |

Performance and storage are negligible at realistic corpus sizes
(scopes per project rarely exceed hundreds; embeddings total <100KB).

## The recurrence-handling protocol

Same five cases as bug-burndown, adapted to scope-level claims:

### Case 1: prior `complete` → currently has gaps (REGRESSION)

The scope was previously claimed complete and is no longer. Actions:

1. Tag finding `recurrence.recurring = true`, `prior_log_match =
   <prior_id>`, `prior_fix_sha = <sha>`.
2. Escalate severity to at least P1.
3. Subagent prompt includes prior completion claim AND list of
   commits to this scope since that claim.
4. Phase 7 reviewer applies extra scrutiny: was the prior completion
   hallucinated (tautological tests + stub impl), or did real new
   work introduce the gap?
5. Append to `prior_completion_chain` on log update.

### Case 2: prior `blocked` / `needs_human`

Carry forward prior lessons. Subagent prompt warns against the same
dead-end approach. Surface to human review immediately if the prior
blocker reason is still likely to hold.

### Case 3: prior `wontfix`

Surface in report: "previously decided wontfix; if this decision
should be revisited, see ${prior_log}". Do not auto-dispatch.

### Case 4: prior `superseded`

Treat as Case 1 (regression) against the superseding completion.

### Case 5: stop-bias pattern recurrence (iteratotron-specific)

If the recurrence detection matches a previously-eliminated
stop-bias-pattern rather than a scope claim, the protocol is:

1. **Same scope as prior**: the prior "elimination" did not actually
   eliminate. Severity lift to P0. Tag
   `prior_elimination_did_not_take: true`. The subagent's prompt
   includes the prior elimination's doctrine plus a strong note that
   it did not work.
2. **Different scope from prior**: the anti-pattern has spread.
   Consider STOP-PAT-NNN promotion if not already promoted.

## The adversarial completion reviewer protocol

Phase 7 delegates verification to the `adversarial-completion-reviewer`
subagent. Its prompt template:

```
You are reviewing a completion claim from an iterate subagent.

You see ONLY:
- The diff between baseline_sha and the worktree's HEAD.
- The scope's linked design artefacts (spec, ADRs, threat model,
  stories) at HEAD (with updates from this completion).
- The iteration log (all entries from this session).
- The original gap inventory (pre-completion).
- The stop-bias findings catalogue (so you can re-run the scan).

You do NOT see the iterate subagent's reasoning or prior context.
Cold-context verification is the point.

# Required output sections — fill every one with cited evidence

## 1. Restate the completion intent

In one sentence per gap category that was claimed closed, what was
the design intent? Cite spec/ADR/story line.

## 2. Three-way diff per gap

For each gap the iteration log claims closed:
- Desired (what the spec/ADR says)
- Documented (what the iteration log claims)
- Implemented (what the diff actually does)
For any divergence, the claim is suspect. Cite line numbers.

## 3. Stop-bias-pattern re-scan

Run the Phase 3c stop-bias scan against the worktree's HEAD (not
baseline). Report:
- Old stop-bias findings: ${list from gap_inventory.stop_bias_findings}
- After completion: ${re-scan results}
- New stop-bias patterns introduced: ${diff}

Any new finding rejects completion. The iterate run cannot introduce
new stop-bias patterns while closing old ones.

## 4. Hallucination spot-check

For every new function/module/test added in the diff:
- Does the function body do substantive work, or return a default?
- Do tests assert on the code under test (call into it), not on
  their own setup output?
- Do new doc comments accurately describe what the code does (read
  the doc, then read the code, then judge)?

Cite specific file:line for any finding.

## 5. Doc-vs-code three-way diff at scope boundaries

For each ADR/spec FR/story claimed moved to Implemented:
- Open the artefact at HEAD; quote the relevant section.
- Open the implementation at HEAD; quote the relevant code.
- State whether they agree.

## 6. Cross-scope contract preservation

Does the diff change any public API/trait/message format that other
scopes depend on?
- Use `rg` to find external callers of any modified public symbol.
- For each caller in another scope, state whether the contract is
  preserved.
- Cite file:line for any potentially-breaking change.

## 7. Iteration-log integrity check

- Does the iteration log have iterate's banned phrases?
- Are entries one-line descriptive (no ordinals, no "Iter N")?
- Does the final entry follow the canonical "complete (YYYY-MM-DD):
  all Step 6 criteria passed, stop hook confirmed." form?

Cite any violation.

## 8. Verdict

Choose ONE:

- **APPROVED** — every subsection filled, no defect found, all
  searches documented.
- **INSUFFICIENT** — return to the iterate loop with the named gaps.
  Cite which gaps remain or were newly introduced.
- **NEEDS_HUMAN** — something requires human design input
  (e.g., spec contradicts ADR; user must adjudicate).
```

## Pruning and maintenance

- Append-only design by intent.
- After 1 year, completion records with `outcome: complete` AND no
  associated `STOP-PAT` AND no recurrence in subsequent sessions may
  be archived to `completion-log-archive/`.
- Patterns are never archived.

## Anti-patterns

- **Trusting iterate's stop hook alone.** The hook checks mechanical
  criteria. Phase 7 adversarial review is what catches the
  hallucination cases.
- **Auto-merging at high similarity without verification.** Even
  >0.95 scope-similarity can be coincidence (two crates with similar
  names but different intent). The fingerprint (linked artefacts) is
  the structural truth; embedding is the semantic fallback.
- **Promoting STOP-PAT patterns too eagerly.** A pattern from a
  single occurrence is just one finding. Two occurrences across
  distinct scopes within a window is the minimum.
- **Editing the completion log retroactively.** Failures and
  regressions are informative; never delete them. Mark `superseded`
  if needed.
- **Skipping adversarial review when "iterate clearly passed".** That
  is exactly the case where review is most valuable — iterate's
  passes are necessary but not sufficient. The hallucinated-impl case
  is iterate-passes-cleanly-but-implementation-is-fake.
