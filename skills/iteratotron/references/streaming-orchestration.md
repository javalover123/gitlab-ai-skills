# Streaming subprocess orchestration with `claude -p`

Genesis dispatches every subagent (iteratotron, bug-burndown, adversarial
reviewer) as a streamed `claude -p` subprocess — not via the in-session
Agent tool. The streaming pipe is what lets iteratotron render progress,
intervene mid-run, and abort cleanly.

This reference covers the event schema, parent-side consumption patterns,
interruption + resumption, permission boundaries, and the adversarial-
reviewer prompt template.

## Canonical invocation

```bash
claude -p "$(jinja_render scope_prompt.md.j2 scope_id=$SID)" \
  --output-format stream-json \
  --verbose \
  --include-partial-messages \
  --permission-mode acceptEdits \
  --max-turns 80 \
  --max-budget-usd 20.00 \
  --model haiku \
  --add-dir .specify \
  --add-dir specs \
  --add-dir adrs \
  --add-dir threat-models \
  --add-dir stories \
  --agents @.claude/agents/iteratotron.md \
  --disallowed-tools "WebSearch" \
  2>>.iteratotron/logs/scope-$SID/stderr.log \
  | tee .iteratotron/logs/scope-$SID/$(date +%s).jsonl \
  | jq -c .
```

**Model policy:** default scope dispatch to Haiku (preferentially via GitLab
Duo's `duo-chat-*` tier, e.g. `gitlab/duo-chat-claude-haiku-4-5`; direct
Anthropic `anthropic/claude-haiku-4-5` only when the run specifically targets
that API). **Never default to Opus.** Raise to Sonnet only for the rare,
genuinely very complex scope where Haiku has demonstrably stalled.

The three flags that **must** appear together for token-level streaming:
`--output-format stream-json`, `--verbose`, `--include-partial-messages`.
Without all three, you get post-hoc messages only, not the partial-token
deltas the parent UI needs.

## Event schema (outer envelope)

One JSON object per line. The schema is community-documented (the
`humanlayer/claudecode-go` typed bindings + `takopi.dev` / `ytyng.com`
cheatsheets) — Anthropic has an open issue (`anthropics/claude-code#24612`)
requesting official documentation. Treat the schema as **stable but
reverse-engineered**; pin a JSON-Lines validator in the parent.

| `type` | `subtype` | When emitted | Key fields |
|---|---|---|---|
| `system` | `init` | once at start | `session_id`, `cwd`, `model`, `permissionMode`, `apiKeySource`, `tools[]`, `mcp_servers[]` |
| `assistant` / `user` | — | once per turn (final form) | `session_id`, `message.id`, `message.content[]`, `message.usage` |
| `stream_event` | — | streaming with `--include-partial-messages` | `event.type` ∈ {`message_start`, `content_block_start`, `content_block_delta`, `content_block_stop`, `message_delta`, `message_stop`, `ping`} |
| `result` | `success` / `error` / `error_max_turns` / `error_during_execution` | once at end | `total_cost_usd`, `is_error`, `duration_ms`, `duration_api_ms`, `num_turns`, `result`, `usage` |
| `system` | `api_retry`, `compact_boundary` | mid-session | retry ETAs; context-compaction markers |

### Inside `stream_event.event`

This mirrors the raw Anthropic Messages SSE schema:

- `content_block_delta` with `delta.type == "text_delta"` → token stream
  for the visible assistant message.
- `content_block_delta` with `delta.type == "input_json_delta"` →
  **partial JSON for a tool-use input**. Accumulate `delta.partial_json`
  strings across deltas with matching `index`, then parse only after the
  matching `content_block_stop` (or use Pydantic partial-JSON parsing).
  The matching `content_block_start` carries `content_block.type ==
  "tool_use"` along with `content_block.name` and `content_block.id`
  (used to correlate the subsequent tool_result).
- `message_delta` carries `delta.stop_reason` ∈ {`end_turn`, `tool_use`,
  `max_tokens`, `pause_turn`} and cumulative `usage.output_tokens`.

## Parent-side consumption patterns

Pick by ecosystem:

- **Bash + `jq -c`** — cheapest, ideal for a TUI strip. Filter:
  ```bash
  jq -c 'select(.type=="stream_event" and .event.delta.type=="text_delta") | .event.delta.text'
  ```
  Pipe to a per-subagent panel.
- **Python** — `claude_agent_sdk.query()` returns the typed message
  hierarchy. Set `include_partial_messages=True` in `ClaudeAgentOptions`.
- **Rust** — spawn with `tokio::process::Command`, read stdout via
  `tokio::io::BufReader::lines()`, parse with
  `serde_json::from_str::<Event>(&line)?`. Khan Academy's
  `format-claude-stream` is a useful reference formatter.
- **Go** — `humanlayer/claudecode-go` already has typed bindings for
  this schema; use them directly.

## Interruption mid-tool-call

Killing the parent process or sending SIGINT to the streamed `claude -p`
subprocess terminates immediately. There is no graceful tool-result
delivery after kill — any in-flight tool's filesystem effect persists,
but its result is never sent back to the assistant.

On Ctrl-C, iteratotron must:

1. **Flush the per-subagent stream log to disk** (the `tee` is already
   doing this if you set it up; otherwise sync explicitly).
2. **Record the last seen `content_block_start` / `tool_use`** so the
   resume prompt can describe what was interrupted.
3. **Clean the per-subagent worktree** *only* if it has no uncommitted
   changes (Claude Code's auto-cleanup follows the same rule per
   `git worktree` semantics). With uncommitted changes, prompt the
   human at resume time.

## Cost and usage

The only authoritative cost is in the final `result.total_cost_usd` and
`result.usage`. Intermediate `message_delta.usage` is cumulative
**within a single assistant message** — right for in-flight TUI
displays, wrong for cross-turn sums.

Track per-subagent cost in `.iteratotron/state.json#cost_log`:

```jsonl
{"scope_id": "...", "subagent_kind": "iteratotron", "start": "...", "end": "...", "total_cost_usd": 4.21, "duration_ms": 1842000}
```

Aggregate to the session level for the global budget check.

## Permissions in stream-json mode

With stream-json, permission prompts surface as system events. For
unattended iteratotron runs in genesis mode:

- **`--permission-mode acceptEdits`** (default) — auto-approves file
  edits; still prompts on Bash and unallowlisted MCP tools.
- **`--dangerously-skip-permissions`** — only inside disposable
  worktrees or containers. Use this for read-only adversarial reviewer
  subagents where you've also denied edit tools via `--disallowed-tools`.
- **Programmatic `canUseTool` callback** (when using the SDK):
  `PermissionResultAllow{updated_input}` sanitises tool inputs
  in-flight; `PermissionResultDeny{message, interrupt}` aborts and
  feeds reasoning back to the model.

The permission-processing order is worth memorising:
**PreToolUse Hook → Deny Rules → Allow Rules → Ask Rules → Permission
Mode Check → canUseTool Callback → PostToolUse Hook.**

## Adversarial reviewer prompt template

Used in Phase 7 of every subagent's completion claim. Substitute the
variables at dispatch time; the prompt is sent as the single
`claude -p` argument.

```
You are an adversarial completion reviewer. You will be shown:

1. The diff between baseline_sha and worktree HEAD
2. The scope's linked design artefacts (spec, ADRs, threat model, stories)
3. The iteration log produced by the subagent
4. The original gap inventory

You do NOT see the subagent's reasoning. Cold-context verification is the point.

Your job: fill in every subsection below. Output a JSON envelope:

{
  "verdict": "APPROVED" | "INSUFFICIENT" | "NEEDS_HUMAN",
  "subsections": {
    "1_restated_intent": "...",
    "2_three_way_diff_per_gap": [
      {"gap_id": "...", "desired": "...", "documented": "...", "implemented": "...", "divergence": "..."}
    ],
    "3_stop_bias_rescan": {
      "new_findings": [...],
      "pattern_kinds_introduced": [...]
    },
    "4_hallucination_spot_check": {
      "functions_inspected": N,
      "tautological_tests_found": [...],
      "doc_vs_code_mismatches": [...]
    },
    "5_doc_vs_code_three_way": [
      {"artefact_id": "...", "claimed_status": "...", "code_evidence": "...", "matches": true/false}
    ],
    "6_cross_scope_contract": {
      "public_api_changed": true/false,
      "affected_scopes": [...]
    }
  },
  "lessons_learned": "...",
  "next_actions": [...]
}

You MUST fill every subsection. An empty subsection means INSUFFICIENT.
Be specific: cite file paths, line numbers, and artefact IDs.

The scope's design artefacts and gap inventory follow.

---

<scope_artefacts>

---

<iteration_log>

---

<git_diff>
```

Spawn with cold context: `--permission-mode bypassPermissions
--disallowed-tools Edit,Write,NotebookEdit,Bash` so the reviewer can
read but can't accidentally mutate the worktree.

## Don't pipe prompts through stdin

Sandbox wrappers like `claude-bwrap` use `systemd-run --pty`, which
allocates a PTY for the child and consumes the parent's stdin pipe
before claude ever sees it. Pass the prompt as a **positional argv
argument** (Linux's ARG_MAX of ~2 MiB easily covers a 75 KiB reviewer
prompt). Set stdin explicitly to `Stdio::null()` so wrappers waiting
on EOF get the right signal.

This is the same lesson `harness-builder/references/runtime-gotchas.md`
documents for the harness's reviewer-bridge subprocess — iteratotron
inherits it.

## Bridge subprocess hangs after `result` event

`child.wait().await` with no timeout is a hang vector. `claude -p`
doesn't reliably close stdout after emitting its final stream-json
`result` event (telemetry flush, MCP cleanup, stream-json shutdown
stalling), so iteratotron can block on the bridge indefinitely while the
outer loop waits to advance.

Fix: detect the `result` event inline in the stdout reader, fire a
`tokio::sync::Notify`, have a watchdog task sleep a short grace
(default 30 s), SIGTERM, sleep 10 s, SIGKILL. The watchdog is aborted
normally on clean exit — it only fires on the hang path.

Full pattern + Rust code in
`harness-builder/references/runtime-gotchas.md` § "Bridge subprocess
hangs after stream-json result event". Worked example: example-harness
commit `88bdb0a`. Genesis must implement the same pattern for every
streamed subprocess.

## Tee the raw stream to disk before any filtering

`--include-partial-messages` produces a deluge of events. Use
non-blocking reads with a bounded buffer, and **tee the raw stream
to disk before any filtering** so audit replay is possible:

```bash
claude -p "..." --output-format stream-json --verbose --include-partial-messages \
  | tee .iteratotron/logs/scope-$SID/raw-$(date +%s).jsonl \
  | (parent_side_consumer)
```

The `tee` write is non-blocking on Linux up to the pipe buffer (~64 KiB
default); past that, set `PIPE_BUF` larger via `fcntl(F_SETPIPE_SZ)` if
you saturate.
