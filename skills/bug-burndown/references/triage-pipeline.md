# Triage pipeline: classify, fingerprint, dedupe, prioritise

This reference is loaded on demand from the `bug-burndown` skill during
Phases 3-5. It defines the data model that turns raw findings into a
prioritised, deduplicated queue ready for the dispatcher.

## The queue entry schema (canonical)

Every queue entry in `${session_dir}/queue.jsonl` is a single JSON
object on its own line. Append-only; updates happen via a new line that
references the prior `id`. The latest line wins on read.

```json
{
  "id": "BUG-7f3a9c1e",
  "schema_version": 1,
  "session_id": "20260516-141503-7a3f",
  "created_at": "2026-05-16T14:18:42Z",
  "updated_at": "2026-05-16T14:18:42Z",

  "kind": "bug",
  "severity": "high",
  "signals": {
    "data_loss": false,
    "crash": true,
    "user_facing": true,
    "security_relevant": false,
    "blocks_release": true
  },

  "title": "panic in orchestrator dispatch on agent disconnect",
  "summary": "Orchestrator panics with 'inflight not found' when an agent disconnects mid-task.",

  "fingerprint": {
    "kind_hash": "rust-panic-ExampleAppError",
    "primary_location": "crates/orchestrator/src/dispatch.rs:142",
    "message_norm": "inflight_not_found_during_disconnect",
    "structural_hash": "a3f8e2d1"
  },
  "embedding_ref": "embeddings/BUG-7f3a9c1e.bin",

  "sources": ["logs", "tests"],
  "observations": [
    {
      "source": "logs",
      "source_ref": "ci-logs/run-7821.json",
      "observed_at": "2026-05-15T18:14:00Z",
      "raw_text_ref": "findings/logs.jsonl#L42"
    },
    {
      "source": "tests",
      "source_ref": "example_orchestrator::dispatch::tests::disconnect_test",
      "raw_text_ref": "findings/tests.jsonl#L7"
    }
  ],

  "blast_radius": {
    "callers": 14,
    "surfaces": ["orchestrator-api", "agent-link"],
    "estimate_method": "rg-symbol-count"
  },

  "dependency": {
    "blocks": ["BUG-9b2e1a04"],
    "blocked_by": [],
    "related": ["BUG-3c4f8a02"]
  },

  "recurrence": {
    "recurring": false,
    "prior_log_match": null,
    "pattern_id": null
  },

  "fix_estimate": {
    "cost": "M",
    "diagnosis_confidence": "high",
    "requires_human_review": false,
    "reasons": ["clear stack frame", "single-file blast radius primary"]
  },

  "priority_rank": 2,
  "priority_reasons": ["severity=high", "blast=14", "blocks=1"],

  "status": "queued",
  "attempt_count": 0,
  "worktree": null,
  "branch": null,
  "fix_sha": null,
  "lessons_learned": []
}
```

`schema_version` lets future versions of the skill migrate old queue
files. Bump when the schema changes incompatibly.

---

## Phase 3 — Classify (in detail)

For every raw finding, walk the classification cascade:

### Step 1 — Kind

Inspect `candidate_kind` from the collector. Promote/demote per these
rules:

- A `bug` whose top stack frame is in a test file → `flaky` (the test
  itself may be broken).
- A `bug` whose message contains `panic`, `unreachable`, or
  `assertion failed` → `crash`.
- A `bug` that matches a `pattern_id` from the bugfix log →
  `pattern-recurrence` (preserve original `bug` kind under
  `original_kind` field).
- A `crash` in a fuzz target with a minimised input → keep `crash`,
  add `signals.adversarial_input_required: true`.

### Step 2 — Severity (cascading rules, first match wins)

1. **Critical** if any of:
   - `signals.data_loss` (corrupts persistent state without notice).
   - `signals.security_relevant` and the violation is exploitable.
   - Panic/crash on a non-adversarial input path (typical user input).
   - Build/CI fundamentally broken (no green path possible).
   - Threat-model violation involving a trust boundary.

2. **High** if any of:
   - User-facing behaviour is wrong (wrong output, wrong error,
     wrong state surfaced).
   - Recurring pattern (a fix was applied before and the pattern is
     back in the codebase).
   - Performance regression >2x on a hot path.
   - Crash on an adversarial-but-plausible input (oversize, encoding).
   - Spec drift on an `MUST` invariant.

3. **Medium** if any of:
   - Wrong internal behaviour without user-visible impact.
   - Spec drift on a `SHOULD` invariant.
   - Issue with diagnosis-confidence low but clear symptom.

4. **Low** if any of:
   - Flaky test with no associated production code defect identified.
   - Cosmetic / log-message-only.
   - Lint-level finding.

**Tie-breaker rule:** when uncertain between two tiers, choose UP.
Misclassified-as-low is the more costly error because it deprioritises
real risk.

### Step 3 — Signals

Set each boolean based on evidence:

| Signal              | Set true when                                         |
|---------------------|-------------------------------------------------------|
| `data_loss`         | persistent state is written incorrectly or lost       |
| `crash`             | panic, abort, segfault, unhandled exception           |
| `user_facing`       | observable to a user via UI, CLI, API response        |
| `security_relevant` | touches auth, crypto, supply chain, trust boundary    |
| `blocks_release`    | severity is critical OR blast_radius.callers > 20     |
| `adversarial_input` | only triggers on attacker-controlled input            |

### Step 4 — Blast radius estimation

For each finding with a clear primary symbol or file:

```bash
# Symbol callers (Rust)
symbol="<extracted from stack frame>"
callers=$(rg -c -t rust "\b${symbol}\b" "${repo_root}" \
           | awk -F: '{s+=$2} END {print s+0}')

# File-as-surface
surfaces=$(rg -l -t rust "use .*${module_path}" "${repo_root}" \
           | wc -l)
```

For spec-drift findings, blast radius is the count of code locations
the artefact's invariant applies to (often >1).

Record `estimate_method`: one of `rg-symbol-count`, `import-count`,
`spec-applicability-count`, `manual`.

### Step 5 — Fix estimate

Diagnosis confidence:

- **high**: stack frame names a single function; bug class is well-
  known; reproducer obvious from the finding.
- **medium**: symptom is clear but multiple plausible origins; needs
  Phase 4 of the bugfix skill to disambiguate.
- **low**: symptom is real but mechanism unclear; needs significant
  Phase 2-4 work in bugfix.

Cost:

- **S**: single file, single function, <50 LOC. Confidence high.
- **M**: single module, <200 LOC. Confidence high or medium.
- **L**: cross-module, may require new abstraction or ADR. Confidence
  medium.
- **XL**: architectural; needs human design input. Confidence low OR
  blast_radius.callers > 50 OR `signals.security_relevant` AND
  confidence not high. Set `requires_human_review: true`; skip
  dispatch.

---

## Phase 4 — Dedupe (in detail)

### 4a. Structural fingerprint (cheap pass)

Compute the `fingerprint` block for every finding:

```
fingerprint = {
    kind_hash:        f"{language}-{error_class}-{error_variant}",
    primary_location: f"{file}:{line}",       // top stack frame
    message_norm:     normalise(error_message),
    structural_hash:  blake2b_4bytes(kind_hash + message_norm + primary_location)
}
```

`normalise(message)`:

```python
def normalise(msg: str) -> str:
    msg = msg.lower()
    # remove run-specific addresses
    msg = re.sub(r'0x[0-9a-f]+', '<addr>', msg)
    # remove timestamps
    msg = re.sub(r'\d{4}-\d{2}-\d{2}t[\d:.]+z?', '<ts>', msg)
    # remove uuid-like blobs
    msg = re.sub(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', '<uuid>', msg)
    # remove numeric IDs (preserve semantic numbers like buffer sizes by keeping numbers in context)
    msg = re.sub(r'\b(?:id|ref|key|task|agent|peer)[_-]?\d+\b', '<id>', msg)
    # collapse whitespace
    msg = re.sub(r'\s+', ' ', msg).strip()
    return msg
```

**Match rule:** two findings with identical `structural_hash` collapse
to one. The first occurrence wins on metadata; subsequent occurrences
contribute to the `observations` list and the `sources` union.

This catches 60-80% of duplicates cheaply.

### 4b. Embedding match (semantic pass)

For findings that did NOT structurally match, run embedding similarity.

**Embedding choice.** Pick one based on what's available locally; the
skill's behaviour doesn't depend on which:

- **Local model (preferred for offline / fleet use):**
  ```bash
  # Using sentence-transformers via Python
  python3 -c '
  from sentence_transformers import SentenceTransformer
  import json, sys, numpy as np
  m = SentenceTransformer("all-MiniLM-L6-v2")
  for line in sys.stdin:
      r = json.loads(line)
      text = f"{r['title']}\n{r['summary']}\n{r['structured'].get('raw_text','')}"
      vec = m.encode(text)
      print(json.dumps({"id": r["id"], "vec": vec.tolist()}))
  '
  ```
  `all-MiniLM-L6-v2` is 80MB, runs in seconds on CPU, gives 384-dim
  vectors. Adequate for symptom-text similarity.

- **Voyage / OpenAI / Cohere embeddings API:** higher quality, costs
  per call. Use when the local model isn't available and the network is.

Store embeddings as float32 `.bin` files under
`${session_dir}/embeddings/<bug_id>.bin` (and similarly for prior
bugfix-log entries).

**Match procedure:**

```python
# Within-session pass
threshold = 0.85
candidates = [f for f in findings if f not in already_matched]
for i, a in enumerate(candidates):
    for b in candidates[i+1:]:
        sim = cosine(a.embedding, b.embedding)
        if sim > 0.85:
            collapse(a, b)              # automatic merge
        elif sim > 0.80:
            ask_user_borderline(a, b)   # AskUserQuestion
```

For borderline cases (0.80-0.85), surface as a single
`AskUserQuestion` at the end of Phase 4 with all pairs in one prompt:

> "I found 3 borderline duplicate pairs. Which (if any) should be
> merged? [a/b/c/none/all]"

### 4c. Cross-session recurrence detection

For each session finding's embedding, compare against
`.bugfix/log/index.jsonl` (the embedded prior corpus):

```python
prior = load_jsonl(".bugfix/log/index.jsonl")
for finding in findings:
    matches = [
        (prior_entry, cosine(finding.embedding, prior_entry.embedding))
        for prior_entry in prior
    ]
    matches.sort(key=lambda x: -x[1])
    if matches and matches[0][1] > 0.80:
        top, sim = matches[0]
        finding.recurrence = {
            "recurring": True,
            "prior_log_match": top.id,
            "prior_fix_sha": top.fix_sha,
            "prior_status": top.status,
            "similarity": sim,
            "pattern_id": top.pattern_id,
        }
        # If prior was status=fixed → this is a regression
        if top.status == "fixed":
            finding.severity = max(finding.severity, "high")
            finding.signals["is_regression"] = True
```

See `references/recurrence-detection.md` for the full bugfix-log schema
and the regression-handling protocol.

---

## Phase 5 — Prioritise (in detail)

### Sort key (strict total order)

```python
def priority_key(bug):
    severity_score = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    return (
        severity_score[bug.severity],                # ascending = higher priority
        -bug.blast_radius["callers"],                # descending = higher priority
        bug.dependency_topo_order,                   # ascending = root-cause first
        cost_score(bug.fix_estimate["cost"]),        # ascending = small first
    )
```

where `cost_score`: S=0, M=1, L=2, XL=3.

### Dependency graph construction

Two indicators that A blocks B:

1. **Code path overlap.** B's primary stack frame passes through (or
   calls) the function A modifies. Detected via:
   - rg for B's frame symbols inside A's `primary_location` file.
   - If A is a `pattern-recurrence` finding, every other finding sharing
     the same `pattern_id` is in the same equivalence class — fix one
     site, the others may resolve.

2. **Artefact dependency.** B is a `spec-drift` finding whose
   `artefact_id` is the ADR being updated by A's fix.

Build a small DAG of these edges, then topologically sort within each
severity tier. Ties broken by cost (cheapest first to maintain
momentum).

### `blocks` / `blocked_by` write-back

After sort, each entry's `dependency.blocks` and
`dependency.blocked_by` get filled with the IDs of the entries it
edges to. The dispatcher uses these to gate dispatchability.

### Priority reasons (for transparency)

For every entry, emit a short list of phrases explaining its rank:

```json
"priority_reasons": [
  "severity=critical",
  "blast=14",
  "blocks=BUG-9b2e1a04, BUG-3c4f8a02",
  "recurring (prior_fix=abc1234)"
]
```

These show up in `report.md` and in the chat summary so the user can
sanity-check the queue ordering.

---

## Validation gate before Phase 6

Before any subagent dispatches, verify the queue:

```
- [ ] Every entry has a unique id, fingerprint, embedding_ref.
- [ ] Every entry has severity, signals, blast_radius set.
- [ ] No entry has `status` other than `queued`, `needs_human`, or
      `skipped` at this point.
- [ ] Dependency edges form a DAG (no cycles).
- [ ] Top-20 entries make sense: spot-check 3 random ones — does the
      severity feel right given the symptom?
```

If the spot-check fails, AskUserQuestion before dispatching. A bad
queue produces a bad burndown; dispatching from a bad queue is wasted
subagent time.

---

## Anti-patterns

- **Auto-merging near-duplicates without AskUserQuestion.** Embeddings
  at 0.80-0.85 are not reliable enough for silent merges. Two
  different bugs with similar symptoms is a common case.
- **Treating fingerprint match as truth.** Two different bugs can
  panic at the same file:line with the same message (e.g., a
  catch-all error helper) — verify with embedding similarity before
  collapsing.
- **Ignoring `pattern-recurrence` siblings.** When 7 sites match the
  same pattern, they should be 7 queue entries with the same
  `pattern_id`, not 1 collapsed entry. The fix may be the same
  structural change applied 7 times, but each site needs its own
  reproducer test.
- **Letting cost beat severity.** "S-cost fixes first" is for
  within-tier momentum; never reorder a critical bug after a low one
  because the low one is smaller.
