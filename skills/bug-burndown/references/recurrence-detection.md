# Recurrence detection and the persistent bugfix log

This reference is loaded on demand from the `bug-burndown` skill during
Phases 1 (load log), 4b/4c (recurrence match), and 8c (write log
update). It is the mechanism that closes the loop: every fix the
burndown produces feeds back into a corpus that informs future
sessions.

The goal is two-sided:

1. **Detect regressions of previously-fixed bugs**, even when the
   symptom presents differently than the original.
2. **Detect recurrences of buggy patterns** that the team has decided
   to fix structurally — catch every site, not just the one that
   showed up in the latest CI run.

Both rely on the same persistent log; the two uses differ in how the
log entries are queried.

## The bugfix-log directory layout

```
.bugfix/log/
├── index.jsonl                # append-only structured index
├── embeddings/
│   ├── BUG-7f3a9c1e.bin       # float32 vector, 384 or 768 dims
│   ├── BUG-9b2e1a04.bin
│   └── ...
├── BUG-7f3a9c1e.md            # full bug record (markdown)
├── BUG-9b2e1a04.md
└── patterns/
    ├── PAT-001.md             # pattern definition (signature + fix doctrine)
    └── PAT-002.md
```

Three classes of artefact:

- **`index.jsonl`** — structured row per bug; the queryable spine.
  Append-only; updates write a new row referencing the prior `id`.
- **`<bug_id>.md`** — the full human-readable record; what an engineer
  reads when investigating "have we seen this before?".
- **`patterns/<pat_id>.md`** — promoted recurring patterns; the source
  of truth for the code-review collector (`bug-burndown` Phase 2e).

## The `index.jsonl` schema

One JSON object per line:

```json
{
  "id": "BUG-7f3a9c1e",
  "schema_version": 1,
  "logged_at": "2026-05-16T16:42:11Z",
  "session_id": "20260516-141503-7a3f",

  "title": "panic in orchestrator dispatch on agent disconnect",
  "summary": "Orchestrator panics with 'inflight not found' when an agent disconnects mid-task.",

  "status": "fixed",
  "fix_sha": "a3f8e2d1b9c4...",
  "fix_branch_merged_into": "main",
  "fix_pr_url": "https://gitlab.com/.../merge_requests/1234",

  "fingerprint": {
    "kind_hash": "rust-panic-ExampleAppError",
    "primary_location": "crates/orchestrator/src/dispatch.rs:142",
    "message_norm": "inflight_not_found_during_disconnect",
    "structural_hash": "a3f8e2d1"
  },
  "embedding_ref": "embeddings/BUG-7f3a9c1e.bin",

  "severity_at_fix": "high",
  "kind": "bug",
  "signals": {
    "data_loss": false,
    "crash": true,
    "user_facing": true,
    "security_relevant": false
  },

  "structural_fix_summary": "Added explicit requeue branch in handle_disconnect; introduced Inflight<T> newtype with Drop-based invariant enforcement.",
  "invariant_restored": "every dispatched task ends in a terminal SurrealDB row",
  "violated_artefact": "ADR-0042",

  "tests_added": [
    "crates/orchestrator/src/dispatch/tests.rs::disconnect_requeues_inflight",
    "crates/orchestrator/src/dispatch/proptest.rs::no_lost_task"
  ],

  "doc_artefacts": [
    "docs/decisions/0061-orchestrator-crash-recovery.md",
    "features/orchestrator/agent_lifecycle.feature"
  ],

  "pattern_id": null,
  "lessons_learned": [
    "Disconnect handlers must enumerate in-flight state before clearing registry, not after.",
    "Drop impls are the right place for cleanup invariants; assert their firing in tests."
  ],

  "related_bug_ids": ["BUG-3c4f8a02"],
  "prior_fix_chain": []
}
```

### Status values

- `fixed` — merged structurally; reproducer kills mutation; DoD ticked.
- `blocked` — bugfix subagent hit circuit breaker; needs human input.
- `needs_human` — burndown dispatcher escalated (severity/blast radius
  too high relative to confidence).
- `wontfix` — explicit decision not to fix (e.g., spec changed instead).
- `regressed` — was `fixed`, observed again in a later session.
- `superseded` — fixed in a different way; entry kept for history.

State transitions are recorded by appending a new row with the same
`id` and updated `status` + `logged_at`. The latest row wins on read.

### `prior_fix_chain`

When a bug is `regressed`, the chain captures the trail:

```
prior_fix_chain: ["BUG-7f3a9c1e@a3f8e2d1", "BUG-7f3a9c1e@cd1234ab"]
```

Each entry is `<bug_id>@<fix_sha>`. The most recent fix is the last
entry. This makes it possible to answer "how many times have we tried
to fix this?" and "which fix held longest?".

## The `<bug_id>.md` schema

```markdown
---
id: BUG-7f3a9c1e
status: fixed
severity_at_fix: high
fix_sha: a3f8e2d1b9c4...
session_id: 20260516-141503-7a3f
logged_at: 2026-05-16T16:42:11Z
pattern_id: null
---

# BUG-7f3a9c1e — panic in orchestrator dispatch on agent disconnect

## Symptom

Orchestrator panics with "inflight not found" when an agent
disconnects mid-task. Observed in CI logs (run-7821) and reproduced by
test `disconnect_requeues_inflight`.

## Root cause

`handle_disconnect` cleared the agent registry before iterating
in-flight tasks for that agent, so the subsequent `requeue` lookup
returned None and the unwrap panicked.

## Three-way diff at time of fix

- **Desired** (per ADR-0042): on disconnect, in-flight tasks transition
  to `pending` or `failed` and are persisted.
- **Documented**: ADR-0042 specifies exactly this.
- **Implemented**: silent drop on disconnect; in-flight state lost.

Classification: **code-defect**. Authoritative: ADR-0042.

## Structural fix

- Added `Inflight<T>` newtype wrapping the per-agent task set.
- `Inflight::take_on_disconnect` returns the set BEFORE the registry
  is cleared; Drop impl asserts the set is empty by the end of the
  handler.
- `handle_disconnect` now: take inflight → requeue → clear registry,
  in that order.

Files changed:
- `crates/orchestrator/src/dispatch.rs` (signature + ordering).
- `crates/orchestrator/src/inflight.rs` (new newtype + Drop).

## Tests added

- `dispatch::tests::disconnect_requeues_inflight` (L2 component).
- `dispatch::proptest::no_lost_task` (L4 stateful proptest, 1000 cases).

## Doc artefacts

- `docs/decisions/0061-orchestrator-crash-recovery.md` (new ADR,
  flowed from adversarial review surfacing crash-recovery decision).
- `features/orchestrator/agent_lifecycle.feature` (new Gherkin
  Scenario via `/spec-create`).

## Lessons learned

- Disconnect handlers must enumerate in-flight state BEFORE clearing
  the registry, not after.
- Drop impls are the right place for cleanup invariants; assert their
  firing in tests.

## Future watchpoints (for recurrence detection)

If you see ANY handler that:
1. Calls `registry.remove(...)` AND
2. Reads `inflight[id]` after that call

…the same class of bug is present. See `patterns/PAT-003.md` if
promoted to a pattern.
```

The Markdown record is what an engineer reads. The frontmatter is
machine-parseable (the burndown skill's collectors read `pattern_id`,
`status`, etc.).

## The `patterns/<pat_id>.md` schema

Promoted patterns deserve a dedicated file because they drive Phase 2e
of the burndown. A pattern is "a bug class we've decided must not
recur anywhere in the codebase, ever".

```markdown
---
pattern_id: PAT-003
promoted_at: 2026-05-16T17:01:33Z
promoted_from: [BUG-7f3a9c1e, BUG-3c4f8a02]
status: active
pattern_signature_kind: ast        # regex | ast | semantic
pattern_signature: |
  // ast-grep pattern: registry mutation followed by inflight read
  let $REG = $$$REG_INIT;
  $REG.remove($AID);
  $$$;
  let $X = $INFLIGHT[$AID];

severity_floor: high
---

# PAT-003 — Registry-clear-before-inflight-read

## What

Any handler that mutates an agent registry to remove an agent AND
then reads the inflight state for that agent. The read returns None;
subsequent unwraps panic.

## Why it's a pattern (not just one bug)

Two distinct bugs (BUG-7f3a9c1e and BUG-3c4f8a02) exhibited this
exact shape in different handlers. The structural mistake is in the
*ordering* of registry mutation vs. inflight enumeration — orthogonal
to the specific handler logic.

## Doctrine: how to fix

1. Enumerate inflight state FIRST: take it into a local variable.
2. Mutate the registry SECOND.
3. Wrap the inflight set in the `Inflight<T>` newtype which asserts
   via its Drop impl that the set was processed before the handler
   returned.

## Detection signature

When the code-review collector runs, it searches for the AST pattern
above. Sites with this shape produce `pattern-recurrence` findings
that get dispatched to bugfix subagents with this doctrine in their
prompt.

## Promotion criteria (how this got here)

A bug becomes a pattern when ANY of:
- The same fix doctrine resolved ≥2 distinct bugs.
- A `bugfix` subagent's adversarial review explicitly named a class
  of sibling cases ("any handler doing X").
- A human review flagged the bug as "fix everywhere, not just here".

Promotion is a manual step the user takes (or the burndown skill
suggests at Phase 8). It is intentionally not automatic — patterns
shape future sessions strongly and false positives waste subagent
time.
```

## Embedding pipeline

### Embedding generation

Both session findings and log entries use the same embedding model.
The skill picks one of:

```python
# Option A: local Sentence-Transformers
from sentence_transformers import SentenceTransformer
model = SentenceTransformer("all-MiniLM-L6-v2")  # 384-dim, 80MB
# or
model = SentenceTransformer("BAAI/bge-base-en-v1.5")  # 768-dim, 440MB, higher quality

def embed(text: str) -> np.ndarray:
    return model.encode(text, normalize_embeddings=True)
```

```python
# Option B: API (Voyage shown; OpenAI/Cohere analogous)
import voyageai
vo = voyageai.Client()
def embed(text: str) -> np.ndarray:
    r = vo.embed([text], model="voyage-3", input_type="document")
    return np.array(r.embeddings[0])
```

Manifest records which embedding model + version was used:

```yaml
embedding:
  model: "all-MiniLM-L6-v2"
  dim: 384
  normalised: true
```

When the model changes, the entire embedding corpus must be regenerated
on the next session — `bug-burndown` detects model mismatch at Phase 1
and regenerates `embeddings/*.bin` from the markdown source records
before proceeding.

### What to embed

For each bug, embed the concatenation:

```
{title}

{summary}

{key error message or symptom}

{primary location}
```

NOT the full markdown record. Embeddings on long documents dilute the
signal; the title + symptom is the right level of granularity for
"same bug?" comparison.

### Similarity match

```python
import numpy as np

def cosine(a: np.ndarray, b: np.ndarray) -> float:
    # vectors are pre-normalised
    return float(np.dot(a, b))

def find_recurrence(finding_vec: np.ndarray, log_corpus: list[dict]) -> tuple | None:
    """Return (best_match_entry, similarity) or None."""
    best, best_sim = None, 0.0
    for entry in log_corpus:
        sim = cosine(finding_vec, entry["embedding"])
        if sim > best_sim:
            best, best_sim = entry, sim
    if best_sim > 0.80:
        return best, best_sim
    return None
```

Thresholds:

| Threshold | Action                                                         |
|-----------|----------------------------------------------------------------|
| ≥ 0.90    | Strong match. Auto-tag `recurring: true`. Add prior context.   |
| 0.85-0.90 | Probable match. Auto-tag but flag for human verification in report. |
| 0.80-0.85 | Borderline. AskUserQuestion at end of Phase 4 with the pair.   |
| < 0.80    | Not a match. No annotation.                                    |

### Performance

- Local model (MiniLM): ~5ms per embedding on CPU, ~0.5ms on GPU.
- 1000 findings × 1000 log entries: 1M cosine ops, <1s with numpy.
- Storage: 384 floats × 4 bytes = 1.5KB per embedding; 10K bugs = 15MB.

Storage and compute are negligible at realistic corpus sizes.

## The recurrence-handling protocol

When a session finding matches a prior log entry (similarity > 0.80):

### Case 1: prior status was `fixed`

This is the regression case. Actions:

1. Tag the session finding `recurrence.recurring = true`,
   `recurrence.prior_log_match = <prior_id>`,
   `recurrence.prior_fix_sha = <sha>`.
2. Escalate severity to at least `high`.
3. Set `signals.is_regression = true`.
4. The subagent's prompt includes the prior fix's
   `structural_fix_summary` and `lessons_learned`.
5. At Phase 8, the regression is highlighted in the chat summary AND
   `prior_fix_chain` of the log entry is appended.

### Case 2: prior status was `blocked` or `needs_human`

The prior session couldn't fix this. Actions:

1. Tag `recurrence.recurring = true` with prior status.
2. Keep severity from current classification (no escalation).
3. Subagent prompt includes the prior `lessons_learned` so it doesn't
   repeat the same dead-end approach.
4. If the prior session's blocker reason is still likely to hold (e.g.,
   "needs new external API access we don't have"), surface to human
   review immediately rather than dispatching.

### Case 3: prior status was `wontfix`

A deliberate decision was made not to fix this. Actions:

1. Tag the session finding `recurrence.recurring = true` with status
   `wontfix`.
2. Do NOT dispatch a subagent. Surface in report: "previously decided
   wontfix; if this decision should be revisited, see ${prior_log}".

### Case 4: prior status was `superseded`

Two prior bugs converged on the same fix. Actions:

1. Tag the session finding `recurrence.recurring = true` with the
   superseding bug's `id`.
2. Treat as Case 1 (regression) against the superseding fix.

## Promotion to pattern (manual ritual at Phase 8)

At session end, the skill suggests pattern promotion when:

- Two or more `fixed` bugs in this session share a substantially
  similar `structural_fix_summary` (embedding similarity > 0.80
  between summaries).
- A subagent's adversarial review (`bugfix` Phase 8b) explicitly
  named a class of sibling cases.

The chat summary includes:

> **Suggested pattern promotion:**
> BUG-7f3a9c1e and BUG-3c4f8a02 share the same structural fix
> ("registry mutation followed by inflight read"). Consider promoting
> to PAT-NNN. To accept: `/bug-burndown promote-pattern
> BUG-7f3a9c1e,BUG-3c4f8a02`. To dismiss: ignore.

Promotion writes a new file under `.bugfix/log/patterns/PAT-NNN.md` with
the doctrine derived from the bugs. The user must edit the
`pattern_signature` to be precise enough for the code-review collector
to use without producing excessive false positives.

## Pruning and maintenance

The bugfix log is append-only by design — failure history is
informative. But over years it can grow large. Suggested hygiene:

- After 1 year, bugs marked `fixed` whose `pattern_id == null` and
  `severity_at_fix < high` may be archived to a `bugfix-log-archive/`
  directory. They are no longer loaded by default; the burndown skill
  can be flagged to include them with `--include-archive`.
- Embeddings for archived bugs stay queryable; the records themselves
  move out of the hot path.
- Patterns are NEVER archived. They are the team's standing wisdom.

## Anti-patterns

- **Editing log entries to remove failed attempts.** Failures are
  informative; future sessions need to know what was tried and didn't
  work. Mark `status: superseded` if needed; do not delete.
- **Promoting patterns from a single bug.** A pattern is "we saw this
  class of mistake at least twice". One-shot bugs go in the log as
  individual entries.
- **Allowing the embedding model to drift silently.** When the model
  changes, regenerate the corpus. Stale embeddings produce wrong
  recurrence claims.
- **Trusting embeddings above 0.95 blindly.** Even near-perfect
  similarity can be coincidence on short texts. The structural
  fingerprint (Phase 4a) is the primary signal; embeddings are the
  semantic fallback.
- **Letting the corpus drive over-eager `pattern-recurrence` findings.**
  A pattern that matches >20 sites in a codebase likely has too loose
  a signature; tighten it or remove the pattern.

## Test-effectiveness recurrence patterns

Three additional recurrence classes track findings sourced from the
test-effectiveness baseline / delta (see `harness-builder/references/runtime-test-effectiveness-baseline.md`).
They live in the same `index.jsonl` corpus but carry distinct fingerprints
so they don't collide with bug fingerprints.

### Mutation-survivor recurrence

Fingerprint: `(file, fn, mutation_op)`. When the same triple appears in
two sessions across a 30-day window, the test the previous session
added (or claimed to add) didn't actually kill the mutant. Either the
test was hollow, or the implementation drifted back. Either way: P0,
tagged `recurring: mutation-survival`.

```json
{
  "id": "TES-1a2b3c4d",
  "kind": "test-effectiveness-recurrence",
  "subkind": "mutation-survivor",
  "fingerprint": "sha256(file+fn+mutation_op)",
  "first_seen_session": "20260418-091012-...",
  "first_seen_at": "2026-04-18T09:10:12Z",
  "last_seen_session": "20260516-141503-...",
  "last_seen_at": "2026-05-16T14:15:03Z",
  "claimed_fixed_in_session": "20260420-...",
  "claimed_fix_sha": "abc1234..."
}
```

When the recurrence detector finds this pattern, surface a `## Test
regressed since prior fix` block in the session report — the previous
fix's test should have killed this mutant, and it didn't.

### CRAP-regression recurrence

Fingerprint: `(file, fn)`. Track the CRAP score over time. When the score:

- **Persisted > 30 across ≥ 2 sessions** without a refactor commit → tag
  `recurring: crap-plateau`. The team's seen the hotspot and not moved
  on it; surface as a refactor recommendation rather than a fresh bug.
- **Dropped below 30 then climbed back** → tag `recurring:
  crap-regression`. Whatever refactor closed it has been undone or
  worked around. P1 with a link to the prior closing fix SHA.
- **Grew by ≥ 2× since the last session** → tag `recurring:
  complexity-creep`. Even if still under 30, accelerating complexity in
  a hot file is worth surfacing.

```json
{
  "id": "TES-9e8f7d6c",
  "kind": "test-effectiveness-recurrence",
  "subkind": "crap-regression | crap-plateau | complexity-creep",
  "fingerprint": "sha256(file+fn)",
  "history": [
    { "session": "...", "crap": 45.0, "at": "2026-04-18T..." },
    { "session": "...", "crap": 28.0, "at": "2026-04-25T..." },
    { "session": "...", "crap": 62.0, "at": "2026-05-16T..." }
  ]
}
```

### Coverage-cliff recurrence

Fingerprint: `(file, fn)`. When a function appeared in `coverage-cliff`
findings in a prior session and reappears now (or appears worse), tag
`recurring: coverage-debt`. P0 when the linked artefact is a
threat-model mitigation; P1 otherwise. The history field tracks
`module_coverage` across sessions.

### Recurrence detection in Phase 4b

The standard Phase 4b loop already runs over `index.jsonl`. Extend it
with:

```python
for finding in test_effectiveness_findings:
    fp = fingerprint_for(finding)              # per subkind above
    matches = corpus.find_by_fingerprint(fp)
    if matches:
        finding["recurring"] = True
        finding["prior_session"] = matches[-1].session_id
        finding["prior_claimed_fix_sha"] = matches[-1].fix_sha
        bump_severity_one_tier(finding)        # always lift on recurrence
```

The fingerprint match is exact — embedding similarity isn't useful here
because mutation operators and CRAP scores are discrete enough that the
structural key catches every real recurrence.
