# Reviewer Rubric

The adversarial reviewer is the most important component of the
harness. It decides which log lines are bugs and which are noise.
The rubric is the system prompt the LLM sees; the output format is
the strict JSON contract the parser depends on.

Get these wrong and the harness either ignores real bugs or files
hundreds of false positives.

The reviewer runs in **two passes**, each with its own rubric:

- **Pass 1 — failure-shaped lines** (WARN/ERROR/FATAL + known failure
  tokens). Failure rubric judges panics, DB write errors, RPC
  deadlines, retry storms. Cheap pre-filter forwards only the lines
  worth reviewing.
- **Pass 2 — silent-divergence lines** (every INFO/DEBUG/TRACE the
  failure pre-filter didn't claim). Lines are normalised to template
  fingerprints, deduplicated, and forwarded with `[seen Nx]`
  occurrence counts. Silent-divergence rubric judges "skipped"
  markers, empty fallbacks, unwired features, zero-count completion
  logs.

Pass 1 catches what regexes can catch. Pass 2 catches what only the
LLM can — INFO-level contract violations that look identical to
healthy operation.

## Anatomy of a rubric

Four concatenated strings forming the full prompt:

1. **System rubric** (per-pass) — what counts as accept/reject for
   THIS system. Pass 1 uses the failure rubric; pass 2 uses the
   silent-divergence rubric.
2. **Batch payload** — the log lines (pass 1) or deduplicated
   templates with `[seen Nx]` prefixes (pass 2), indexed.
3. **Output format** — the strict JSON contract, identical across
   passes.
4. **Empty array allowance** — `[]` if everything in the batch is
   acceptable.

Only the system rubric varies per target. The output format is one
template you keep verbatim across both passes — the harness parser
is shared.

## Template: pass 1 system rubric (failure-shaped)

```text
You are the adversarial reviewer for the <SYSTEM NAME> daemon log.
<ONE-PARAGRAPH SYSTEM SUMMARY — what the system does, what its agents /
components are, what success looks like.>

Your job: read a batch of log lines and decide which ones reveal a bug,
regression, or contract violation. Be strict — the system intent is:

  - <intent rule 1>
  - <intent rule 2>
  - <intent rule 3>
  - ...

ACCEPT — benign / expected:
  - <category 1 — INFO startups, lifecycle banners>
  - <category 2 — designed fallbacks that succeeded>
  - <category 3 — clean shutdown sequences>
  - <category 4 — explicit project-specific accepts>

REJECT — every other failure-shaped line. When in doubt, REJECT —
false positives become accepted findings during triage, but false
negatives hide real bugs.

Collapse duplicate lines that share the same defect into a single
verdict with `count` set to the multiplicity. Some lines may carry
a `"seen": N` field — the harness pre-dedups by fingerprint when
the failure-candidate pool is large (see "Adaptive cap" below), and
N is how many raw lines collapsed onto that exemplar. When `seen`
is present, treat the line as N occurrences and fold it into the
verdict's `count`.
```

The bullet lists target 4–7 items. Avoid exactly 3 or 5 — the voice
rules apply to rubric text too, since LLMs match the cadence.

The `seen` field is optional. When pass-1 input fits below the cap
the harness emits raw lines and no `seen` is present — the LLM can
read each line as exactly one occurrence. Above the cap, exemplars
carry `seen` and the rubric paragraph above is what tells the LLM
to weigh them appropriately. Keep the paragraph in lockstep with
the pass-1 builder; if you change the field name in code, change it
here too.

## Canonical pass 1 instance — ExampleApp

Reproduced verbatim from `the reference harness/src/reviewer.rs`:

```text
You are the adversarial reviewer for the ExampleApp security system's
daemon log. ExampleApp is a multi-agent supply-chain security platform
(orchestrator + 20 specialised agents talking over ZeroMQ, backed by
SurrealDB, exposed via tarpc and a web/TUI/GTK trio). The daemon's job
is to ingest a forge project, discover its artefacts, scan dependencies
for vulnerabilities, and persist results.

Your job: read a batch of log lines and decide which ones reveal a bug,
regression, or contract violation. Be strict — the system intent is:

  - agents make forward progress (no retry loops, no stuck workflows);
  - database writes succeed (no `Found NONE for field …`, no
    `Failed to create …`, no rejected schema mismatches);
  - RPC calls return within their deadlines (no `DeadlineExceeded`,
    no `the request exceeded its deadline`, no force-reconnect loops);
  - the bus delivers every message exactly once (no `rejected`,
    no `dropped`, no socket-mismatch warnings outside a planned restart);
  - no panics, no `unreachable!`, no `unwrap`/`expect` traceback;
  - clean error paths (errors must be informative AND recoverable;
    `Err(internal: …)` with no actionable detail is a defect).

ACCEPT — benign / expected. A "designed fallback" only qualifies when
ALL of:
  (a) the SAME batch contains a line showing the live operation
      SUCCEEDED on this run (cache miss → live query that returned
      REAL upstream data, retry that worked on a later attempt,
      cooldown followed by a normal completion);
  (b) the success line does NOT carry fallback / cached / seed
      wording (see EUPHEMISM WATCHLIST below);
  (c) the failure line is the only one of its class in the batch
      (a 5x-repeated "deferred to designed error path" is real, not
      transient).
Also accept startup banners, periodic ticks, clean shutdown
sequences (`Shutting down`, `Received SIGTERM`, `agent X stopped`).

REJECT — every other failure-shaped line. When in doubt, REJECT —
false positives become accepted findings during triage, but false
negatives hide real bugs.

EUPHEMISM WATCHLIST — phrasings system authors use to dress real
failures as designed paths. Each is a REJECT signal, not an ACCEPT
signal:

  - "designed error path", "designed fallback", "designed
    error-finding path" — the word "designed" does not certify
    success. It only certifies the failure branch was written.
  - "deferred to …" with no later success line in the batch.
  - "served from cached entries", "last-good cache entries remain
    authoritative", "from build-time seed", "bundled seed",
    "seed-fallback", "cache-fallback live-query succeeded" — these
    confirm the upstream did NOT deliver.
  - "Barbara will emit a structured finding" / "emitted error
    finding" / "emitted no-op finding" / "routing to designed
    error-finding path" — the daemon logging the failure does not
    fix the failure.
  - "Task completed … success=true" downstream of a fallback path
    — workflow self-stamps fire on fallback. The structural audit
    pass catches these; flag here too.
  - "upstream contract violation", `kind="*_error"`, `kind="*_violation"`
    — the daemon's own classifier confirming the failure is real.

The structural action-audit pass (mandatory in every runtime harness,
see SKILL.md § "Structural anti-rationalization pass") runs after
this reviewer and catches these patterns regardless of the LLM's
verdict. Leaning toward reject in the LLM pass costs only a triage
entry; accepting a euphemism hides a defect for a full iteration.

Collapse duplicate lines that share the same defect into a single
verdict with `count` set to the multiplicity.
```

Note how the "system intent" bullets reference specific log substrings
from the actual codebase. Generic rubrics ("no errors", "make sure it
works") produce generic verdicts. The whole point of an
LLM-as-reviewer is that it can read the daemon's own conventions and
apply them.

## Template: pass 2 system rubric (silent divergence)

Pass 2 is the bug-class catcher pass 1 can't see. The rubric is
phrased in the **positive** form (what the system PROMISES to do) so
the LLM compares observed INFO/DEBUG lines against intent rather
than against a denylist.

```text
You are the silent-divergence reviewer for the <SYSTEM NAME> daemon log.

You are reading deduplicated INFO/DEBUG/TRACE templates — the
"everything is fine" output of the daemon. Each line carries a
`[seen Nx]` prefix telling you how many times that template appeared
in this run. Dynamic spans (timestamps, UUIDs, record IDs, integers)
have already been replaced with `<ts>` / `<uuid>` / `<id>` / `<n>`
placeholders, so identical code paths collapse to one entry.

Most of these are benign. Your job is to flag templates that look
benign but actually represent the system silently diverging from its
documented intent.

<SYSTEM NAME>'s documented intent (positive form — what the system
PROMISES to deliver):

  - <agents/components that report completion must produce real output>
  - <every discovered input must flow through full pipeline before downstream consumers act>
  - <every cache namespace / scheduled task must have a wired action — not a placeholder>
  - <identifiers must be validated against known sources — lookup miss is a bug, not a skip>
  - <tools/subprocesses must execute or surface a useful diagnostic — empty errors are contract violations>
  - <workflows that report finished must have non-zero work product>

REJECT — silent-divergence phrasings (be alert to paraphrases):

  - "skipped", "no-op", "not wired", "unimplemented", "TODO",
    "stub", "placeholder", "not yet supported", "deferred",
    "would have X but …";
  - "fallback to empty / zero / null / default" with no upstream
    cause that justifies it;
  - "unknown product / slug / identifier" — lookup miss with no
    recovery path;
  - "minimal X" / "empty Y set" / "0 components found" coming from
    components that should have produced real data;
  - completion logs with 0-valued counters for workflows that ran
    against non-empty input;
  - "cache miss" with no follow-up live query.

ACCEPT — benign:

  - Designed cache misses followed by live-query success — only
    when the live query persisted REAL upstream data, not a
    fallback / seed / cached entry (see EUPHEMISM WATCHLIST);
  - Periodic ticks / heartbeats / lifecycle banners;
  - Operational counters with non-zero values consistent with the
    workload;
  - `rate-limit cooldown` / `retry with backoff` that you can see
    succeeded on a later line WITHOUT fallback wording.

EUPHEMISM WATCHLIST — INFO lines that dress failures in
healthy-looking words. Each is a REJECT signal:

  - "served from cached entries", "from build-time seed",
    "seed-fallback", "cache-fallback live-query succeeded",
    "last-good cache entries remain authoritative" — the upstream
    did NOT deliver; the system reached for the cache / seed.
  - "designed error path", "designed fallback", "designed
    error-finding path" — "designed" is not proof of success.
  - "Task completed … success=true" on actions whose only other
    evidence in the batch is failure-shaped — the flag fires on
    the fallback path too.
  - "emitted error finding" / "emitted no-op finding" /
    "Barbara will emit a structured finding" — error-reporting
    is not error-fixing.

When in doubt, REJECT. False positives surface in triage. False
negatives hide bugs the failure-shaped pre-filter already missed —
that's the whole reason this pass exists.

Use the `[seen Nx]` count as evidence of severity: a 1600x repetition
of a `skipped` marker is far more damaging than a one-off DEBUG line.
Carry that count through into the verdict's `count` field.
```

Same 4–7 bullet structure as pass 1. Same anti-3-or-5 rule applies.

## Canonical pass 2 instance — ExampleApp

Reproduced verbatim from `the reference harness/src/reviewer.rs::PASS2_SYSTEM`.
The "system intent" bullets reference specific ExampleApp agents and the
exact phrasings observed during failed iterations (`emitting minimal
SBOM — no upstream analysis`, `cache warm skipped — no scheduled
refresh action wired`, `unknown product slug 'centosstream'`). Look
at the file directly for the current version; updating it here would
just drift.

## Template fingerprinting (pass 2)

Pass 2 only works because the fingerprinter collapses thousands of
log lines emitted from the same code path to a single template.
Without dedup, 1600 `Failed to create vulnerability:<random_id>`
lines would burn 1600 LLM-context slots; with dedup they collapse to
one template with `count: 1600`.

Six lazy-compiled regexes do the normalisation, run in order:

```rust
static TIMESTAMP_RE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?").unwrap()
});
static UUID_RE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b").unwrap()
});
static RECORD_ID_RE: LazyLock<Regex> = LazyLock::new(|| {
    // SurrealDB-style `table:id` where the id half is 12–24 alphanumerics.
    Regex::new(r"\b([a-z_][a-z0-9_]*):([0-9a-z]{12,24})\b").unwrap()
});
static HEX_BLOB_RE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"\b[0-9a-fA-F]{16,}\b").unwrap()
});
static NUM_UNIT_RE: LazyLock<Regex> = LazyLock::new(|| {
    // "56ms", "1234x", "42KB". Needs its own pass because `\b\d+\b`
    // sees no word boundary between digits and the letter suffix.
    Regex::new(r"\b\d+[a-zA-Z]{1,4}\b").unwrap()
});
static NUM_RE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"\b\d+\b").unwrap()
});

pub(crate) fn fingerprint_template(line: &str) -> String {
    let s = TIMESTAMP_RE.replace_all(line, "<ts>");
    let s = UUID_RE.replace_all(&s, "<uuid>");
    let s = RECORD_ID_RE.replace_all(&s, "$1:<id>");
    let s = HEX_BLOB_RE.replace_all(&s, "<hex>");
    let s = NUM_UNIT_RE.replace_all(&s, "<n>");
    let s = NUM_RE.replace_all(&s, "<n>");
    s.into_owned()
}
```

**What gets normalised**:
- ISO 8601 timestamps → `<ts>`
- UUIDs → `<uuid>`
- SurrealDB-style record IDs (`vulnerability:cy6y02l8balyvc4kroyl`) → `<table>:<id>`
- Hex blobs of 16+ chars → `<hex>`
- Number-with-unit suffixes (`56ms`, `42KB`) → `<n>`
- Bare integers → `<n>`

**What stays**: module paths, prose, agent names, structural words —
exactly the signal the LLM needs to recognise what it's looking at.

**Order matters**: `RECORD_ID_RE` runs before `NUM_RE` so the digits
inside record IDs (`cy6y02l8...`) don't get partially substituted.
`NUM_UNIT_RE` runs before `NUM_RE` so `56ms` becomes one `<n>` token
rather than `<n>ms`.

**Cap the unique-template count** at ~600 to bound LLM cost. Real
ingest runs produce 100–500 templates after dedup; the cap fires
only on pathologically diverse logs and the truncation is logged so
the operator can investigate.

```rust
const MAX_PASS2_TEMPLATES: usize = 600;
```

Truncate to most-frequent templates (sort by occurrence count
descending, take top N) — those carry the strongest signal.

## Template: output format (verbatim across systems)

```text
Output rules — STRICT:

1. Emit a single JSON array. Nothing before, nothing after. No
   markdown fences, no commentary.
2. Each element is an object with the keys:
     fingerprint  (string, short stable signature like
                   "sucrose-create-vulnerability-artifact-NONE")
     verdict      ("accept" or "reject")
     kind         (one of: panic, db-write-failure, rpc-deadline,
                   retry-storm, data-loss, state-corruption,
                   cascade-failure, unsound-recovery,
                   silent-divergence, unimplemented-feature,
                   contract-violation, unknown)
     severity     ("critical", "high", "medium", "low")
     reason       (one sentence — what's wrong and why it violates
                   system intent)
     count        (integer ≥ 1 — number of lines this verdict covers)
     line         (one representative truncated line, ≤500 chars)
3. Only include rejected verdicts in the array. Accepted lines are
   dropped — the harness only needs the rejection list.
4. If the entire batch is acceptable, emit `[]`.
5. Never invent log lines that weren't in the batch.
```

Rule 3 is load-bearing: the harness drops accepts at parse time, so
having the LLM filter at output time keeps the round-trip cheap. Rule
5 stops hallucinated fingerprints landing in the bug-burndown queue.

The `kind` enum is fixed. If you want to add new categories, update
the enum here AND in `bug-burndown`'s findings schema so the queue
entries don't fail validation downstream.

## build_prompt — Rust implementation

```rust
fn build_prompt(lines: &[&String]) -> String {
    let mut p = String::new();
    p.push_str(REVIEWER_SYSTEM);
    p.push_str("\n\nHere are the log lines to judge — one per line, prefixed \
                with its 1-based index in this batch. Truncated to 500 chars each.\n\n");
    p.push_str("```\n");
    for (i, line) in lines.iter().enumerate() {
        let mut truncated: String = line.chars().take(500).collect();
        if line.chars().count() > 500 {
            truncated.push_str(" …<truncated>");
        }
        p.push_str(&format!("{:>4}: {}\n", i + 1, truncated));
    }
    p.push_str("```\n\n");
    p.push_str(VERDICT_FORMAT);
    p
}
```

Three pieces, fenced payload, indexed lines. The index isn't strictly
needed for the JSON output but it lets the LLM cite specific lines in
its `reason` field, which makes debugging much easier when a verdict
seems wrong.

## parse_verdicts — Rust implementation

The LLM is asked to emit a single JSON array with nothing around it.
In practice it sometimes wraps the output in markdown fences or adds a
sentence of prose. Be lenient — but **don't write a string-blind
bracket-depth walker**: log lines that end up in the verdict's `line`
field routinely contain literal `[` / `]` (e.g. `WARN [module]: ...`),
and a naive counter trips on the bracket inside the string before
reaching the array's actual end. We learned this the hard way; see
gotchas.md § "String-blind JSON parsing".

Use `serde_json::Deserializer` instead. It parses one JSON value
(the array) with full string + escape awareness and stops there;
trailing markdown / prose after the value is silently ignored.

```rust
fn parse_verdicts(raw: &str) -> Result<Vec<Verdict>> {
    let json_start = raw.find('[').ok_or_else(|| {
        anyhow!("reviewer output had no JSON array. raw output:\n{}",
                raw.chars().take(2000).collect::<String>())
    })?;
    let slice = &raw[json_start..];
    let mut de = serde_json::Deserializer::from_str(slice);
    Vec::<Verdict>::deserialize(&mut de).with_context(|| {
        format!(
            "parse reviewer JSON. slice (first 2000 chars):\n{}",
            slice.chars().take(2000).collect::<String>()
        )
    })
}
```

Mandatory regression tests cover brackets-inside-strings, escaped-
quotes-inside-strings, and trailing-text-after-array — write them
once and the parser stays honest as the rubric evolves.

`Deserializer` handles *valid* JSON wrapped in prose. It does **not**
rescue JSON the model emitted that is invalid by the spec — a raw
newline inside a `reason`, a verbatim `\d` regex, a Windows path. Those
must be repaired by a **recovery ladder** before you drop the batch
(dropping a batch is a reviewer outage → `WorkRemaining`, never zero
rejects). On first decode error, run cumulative string-aware cleanup
passes and re-decode after each: strip-stray-escapes-outside-strings →
escape-control-chars-inside-strings → escape-bad-backslash-escapes-
inside-strings. Full pattern, the Go reference implementation, and the
required tests (including the 2026-06-16 raw-newline incident): see
gotchas.md § "String-blind JSON parsing → …genuinely-invalid JSON".

## Sync invariant — pre-filter and rubric must agree

The `worth_reviewing` function in `reviewer.rs` is the cheap pre-filter
that decides which lines even reach the LLM. The rubric is what the
LLM does with those lines. If the pre-filter drops a class of lines
that the rubric would have rejected, you get silent false negatives —
the bug never reaches the LLM, so it never reaches the queue.

Rule: every substring the rubric reasons about must also be in the
`SIGNALS` constant in `worth_reviewing`. When you add a new "this is a
defect" line to the rubric, add the substring to the pre-filter at
the same time. Keep both in `reviewer.rs`. The unit tests around
`worth_reviewing` guard the seam.

## Adaptive cap on pass 1 (the 185k-candidate failure)

Pass 2 has always capped templates at ~600. Pass 1 used to be
uncapped — it sent every WARN/ERROR line through the LLM, one batch
at a time. That worked fine until a single failure mode (a postgres
connection-pool exhaustion cascade in vulnmapper) emitted 185 000
failure-shaped lines in one iteration. At 150 lines per batch the
reviewer would have taken ~1240 claude calls — most of a day —
before a single `/bug-burndown` invocation could start. The
candidate pool stayed pinned because no bugs were getting burned
down.

The fix is an **adaptive cap** mirroring pass 2's design. Pass 1
batches are bounded by two numbers:

- `MaxBatchLines` (default 300) — failure-shaped lines per LLM call.
  Bigger than pass 2 (which sends one line per template) because
  failure lines are usually short and have higher signal density.
- `MaxBatches` (default 100) — ceiling on how many LLM calls one
  iteration's pass 1 is allowed to make. 300 × 100 = 30 000
  exemplars max.

When the raw failure-candidate count is at or below the ceiling, no
dedup happens and full-fidelity raw lines are reviewed — same as
the pre-cap behavior. Above the ceiling the harness fingerprints
the failures, keeps the top-N most-frequent exemplars (sorted
desc), and threads the per-exemplar count through to the prompt as
`"seen": N` so the LLM can weight by occurrence.

The result is **adaptive fidelity**: a dirty pool gets compressed
to fit; a clean pool retains every line. As `/bug-burndown` fixes
the dominant defects across iterations, raw candidate counts drop
below the cap and dedup stops engaging — review fidelity rises
automatically as the burndown progresses.

### Reference implementation (Go)

```go
// CapAndDedupFailures applies an adaptive cap to pass-1 input. When raw
// record count exceeds maxBatches*maxBatchLines, records are grouped by
// FingerprintTemplate, the top-N most-frequent exemplars are kept, and
// a parallel counts slice is returned so the prompt can carry
// occurrence count into the LLM's reasoning. Below the ceiling the
// records are returned as-is and counts is nil — full fidelity, no
// behavior change.
func CapAndDedupFailures(records []Record, maxBatches, maxBatchLines int) ([]Record, []int64) {
    if maxBatches <= 0 || maxBatchLines <= 0 {
        return records, nil
    }
    ceiling := maxBatches * maxBatchLines
    if len(records) <= ceiling {
        return records, nil
    }
    type grp struct {
        exemplar Record
        count    int64
    }
    groups := map[string]*grp{}
    order := []string{}
    for _, r := range records {
        fp := FingerprintTemplate(r.Msg)
        if g, ok := groups[fp]; ok {
            g.count++
            continue
        }
        groups[fp] = &grp{exemplar: r, count: 1}
        order = append(order, fp)
    }
    sort.SliceStable(order, func(i, j int) bool {
        if groups[order[i]].count != groups[order[j]].count {
            return groups[order[i]].count > groups[order[j]].count
        }
        return order[i] < order[j]
    })
    if len(order) > ceiling {
        order = order[:ceiling]
    }
    outRecs := make([]Record, len(order))
    outCounts := make([]int64, len(order))
    for i, fp := range order {
        outRecs[i] = groups[fp].exemplar
        outCounts[i] = groups[fp].count
    }
    return outRecs, outCounts
}
```

The fingerprint function is the same `FingerprintTemplate` pass 2
uses, so a failure-shaped line and its silent-divergence shadow
collapse to the same template if they're really the same code
path. Use one fingerprinter, not two.

### Expose the knobs

Surface both as CLI flags so an operator can dial the trade-off
without recompiling:

```go
harnessCmd.Flags().IntVar(&maxBatchLines, "reviewer-batch-lines", 300, ...)
harnessCmd.Flags().IntVar(&maxBatches, "reviewer-max-batches", 100, ...)
```

Set `--reviewer-max-batches=0` to disable the cap. Don't recommend
this — uncapped runs are how the 185k-candidate failure mode goes
unnoticed for a full work day. Capping is the right default.

## Other tuning notes

- **MaxBatchLines = 300** is the new default. The old 150 was a
  pre-adaptive-cap choice that wasted startup tokens per call on
  small batches; 300 doubles per-call throughput and Haiku's context
  window swallows it comfortably (300 × ~700 chars/line ≈ 210 KB
  prompt body, well under Haiku's limit).
- **One batch ≈ 20-60 seconds wall time** on Haiku. Show per-batch
  progress so the operator can tell the harness is working.
- **Dedupe by fingerprint** after the LLM returns too, summing
  counts. A retry storm of 1600 identical errors collapses to one
  queue entry with `count: 1600`. The pre-LLM dedup (above) AND
  the post-LLM merge work together: pre-LLM bounds wall-time;
  post-LLM bounds the queue.
- **Cap per-line length at 500 chars** before sending to the LLM.
  Long log lines (full backtraces, JSON dumps) eat context and add
  no signal — the first 500 chars carry the diagnostic.
- **If the LLM consistently over-rejects** (everything looks like a
  bug): tighten the ACCEPT list with more specific designed-fallback
  examples. The rubric is too cautious.
- **If the LLM consistently under-rejects** (real bugs slip through):
  add the specific log substring to the "system intent" bullets and
  to the `SIGNALS` pre-filter constant.

## Meta-use: reviewing generated harnesses for sandbox compliance

The batch-reviewer architecture works for more than daemon log output.
When harness-builder scaffolds a new harness, you can run the same
pass-1 shape against the generated source files — or a log of spawn
commands emitted during a run — to catch sandbox violations before the
harness ever touches production.

Every `claude` spawn site in a generated harness must go through
`nono run`. A bare `claude -p` invocation is a hard failure — bypass
without the boundary is unsafe by construction regardless of what
permission mode it uses. `tests/eval.yaml` catches this statically
with `contains`/`not-contains` assertions. The reviewer clause below
is a second enforcement layer that fires dynamically and covers code
paths the eval can't reach (exploratory generation, post-edit drift).

### Adding the sandbox clause to pass 1

When the input is generated harness source code rather than daemon log
lines, add this block to the `REJECT` section of your pass-1 rubric:

```text
REJECT — sandbox violation, hard failure, no exception:
  - Any `claude` invocation whose argv does not begin with
    `nono run --silent`. A bare `claude -p` is a hard failure
    regardless of what permission mode it uses.
  - Any spawn site setting `permission_mode = bypassPermissions`
    without a `nono run` wrapper in the same argv. Bypass without
    the boundary is unsafe.
  - `--add-dir` and nono `--allow` lists that differ in content —
    they must derive from the same source variable; diverging lists
    mean the filesystem sandbox doesn't cover what Claude reads.
  - `--allow-unsandboxed` in a generated CLI declaration without a
    matching loud-banner fallback that forces `permission_mode` back
    to `acceptEdits`.
```

And add to the `ACCEPT` section:

```text
ACCEPT — sandbox presence confirmed:
  - Spawn sites where argv[0] = "nono", argv[1] = "run" and
    `--permission-mode bypassPermissions` appears after the `--`
    separator.
  - Preflight paths where `nono --version` fails AND
    `permission_mode` is set to `acceptEdits` (not
    `bypassPermissions`) — this is the correct unsandboxed fallback.
```

The same invariant in eval form — these belong in `tests/eval.yaml`
alongside the rubric, not instead of it:

```yaml
- type: not-contains
  value: "claude -p"   # bare invocation = fail; must be nono-wrapped
- type: contains
  value: "nono run"
- type: contains
  value: "--permission-mode bypassPermissions"
```

See `references/nono-integration.md` for the full sandbox contract and
the `--add-dir` ↔ `--allow` invariant. The pass-1 clause above is
intentionally strict — a reviewer that flags a correct scaffold as
wrong is a calibration problem you fix by expanding the ACCEPT list.
A reviewer that misses an unwrapped spawn site is a security gap.
