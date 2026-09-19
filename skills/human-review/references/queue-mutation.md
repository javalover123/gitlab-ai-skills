# Queue Mutation — atomic JSONL edits that survive crashes

This reference covers the protocol for editing the queue files produced
by `iteratotron` and `bug-burndown`. The protocol matters because
mid-write corruption breaks the parent skill's Stop hook, which then
either blocks forever or approves prematurely. Neither's a good
failure mode.

## The two queue shapes

### iteratotron — `scope_queue.jsonl`

Located at `.iteratotron/<session-id>/scope_queue.jsonl`. Each line is
one JSON object with at least these fields:

```json
{
  "scope_id":          "<hash of kind + path>",
  "kind":              "cargo_crate|python_package|feature_area|...",
  "path":              "<path>",
  "linked_artefacts":  ["FR-12", "ADR-005", "TM-AUTH-003"],
  "priority":          "P0|P1|P2|P3",
  "status":            "queued|in_flight|complete|...|needs_human|...",
  "attempt_count":     0,
  "blocks":            ["<scope_id>", ...],
  "blocked_by":        ["<scope_id>", ...],
  "needs_all_aboard":  false,
  "last_error":        ""
}
```

### bug-burndown — `queue.jsonl`

Located at `.bug-burndown/<session-id>/queue.jsonl`. Each line is one
JSON object with at least these fields:

```json
{
  "bug_id":            "BUG-NNNN",
  "kind":              "panic|test_failure|spec_drift|...",
  "severity":          "critical|high|medium|low",
  "sources":           ["logs", "tests", "issues"],
  "fingerprint":       "<hash>",
  "status":            "queued|in_flight|fixed|...|needs_human|...",
  "attempt_count":     0,
  "blocks":            ["<bug_id>", ...],
  "blocked_by":        ["<bug_id>", ...],
  "priority_rank":     0,
  "priority_reasons":  ["<reason>", ...]
}
```

The shapes differ in the ID field and the priority encoding, but both
have `status` and both are JSONL.

### harness-spawned bug-burndown sessions

A `harness-builder` runtime harness drives its BURN DOWN phase by
launching a **fresh `bug-burndown` session per iteration**. These sessions
use the identical `queue.jsonl` shape above and live at
`.bug-burndown/<id>/queue.jsonl`, but they are distinguished by their
`manifest.yaml`:

```yaml
session_id: 20260601-165802-e6887c0e
origin: <toolname>-harness
log_files:
  - .harness/iter-003/server.log
```

Two consequences for mutation:

1. **`.bug-burndown/CURRENT` does not point at them.** The collector finds
   them via `--all-sessions` (default) or `--scan-harness` (origin filter),
   not via CURRENT. The mutation protocol is otherwise unchanged — the
   `queue_path` the collector emits is the absolute path to that session's
   own `queue.jsonl`.
2. **Flipping the status unblocks the harness loop.** A `needs_human` item
   is terminal `WorkRemaining` for the harness's global fixpoint. Mutating
   it to `queued` or `re-evaluate` is exactly what lets the next harness
   round's burndown bridge re-dispatch the item so the loop can converge.
   Write the decision record under the harness session's *own*
   `human_decisions/` dir so the collector's skip-if-decided check sees it
   on the next drain.

The `update-queue-status.py` script is path-agnostic — pass the harness
session's `queue.jsonl` and it mutates identically to an interactive one.

## The atomic rewrite protocol

Direct `Edit` on a JSONL file is unsafe — the file's line-oriented and
a partial write between lines leaves the file half-mutated. Use this
sequence:

1. **Read** all lines into memory (parse each as JSON; preserve blank lines).
2. **Find** the entry by ID (matching `scope_id` or `bug_id` or `id`).
3. **Validate** the current status is in the human-review-eligible set (`needs_human`, `requires_human_review`, `blocked`). Refuse on protected statuses (`complete`, `fixed`, `introduced_regression`).
4. **Mutate** the entry: set new status, store `prior_status`, attach `human_decision` dict.
5. **Write** to a temp file in the same directory (`tempfile.mkstemp(dir=path.parent)`).
6. **Fsync** the temp file.
7. **Rename** the temp file over the original (`os.replace`).
8. **Keep** a `.bak` copy of the original next to it for manual recovery.

The `update-queue-status.py` script implements this protocol. Use it.

### Why same-directory temp files

Cross-filesystem renames aren't atomic on most platforms. The temp file
has to be in the same directory as the target so the `os.replace` call
hits the same filesystem.

### Why JSON `sort_keys=True`

The parent skill's reconciler reads entries field-by-field; consistent
field ordering means diffs in `.bak` files are reviewable. Don't skip
the sort.

## The `human_decision` field

When the script mutates an entry, it attaches:

```json
{
  "human_decision": {
    "decided_at":   "2026-05-17T14:23:51Z",
    "record_path":  "/abs/path/to/decision_record.md",
    "reason":       "Adopt ES256 per ADR-005",
    "transition":   "needs_human -> queued"
  },
  "prior_status": "needs_human"
}
```

These fields are additive — they don't replace any existing fields. The
parent skill's reconciler can ignore them (they're metadata), but they
make the decision auditable in the queue itself, not just in a
side-channel markdown file.

## Status transition matrix

The script enforces this transition matrix:

| Current status            | New status (allowed)                                             |
|---------------------------|------------------------------------------------------------------|
| `needs_human`             | `queued`, `re-evaluate`, `blocked`, `skipped`, `skipped_recently_complete`, `requires_human_review` |
| `requires_human_review`   | `queued`, `re-evaluate`, `blocked`, `skipped`, `skipped_recently_complete` |
| `blocked`                 | `queued`, `re-evaluate`, `skipped`                               |
| `complete`                | **refused** — protected                                          |
| `fixed`                   | **refused** — protected                                          |
| `introduced_regression`   | **refused** — protected                                          |
| anything else             | **refused** — out of scope                                       |

Why refuse on `complete` / `fixed` / `introduced_regression`? Those
statuses already encode an actionable terminal decision. Re-mutating
them via human-review would erase the parent skill's reconciliation
work and confuse the persistence log.

## Recovery semantics

If something goes wrong mid-update:

1. The original queue file is untouched until the final `os.replace` — partial writes can't corrupt it.
2. After `os.replace` succeeds, the `.bak` file holds the prior state. Manual recovery: `cp queue.jsonl.bak queue.jsonl`.
3. If the `.bak` file's missing, `git log` on the queue file (parents commit it after each phase) gives the prior state.

The skill never deletes `.bak` files automatically. They're cheap and
the audit trail's valuable. The user can `rm` them when they're sure
the mutation stuck.

## Multiple mutations per session

When the human resolves several items in one /human-review session, the
script's called once per item. Each invocation:

- Reads the (possibly already-mutated) queue file fresh
- Mutates one entry
- Writes a new `.bak` (overwriting the prior `.bak`)
- Replaces the queue file

If you want to preserve every intermediate state, copy each `.bak` to a
timestamped name before the next mutation. The skill doesn't do this
by default because most sessions are small enough that the most recent
`.bak` plus `git log` provides enough recovery.

## Concurrency

The protocol assumes no concurrent writer. The parent skill won't run
in parallel with `/human-review` (its Stop hook approved the stop, and
the user explicitly invoked the new skill), but if a stray subagent's
still in-flight, the rename could race.

Mitigation: before mutating, run `git status --short` and check no
`.bug-burndown/` or `.iteratotron/` paths are in the modify queue. If
they are, the session's still active; surface and stop.

## Sanity checks before each mutation

The script enforces these. Repeat them in prose review if you suspect
the script's misbehaving:

- The `--decision-record` path exists and is a regular file
- The `--new-status` is in `ALLOWED_NEW_STATUSES`
- The matched entry's current status is in `VALID_CURRENT_STATUSES`
- The queue file's a regular file (not a symlink to something weird)
- The queue's parent directory matches `.iteratotron/<id>/` or `.bug-burndown/<id>/` (harness-spawned sessions live under `.bug-burndown/<id>/` too, so they satisfy this check unchanged)
