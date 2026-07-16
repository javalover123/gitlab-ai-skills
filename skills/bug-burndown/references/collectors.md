# Collector specifications

This reference is loaded on demand from the `bug-burndown` skill during
Phase 2 (collect). It specifies the extraction protocol for each of the
six input sources and the canonical raw-finding schema that all
collectors must emit.

## The raw finding schema

Every collector appends one or more JSON objects to
`${session_dir}/findings/<source>.jsonl`. Each object MUST contain:

```json
{
  "source": "logs | tests | live | issues | code-review | spec-drift",
  "source_ref": "path or URL or test name identifying the observation",
  "observed_at": "ISO-8601 timestamp of the observation, if known",
  "raw_text": "verbatim extracted text (truncate if >8KB; cite full path)",
  "structured": { ... },
  "candidate_kind": "bug | regression | flaky | spec-drift | pattern-recurrence | crash | unknown"
}
```

The `structured` block varies per source — see each collector below.
Classification, deduplication, and prioritisation happen in Phases 3-5;
collectors should over-extract rather than under-extract, since false
positives are cheap (dedup will collapse them) but missed bugs are not.

---

## 2a. Log collector

**Inputs:** paths supplied in arguments, or default search across:
- `./logs/*.{json,log,txt}`
- `./target/test-logs/`
- `./ci-logs/`
- `./test-results/`
- `./.bug-burndown/*/reports/` (recent burndown reports themselves)

**JSON tracing extraction:**

```bash
# Find all error-level events
jq -c 'select(.level == "ERROR" or .level == "FATAL")' "$log_file" >> /tmp/json_errors.jsonl

# Find span exits that carried an error field
jq -c 'select(.fields.error != null and .span != null)' "$log_file" >> /tmp/json_errors.jsonl

# Find spans that opened but never closed within the file (potential bugs)
jq -c '
  group_by(.span.span_id)
  | map(select(length == 1 and .[0].span.name != null))
  | .[]
  | .[0]
' "$log_file" >> /tmp/json_orphan_spans.jsonl
```

For each extracted event, the `structured` block becomes:

```json
{
  "error_class": "<event.fields.error.kind or inferred>",
  "error_message": "<event.fields.error.message or event.fields.message>",
  "target": "<event.target>",
  "trace_id": "<event.span.trace_id>",
  "span_chain": ["<outer>", "<inner>", "..."],
  "fields": { /* relevant fields, no secrets */ }
}
```

`candidate_kind`:
- Panic / `panic_hook` event → `crash`
- Error variant containing `regression` → `regression`
- `flaky` or `intermittent` in error message → `flaky`
- Otherwise → `bug`

**Plaintext log extraction:**

```bash
rg --json -e '^(thread.*panicked|FATAL|ERROR)' "$log_file" \
   | jq -c 'select(.type == "match")' \
   >> /tmp/text_errors.jsonl

# Capture the panic location + frames
rg -A 30 'thread.*panicked at' "$log_file"
```

For panics specifically, extract:
- Thread name (often the failing test).
- Panic message.
- `note: run with RUST_BACKTRACE=1` indicator (if absent, the next
  collector pass should re-run with backtrace enabled).
- Stack frames if present.

**Secret hygiene.** Logs may contain tokens, paths, env vars. Before
appending to findings, redact via:

```bash
# crude but effective for common patterns
sed -E '
  s/(token=)[A-Za-z0-9_-]+/\1[REDACTED]/g
  s/(authorization: bearer )[A-Za-z0-9._-]+/\1[REDACTED]/gi
  s/(ghp_|gho_|glpat-)[A-Za-z0-9_-]+/[REDACTED]/g
'
```

The collector's job is extraction, not analysis. Save the extracts;
Phase 3 will classify.

---

## 2b. Test report collector

**Cargo (Rust):**

```bash
# Run with structured output
cargo nextest run --message-format libtest-json 2>&1 \
    | tee "${session_dir}/findings/test-cargo-raw.json" \
    | jq -c 'select(.event == "failed" or .event == "ok" and .status == "FAILED")'
```

For each failure:

```json
{
  "structured": {
    "test_name": "<crate::module::test_name>",
    "test_kind": "unit | integration | doc | bench",
    "failure_message": "<stdout/stderr of the failing test>",
    "failure_location": "<file:line if captured>",
    "duration_ms": 0,
    "panic_payload": "<extracted if present>"
  }
}
```

**JUnit XML:**

```bash
# Parse JUnit XML with xmlstarlet or python
python3 -c '
import xml.etree.ElementTree as ET, json, sys
for p in sys.argv[1:]:
    tree = ET.parse(p)
    for tc in tree.iter("testcase"):
        for fail in tc.findall("failure"):
            print(json.dumps({
                "source": "tests",
                "source_ref": p + "::" + tc.attrib["name"],
                "structured": {
                    "test_name": tc.attrib["name"],
                    "classname": tc.attrib.get("classname", ""),
                    "failure_message": fail.attrib.get("message", ""),
                    "failure_type": fail.attrib.get("type", ""),
                    "failure_detail": fail.text or ""
                },
                "candidate_kind": "bug"
            }))
' "$@" >> "${session_dir}/findings/tests.jsonl"
```

**pytest JSON:**

```bash
pytest --json-report --json-report-file="${session_dir}/findings/pytest-raw.json"
jq -c '
  .tests[]
  | select(.outcome == "failed" or .outcome == "error")
  | {
      source: "tests",
      source_ref: .nodeid,
      structured: {
        test_name: .nodeid,
        outcome: .outcome,
        failure_message: (.call.longrepr // .setup.longrepr // ""),
        duration_s: .duration
      },
      candidate_kind: "bug"
    }
' "${session_dir}/findings/pytest-raw.json" \
  >> "${session_dir}/findings/tests.jsonl"
```

**Flaky detection.** If the same test appears in multiple test runs
with inconsistent outcomes (failed in one, passed in another), tag
`candidate_kind: flaky`. Flakes are real bugs but distinct from
deterministic failures; the bugfix skill handles them differently
(Layer 4 stateful proptest is usually the right reproducer).

---

## 2c. Live harness collector

The live harness collector is opt-in (requires explicit `live:<cmd>` in
arguments) because it runs code, costs time, and may produce false
positives from environmental flakiness. Budget enforced by
`harness_budget` in manifest (default 20 min).

**Recommended invocations:**

```bash
# Standard suite
timeout 1200 cargo nextest run --message-format libtest-json --workspace \
    > "${session_dir}/findings/live-nextest.json" 2>&1

# Property tests with extended cases
timeout 600 cargo test --features proptest --release -- proptest \
    --test-threads=1 --nocapture \
    > "${session_dir}/findings/live-proptest.log" 2>&1

# Fuzzing (short burst per target)
for target in $(cargo +nightly fuzz list); do
    timeout 120 cargo +nightly fuzz run "$target" -- -max_total_time=100
done

# Concurrency models (loom)
RUSTFLAGS="--cfg loom" timeout 600 \
    cargo test --release --test loom_tests \
    > "${session_dir}/findings/live-loom.log" 2>&1
```

Parse outputs the same way as 2b. Findings from fuzz/property tests
should carry an additional `structured.minimised_input` field if the
runner produced a minimal counterexample.

**Important:** the live collector runs on the **baseline integration
branch** (clean, before any fix worktrees exist). It must not run
concurrently with the dispatcher's worktrees, or you'll get
non-deterministic findings.

---

## 2d. Issue/ticket collector

### Step 0: detect the upstream host

```bash
upstream_url="$(git remote get-url origin 2>/dev/null || git remote get-url upstream 2>/dev/null || echo '')"
if echo "$upstream_url" | grep -q "github\.com"; then
    issue_host="github"
else
    # Treat anything else as GitLab — covers gitlab.com and self-hosted instances.
    # Self-hosted GitLab: set GITLAB_HOST in the environment if needed.
    issue_host="gitlab"
fi
```

Record `issue_host` in `manifest.yaml`. Never use `gh` for a GitLab remote or
vice versa — wrong credentials, wrong API shape, wrong issue IDs.

---

### GitLab remote (default)

Work through these in priority order, stopping at the first that succeeds:

**Priority 1 — GitLab MCP (preferred)**

When the GitLab MCP server is connected, use its tools directly. They give
richer context than the API alone: linked MRs, iteration membership, related
issues, milestone, health status. Call the MCP list-issues tool with:

```
project: <inferred from git remote URL>
state: opened
labels: ["bug"]
updated_after: <30 days ago>
```

Map each result into the standard findings envelope before appending to
`${session_dir}/findings/issues.jsonl`.

**Priority 2 — `glab` CLI**

If the MCP isn't connected, `glab` is the next best option. It handles
both gitlab.com and self-hosted instances via `GITLAB_HOST`:

```bash
glab issue list \
    --label bug \
    --state opened \
    --per-page 100 \
    --output json \
  | jq -c '.[]
    | {
        source: "issues",
        source_ref: .web_url,
        observed_at: .updated_at,
        raw_text: .description,
        structured: {
          ticket_id: .iid,
          title: .title,
          labels: .labels,
          author: .author.username,
          url: .web_url,
          confidence_hint: "user_reported"
        },
        candidate_kind: "bug"
      }
  ' >> "${session_dir}/findings/issues.jsonl"
```

**Priority 3 — GitLab REST API (last resort)**

Use only when neither MCP nor `glab` is available. Requires `GITLAB_TOKEN`
and `GITLAB_PROJECT_ID` (or path-encoded project path):

```bash
project_id="${GITLAB_PROJECT_ID:-$(git remote get-url origin | sed 's|.*gitlab[^/]*/||;s|\.git$||;s|/|%2F|g')}"
gitlab_host="${GITLAB_HOST:-gitlab.com}"

curl -sH "PRIVATE-TOKEN: $GITLAB_TOKEN" \
    "https://${gitlab_host}/api/v4/projects/${project_id}/issues?state=opened&labels=bug&per_page=100&updated_after=$(date -Iseconds -d '30 days ago')" \
  | jq -c '
      .[]
      | {
          source: "issues",
          source_ref: .web_url,
          observed_at: .updated_at,
          raw_text: .description,
          structured: {
            ticket_id: .iid,
            title: .title,
            labels: .labels,
            author: .author.username,
            url: .web_url,
            confidence_hint: "user_reported"
          },
          candidate_kind: "bug"
        }
    ' >> "${session_dir}/findings/issues.jsonl"
```

If none of the three succeed, disable the issues source for this session and
record it in `manifest.yaml` — don't proceed silently.

---

### GitHub remote (only when `issue_host == "github"`)

Use the `gh` CLI. It must be authenticated (`gh auth status`); if not,
disable the source and record it in `manifest.yaml`.

```bash
gh issue list --label bug --state open --limit 200 \
    --json number,title,body,labels,url,updatedAt \
  | jq -c '.[]
    | {
        source: "issues",
        source_ref: .url,
        observed_at: .updatedAt,
        raw_text: .body,
        structured: {
          ticket_id: .number,
          title: .title,
          labels: [.labels[].name],
          url: .url,
          confidence_hint: "user_reported"
        },
        candidate_kind: "bug"
      }
  ' >> "${session_dir}/findings/issues.jsonl"
```

**Sentry digests (optional):** if provided as a digest export, parse
the JSON envelope and extract each issue's title, event count, and
representative event payload. Sentry's `event count` becomes a hint for
blast radius in Phase 3.

**Ticket triage hint.** Issues with `wontfix`, `duplicate`,
`works-as-designed`, or `needs-info` labels should be filtered out at
collection time — they'll skew dedup and waste subagent time. Record
them in `${session_dir}/findings/issues-skipped.jsonl` for visibility.

---

## 2e. Code-review collector (pattern recurrence)

This collector reads the persistent bugfix log and searches the
codebase for sites that match patterns from prior fixes. It is the
mechanism that turns "we fixed this once" into "we make sure it stays
fixed everywhere".

**Protocol:**

1. Load every `.bugfix/log/*.md` entry whose frontmatter contains
   `pattern_id: <id>` AND `pattern_signature: <regex_or_ast_pattern>`.
2. For each pattern, search the current codebase:

   ```bash
   for entry in .bugfix/log/*.md; do
       pattern_id=$(yq '.pattern_id' "$entry" 2>/dev/null)
       signature=$(yq '.pattern_signature' "$entry" 2>/dev/null)
       [[ -z "$signature" || "$signature" == "null" ]] && continue

       rg --json --pcre2 "$signature" \
         | jq -c --arg pid "$pattern_id" --arg ref "$entry" '
             select(.type == "match")
             | {
                 source: "code-review",
                 source_ref: (.data.path.text + ":" + (.data.line_number|tostring)),
                 raw_text: .data.lines.text,
                 structured: {
                   pattern_id: $pid,
                   prior_fix_log: $ref,
                   file: .data.path.text,
                   line: .data.line_number,
                   match_text: .data.submatches[0].match.text
                 },
                 candidate_kind: "pattern-recurrence"
               }
           ' \
         >> "${session_dir}/findings/code-review.jsonl"
   done
   ```

3. The bugfix skill subagent receiving a `pattern-recurrence` finding
   gets the prior log entry in its prompt, so it knows the structural
   fix applied last time and can adapt it.

**Pattern signature formats supported:**

- **Regex (`pattern_signature_kind: regex`):** PCRE2; matched
  line-by-line. Best for syntactic patterns like
  `\.unwrap_or_default\(\)\s*//.*swallow`.
- **AST pattern (`pattern_signature_kind: ast`):** Tree-sitter query
  or `ast-grep` pattern. Best for structural patterns like "any
  `match` expression missing the error arm". When the codebase has
  `ast-grep` available:

  ```bash
  ast-grep --pattern "$signature" --lang rust --json \
    >> "${session_dir}/findings/code-review-ast.jsonl"
  ```

- **Semantic (`pattern_signature_kind: semantic`):** for patterns too
  fuzzy for regex/AST, store an embedding of the buggy code snippet in
  the log entry and search via cosine similarity in
  `references/recurrence-detection.md`. Use sparingly — false positive
  rates rise quickly.

---

## 2f. Spec/ADR/threat-model drift collector

The most computationally expensive collector. Its job is to surface
places where the *implementation* contradicts an *authoritative
artefact* (ADR, spec, threat model, user-story AC).

**Protocol:**

1. **Enumerate artefacts:**

   ```bash
   adrs=$(find docs/decisions docs/adr -name '*.md' 2>/dev/null)
   specs=$(find docs/specs features -name '*.md' -o -name '*.feature' 2>/dev/null)
   threats=$(find . -name 'THREATMODEL.md' -o -path 'docs/security/*.md' 2>/dev/null)
   stories=$(find docs/stories -name '*.md' 2>/dev/null)
   ```

2. **Extract invariants per artefact.** Each kind has a canonical
   location for the contract:
   - ADR: the "Decision Outcome" / "Decision" section, plus any
     explicit `MUST` / `SHOULD` statements.
   - Spec: `.feature` Scenarios (Given/When/Then) are executable
     invariants; ordinary Markdown specs need the MUST/SHALL/SHOULD
     statements parsed.
   - Threat model: STRIDE/LINDDUN table rows; trust boundary
     assertions.
   - Story: acceptance criteria, especially Gherkin scenarios.

3. **For each invariant, search the codebase for contradictions.**

   This is the hard part — invariants are in natural language, code
   isn't. The collector uses three escalating strategies:

   a. **Direct symbol search.** If the invariant mentions a specific
      function, type, or message, grep for its definition and check
      whether the implementation matches the contract textually.

   b. **Embedding-guided code search.** Embed each invariant; embed
      sliding windows of code (function-level granularity); cosine-
      similarity match → human-readable shortlist of "code that
      claims to implement this invariant".

   c. **Subagent delegation.** For complex invariants (multi-step
      protocols, security properties), delegate to a focused subagent
      that reads both the artefact section and the candidate
      implementation and reports whether they agree. The subagent's
      output is a structured finding with the artefact path:line and
      the implementation path:line.

   Strategy choice depends on artefact size and codebase size; for
   most invariants, (a) and (b) suffice. (c) is reserved for cases
   where (a) and (b) produce ambiguous results.

4. **Finding shape:**

   ```json
   {
     "source": "spec-drift",
     "source_ref": "<artefact-path>:<artefact-line>",
     "raw_text": "<the contract statement, verbatim>",
     "structured": {
       "artefact_kind": "adr | spec | threat-model | story",
       "artefact_path": "<path>",
       "artefact_id": "<ADR-0042 | STORY-187 | etc>",
       "invariant": "<the MUST/SHALL/SHOULD claim>",
       "candidate_violation_path": "<src/...:NN>",
       "violation_evidence": "<one-paragraph explanation>",
       "authoritative_source": "adr | spec | threat-model | story",
       "confidence": "high | medium | low"
     },
     "candidate_kind": "spec-drift"
   }
   ```

5. **For high-confidence drift,** Phase 3 will likely classify these as
   `severity: medium` by default, but threat-model violations get
   automatic escalation to `high` and security-relevant ones to
   `critical`.

**Performance note.** On a large codebase, full drift scanning can take
30+ minutes. Use the `spec-drift-budget` manifest field (default 15
min) and prefer to delegate to a focused subagent rather than running
inline. The skill checks `manifest.yaml`'s `spec_drift_subagent: true`
flag for this.

---

## 2g. Test-effectiveness collectors

The test-effectiveness lane is split into three sub-collectors. They
share a single input source: the harness-produced
`.test-effectiveness/baseline.json` (iter 1) and
`.test-effectiveness/iter-NNN/delta.json` (iter N ≥ 2). Full schema in
`harness-builder/references/runtime-test-effectiveness-baseline.md`.

### 2g.0 baseline detection

```bash
baseline=".test-effectiveness/baseline.json"
latest_iter_dir="$(ls -1d .test-effectiveness/iter-*/ 2>/dev/null | tail -1)"
latest_delta="${latest_iter_dir%/}/delta.json"
verdicts="${latest_iter_dir%/}/triage-verdict.json"

if [[ -f "$baseline" ]]; then
    echo "harness baseline present (sha: $(yq '.baseline_sha' .test-effectiveness/manifest.yaml))"
    harness_input=1
else
    echo "no harness baseline; running scoped scan"
    harness_input=0
fi
```

When `harness_input=1`, the three sub-collectors **read from disk only**.
When `harness_input=0`, they each run their tool natively, scoped to the
files changed since `git merge-base origin/main HEAD` (or, on a session
resume, since the prior `baseline_sha` in `manifest.yaml`).

Record the result in `manifest.yaml`:

```yaml
test_effectiveness:
  source: harness-baseline | scoped-scan
  baseline_sha: <sha>
  iteration: <NNN>          # null when scoped-scan
  verdict_file_present: true | false
```

### 2g.1 mutation-survivor collector

**Source of truth when harness baseline present:** read entries with
`kind: mutation-survivor` from `baseline.json` (iter 1) or
`iter-NNN/delta.json` (iter N ≥ 2). Filter by `class: appeared` and
`class: regressed` unless the session arguments include
`include-persisted`.

**Native scan when no baseline:**

```bash
# Rust — scoped to the diff
cargo mutants --in-diff <(git diff origin/main) --json \
    > "${session_dir}/findings/mutants-raw.json"

# Python
mutmut run --paths-to-mutate="$(git diff --name-only origin/main -- '*.py' | tr '\n' ',')" \
    --json > "${session_dir}/findings/mutants-raw.json"

# Go
gremlins unleash --output json ./... > "${session_dir}/findings/mutants-raw.json"

# Ruby
bundle exec mutant run --use rspec --json-dump "${session_dir}/findings/mutants-raw.json"
```

For each surviving mutant, emit:

```json
{
  "source": "test-effectiveness",
  "source_ref": "<file>:<line>",
  "raw_text": "<mutation_diff>",
  "structured": {
    "tool": "cargo-mutants",
    "file": "...",
    "fn": "...",
    "line": 142,
    "mutation_op": "replace == with !=",
    "linked_artefact": "<from baseline, when present>",
    "linked_status": "<from baseline>",
    "harness_verdict": "real-bug | test-gap | stub-implementation | null"
  },
  "candidate_kind": "test-gap"
}
```

The `harness_verdict` field is null when `verdict_file_present: false`.
When present, Phase 3 uses it to short-circuit classification:
`stub-implementation` lifts to P0 unconditionally; `dead-code` rewrites
the kind to `orphan-scaffolding`; `acceptable-debt` skips this session.

### 2g.2 CRAP-hotspot collector

**Source of truth when harness baseline present:** read entries with
`kind: crap-hotspot` from baseline/delta. Always include `class:
regressed` (the score got worse) plus `class: appeared` (a new hotspot
crossed CRAP > 30).

**Native scan when no baseline:**

```bash
# Rust (cargo-crap v0.2.0 — pin to avoid pre-1.0 surprises)
cargo install cargo-crap@0.2.0 --locked 2>&1 || crap_fallback=1
cargo llvm-cov --lcov --output-path lcov.info --workspace
if [[ -z "$crap_fallback" ]]; then
    cargo crap --lcov lcov.info --format json > "${session_dir}/findings/crap-raw.json"
else
    # hand-computed fallback: parse lcov + run cyclomatic via syn-cli or rust-code-analysis
    rust-code-analysis-cli -p . -m -O json > /tmp/cc.json
    python3 scripts/hand_crap.py /tmp/cc.json lcov.info \
        > "${session_dir}/findings/crap-raw.json"
fi

# Python — radon + coverage.py
radon cc --total-average --json . > /tmp/cc.json
coverage lcov -o lcov.info
python3 scripts/hand_crap.py /tmp/cc.json lcov.info > "${session_dir}/findings/crap-raw.json"

# Ruby — rubycritic (already produces CRAP-equivalent)
bundle exec rubycritic --format json --no-browser > "${session_dir}/findings/crap-raw.json"
```

For each CRAP > 30 entry, emit:

```json
{
  "source": "test-effectiveness",
  "source_ref": "<file>:<fn>",
  "structured": {
    "tool": "cargo-crap | rubycritic | hand-computed",
    "crap": 156.0,
    "complexity": 12,
    "coverage": 0.12,
    "linked_artefact": "<from baseline>",
    "linked_status": "<from baseline>",
    "harness_verdict": "<from triage-verdict.json>"
  },
  "candidate_kind": "dangerous-complexity"
}
```

Phase 3's severity rules: P1 base; lift to P0 when `linked_status:
implemented` (the doc-claimed-done lift in SKILL.md § Phase 3a.1).

### 2g.3 coverage-cliff collector

**Source of truth when harness baseline present:** read entries with
`kind: coverage-cliff` from baseline/delta. The harness already scored
threat-model proximity in the seed; respect it.

**Native scan when no baseline:** parse the workspace LCOV directly and
emit one entry per function with `<50%` line coverage on changed
files. Cheap and language-agnostic — every coverage tool can produce
LCOV.

For each cliff, emit:

```json
{
  "source": "test-effectiveness",
  "source_ref": "<file>:<fn>",
  "structured": {
    "tool": "llvm-cov | coverage.py | gocover | simplecov",
    "uncovered_lines": [88, 89, 91, 92],
    "module_coverage": 0.42,
    "linked_artefact": "<from baseline>",
    "linked_status": "<from baseline>",
    "near_threat_boundary": true,
    "harness_verdict": "<from triage-verdict.json>"
  },
  "candidate_kind": "untested-mitigation | untested-branch"
}
```

`candidate_kind` is `untested-mitigation` when `linked_artefact` is a
threat-model entry (TM-XXX-NNN), `untested-branch` otherwise. The first
case is always P0; the second starts P2 and lifts via the doc-claimed-done
rule.

### Cost-aware scan sequencing

When running native scans (no harness baseline), the three sub-collectors
are not equal in cost:

- **Coverage cliff** — cheap (parses existing LCOV). Run first.
- **CRAP hotspot** — cheap if `cargo-crap` is installed; the fallback's a
  few seconds longer. Run second.
- **Mutation survivor** — expensive (1–5 min on a typical diff). Run
  third, in parallel with Phase 2f's spec-drift subagent if both are
  enabled.

The cheap-first ordering means Phase 2 can produce a partial findings
file even when the mutation run times out — Phase 3 onward can proceed
on CRAP + coverage findings while mutation continues in the background.

## Cross-collector hygiene

After all collectors finish:

1. **Concatenate** all findings into `${session_dir}/findings/all.jsonl`.
2. **Validate** each record against the raw-finding schema; reject
   malformed entries with a warning in `report.md`.
3. **Count by source** and write to `manifest.yaml`:

   ```yaml
   collection_summary:
     logs: 134
     tests: 23
     live: 3
     issues: 8
     code-review: 11
     spec-drift: 4
     mutation-survivor: 17
     crap-hotspot: 9
     coverage-cliff: 22
     total: 231
   collection_duration_s: 421
   ```

4. **Emit** the Phase-2 status line with these counts.

The triage pipeline takes over from here (see
`references/triage-pipeline.md`).
