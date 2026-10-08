# `references/audit-mode.md`

How to audit an existing harness against the harness-builder standard and fix
the gaps in place. Audit mode runs when Step 2 detects a harness of the
requested type already on disk. The skill's guidance is the spec; the harness
is the implementation; this reference is the checklist that turns the diff into
patches.

The mindset is adversarial: assume the harness *looks* fine and *passes its own
tests* but silently exits early, leaks server resources, or skips the
adversarial review. Those are exactly the defects that don't surface until a
long run. Every item below has a failure mode that a green test suite hides.

## Procedure

1. **Inventory (A1).** List the harness modules and manifest. Map each to the
   canonical list (SKILL Steps 4–5). Record missing modules as findings.
2. **Score every item (A2).** For each checklist item: PASS / GAP / N/A, plus a
   one-line evidence pointer `file:line` (the code that satisfies or violates
   it). Don't accept "probably fine" — open the file and read the code path.
3. **Fix highest-severity first (A3).** Severity order: loop logic ≈ opencode
   gotchas > adversarial review > no-op/completion guards > sandbox > resilience
   > completeness > style. Preserve the project-specific `client` module.
   **Work in a git worktree if the harness's project is being driven by a live
   run on the same checkout.** A running genesis/burndown merges its agent
   worktrees back into the root, and an uncommitted audit edit in the root will
   be clobbered mid-fix (`git status` shows nothing, the file reverts). Use
   `git worktree add -d /tmp/audit HEAD` with its own `--target-dir`, fix and
   commit there, merge when the live run isn't mid-merge. This is the same
   worktree-isolation the harness imposes on dispatched agents — apply it to the
   auditor too. (2026-06-16 contended-checkout incident.)
4. **Verify with a regression test per fix (A4).** Build + test + clippy/vet.
5. **Commit per restored guardrail (A5).** Then run the post-merge `bugfix`
   review over the changed modules.

## Checklist

Severity key: **C** critical (causes false-clean or run death), **H** high,
**M** medium.

### Family 1 — Loop logic (C/H)

- **[C] Global fixpoint.** The outer loop terminates only when iterate +
  adversarial review + bug burndown all report no work **in the same round**.
  *Gap signature:* the flow exits after one phase's clean result; phases are
  independent early-returns. *Evidence:* find the outer loop; confirm it repeats
  the full plan and breaks only on an all-clean round.
- **[C] Two-state phase outcome.** Every phase returns `Clean | WorkRemaining`,
  never bare `Ok(())`. *Gap:* a phase returns `Ok` and the caller can't tell
  whether work remains.
- **[C] Reviewer/transport outage ≠ clean.** A phase that obtained no verdict
  (all passes 500'd / deadlined / unparseable) returns an **error** →
  `WorkRemaining`, never an empty verdict list read as `CLEAN`. *Gap signature:*
  `ITERATION CLEAN — zero rejects` logged when the reviewer never actually ran.
- **[H] Bounded outer loop.** `max_rounds` (derived from `max_iterations`)
  bounds cross-phase oscillation and fails **loud** on exhaustion — never as a
  success.
- **[H] Cap ≠ completeness.** Hitting `max_iterations` / time budget is
  `WorkRemaining`, not done. A `--dry-run` proved nothing → `WorkRemaining`.
- **[H] Repeat-fingerprint anti-stall.** A *deterministic, unfixable* reject —
  a coverage cliff the agent can't close, a mutation survivor needing a design
  change, a structural audit that fires on pre-existing state — re-dispatches the
  same fix every round and makes no progress until `max_rounds`, then exits
  NOT-done with no explanation. The burndown phase must track the reject
  fingerprint **set** across rounds (an order-independent hash) and, after N
  consecutive identical rounds (3 is reasonable), surface a **loud escalation**
  that names the stuck fingerprints and points at human review — rather than
  spinning silently. *Gap signature:* the same reject set recurs round after
  round with byte-identical fingerprints and no escalation log; the run only ever
  stops by hitting the round ceiling. *Evidence:* a per-session
  `last_burndown_fingerprint` + `recurrence` counter, reset on a clean round.
  This is the 2026-06-16 anti-stall finding (HIGH-4 of the cold review).

### Family 2 — Adversarial review (C/H)

- **[C] Three-pass reviewer present *and wired*.** Overt-failure pass,
  silent-divergence pass, and the structural `action_audit` anti-rationalization
  pass all exist **and have a production call site in the burndown/triage path**.
  *Gap:* only one pass, or no silent-divergence rubric (the most damaging bugs
  surface as INFO/DEBUG divergence). **Don't accept "the function is defined" as
  PASS — `grep` for its call site.** A fully-implemented reviewer pass with zero
  callers is dead code that does nothing at runtime; the literal three-pass
  requirement is unmet even though the source looks complete. *Evidence:* for
  each pass, the function definition **and** the line in `burn_down` (or
  equivalent) that appends its verdicts into the reject set. This is the
  2026-06-16 dead-pass finding: a hollow-completion / test-effectiveness pass-3
  and a snapshot-drift audit were both fully written but never called, so "tests
  pass but assert nothing" slipped through. *Fix:* wire each orphaned pass into
  the reject set; degrade safe (no scan tool installed → empty payload → zero
  verdicts, never a false reject).
- **[H] Reviewer model assignment.** Reviewer uses the configured reviewer
  model, parses verdicts robustly (fenced JSON after prose), fingerprints
  rejects.
- **[H] Reviewer JSON parse has a recovery ladder, not first-error-bail.** The
  verdict parser is (a) string-aware (a `json.Decoder`/`Deserializer`, never a
  bracket-counting walk that trips on `[` inside a `line` string) **and** (b) on
  decode failure runs cumulative, string-state-aware cleanup passes —
  strip-stray-escapes-outside-strings → escape-raw-control-chars-inside-strings →
  escape-bad-backslash-escapes-inside-strings — re-decoding after each and
  returning on first success. *Gap signature:* a batch is dropped on
  `invalid character '\\' looking for beginning of object key string`,
  `… in string literal`, or `… in string escape code` — the model emitted
  spec-invalid JSON (a raw newline in a `reason`, a verbatim `\d`/Windows path)
  and the parser bailed instead of repairing it. *Critically:* a parser that
  drops the batch silently can read as "zero rejects" → false `Clean`; the ladder
  must reduce outages, and a *fully* exhausted ladder is still a real parse
  failure → `WorkRemaining` (Family 1 reviewer-outage rule), never zero rejects.
  *Fix + test:* runtime-gotchas "String-blind JSON parsing → …genuinely-invalid
  JSON"; tests cover the incident (raw newline in string), bad-escape recovery,
  and no-op guards proving cleanup never corrupts valid JSON. This is the
  2026-06-16 reviewer-JSON-decode incident.
- **[H] Required `action_audit` tests present by exact name.** The four
  mandatory tests (`failure_only_run_emits_synthetic_reject`,
  `cache_fallback_success_does_not_clear_failure`,
  `genuine_upstream_success_clears_failure`, `non_action_lines_ignored`) exist
  **under those exact names** — a project-prefixed rename
  (`kev_failure_only_…`) is a GAP: a by-name check fails and the standard's
  contract is silently weakened. *Fix:* rename to the canonical name, keep the
  project context in a comment.
- **[H] Structural audit reads the failure CAUSE from attrs, and counts a
  failing lifecycle line.** The hard-failure scan must not be `msg`-only. *Gap
  signature:* a fast-fail unit (provider creation / auth / DNS) that emits only
  a terminal `scenario failed` lifecycle line with the cause in `attrs.error`
  and no bulk `"failed to …"` message lines records **zero** hard failures →
  **no** verdict → an operation that failed every iteration is silently
  accepted. Verify by replaying a real run's log through `audit()` and checking
  that every scenario whose lifecycle shows `scenario failed` produces an
  `audit-action-only-failures-<scenario>` verdict (unless it recorded a genuine
  non-fallback success). *Evidence:* the audit treats a failing terminal
  lifecycle line as a hard failure independent of message markers, and the
  failure exemplar renders `attrs.error` (string **and** structured array/object
  forms). *Fix + tests:* fast-fail-with-error-only-in-attrs emits a reject
  (string + structured-array), passing unit not flagged, failed-but-genuine-
  success not flagged. This is the 2026-06-18 wiz-evaluation gap (wiz failed
  every full-set iteration with an OAuth 401 in `attrs.error` and was missed by
  the structural pass for ~27 iterations).
- **[H] Whole-log correlation pass present *and wired*.** Beyond the
  per-operation failure tally, a **second** structural pass with **whole-run
  scope** correlates a key across the entire record set and flags a key whose
  state **oscillates** (revisits a value it already left, `A→B→A`) rather than
  converging. *Why it's mandatory:* this catches non-error divergence where
  every individual line is a benign INFO and the bug lives only in the
  relationship between lines spread across the run — invisible to both the
  per-operation tally (no failure marker) and the LLM reviewer (batched, no
  cross-batch memory). The canonical case is advisory identity migrating
  CVE→vendor-alias→CVE→alias repeatedly (two ingest paths fighting over the
  canonical id: wasted re-writes + a non-converging identity). *Gap signatures:*
  (a) no whole-log pass at all — the harness only tallies per operation; (b) the
  pass exists but has **no production call site** between the LLM passes and the
  burndown bridge (`grep` for it in the loop, same discipline as the three-pass
  check); (c) it flags **one-way convergence** (`A→B` never back) as a false
  positive; (d) consecutive idempotent re-emits aren't collapsed (false
  oscillation); (e) the verdict's `reason` hands the agent only the exemplar line
  and not the **full state sequence + an instruction to read the whole iteration
  log**, and the burndown prompt doesn't point whole-log findings at the complete
  log for a **structural, idempotent** fix with a re-ingest-twice regression test;
  (f) the LLM silent-divergence rubric doesn't also reject a migration/identity
  template with a high `[seen Nx]` count (belt-and-suspenders for a provider whose
  line omits the correlation attr). *Evidence:* the pass function, its loop call
  site appending into the reject set, and the by-name tests
  (`oscillation_back_and_forth_is_flagged`, `one_way_convergence_is_not_flagged`,
  `duplicate_snapshots_do_not_count_as_oscillation`, `distinct_keys_not_conflated`,
  `correlation_key_absent_is_ignored`). This is the 2026-06-17 alias-oscillation
  finding.
- **[H] Change-scoped structural audits use the *turn's own* diff.** Any
  structural audit that reasons about "what the fix turn changed" (snapshot-drift
  / "just re-snapshot it", churn heuristics, touched-file gating) must scope to
  the files **that turn** changed — captured as the set difference between a
  pre-dispatch dirty snapshot and the post-dispatch dirty set — **not** the whole
  dirty worktree (`git diff HEAD` / `git status` alone). *Gap signature:* the
  audit reads the entire uncommitted tree, so a `.snap` (or any file) left dirty
  by an earlier phase, a prior round, or operator state is attributed to this
  turn → a deterministic false reject that, combined with the burndown
  always-WorkRemaining rule, wedges the loop to `max_rounds`. *Evidence:* a
  `pre_fix_dirty` snapshot taken immediately before dispatch and a set-difference
  against the post-fix dirty set. This is the 2026-06-16 HIGH-3 finding.
- **[H] Post-merge `bugfix` review.** The harness's own modules were run through
  the `bugfix` skill (cold-context) **and its findings were fixed**, not just
  filed. *Gap:* never done — the canonical implementation found seven defects
  this way, and the 2026-06-16 audit found four more HIGH soundness defects *in
  the audit fixes themselves* (a re-arm race, a no-op-laundering tool count, a
  whole-worktree snapshot-drift wedge, a missing anti-stall). The review is not
  optional and it is not a rubber stamp: budget for it finding real bugs in your
  fresh code and fix them in the same campaign.

### Family 3 — opencode gotchas (C/H)

- **[C] One shared `/event` connection.** Exactly one long-lived `/event`
  reader per server; per-session observers fan out from an in-process broadcast
  channel. *Gap signature:* `run_event_loop` opens `GET /event` on every call →
  `MaxListenersExceededWarning` after ~11 sessions. *Fix + test:*
  opencode-server-integration §13.1; regression test asserts N observers → 1
  connection.
- **[C] No out-of-band session deletes.** The driver must **NOT** call
  `DELETE /session/:id` mid-run; the store is reclaimed by disposing the server
  instance at run end. *Gap signature (this is now a defect to REMOVE, not add):*
  a `delete_session`/`delete_json` helper called from `observe_session` teardown
  or a reviewer pass → `session.error … "FOREIGN KEY constraint failed" /
  "Failed to execute statement" / UnknownError`, after which *every* later
  session fails and the loop spins or hangs (the 2026-06-16 FK-corruption
  incident). The delete races the server's background `prompt_async` writes and
  poisons the SQLite store for all subsequent sessions. *Fix + test:* §13.2 —
  remove the delete and all its call sites; regression test asserts the driver
  exposes no session-delete path and the teardown issues no `DELETE`.
  (Earlier audit guidance *required* the delete; that was the bug. If you are
  auditing a harness generated against the old standard, the delete is the
  finding.)
- **[C] `properties` envelope unwrapped.** SSE frames are unwrapped once at
   parse time. *Gap signature:* every prompt runs to its deadline ("context
   deadline exceeded"), N-for-N. *Test:* drive captured wire bytes through the
   parser; assert completion detected.
- **[C] Server HTTP client is a fresh transport with a header bound, never the
   global default and never unbounded.** The `ServerHandle` client (a) builds a
   **fresh** `*http.Transport` / a `reqwest::Client` with `connect_timeout` +
   `read_timeout` — *not* `&http.Client{}`, *not*
   `http.DefaultTransport.(*http.Transport).Clone()`; and (b) sets a header-wait
   bound (`ResponseHeaderTimeout`), *not* a client-level `Timeout` (which would
   sever the `/event` SSE body). `waitHealthy` also wraps each probe in its own
   short timeout context. *Gap signature:* the harness logs `opencode server
   listening` then **never** `opencode server healthy`, hangs, and dies only on
   the outer signal — the operator says "stalls right after launching opencode".
   Two roots, often together: a no-timeout client + deadline-less `waitHealthy`
   ctx (a single hung probe through the not-yet-ready nono proxy blocks forever,
   the budget never re-checks), and `&http.Client{}` routing loopback through a
   process-wide transport guard the harness installed at startup (a dry-run
   guard over `http.DefaultTransport`) — which also makes any
   `DefaultTransport.(*http.Transport)` assertion **panic** at launch. *Fix +
   tests:* opencode-server-integration §6.1 `newHarnessHTTPClient` /
   `controlResponseHeaderTimeout`; runtime-gotchas "The no-timeout HTTP client
   hangs forever after 'opencode server listening'". Tests: constructor does not
   panic when `http.DefaultTransport` is replaced by a guard; client `Timeout ==
   0` but `Transport.ResponseHeaderTimeout` set. This is the 2026-06-16
   health-probe-hang incident.
- **[C] Session-create errors capture the body.** `CreateSession` (and any
  synchronous prompt path) reads the response body on a `>= 300` status and
  includes it in the error (`status %d: %s`). *Gap signature:* a bare
  `create session: status 500` with no body — undebuggable, and `POST /session`
  500 is the #1 loop-stall cause (reviewer/burndown can't get a session → total
  outage). *Fix:* opencode-server-integration §5 `CreateSession`; the body names
  the missing nono grant / 403 / store error. *Test:* a fake server returning
  500 with a JSON body → error contains the body text.
- **[C] `model` field is `{ providerID, modelID }`, model defaults
  provider-qualified.** When the prompt body sends an explicit `model`, it is
  the object `{ providerID, modelID }` (split a `provider/model` string on the
  first `/`), never a bare `{ modelID }` or a bare string. *Gap signature:*
  every prompt 400s with `BadRequest: Missing key at ["model"]["providerID"]`,
  read as a total reviewer outage (2026-06-16). *Fix + test:*
  opencode-server-integration §10 + the `model_field` helper in the §6.1
  skeleton; tests assert both keys emitted, first-slash split, bare-model
   rejected. *Also check the model **defaults**:* they must be
    provider-qualified (`gitlab/duo-chat-haiku-4-5` — **no `claude-` infix**; the
    stale `duo-chat-claude-haiku-4-5` 404s every prompt) **and** the right tier
   — for GitLab Duo the `duo-chat-*` tier, NOT `duo-workflow-*` (which no-ops;
   §4.1). GAP if the id is not verified against `GET /config/providers`, or if a
   `session.error` is not classified as a fast turn-end failure (a wrong id then
   rides the deadline with `tool_calls=0` — the 2026-07-09 hang). Defaults must
   be **Haiku, never Opus** (Sonnet only for the rare very
   complex burn). A default of bare `duo-workflow`, of an Opus-tier id, or of an
   unqualified bare model is a gap.
- **[H] Per-tool-call INFO + liveness heartbeat (§4.1 observability) — detail
  level enforced, EVERY phase.** The driver emits one INFO line per deduped
  tool-use part naming the tool **and a per-tool detail summary** that captures
  the tool's *distinguishing* parameters, and a ~30s heartbeat (`elapsed_secs`,
  `idle_secs`, `no_progress_secs`, `tool_calls`, `last_tool`) so an operator
  tailing at `info` sees a long turn progress. The detail bar is now explicit
  (§4.1 table) and applies in the reviewer, genesis/iteratotron, done-gate, and
  every subagent drive — not just burndown:
    - **codebase-mutating calls are the most detailed**: `edit` logs the
      `filePath` **plus** the change shape (`replaceAll` and/or an
      oldString→newString preview); `write` logs the `filePath` **plus** content
      size; `bash` logs the **full command** (+ `description`). A bare
      `tool=edit` (no file/change) or `tool=bash` (no command) is the canonical
      defect — flag it.
    - read/grep/glob/skill/webfetch/task/todowrite each log their meaningful
      params (offset/limit, pattern+path, name, url, subagent_type+description,
      todo count + in-progress item).
    - an **unknown** tool logs its full `k=v` field set, **not** just the first
      string field (a first-string-only fallback is a gap).
    - deferred log until input is present, once per part id, never silently
      dropped; single-line collapse + ~160-char truncation per value.
  *Gaps:* tool calls counted but never logged (a multi-minute turn reads as a
  freeze); logged with tool name only (no params); `edit`/`bash` logged without
  the file/command; a generic first-string fallback used for all tools.
  *Tests (one per tool family, not optional):* the summary picks the right
  param(s) for `edit`/`write`/`read`/`bash`/`grep`/`glob`/`skill`/`webfetch`,
  `edit`/`write`/`bash` carry their change-shape/command, newlines collapse,
  over-long values truncate, and an unknown tool emits its full field set.
- **[H] Three-way AND completion.** Completion requires `message.updated` +
  `info.time.completed` **and** `session.idle` **and** empty todo — not idle
  alone. Completion guarded on `role == "assistant"`.
- **[C] Interactive question handled — matching the BUILD's vocabulary.** The
  question signal is classified separately (`EventSignal::QuestionAsked`) and
  auto-answered, and every dispatched prompt carries the standing no-questions
  directive. *Critically, check WHICH event the classifier watches against the
  target build's `/doc`:* opencode **1.16.x** emits questions as **first-class
  `question.asked` / `question.v2.asked` events** (with `questions[]` + request
  `id`), answered via `POST /api/session/:id/question/request/:rid/reject` — a
  driver that only watches for a `message.part` tool *named* `question` (the
  older shape) has **dead** question handling on 1.16.x. Either approach must
  dedupe (by request id / part id) and cap injections per session; a question is
  **never** counted as a tool call. *Gap signature:* a session that asks never
  completes and rides to its deadline as a false Timeout. *Fix + test:*
  opencode-server-integration §14 + §16; tests assert the build's question event
  classifies as `QuestionAsked`, the `.v2`/alias is caught, ordinary tool use is
  untouched, the answer states autonomy + the defer branch, prompts carry the
  directive.
- **[C] Event-vocabulary matches the running build (validate against `/doc`).**
  The classifier's `type` discriminators are reconciled against the pinned
  opencode version's `/doc` Event union — not hardcoded to an older build. For
  **1.16.x** specifically: turn lifecycle via `session.next.*`
  (`tool.called`/`step.failed`/`text.delta`), questions via `question.asked`,
  permissions via `permission.asked` (**`permission.updated` does not exist**).
  *Gap signature:* the canonical event-vocabulary-drift hang — `tool_calls`
  frozen at a round number, `idle_secs`/`progress_idle_secs` pinned at a small
  constant (the ~30s `server.heartbeat`), every session riding to its deadline;
  a forensic frame log (if present) shows `session.next.*` / `*.asked` kinds the
  classifier dropped to `Other`. *Fix + test:* opencode-server-integration §16;
  tests cover the build's tool/question/permission/step-failed shapes. This is
  the 2026-06-16 `session.next.*` incident.
- **[C] Both tool vocabularies handled, deduped by id.** Tool calls are counted
  from **both** `session.next.tool.called` (keyed by `callID`) **and**
  `message.part.updated` tool parts (keyed by part `callID`, falling back to part
  `id`) — whichever the provider uses (GitLab Duo uses the latter) — and the
  drive loop dedups by that id in a `seen_tool_calls` set so N re-emitted
  snapshots of one call count **once**. *Gap signature:* `tool_calls` inflated
  into the hundreds (≈one per `message.part.updated` snapshot), making the no-op
  guard meaningless; or `tool_calls` stuck at 0 on a build whose tool vocabulary
  the classifier doesn't handle. *Fix + test:* opencode-server-integration §16;
  tests assert both vocabularies → `ToolUse{call_id}` with `callID` preferred,
  and N snapshots → 1 count.
- **[C] LIVENESS-keyed stall watchdog with a keepalive DENYLIST (not a
  real-work allowlist).** The drive loop tracks `last_activity` reset on **every
  turn-attributable frame** — new tool call, answer text, *re-emitted* tool
  snapshot, reasoning delta, `session.status`/`diff`/`updated`, `todo.updated`,
  any `session.next.*` — and treats **only** `server.heartbeat`/`server.connected`
  as inert (an `is_inert_kind` denylist). It aborts (→ `WorkRemaining`) when
  `last_activity` exceeds `STALL_TIMEOUT` (well under `SESSION_DEADLINE`). The
  liveness reset must be **independent of the tool-call dedup**: dedup keeps
  `tool_calls` honest, but a deduped (already-seen `callID`) snapshot still resets
  the clock. *Two gap signatures, both critical:* (a) **no/over-narrow watchdog**
  — the only escape is the multi-ten-minute deadline, or it's keyed on raw frame
  arrival so the 30s heartbeat resets it forever and it never fires; (b) **the
  false-stall** — the watchdog resets **only** on new-tool-call/answer-text
  (a real-work *allowlist*), so a busy agent doing a long single tool call (same
  `callID` re-emitted, deduped) or a reasoning/status burst gets aborted mid-work
  (the 2026-06-16 incident: 118 tool calls, 271 `message.part.updated`, 184
  `session.status` in the window, killed at 5 min). A future opencode build
  adding new progress events must count as liveness **by default**, so inert is a
  denylist, never an allowlist. *Fix + tests:* opencode-server-integration §16.3;
  `is_inert_kind` denylist; tests assert (i) `is_inert_kind` is true only for the
  keepalive kinds and false for every working kind, (ii) the watchdog fires on a
  heartbeat-only stream within `STALL_TIMEOUT`, and (iii) does **not** fire on a
  steady stream of re-emitted tool snapshots / status frames.
- **[H] Deadlines sized to the workload (false-Timeout audit).** The hard
  ceilings — `SESSION_DEADLINE`, `STALL_TIMEOUT`, `--time`, and every per-gate
  build/test/check timeout — must clear the slowest *productive* turn for **this**
  project's workload, not a generic service watchdog. Classify the workload
  (does the drive surface or a fix turn shell out to `nix build` / `docker build`
  / `bazel` / `cargo build --release` / a VM-booting test suite?): a build-system
  / E2E harness needs `--time` in **days** (`604_800` is a sane default), per-session
  deadline `2–4 h`, stall window `20–30 min`, full check-graph `4–6 h`, single
  build `2–4 h`. *Gap signatures:* (a) `--time` ≈ 8 h / `SESSION_DEADLINE` ≈ 40 min
  / build gates ≈ 1 h on a project whose builds or E2E plainly take longer — the
  symptom is *phases timing out mid-flight and logged as false Timeouts*, which
  under the outage rule can stall the whole loop; (b) a *tight* hard ceiling used
  as a hang-catcher (that is the stall window's job — the hard ceiling must be
  generous, the stall window tight); (c) any >30 s gate without a liveness
  heartbeat (a silent slow build reads as a hang and tempts shrinking the
  ceiling). *Fix:* raise the ceilings per SKILL.md "Size the deadlines to the
  workload"; keep `STALL_TIMEOUT` ≪ `SESSION_DEADLINE`; ensure every long gate
  carries the ~30 s heartbeat. *Evidence:* report the four ceiling values, the
  observed slowest build/test step, and the workload class. This is the
  service-watchdog-default-on-a-build-system gap.
- **[H] Unhandled-kind tracking + per-session forensic frame log.** Every
  `Other`-classified event `kind` is counted and surfaced in the heartbeat
  (`unhandled_kinds`) and loudly on stall/abort (naming the dropped kinds); every
  raw `{kind,payload}` frame is teed to a per-session `frames/<id>.jsonl`. *Gap
  signature:* a vocabulary-drift hang requires bundle-string archaeology to
  diagnose because nothing recorded what was on the wire. *Fix:*
  opencode-server-integration §16.3.
- **[H] Process-group kill.** Teardown signals the process group, not just the
  parent; no orphaned bash/MCP children.
- **[H] Dynamic port to both sinks.** Resolved port passed to **both**
  `--port` and nono `--open-port`; never parsed back from stdout.
- **[M] `agent`+`model` determinism.** Model encoded in the agent definition.
- **[H] Fix-agent model is tool-capable for its provider.** The burndown/genesis
  fix model is one the configured provider serves with tool-calling, verified by
  the no-op guard — **not** chosen by a `*-workflow-*` substring. For **GitLab
  Duo** the working tier is `duo-chat-*` defaulting to Haiku
  (`gitlab/duo-chat-haiku-4-5`, no `claude-` infix); flag a `duo-workflow-*` default as a GAP
  (it returns empty no-tool completions on observed servers and burns
  iterations), and flag an **Opus-tier default** as a GAP too (never auto-Opus —
  Sonnet only for the rare very complex burn). For **direct Anthropic** (only
  when specifically required) a current tool-capable Claude defaulting to
  `anthropic/claude-haiku-4-5`. See `opencode-server-integration.md` §4.1.
- **[H] `session.error` is rendered, not dropped to `null`/empty.** A drive that
  ends in a server-side `session.error` (or an assistant-message error) renders
  the opencode `{ name, data: { message } }` shape into a human-readable,
  never-empty string (name + message + raw JSON fallback) AND preserves a tail
  of the partial assistant reply in the error. *Gap signature:* `Error: drive
  … session` with an empty cause chain, or `error event: null` — a server-side
  rejection (`MODEL_MAPPINGS` skew, store `Failed to execute statement`) looks
  like a mystery harness bug, and the forensic log (written only on the success
  path) is lost. *Fix + tests:* opencode-server-integration §5 / §15;
  `format_session_error` + `reply_tail` wired into both error arms; tests cover
  the store-error and model-skew shapes and the missing/null/unrecognized cases.
- **[H] Bounded, transient-ONLY retry on `session.error` (flakey API).** The
  driver retries a `session.error` **only** when it classifies as transient
  (5xx/gateway, timeouts, connection resets, rate limits) — bounded attempts,
  exponential backoff, **recreating a fresh session each attempt** — and
  **fails fast** on a deterministic rejection (`Unknown model ID`/
  `MODEL_MAPPINGS`, `BadRequest`, `EACCES`, auth, **and the SQLite store
  errors `Failed to execute statement`/`FOREIGN KEY constraint failed`/
  `UnknownError`** — a corrupt store is not a hiccup; every later session
  fails too, so retrying just burns budget — §13.2), with an unrecognized
  error defaulting to deterministic.
  *Gap signatures, both bad:* (a) **no retry** — a single mid-drive hiccup after
  real progress throws away the whole expensive drive (the 2026-06-16 burndown
  incident); (b) **blind retry of everything** — deterministic config bugs get
  retried into the budget and masked as "flakiness", and worse, an exhausted
  retry that collapses into zero-rejects/clean is a reviewer-outage false-clean.
  *The invariants to check:* deterministic markers take precedence over
  transient ones; a timeout/abort stays `completed:false` (NOT retried — the
  deadline already bounds it); an exhausted transient retry surfaces as an
  **error → `WorkRemaining`**, never clean; the retry lives in the driver
  (`prompt_and_drive` owns session creation + the loop, callers pass a *title*),
  not duplicated per caller. *Fix + tests:* opencode-server-integration §15;
  `classify_session_error` + `DETERMINISTIC_ERROR_MARKERS` /
  `TRANSIENT_ERROR_MARKERS` + the bounded loop in `prompt_and_drive`; test
  asserts transient/deterministic/precedence/unknown classification.

### Family 4 — Sandbox (C/H)

- **[C] nono is the direct parent** of `opencode serve`; preflight aborts if
  nono is missing and `--allow-unsandboxed` isn't set. No silent
  `bypassPermissions` fallthrough.
- **[H] One source for `--add-dir` and `--allow`.** Both lists derive from the
  same variable in `wrap_with_nono`; drift is the bug.
- **[C] All skills + LSPs available (over-isolation is a gap).** The server runs
  against the operator's **real** `~/.config/opencode` (or, if isolation is
  forced, against a copy of the **whole** skills tree) so **every** host skill
  and **every** configured LSP loads. *Gap signature:* a minimal isolated
  `XDG_CONFIG_HOME` with a hand-picked skill subset, `"plugin": []` stripping
  everything, or a blanket-disabled LSP — the iter-001 shape that makes the fix
  agent no-op. *Fix:* point at the real config and widen the nono profile to
  cover what it touches (don't isolate to dodge an EPERM — grant the offending
  cache dir). See opencode-server-integration §4.1.
- **[C] Session-create grants present (the EACCES/403 set).** `DefaultAllowDirs`
  (the one source for `--add-dir`/`--allow`) grants the three things the server
  touches at session-create that the profile misses, or `POST /session` 500s and
  the loop stalls: (1) the **`~/.opencode` install dir** (read of
  `package.json`); (2) **`models.dev`** in the egress domain list (model-catalog
  fetch, else 403 → models don't resolve); (3) **config symlink targets** —
  resolve `skills`/`commands`/`agents`/`plugins`/`themes` under
  `~/.config/opencode` and grant any target outside the config dir (a symlinked
  `skills` dir is the common one; without it bug-burndown/bugfix EACCES and the
  fix agent no-ops). *Gap signature:* `status 500: …EACCES…package.json`,
  `Failed to fetch models.dev …403`, or sessions create but the burndown turn
  makes zero tool calls. *Fix + tests:* nono-integration.md "session-create
  500 / EACCES"; regression tests assert each dir/domain is emitted (and a
  symlink target outside the config dir is granted, an internal one is not).
- **[H] Capability loosened, secrets still denied.** The sandbox grants enough
  that dispatched agents can actually fix things (skills, LSP binary/state dirs,
  toolchain read dirs, plugin/cache dirs, egress domains) **while** `default`'s
  `deny_*` credential/secret/browser groups and the `.env` deny stay intact.
  *Gap:* either over-restriction (a skill/LSP can't load) **or** a relaxed
  `deny_*` group. Loosen capability, never secrets. See nono-integration.md
  § "Loosen capability, never secrets".

### Family 5 — No-op / completion guards (H)

- **[H] Zero-tool-call turn = WorkRemaining.** A fix/burndown turn that made no
  tool calls did no work; flag it, don't report success.
- **[H] Done predicate complete.** All clauses present; SLSA L3 attestation
  non-optional in genesis mode (clause 8).
- **[H] Unsubstantiated-claim verification.** Verification re-queues scope with
  a gap when a claim isn't substantiated; an empty/garbage reply reopens
  everything, never passes.

### Family 6 — Resilience (H/M)

- **[H] Auto-resume by default**, `--no-resume` to opt out; iteration/session
  state persisted per round.
- **[H] Resume reuses gathered logs.** Resume targets the most recent
  *incomplete* iteration whose application logs are already on disk but whose
  review/burndown never ran, and **reuses those logs** (no rebuild, no daemon
  respawn, no re-`collect_until_idle`) — running only the review → action-audit
  → burndown phases against them. *Gap signature:* resume re-drives the app and
  re-collects identical logs, or skips a logs-gathered/unreviewed iteration as
  "partial". Only a genuinely *log-less* directory is skipped. *Evidence:* the
  resume resolver returns a "review existing" phase for `has_logs &&
  !has_verdict`; `has_verdict` is written by the review phase that the resolver
  reads (one shared predicate, no drift).
- **[M] Fresh logs after the resumed iteration.** Every iteration *after* the
  resumed one rebuilds the application and gathers fresh logs — stale logs are
  reused for exactly one iteration, never more (otherwise the review judges code
  that no longer exists).
- **[M] Agent observability + liveness logging — full per-tool detail.** Each
  deduped tool-use part emits an INFO line with the tool **name and a per-tool
  detail summary** that captures the call's distinguishing parameters (§4.1
  table): `edit` → filePath **+ change shape**, `write` → filePath **+ size**,
  `bash` → **full command**, read/grep/glob/skill/webfetch/task/todowrite →
  their meaningful params, unknown → full `k=v` set; single-line and truncated.
  A ~30s INFO heartbeat logs `elapsed_secs`/`idle_secs`/`no_progress_secs`/
  `tool_calls`/`last_tool` (with detail) so a long session is visibly alive.
  This holds in **every** phase, and codebase mutations must be the most
  detailed entries in the stream — the reviewer/audit phase reconstructs the
  change from these lines. *Gap signature:* the harness logs only `agent tool
  call` with no params, logs `edit`/`bash` without the file/command, uses a
  first-string fallback for all tools, or goes silent for minutes mid-session —
  so an operator can't tell *what* the agents did to the codebase from the
  harness logs. *Fix + tests:* opencode-server-integration §4.1 "Observability";
  tests assert the summary picks the right param(s) per tool family, that
  mutating tools carry change-shape/command, newlines collapse, values truncate,
  and an unknown tool emits its full field set.
- **[M] No duplicate tool-call logging across routers.** When dispatch goes
  through the shared drive loop (`RunPrompt`/`run_event_loop`) that already logs
  tool calls at INFO, the per-bridge event router (`routeBurndownEvent`,
  `routeGenesisEvent`) must **not** re-log the same tool call — especially not a
  less-informative copy missing the target. *Gap signature:* every tool call
  appears twice in the harness log, the bridge copy lacking the target the
  generic driver includes. *Fix:* make the bridge router minimal (its distinct
  value is the verbatim event dump to the per-session forensic file, done by the
  sink before the router runs). This is the 2026-06-16 genesis-double-log gap.
- **[M] Long-running test-effectiveness tools heartbeat.** Mutation
  (`gremlins`/`cargo mutants`/`mutmut`) and full-suite coverage tools run 20–60
  min with zero output; each blocking invocation runs under a liveness heartbeat
  (~30s `tool still running — phase alive` + `tool finished`) that stops on every
  return path and propagates the call's result unchanged. *Gap signature:* the
  test-effectiveness phase goes silent for many minutes through a bare
  `cmd.Output()`/`cmd.Run()`/`subprocess.run`, indistinguishable from a hang. *Fix
  + test:* runtime-test-effectiveness-baseline "Liveness — heartbeat every
  long-running tool"; tests assert result/error pass-through, no spurious line on
  a fast call, and no leaked timer after return. This is the 2026-06-16
  test-effectiveness-hang incident.
- **[H] Fix-agent model is tool-capable AND registered on the server build.**
  Beyond the §4.1 provider-tier check (Family 4), audit that the configured model
  id is actually accepted by the gateway the harness's `opencode serve` talks to,
  not merely present in the `opencode models` catalog. *Gap signature:*
  `session.error … "Unknown model ID: <id>. Model must be registered in
  MODEL_MAPPINGS"` — a server-side GitLab AI-Gateway rejection, usually because
  the harness launches an **older pinned opencode** (e.g. a devshell `pkgs.opencode`
  from a stale nixpkgs rev) than the interactive shell, and the catalog drifted
  ahead of that build's gateway map. *Fix:* upgrade the opencode the harness
  launches (check the Nix/devshell pin), don't downgrade the model; confirm by
  probing the id against the actual server build. This is the 2026-06-16
  version-skew incident. See opencode-server-integration §4.1.
- **[H] Serial outer loop.** Outer runtime/daemon loop is serial
  (`parallelism == 1`); only inner burndown fans out. Two daemons over one DB
  break everything.
- **[H] Freshness gate doesn't relaunch-loop.** If the harness has a
  self-freshness/relaunch gate (three signals: source-after-start, HEAD-changed,
  binary-stale), it must (a) **suppress `binaryStale` when running under
  `go run`/`cargo run`** — the build cache stamps the artefact with an mtime
  older than compiled-in source, so it's a false positive that re-execs the same
  cached binary forever; and (b) **on a failed relaunch (exec error, `go` not on
  PATH), log and continue with the current binary**, never propagate an error
  that aborts the loop and lets the outer wrapper restart-and-retrigger. *Gap
  signature:* `re-launching via go run` every iteration with no progress, or the
  process exiting and being restarted into the same relaunch. *Fix + test:*
  runtime-gotchas.md "The freshness relaunch loop"; test `isGoRunPath`
  (go-build cache/TMPDIR paths → true, installed paths → false).
- **[M] Teardown always runs.** Server `shutdown`/`dispose` runs on every exit
  path (capture the result, tear down, then propagate).

### Family 7 — Implementation + bugfix loop completeness (H/M)

- **[H] Orchestration bridges match the declared `orchestration:`.** Genesis →
  `inner_loop` dispatches iteratotron against worktree-isolated scopes; burndown
  bridge present if selected; sweep wired if selected.
- **[H] Genesis module set complete.** gap_analysis → plan → inner_loop →
  constitution_check → adversarial_review → verification → done_predicate → slsa
  all present and wired.
- **[M] Findings schema.** Findings written in the bug-burndown session schema
  so `/bug-burndown` can consume them.

## Scored-report template

Emit this before fixing, so the operator sees the whole gap surface:

```
Harness audit — <project>-harness  (mode: audit, type: <…>, lang: <…>)

Family                          PASS  GAP  N/A
1 Loop logic                      3    2    0
2 Adversarial review              2    1    0
3 opencode gotchas                5    2    0   ← 2 CRITICAL
4 Sandbox                         3    0    0
5 No-op / completion guards       2    1    0
6 Resilience                      2    1    0
7 Completeness                    2    1    0

CRITICAL gaps (fix first):
- [3] per-session /event connection      opencode_server.rs:412  → §13.1
- [3] out-of-band session deletes        opencode_server.rs:690  → §13.2
HIGH gaps:
- [1] no global fixpoint; exits on burndown-clean   main.rs:88
- [2] no post-merge bugfix review                   (process)
…
```

Then fix in severity order, one commit per restored guardrail, each with a
regression test.

## What "fixed" means

A gap is closed only when: (1) the code matches the standard, (2) a regression
test fails on the old code and passes on the new, and (3) the build + lints are
green. Reopen the item otherwise. After all CRITICAL/HIGH gaps are closed, run
the post-merge `bugfix` review over the changed modules — audit-mode fixes touch
concurrency, persistence, and process identity, exactly where new bugs hide.
