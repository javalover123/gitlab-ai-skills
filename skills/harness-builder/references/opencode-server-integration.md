# `references/opencode-server-integration.md`

The **default harness-builder agent-host backend**: a single, project-scoped,
**nono-sandboxed `opencode serve`** instance that every harness agent connects
to over HTTP+SSE, started at the beginning of a harness run and disposed when
scope is exhausted or the run exits.

This is the primary backend new harnesses target. The legacy Claude Code
`--print --input-format stream-json --output-format stream-json` streaming
modules remain documented for reference, but where that path spawned one
sandboxed subprocess **per invocation**, the default opencode path spawns one
sandboxed **server per project per run** and multiplexes all agents/sessions
onto it — one wrap site, one inherited boundary. Read
`references/nono-integration.md` first — it is the source of truth for exact
`nono` flags (including the default **`opencode-serve` profile**) and the
preflight check; this document references the `wrap_with_nono` helper rather
than re-specifying nono's CLI.

Applies to opencode `1.17.x` (server API validated against docs dated
2026-06-10). opencode ships multiple releases per week; re-validate the API shape
against `http://<host>:<port>/doc` for your pinned version before trusting any
field below.

---

## 1. Why the server model changes the safety story

The Claude Code streaming path enforces the invariant **per process**: every
`claude -p` invocation must be individually wrapped in `nono run`, and an
unwrapped invocation is a bug the eval catches. That is N wrap sites, N policy
derivations, N chances to drift.

The opencode server path enforces the invariant **once**:

> An opencode server may run with permissions effectively bypassed
> (auto-approve, or `"permission": "allow"`) **if and only if** the `opencode
> serve` process was launched under `nono run` with a least-privilege policy.
> Every session, agent, subagent (child session), `bash` tool call, MCP server,
> and formatter the server spawns is a **child** of that process and therefore
> inherits the kernel boundary irreversibly. No nono wrapper on the server → no
> bypass anywhere.

This is strictly stronger and simpler:

- **One wrap site.** The boundary is applied at `opencode serve` launch. There is
  no per-agent or per-tool wrap to forget.
- **Inheritance does the work.** Landlock (Linux) / Seatbelt (macOS) restrictions
  are inherited by all descendants and cannot be widened by the agent, so the
  server cannot escalate beyond the launch policy regardless of what tools it
  invokes.
- **The eval target shrinks** from "every invocation site across the run" to "the
  single server-launch site," which is far easier to assert and far harder to
  bypass.

The tradeoff: because the boundary is set once and inherited, it is a **single
policy for the whole server lifetime**. You scope filesystem to the project
worktree + the harness dotfiles + opencode's own state dirs, and network to the
model-provider egress + loopback. You cannot narrow per-tool-call at the server
boundary. If you want per-`bash`-call inner narrowing (nesting-to-narrow), that is
the **opencode plugin** layer (`tool.execute.before` re-wrapping the command in a
tighter inner `nono run`), documented separately; it is additive defense-in-depth
and out of scope here. For a project harness, the server-boundary policy is the
primary and sufficient control.

---

## 2. Server topology constraints (these drive the design)

From the opencode server API (`/docs/server`):

- **One server = one Instance = one project root.** The API has a singular
  *current* project (`GET /project/current`), path (`GET /path`), and instance
  (`POST /instance/dispose`). `POST /session` takes only `{ parentID?, title? }`
  — **no directory parameter**. A session inherits the server's project root.
  Therefore: **one sandboxed server per project**, never one server shared across
  projects. This aligns the nono boundary 1:1 with the project, which is what the
  threat model wants anyway.
- **The server roots at its launch cwd.** `opencode serve` has no `--directory`
  flag (only `--port`, `--hostname`, `--mdns`, `--mdns-domain`, `--cors`).
  **Always `cd` into the project root before launching**, or set the child
  process cwd to the project root. Launching from elsewhere can cause the server
  to take `/` as its base directory and expose the whole filesystem through the
  file APIs (known bug; see §10). Under nono this is contained, but a mismatched
  cwd also breaks permission-path matching, so set cwd explicitly.
- **Multiple agents and sessions on one server are free.** Agent is per-prompt
  (`agent` field). Sessions are first-class and concurrent. Subagents are child
  sessions on the same event bus. This is exactly the fan-out a harness needs.
- **Clients connect over HTTP.** Bind `127.0.0.1:<port>` (loopback only),
  protect with `OPENCODE_SERVER_PASSWORD`, and connect any number of harness
  agents/workers to that one base URL.

---

## 3. Server lifecycle state machine

The harness owns the full lifecycle for the duration of a run:

```
            ┌──────────────────────────────────────────────────────────┐
            │                                                            │
  PREFLIGHT ─► LAUNCH ─► READY ─► DRIVE ──► DRAIN ─► DISPOSE ─► TERMINATE ─► REAPED
  (nono ABI) (nono run  (poll   (sessions  (queue   (POST      (SIGTERM →   (waitpid,
   + opencode opencode  health) + agents + empty &  /instance  SIGKILL on   assert no
   on PATH)   serve,    │       SSE +      all      /dispose)  stall, kill  orphans)
              cwd=proj, │       perms +    sessions             process
              loopback) │       completion completed)           group)
                        │       detection)                      │
                        └───────── on fatal error / timeout ────┘
```

State definitions and transitions:

1. **PREFLIGHT** — verify `nono` is present and the Landlock ABI is sufficient
   (`nono setup --check-only`, per `nono-integration.md`); verify `opencode` is on
   PATH and report `opencode --version`. Hard-fail if nono is unavailable unless
   `--allow-unsandboxed` is explicitly set (then the server must run with
   interactive/`ask` permissions, never bypass — same fallback contract as the
   Claude Code path).
2. **LAUNCH** — start `wrap_with_nono(["opencode","serve","--hostname","127.0.0.1",
   "--port", PORT], policy)` with **cwd = project root**, in its **own process
   group** (so the whole tree can be signalled), capturing stdout/stderr to the
   harness log. Pass `OPENCODE_SERVER_PASSWORD` via env, never argv.
3. **READY** — poll `GET /global/health` until `{ healthy: true, version }` or a
   readiness timeout. Do not create sessions before health passes. (Prefer a
   fixed, harness-chosen port over dynamic-port stdout parsing; see §10.)
4. **DRIVE** — for each work item in scope, create a session, prompt the chosen
   agent, consume the SSE event stream, auto-respond to permission requests per
   policy, and detect per-session completion. Sessions may run concurrently up to
   a bounded parallelism (reuse the harness `N` cap).
5. **DRAIN** — scope is exhausted when the work queue is empty **and** every
   in-flight session has reached completion (`info.time.completed` set, no
   `info.error`). Abort any session that exceeds its per-session deadline
   (`POST /session/:id/abort`) before declaring drain.
6. **DISPOSE** — `POST /instance/dispose` to ask the server to shut down cleanly.
7. **TERMINATE** — if the process has not exited within the shutdown grace window,
   escalate `SIGTERM → SIGKILL` to the **process group** (mirrors the Claude Code
   bridge watchdog). This reaps bash/MCP/subagent children too.
8. **REAPED** — `waitpid`/`Wait`, then assert no orphaned descendants remain
   (the eval checks this).

Any fatal error in DRIVE/DRAIN jumps to DISPOSE → TERMINATE; the server is never
left running after a harness run exits.

---

## 4. nono policy for the server boundary

The boundary is codified as the **`opencode-serve` nono profile** — the single
source of truth for the server's least-privilege set. Its full JSON, a
grant-by-grant rationale, and the canonical launch command live in
`references/nono-integration.md` § "opencode server boundary". This section
states *what* the boundary covers; that section states the *exact flags*.

The profile extends `default` (carrying all the `deny_*` credential /
shell-history / browser-data groups) and adds only:

**Filesystem:**
- `project_root` — shared via `workdir.access: readwrite` + `--allow-cwd` at
  launch (the server roots at its launch cwd; see §2). For a worktree outside
  CWD, add `--allow <worktree>` from the same source variable. The harness
  dotfiles (`.harness/`, `.bug-burndown/`, `.iteratotron/`,
  `.test-effectiveness/`) live under `project_root` and are covered by it.
- opencode state the server reads/writes: `~/.config/opencode` (config, agents,
  plugins), `~/.local/share/opencode` (SQLite store, `auth.json`, server log —
  confirm with `opencode db path`), `~/.cache/opencode` (caches). All three are
  `filesystem.allow` entries in the profile.
- Toolchain/runtime read access via groups `nix_runtime` (binary + Bun +
  `libstdc++` + LSP resolution on Nix hosts), `opencode_linux` (`~/.opencode/bin`),
  and `git_config`.

**Filesystem (deny):** everything else — other project roots, `$HOME` at large,
and `/` — enforced by `default`'s allow-list model. opencode denies `.env` by
default; keep it.

**Network:** the profile sets `network_profile: null` — opencode talks to
**whatever model provider the run configured** (Anthropic, OpenAI, a GitLab Duo
endpoint, a local model, …), so there is no fixed provider host to pin. nono's
always-on proxy still blocks cloud-metadata (`169.254.169.254`). To *narrow*
egress to a known provider for a run, add that host via `--allow-domain <host>`
(or `network.allow_domain` in a project-specific profile) and record it in the
manifest — do not reintroduce the Claude Code `--network-profile claude-code`.
Loopback is granted via `--open-port <PORT>` (connect + listen) for the HTTP/SSE
client and any local MCP/LSP. Note the inheritance tradeoff: every `bash` call
inherits this egress, so if a work item needs a registry (`cargo`, `go mod`,
`bundle`), add that specific host explicitly and record it.

**cwd:** the child process cwd **must** be `project_root` (see §2 / §10).

`wrap_with_nono(argv, project_root)` returns the fully wrapped argv —
`["nono","run","--silent","-p","opencode-serve","--allow-cwd","--open-port",PORT,
…,"--","opencode","serve",…]` — with the port and any extra `--allow` /
`--allow-domain` derived from one source variable. Record the realized policy
(profile name, paths, `open_port`, any `allow_domain` hosts) in the run manifest
so provenance stays honest about which boundary was enforced.

---

## 4.1 Capability provisioning — the server must be able to actually FIX things

> **The invariant that makes the whole loop worth running:** the sandboxed
> opencode server must have access to the **skills, LSP servers, plugins, and
> agentic model** the fix agent needs. A harness that captures defects but
> dispatches them to a server that cannot load the bug-burndown/bugfix skill,
> cannot run the project's LSP, or runs a chat-only model is **pointless** — it
> will observe failures and fix nothing. Isolation and capability are two
> different axes; getting one right at the cost of the other breaks the loop.

This is the single most consequential thing to get right when **building or
migrating** a harness, and the easiest to break. It was broken on vulnmapper
(iter-001, 2026-06-13): to stop the operator's global config (MCP servers via
uvx, a completion-loop plugin doing `npm install`) from `EACCES`-ing under the
sandbox, the server was pointed at a minimal isolated `XDG_CONFIG_HOME` with
`"mcp": {}, "plugin": []` **and no skills directory**. The burndown bridge then
dispatched the `bug-burndown` skill against a server that could not see it. The
agent had nothing to load, produced **0 output tokens and 0 tool calls**, went
idle — and the loop recorded "completed" and advanced, leaving **all 133
captured high-severity findings unfixed**. The capture half worked perfectly;
the fix half was a silent no-op.

### Use the operator's real config — ALL skills, ALL LSPs available

> **Default to the operator's real `~/.config/opencode`, not a minimal isolated
> copy.** The iter-001 fix over-corrected: it isolated the config so hard that it
> stripped the very skills the fix agent needed. The right model is the opposite
> — the sandboxed server runs against the operator's **real** config so that
> **every** host skill, **every** configured LSP, and the operator's agents are
> available, exactly as they are in an interactive opencode session. The nono
> profile is what keeps this safe: it loosens *capability* (skills, LSPs,
> toolchains, caches) while `default`'s `deny_*` groups and the `.env` deny keep
> *secrets* out of reach. Don't isolate the config to solve a sandbox problem —
> widen the sandbox to cover what the real config touches.

The original isolation existed only to stop a handful of config entries from
`EACCES`-ing under nono — an MCP server doing `uvx` into `~/.cache/uv`, a plugin
running `npm install` into `~/.npm`. The fix for *those* is to grant their
write dirs (or disable just those entries), **not** to throw away every skill
and language server.

When wiring the server's config, in priority order:

1. **Point `XDG_CONFIG_HOME` at the operator's real config** (the default — do
   **not** set a minimal isolated `XDG_CONFIG_HOME`). The server then discovers
   all skills under `~/.config/opencode/skills/`, all LSP definitions, and the
   operator's agents. Grant `~/.config/opencode` `readwrite` in the
   `opencode-serve` profile so they load without EPERM. This is what makes
   `bug-burndown`, its `bugfix` delegate, **and** any other skill the run needs
   available without a hand-picked copy step.
2. **Keep `"lsp": true` and grant every configured LSP's binary dir.** Don't
   enumerate one project LSP — the run may touch several languages. On Nix hosts
   the LSP servers (gopls, rust-analyzer, pyright, …) resolve from `/nix/store`
   via the profile's `nix_runtime` group; on other hosts the toolchain `--read`
   dirs (per-language table in `nono-integration.md`) cover them. Never
   blanket-disable LSP "to keep it lean" — the fix agent needs diagnostics.
3. **Disable only the specific config entries that break under the sandbox**,
   and grant the write dirs of the ones you keep. If an MCP server or plugin
   insists on writing outside the allow set and you can't grant its dir, set just
   that entry off via a thin config overlay (an `opencode.json` under the project
   root that the run layers on top) — strip the *offending entry*, never the
   whole skills/LSP surface. Most plugins are fine once their cache dir is
   granted; reach for disabling last.
4. **A missing *required* skill is still a HARD ERROR at launch.** With the real
   config this is rare (all host skills are present), but if `bug-burndown` or
   `bugfix` genuinely isn't installed, fail the launch with a clear message
   ("install skill X in `~/.config/opencode/skills/`") rather than no-op'ing.
5. **Auth is separate from config.** The Duo/Anthropic credential lives under
   `~/.local/share/opencode/auth.json` (XDG_DATA, not XDG_CONFIG) — keep
   `~/.local/share/opencode` in the profile's allow set regardless.

If you *must* isolate (e.g. a CI host where the operator config is untrusted),
provision **all** host skills into the isolated dir, not a hand-picked subset:
copy the whole `~/.config/opencode/skills/` tree (copy, don't symlink, so it
stays under the project root and inside the allow set) and keep `"lsp": true`.
A hand-picked skill subset is itself a defect — it's how iter-001 happened.

### The fix agent must be tool-capable, and invoked as a skill

- **Model — pick a model the opencode provider exposes as tool-capable.** The
  burndown/fix agent edits files and runs tests, so it must use a model that the
  provider serves with tool-calling enabled. What "tool-capable" means is
  **provider-specific** — encode the model in the agent definition for
  determinism (§10: `agent` + `model` together can be ignored), and verify with
  the no-op guard below rather than trusting a naming convention.

  **GitLab Duo (`providerID: "gitlab"`).** Use the **`duo-chat-*` tier**, and
  **default everything to Haiku**. **⚠ The id has NO `claude-` segment** on the
  currently-observed servers (opencode 1.17.x): it is **`gitlab/duo-chat-haiku-4-5`**
  (and the escalation is **`gitlab/duo-chat-sonnet-4-6`**) — **NOT**
  `duo-chat-claude-haiku-4-5`/`duo-chat-claude-sonnet-4-6`, which 404 with
  `ProviderModelNotFoundError: Model not found: … Did you mean: duo-chat-haiku-4-5, …`.
  Older docs/snapshots (and this file's pre-1.17 history) said
  `duo-chat-claude-haiku-4-5`; that name is stale — the `claude-`/`gpt-`/`opus-`
  vendor infix drifts release-to-release, so **do not hardcode it.** **Verify the
  exact ids your server exposes** with `GET /config/providers` (walk
  `.providers[] | select(.id=="gitlab") | .models | keys`) at scaffold/audit
  time and pick the Haiku-tier chat id from *that* list. Use the chosen id for
  fix/burndown, genesis, iteratotron dispatch, *and* the reviewer passes.
  **Never default to Opus.** Raise to the sonnet-tier chat id **only** for the
  rare, genuinely very complex burn or root-cause hunt where Haiku has
  demonstrably stalled. The opencode `gitlab` provider drives the chat models
  through the agentic tool loop, and they make real tool calls. **Do not default
  to the `duo-workflow-*` tier** even though its name reads "agentic": on the
  observed servers `duo-workflow-opus-4-6` returns an *empty* completion
  (`input>0, output:0, finish:"stop"`, zero tool-use parts), which the no-op
  guard correctly fails as `WorkRemaining` — a wasted iteration, not a fix.
  Treat `duo-chat-*` as the working default for Duo; only reach for a
  `duo-workflow-*` id if you've confirmed *that specific id* makes tool calls on
  *your* server via the no-op guard.

  > **A wrong model id must FAIL FAST, not ride the deadline (the 2026-07-09
  > gitlab-e2e-rs incident).** A bad id (`gitlab/duo-chat-claude-haiku-4-5` on a
  > server that only has `duo-chat-haiku-4-5`) makes **every** prompt emit a
  > `session.error` with `ProviderModelNotFoundError` and **no** assistant
  > message — so a driver that only watches the completion legs sees
  > `tool_calls=0`, never completes, and rides the per-session deadline (observed:
  > 20+ min of `drive alive … tool_calls=0 last_tool=`). The driver **must**
  > classify `session.error` (and `*.step.failed`) as a hard turn-end failure,
  > capture `error.data.message`, abort, and return it — turning a silent
  > multi-hour hang into an instant, named failure. See §16.2 (the classifier
  > must handle `session.error`) and §16.3 (the stall watchdog is the backstop).

  > **`Unknown model ID … must be registered in MODEL_MAPPINGS` is a
  > version-skew bug, not a bad model choice.** `MODEL_MAPPINGS` lives in
  > GitLab's server-side Duo Workflow / AI Gateway, *not* in opencode. The
  > opencode model **catalog** (`opencode models`, from `models.dev`/provider
  > metadata) is broader than, and drifts from, what a given gateway build has
  > mapped — so a model id can appear in the catalog yet be rejected by the
  > gateway the harness's `opencode serve` talks to. The usual cause is the
  > harness running an **older pinned opencode** than your interactive shell:
  > e.g. `duo-chat-haiku-4-5` is accepted by a current opencode but rejected by a
  > stale 1.4.x server even though both `opencode models` lists show it. *Fix:*
  > upgrade the opencode the harness launches (check the devshell/Nix pin —
  > `pkgs.opencode` from the locked nixpkgs rev can shadow your system
  > opencode), don't blindly downgrade the model. *Confirm* by probing the id
  > against the actual server build (`POST /session` → `POST /session/:id/message`
  > with the model; a `session.error` carrying `Unknown model ID` means that
  > build's gateway lacks it). This is the 2026-06-16 version-skew incident: a
  > harness on opencode 1.4.0 rejected the chat id with `MODEL_MAPPINGS`
  > while the same id worked in an interactive 1.16.2 session.

  **Direct Anthropic (`providerID: "anthropic"`).** Only reach for the direct
  Anthropic API when the requirement specifically calls for it (Duo is the
  preferred path). Use a current tool-capable Claude model and **default to
  `anthropic/claude-haiku-4-5`** for fix/burndown/genesis, iteratotron dispatch,
  *and* reviewer passes. **Never default to Opus.** Raise to
  `anthropic/claude-sonnet-4-5` **only** for the rare, genuinely very complex
  task where Haiku has demonstrably stalled. (Adjust to the latest GA ids
  the operator's `auth.json` is entitled to; all current Claude 4.x models are
  tool-capable.) Requires an Anthropic API key in
  `~/.local/share/opencode/auth.json` and `api.anthropic.com` in the nono egress
  allow-list.

  Whatever the provider, the rule is the same: **a fix turn that makes zero tool
  calls is a failure** (next bullet), and the model id is chosen to satisfy that
  guard, not to match a `*-workflow-*` substring.
- **Invocation shape:** `bug-burndown` is an opencode **skill** (loaded via the
  `skill` tool), **not** a `/`-slash command. Do not dispatch a bare
  "/bug-burndown resume:<id>" string — opencode does not act on it and the model
  stops with zero tool calls. Prompt the agent to *load and run the bug-burndown
  skill* against the harness-written session, naming the session manifest and
  verdicts paths explicitly.

### Verify the fix actually did something — the no-op guard

Completion detection (the three-way AND in §5) tells you the turn **ended**, not
that it **did work**. Track the number of tool-use parts (`type ∈ {tool,
tool_use}`, deduped by part id) the assistant emitted, and surface the count on
the run result. After a fix turn:

> **`tool_calls == 0` ⇒ fail the burndown loudly**, do not report success and
> advance. Zero tool calls means the agent edited no file, ran no test, and
> likely never loaded its skill. The error message must name the likely causes:
> skill not discoverable on the server, fix agent lacks the required tools/LSP,
> or the configured model returns empty/no-tool completions on this provider
> (e.g. Duo `duo-workflow-opus-4-6` returning `output:0` — switch to the
> `duo-chat-*` tier; see §4.1). This guard is what converts the iter-001 silent
> no-op into an actionable launch/dispatch failure.

The eval (§8) asserts all of the above.

### Observability — log *what* the agent does, not just that it's busy

The no-op guard is a count; an operator tailing the harness needs to see the
work happen in real time. Two requirements, both MANDATORY for the server
backend:

1. **Per-tool-call INFO line with a per-tool detail summary — MANDATORY in
   EVERY phase.** When a deduped `message.part.updated` tool-use part arrives,
   emit one INFO line carrying the tool **name** *and* a summary that captures
   the tool's **distinguishing parameters**, not merely its first string field.
   This requirement is not specific to the burndown phase: it holds identically
   for the reviewer drive, the genesis/iteratotron drive, the done-gate drive,
   and every dispatched subagent. An operator tailing **any** phase must be able
   to reconstruct what the agent did to the codebase from the INFO stream alone.

   The summary must be **per-tool aware** — a single "first string field"
   fallback is insufficient and is an audit finding. For each known tool, log the
   parameter(s) that make the call meaningful and reviewable:

   | Tool | Log (in priority order) | Example INFO target |
   |---|---|---|
   | `edit` | `filePath` **+** a change indicator: `replaceAll` flag and/or a short oldString→newString preview | `target=src/foo.rs replaceAll=false "old_fn"→"new_fn"` |
   | `write` | `filePath` **+** content size in bytes/lines (so a full-file overwrite is visible without dumping the body) | `target=src/foo.rs (new, 412 bytes)` |
   | `read` | `filePath` **+** `offset`/`limit` when present | `target=src/foo.rs offset=200 limit=100` |
   | `bash` | the full `command` (collapsed to one line) **+** `description` when present | `target=cargo test -p gitlab-core (run core tests)` |
   | `grep` | `pattern` **+** `path`/`include` when present | `target=/TODO/ include=*.rs path=src` |
   | `glob` | `pattern` **+** `path` | `target=**/*.rs path=crates` |
   | `skill` | skill `name` | `target=bug-burndown` |
   | `webfetch` | `url` **+** `format` | `target=https://… (markdown)` |
   | `task` / subagent | `subagent_type` **+** `description` | `target=explore "find auth handlers"` |
   | `todowrite` | the count of todos and a one-line digest of the in-progress item | `target=7 todos (in_progress: wire scenario rejects)` |
   | _unknown_ | every string/bool/number field as `k=v` pairs (NOT just the first) | `target=foo=1 bar=baz` |

   The point is that a **codebase-mutating** call (`edit`/`write`/`bash`) must be
   the most detailed of all: the file touched, whether it was a full overwrite or
   a scoped edit, and for `bash` the exact command — because these are the calls
   that change the project, and the reviewer/audit phase reconstructs the change
   from this stream. Treat a bare `agent tool call tool=edit` (no file, no change
   shape) or `tool=bash` (no command) as the canonical observability defect.

   Mechanics that still apply to every field above: the summary is collapsed to a
   single line (whitespace runs → one space, so a heredoc doesn't span lines) and
   each captured value is truncated (~160 chars + ellipsis) so one tool call is
   one readable line and never floods the log with a multi-KB file body. The tool
   args live under `part.state.input` in the live schema (fall back to
   `part.input`). Defer the log until a snapshot carries the parameters (the
   pending → running-with-input → completed streaming means the first snapshot is
   usually empty), log at most once per part id, and if the part completes having
   never carried its input, log once with what's available so a call is **never
   silently dropped**.

2. **Liveness heartbeat at INFO.** A genesis/burndown turn legitimately runs for
   many minutes between dispatch and completion emitting no INFO lines — to an
   operator on the default `info` log that reads as a freeze. Run a periodic
   (~30s) heartbeat that proves the drive loop is still polling: log
   `elapsed_secs`, `idle_secs` (time since the last classified frame for this
   session, *not* since loop start), `no_progress_secs` (time since the last
   genuine forward-motion frame — a new tool call or fresh assistant text — which
   the settled-completion fallback also reads), the running `tool_calls` count,
   and `last_tool` (the most recent tool **and its full detail summary** from the
   table above, e.g. `bash(cargo test -p gitlab-core)` or
   `edit(src/foo.rs "old"→"new")` — never a bare `edit`). Bias the event-select
   toward draining frames over firing the heartbeat so completion is still
   observed promptly.

Both are unit-testable on the pure classifier, and the test set is **not
optional**: assert the detail summary picks the right parameter(s) **for each
known tool in the table above** (one test per tool family is the standard),
that `edit`/`write`/`bash` carry their change-shape/command detail (not just the
file path), that newlines collapse, that an over-long value truncates, and that
an unknown tool emits its full `k=v` field set (not just the first string).
Canonical implementations: `the reference harness/src/opencode_server.rs`
(`tool_target_summary` + the `ToolUse { part_id, tool, target }` signal + the
heartbeat arm of `run_event_loop`) and `gitlab-harness/src/opencode_server.rs`
(`tool_target` + the deferred-log gate in the `message.part.updated` arm). Tee
every raw SSE frame to the per-session forensic log (`<iter>/burndown.log`)
regardless, so the INFO stream stays readable while the full record is on disk
for the reviewer/audit phase.

3. **Don't double-log across the bridge routers.** Because the shared drive
   loop (`RunPrompt` / `run_event_loop`) now logs every tool call (with target),
   streamed text, permission decisions, idle, and errors at INFO for **every**
   session, a per-bridge event router (`routeBurndownEvent` / `routeGenesisEvent`
   / a reviewer sink) must **not** re-log those — doing so doubles every line in
   the harness log, and the bridge copy is usually the *less* informative one
   (tool name without the target). Keep the bridge router minimal: its only
   distinct job is the verbatim raw-frame dump to the per-session forensic file
   (done by the sink before the router runs). A no-op `func routeXEvent(_ Event)
   {}` with a comment explaining why is the correct shape once the generic driver
   owns observability. This is the 2026-06-16 genesis-double-log gap (the burndown
   router was already minimal; the genesis router still re-logged tool calls
   without the target).

---

## 5. The driver API contract (language-independent)

Every per-language driver implements the same minimal contract against the server.
Base URL is `http://127.0.0.1:<port>`; all requests carry HTTP basic auth
(`opencode:$OPENCODE_SERVER_PASSWORD`).

**Readiness**
- `GET /global/health` → `{ healthy: true, version }`. Poll until healthy.

**Session management**
- `POST /session` body `{ title? }` → `Session` (read `id`, e.g. `ses_…`).
- `POST /session/:id/abort` → cancel an in-flight turn before a deadline kill.
- `GET /session/:id/todo` → `Todo[]` (used in completion detection).
- `DELETE /session/:id` → exists, but **do NOT use it.** Deleting a live
  session races the server's own background writes for `prompt_async` turns and
  corrupts the store with cascading FOREIGN KEY failures. Reclaim the store by
  disposing the server instance at run end, never per-session. See §13.2.

**Prompting an agent** (pick one per work item)
- Async (preferred for concurrent fan-out): `POST /session/:id/prompt_async`,
  body below, returns **204 No Content**. Observe results over SSE.
- Sync (simplest for serial items): `POST /session/:id/message`, same body,
  returns `{ info: AssistantMessage, parts: Part[] }` when the turn completes.

Prompt body (both endpoints):
```jsonc
{
  "agent": "build",                 // or your custom reviewer/bugfix agent
  "model": { "providerID": "anthropic", "modelID": "claude-…" }, // optional; omit to use agent default
  "system": "…",                    // optional system-prompt override
  "tools": { "bash": true },        // optional per-prompt tool gating
  "parts": [ { "type": "text", "text": "<the agent prompt>" } ]
}
```
Caveat: if both `agent` and `model` are sent, opencode has historically let the
agent's fallback model win over the explicit `model` (issue #18615). Prefer
encoding the model in the agent definition for determinism.

**Event stream**
- `GET /event` → SSE. First frame is `server.connected`; then bus events;
  ~30s heartbeats; closes on instance dispose. Parse each `data:` line as JSON
  and read the event discriminator (a top-level `type` field in the JSON
  payload; if your pinned version puts the name in the SSE `event:` field
  instead, fall back to that — confirm against `/doc`).

> **⚠ The `properties` envelope (validated against opencode 1.15.13 — vulnmapper 2026-06-12).**
> Every event payload nests its attributes under a `properties` key. The wire
> shape is:
> ```json
> {"id":"evt_…","type":"message.updated","properties":{"sessionID":"ses_…","info":{…}}}
> ```
> `type` is top-level; **every** field the driver reads — `info`, `sessionID`,
> `part`, `delta`, `status`, `error` — lives inside `properties`. Read them at
> the top level and they are all `nil`: `message.updated`'s `info` is missing,
> the completion signal is never observed, the three-way AND never fires, and
> **every prompt runs to the per-prompt deadline** and returns `"context
> deadline exceeded"`. This is exactly what a whole reviewer run looks like when
> it's broken — 28 batches, each failing at the 5-minute mark.
>
> **Unwrap once, at parse time**, so every downstream handler sees a flat
> payload (and keep a fallback to the raw map in case a future build drops the
> envelope):
> ```go
> payload := data
> if props, ok := data["properties"].(map[string]any); ok {
>     payload = props
> }
> out <- Event{Kind: kind, Data: payload}
> ```
> Re-confirm against `/doc` and a live `GET /event` capture after any opencode
> bump; the envelope is not in the generated OpenAPI schema as a wrapper.

- Relevant events and the fields the driver needs (all **inside `properties`**).
  > **⚠ This list is a per-version SNAPSHOT — the `type` discriminators drift
  > across opencode builds and providers. Validate against the running server's
  > `/doc` Event union for your pinned version and handle every vocabulary your
  > targets use. opencode 1.16.x emits a whole `session.next.*` turn-lifecycle
  > family, plus first-class `question.asked` / `permission.asked` events (NOT
  > `permission.updated`) — a driver hardcoded to the names below sees those as
  > `Other`, never completes, and hangs to the deadline. Full incident, the dual
  > tool vocabulary, the stall watchdog, and the forensic-frame-log safety nets:
  > §16.**
  - `message.part.delta` → `{ sessionID, messageID, partID, field, delta }` —
    streaming output. `delta` is the text chunk; **`field` is `"text"` only for
    answer text** (it is also emitted for `reasoning` etc., which must not be
    folded into the reply). Attribute via `messageID`.
  - `message.part.updated` → `{ sessionID, part }` — a full-text *snapshot* of a
    part (`part.text`). Do **not** accumulate both deltas and snapshots or you
    double-count the text; prefer deltas and ignore the snapshots, or vice
    versa, but not both.
  - `message.updated` → `{ sessionID, info }` — fires for **both** the user
    message (`info.role == "user"`, no `time.completed`) and the assistant reply
    (`info.role == "assistant"`). Guard on `role == "assistant"`; completion is
    when the assistant message has `info.time.completed` set and no `info.error`.
    The user message also emits `message.part.*` echoing the prompt text — filter
    parts by the assistant `info.id` (the `messageID`) or the prompt prepends
    itself to your answer.
  - `session.idle` → `{ sessionID }` — secondary completion signal (not
    authoritative alone; can fire early).
  - `session.status` → `{ sessionID, status }`, `status.type ∈ {idle,busy,retry}`.
    `retry` means still working (backing off), not awaiting input.
  - `session.error` → `{ sessionID?, error? }` — note `sessionID` may be absent.
  - `permission.updated` → full `Permission` `{ id, type, pattern?, sessionID,
    messageID, callID?, title, metadata, time }` — requires a response.
  - `permission.replied` → `{ sessionID, permissionID, response }`.

**Permission auto-response** (the unattended-run policy)
- `POST /session/:id/permissions/:permissionID` body `{ response, remember? }`
  where `response ∈ { "once", "always", "reject" }`. `always` persists the
  suggested `pattern`; `reject` fails the call with feedback the agent can see.
- Driver policy: maintain an **allowlist** (tool + pattern). On
  `permission.updated`, respond `always` if the request matches the allowlist,
  else `reject`, and append every decision to the run audit log. This is safer and
  more auditable than blanket bypass. Blanket bypass (`"permission":"allow"` in
  config, or `opencode run --dangerously-skip-permissions`) is acceptable **only**
  because the server is under nono — but prefer the allowlist for the audit trail.

**Completion detection (authoritative)**
A session/work item is complete when **all** hold:
1. the assistant message for the prompt has `info.time.completed` set and no
   `info.error` (from sync response, or `message.updated` over SSE), **and**
2. `session.idle` has fired for that `sessionID` (or `GET /session/status`
   reports `idle`), **and**
3. `GET /session/:id/todo` is empty (guards against premature idle while a plan
   is still pending).
Treat `retry` status as in-progress. If you injected a follow-up prompt on idle,
re-arm detection (idle handlers are fire-and-forget server-side; the driver, not
the server, owns the loop).

**Clean shutdown**
- `POST /instance/dispose` → `boolean`. Then terminate the process group with the
  watchdog (§3.7).

---

## 6. Per-language driver modules

Each module mirrors the lifecycle in §3 and the contract in §5. None of Rust,
Ruby, or Go has a first-party opencode SDK in 1.17.x (only JS/TS, Go, and Python
are generated — and the Go one tracks `dev`), so the **portable core is raw
HTTP + SSE**, which also matches the skill's existing "speak the wire protocol
directly" streaming-module style. Go may optionally use the generated SDK; the
example below stays on `net/http` for parity and zero extra deps.

These are paste-ready skeletons (`opencode_server.{rs,go,rb}`), not toy snippets;
wire them to the harness's existing logging, worktree, and `N`-parallelism
plumbing. They call `wrap_with_nono` from the skill's shared helper.

### 6.1 Rust — `opencode_server.rs`

```rust
//! Project-scoped, nono-sandboxed opencode server driver.
//! deps: tokio (rt, process, time), reqwest (json, stream), serde_json,
//!       eventsource-stream, futures-util, nix (signals/process group), anyhow.

use std::process::Stdio;
use std::time::Duration;
use anyhow::{anyhow, Context, Result};
use eventsource_stream::Eventsource;
use futures_util::StreamExt;
use nix::sys::signal::{killpg, Signal};
use nix::unistd::{setsid, Pid};
use serde_json::{json, Value};
use tokio::process::{Child, Command};
use tokio::time::{sleep, timeout};

pub struct ServerHandle {
    child: Child,
    pgid: Pid,
    pub base_url: String,
    pub password: String,
    http: reqwest::Client,
}

/// Build the wrapped argv via the skill's shared helper (defined elsewhere).
/// Returns e.g. ["nono","run", <policy flags>, "--", "opencode","serve", ...].
fn wrap_with_nono(argv: &[&str], project_root: &str) -> Vec<String> {
    // Delegates to references/nono-integration.md flag derivation.
    crate::nono::wrap_with_nono(argv, project_root)
}

impl ServerHandle {
    pub async fn launch(project_root: &str, port: u16, password: &str) -> Result<Self> {
        // PREFLIGHT (nono ABI + opencode presence) is asserted by the caller.
        let inner = [
            "opencode", "serve",
            "--hostname", "127.0.0.1",
            "--port", &port.to_string(),
        ];
        let wrapped = wrap_with_nono(&inner, project_root);
        let (cmd0, args) = wrapped.split_first().ok_or_else(|| anyhow!("empty argv"))?;

        let mut command = Command::new(cmd0);
        command
            .args(args)
            .current_dir(project_root)                 // §2: cwd MUST be project root
            .env("OPENCODE_SERVER_PASSWORD", password)  // never via argv
            .env("OPENCODE_DISABLE_AUTOUPDATE", "1")
            .stdin(Stdio::null())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());
        unsafe {
            command.pre_exec(|| {
                setsid().map(|_| ()).map_err(|e| std::io::Error::from_raw_os_error(e as i32))
            });
        }
        let child = command.spawn().context("spawn nono-wrapped opencode serve")?;
        let pid = child.id().ok_or_else(|| anyhow!("no child pid"))? as i32;
        let pgid = Pid::from_raw(pid);

        let handle = Self {
            child,
            pgid,
            base_url: format!("http://127.0.0.1:{port}"),
            password: password.to_string(),
            // Bound the connect + header wait so a hung control request can't
            // stall the loop forever. Do NOT set a blanket `.timeout(...)`: it
            // covers the whole exchange incl. body and would sever the
            // long-lived /event SSE stream. `connect_timeout` + a
            // `read_timeout` bound the dial and the inter-byte gap (the points
            // the nono supervisor proxy can hang right after launch) while
            // letting a steadily-streaming SSE body run as long as it likes.
            // Same lesson as the Go newHarnessHTTPClient — a no-timeout client
            // is the "harness stalls after launching opencode" hang.
            http: reqwest::Client::builder()
                .connect_timeout(Duration::from_secs(10))
                .read_timeout(Duration::from_secs(15))
                .build()?,
        };
        handle.wait_healthy(Duration::from_secs(30)).await?;
        Ok(handle)
    }

    fn req(&self, m: reqwest::Method, path: &str) -> reqwest::RequestBuilder {
        self.http
            .request(m, format!("{}{path}", self.base_url))
            .basic_auth("opencode", Some(&self.password))
    }

    async fn wait_healthy(&self, budget: Duration) -> Result<()> {
        let deadline = tokio::time::Instant::now() + budget;
        loop {
            if tokio::time::Instant::now() > deadline {
                return Err(anyhow!("opencode server failed health within budget"));
            }
            if let Ok(resp) = self.req(reqwest::Method::GET, "/global/health").send().await {
                if resp.status().is_success() {
                    if let Ok(v) = resp.json::<Value>().await {
                        if v.get("healthy").and_then(Value::as_bool) == Some(true) {
                            return Ok(());
                        }
                    }
                }
            }
            sleep(Duration::from_millis(200)).await;
        }
    }

    pub async fn create_session(&self, title: &str) -> Result<String> {
        let v: Value = self
            .req(reqwest::Method::POST, "/session")
            .json(&json!({ "title": title }))
            .send().await?.error_for_status()?.json().await?;
        v.get("id").and_then(Value::as_str).map(str::to_string)
            .ok_or_else(|| anyhow!("session create: missing id"))
    }

    pub async fn prompt_async(
        &self, session: &str, agent: &str, model: Option<&str>, text: &str,
    ) -> Result<()> {
        let mut body = json!({
            "agent": agent,
            "parts": [ { "type": "text", "text": text } ],
        });
        // The model field is { providerID, modelID } — BOTH keys (§10). A bare
        // { modelID } 400s every prompt with `Missing key at
        // ["model"]["providerID"]` and the reviewer reads it as a total outage.
        if let Some(m) = model { body["model"] = model_field(m)?; }
        let resp = self
            .req(reqwest::Method::POST, &format!("/session/{session}/prompt_async"))
            .json(&body)
            .send().await?;
        if resp.status().as_u16() != 204 {
            // capture the body — a 400 names the missing key / bad model id
            let code = resp.status().as_u16();
            let b = resp.text().await.unwrap_or_default();
            return Err(anyhow!("prompt_async status {code}: {}", b.trim()));
        }
        Ok(())
    }
}

/// `provider/model` -> `{ providerID, modelID }` (split on the FIRST `/` so a
/// modelID containing `/` survives). opencode requires both keys; a bare model
/// with no provider is an operator error, rejected loudly rather than sent in a
/// shape the server 400s on. Unit-test: both keys emitted, first-slash split,
/// bare-model rejected. See §10 "the `model` field is { providerID, modelID }".
fn model_field(model: &str) -> Result<Value> {
    let (provider, id) = model.split_once('/')
        .ok_or_else(|| anyhow!("model `{model}` must be `provider/model` (e.g. \
            gitlab/duo-chat-haiku-4-5); opencode requires providerID and modelID"))?;
    if provider.is_empty() || id.is_empty() {
        return Err(anyhow!("model `{model}` has an empty provider or id"));
    }
    Ok(json!({ "providerID": provider, "modelID": id }))
}

impl ServerHandle {
    pub async fn respond_permission(&self, session: &str, perm: &str, decision: &str) -> Result<()> {
        self.req(reqwest::Method::POST,
                 &format!("/session/{session}/permissions/{perm}"))
            .json(&json!({ "response": decision, "remember": decision == "always" }))
            .send().await?.error_for_status()?;
        Ok(())
    }

    pub async fn todo_empty(&self, session: &str) -> Result<bool> {
        let v: Value = self
            .req(reqwest::Method::GET, &format!("/session/{session}/todo"))
            .send().await?.error_for_status()?.json().await?;
        Ok(v.as_array().map(|a| a.is_empty()).unwrap_or(true))
    }

    pub async fn abort(&self, session: &str) -> Result<()> {
        self.req(reqwest::Method::POST, &format!("/session/{session}/abort"))
            .send().await.ok();
        Ok(())
    }

    /// Consume the SSE bus until `should_stop` returns true. `on_event` receives
    /// every parsed event; the driver uses it for streaming output, permission
    /// auto-response, completion bookkeeping, and error capture.
    ///
    /// ⚠️ MULTI-SESSION HARNESSES: opencode does NOT multiplex `/event`. This
    /// skeleton opens one `GET /event` connection per call, which is fine for a
    /// single-session driver but leaks one server-side Bus listener per session
    /// in a long genesis/burndown run (MaxListenersExceededWarning at ~11). For
    /// any harness that observes many sessions, refactor to ONE long-lived
    /// shared reader + an in-process broadcast fan-out. Do NOT delete sessions
    /// per-finish (it corrupts the store — §13.2); reclaim via server dispose at
    /// run end. See §13 (Session & event-stream lifecycle).
    pub async fn run_event_loop<F, S>(&self, mut on_event: F, mut should_stop: S) -> Result<()>
    where
        F: FnMut(&str, &Value),
        S: FnMut() -> bool,
    {
        let resp = self.req(reqwest::Method::GET, "/event").send().await?;
        let mut stream = resp.bytes_stream().eventsource();
        while let Some(ev) = stream.next().await {
            let ev = ev.context("sse frame")?;
            let data: Value = serde_json::from_str(&ev.data).unwrap_or(Value::Null);
            // Prefer JSON `type`; fall back to the SSE event field.
            let kind = data.get("type").and_then(Value::as_str)
                .map(str::to_string)
                .unwrap_or_else(|| ev.event.clone());
            // opencode (1.15.13) nests every attribute under `properties`;
            // only `type` is top-level. Hand the handler the unwrapped payload
            // so it reads info/sessionID/part/delta directly — otherwise
            // completion is never detected and prompts run to their deadline.
            // Fall back to the raw value if a build drops the envelope.
            let payload = data.get("properties").cloned().unwrap_or(data);
            on_event(&kind, &payload);
            if should_stop() { break; }
        }
        Ok(())
    }

    /// DISPOSE → TERMINATE with watchdog. Idempotent; safe in Drop-style cleanup.
    pub async fn shutdown(mut self, grace: Duration) -> Result<()> {
        let _ = self.req(reqwest::Method::POST, "/instance/dispose").send().await;
        match timeout(grace, self.child.wait()).await {
            Ok(Ok(_status)) => {}
            _ => {
                let _ = killpg(self.pgid, Signal::SIGTERM);
                if timeout(Duration::from_secs(5), self.child.wait()).await.is_err() {
                    let _ = killpg(self.pgid, Signal::SIGKILL);
                    let _ = self.child.wait().await;
                }
            }
        }
        Ok(())
    }
}
```

Driver-side completion bookkeeping (sketch) using the event loop, against the
**unwrapped** payload (see the `properties` envelope warning in §5): keep a
per-session struct `{ message_completed: bool, idle: bool }`; on
`message.updated` **where `info.role == "assistant"`** with `info.time.completed`
set and no `info.error` → `message_completed = true` (the user message also
fires `message.updated`, with no `completed` — don't let it through); on
`session.idle` → `idle = true`; on `permission.updated` → match allowlist and
call `respond_permission`; on `session.error` → record and abort. Accumulate
reply text from `message.part.delta` with `field == "text"` belonging to the
assistant `messageID` only (the echoed user prompt streams under a different
`messageID`, and folding in the `message.part.updated` snapshots double-counts).
A session is done when `message_completed && idle && todo_empty(session).await?`.
The run is done when the work queue is empty and all sessions are done →
`shutdown`.

### 6.2 Go — `opencode_server.go`

```go
// Project-scoped, nono-sandboxed opencode server driver (raw net/http + SSE).
package harness

import (
    "bufio"
    "bytes"
    "context"
    "encoding/json"
    "fmt"
    "net/http"
    "os"
    "os/exec"
    "strings"
    "syscall"
    "time"
)

type ServerHandle struct {
    cmd      *exec.Cmd
    BaseURL  string
    Password string
    hc       *http.Client
}

// wrapWithNono delegates to the skill's shared helper (nono-integration.md).
func wrapWithNono(argv []string, projectRoot string) []string {
    return NonoWrap(argv, projectRoot) // returns ["nono","run",...,"--","opencode","serve",...]
}

func LaunchServer(ctx context.Context, projectRoot string, port int, password string) (*ServerHandle, error) {
    inner := []string{"opencode", "serve", "--hostname", "127.0.0.1", "--port", fmt.Sprint(port)}
    wrapped := wrapWithNono(inner, projectRoot)

    cmd := exec.CommandContext(ctx, wrapped[0], wrapped[1:]...)
    cmd.Dir = projectRoot // §2: cwd MUST be project root
    cmd.Env = append(os.Environ(),
        "OPENCODE_SERVER_PASSWORD="+password,
        "OPENCODE_DISABLE_AUTOUPDATE=1",
    )
    cmd.SysProcAttr = &syscall.SysProcAttr{Setpgid: true} // own process group
    cmd.Stdin = nil
    if err := cmd.Start(); err != nil {
        return nil, fmt.Errorf("spawn nono-wrapped opencode serve: %w", err)
    }
    h := &ServerHandle{
        cmd:      cmd,
        BaseURL:  fmt.Sprintf("http://127.0.0.1:%d", port),
        Password: password,
        hc:       newHarnessHTTPClient(), // NOT &http.Client{} — see below
    }
    if err := h.waitHealthy(ctx, 30*time.Second); err != nil {
        _ = h.Shutdown(10 * time.Second)
        return nil, err
    }
    return h, nil
}

// controlResponseHeaderTimeout bounds how long ANY single request waits for the
// opencode server's response HEADERS. It must NOT bound the body: the /event
// SSE stream is a deliberately long-lived response, and a client-level
// http.Client.Timeout (which covers the whole exchange incl. body read) would
// sever it. ResponseHeaderTimeout fires only while waiting for the status line
// + headers — exactly the point the nono supervisor proxy can hold a connection
// open indefinitely right after launch.
const controlResponseHeaderTimeout = 15 * time.Second

// newHarnessHTTPClient builds the HTTP client every ServerHandle uses. Two
// non-obvious requirements, both learned from real "harness stalls after
// launching opencode" incidents (2026-06-16):
//
//  1. BUILD A FRESH *http.Transport — never clone or type-assert
//     http.DefaultTransport. A runtime harness commonly installs a GLOBAL
//     transport guard over http.DefaultTransport at startup (e.g. a dry-run
//     guard that blocks mutating calls to the project's API host). After that,
//     `http.DefaultTransport.(*http.Transport)` PANICS ("interface conversion:
//     http.RoundTripper is *DryRunTransport, not *http.Transport"), and
//     `&http.Client{}` (which uses the default) would route opencode LOOPBACK
//     traffic through that guard. A dedicated transport keeps the server client
//     independent of whatever the process default was swapped to.
//  2. NO client-level Timeout (SSE must run long), but DO set
//     ResponseHeaderTimeout. Without a header bound, a single hung request (the
//     first health probe through the not-yet-ready nono proxy, a session create
//     touching a missing grant) blocks forever — and because waitHealthy only
//     checks its budget BETWEEN requests, the budget is never enforced and the
//     whole harness hangs until the outer signal kills it. This reads to the
//     operator as "stalls right after `opencode server listening`, then dies".
func newHarnessHTTPClient() *http.Client {
    tr := &http.Transport{
        Proxy:                 http.ProxyFromEnvironment,
        ResponseHeaderTimeout: controlResponseHeaderTimeout,
    }
    return &http.Client{Transport: tr}
}

func (h *ServerHandle) do(ctx context.Context, method, path string, body any) (*http.Response, error) {
    var rdr *bytes.Reader
    if body != nil {
        b, _ := json.Marshal(body)
        rdr = bytes.NewReader(b)
    } else {
        rdr = bytes.NewReader(nil)
    }
    req, err := http.NewRequestWithContext(ctx, method, h.BaseURL+path, rdr)
    if err != nil {
        return nil, err
    }
    req.SetBasicAuth("opencode", h.Password)
    if body != nil {
        req.Header.Set("Content-Type", "application/json")
    }
    return h.hc.Do(req)
}

func (h *ServerHandle) waitHealthy(ctx context.Context, budget time.Duration) error {
    deadline := time.Now().Add(budget)
    for time.Now().Before(deadline) {
        if ctx.Err() != nil {
            return ctx.Err()
        }
        // Per-probe deadline. The parent ctx (signal.NotifyContext) has NO
        // deadline, so without this a single hung probe blocks here forever and
        // the budget check above never re-runs (it only fires BETWEEN probes).
        // Combined with newHarnessHTTPClient's ResponseHeaderTimeout this gives
        // two independent ways for a stuck probe to fail fast and retry until
        // the budget genuinely expires.
        probeCtx, cancel := context.WithTimeout(ctx, 5*time.Second)
        resp, err := h.do(probeCtx, "GET", "/global/health", nil)
        if err == nil {
            var v struct {
                Healthy bool `json:"healthy"`
            }
            _ = json.NewDecoder(resp.Body).Decode(&v)
            resp.Body.Close()
            cancel()
            if v.Healthy {
                return nil
            }
        } else {
            cancel()
        }
        time.Sleep(200 * time.Millisecond)
    }
    return fmt.Errorf("opencode server failed health within budget")
}

func (h *ServerHandle) CreateSession(ctx context.Context, title string) (string, error) {
    resp, err := h.do(ctx, "POST", "/session", map[string]any{"title": title})
    if err != nil {
        return "", err
    }
    defer resp.Body.Close()
    // CAPTURE THE BODY ON AN ERROR STATUS. A bare "status 500" here is
    // undebuggable, and POST /session 500 is the #1 reason the whole loop
    // stalls (the reviewer/burndown can't get a session → total outage). The
    // body names the cause — an EACCES on a missing nono grant
    // (~/.opencode/package.json, a config skills-symlink target), a models.dev
    // 403, or a store error — turning a multi-hour blind stall into a one-line
    // grant fix. This is the "don't discard the forensic record" rule applied
    // to HTTP errors. See nono-integration.md "session-create 500 / EACCES".
    if resp.StatusCode >= 300 {
        body, _ := io.ReadAll(io.LimitReader(resp.Body, 8192))
        return "", fmt.Errorf("create session: status %d: %s",
            resp.StatusCode, strings.TrimSpace(string(body)))
    }
    var v struct {
        ID string `json:"id"`
    }
    if err := json.NewDecoder(resp.Body).Decode(&v); err != nil {
        return "", err
    }
    if v.ID == "" {
        return "", fmt.Errorf("session create: missing id")
    }
    return v.ID, nil
}

func (h *ServerHandle) PromptAsync(ctx context.Context, session, agent, text string) error {
    resp, err := h.do(ctx, "POST", "/session/"+session+"/prompt_async", map[string]any{
        "agent": agent,
        "parts": []map[string]any{{"type": "text", "text": text}},
    })
    if err != nil {
        return err
    }
    defer resp.Body.Close()
    if resp.StatusCode != http.StatusNoContent {
        return fmt.Errorf("prompt_async unexpected status %d", resp.StatusCode)
    }
    return nil
}

func (h *ServerHandle) RespondPermission(ctx context.Context, session, perm, decision string) error {
    resp, err := h.do(ctx, "POST", "/session/"+session+"/permissions/"+perm, map[string]any{
        "response": decision,
        "remember": decision == "always",
    })
    if err != nil {
        return err
    }
    resp.Body.Close()
    return nil
}

func (h *ServerHandle) TodoEmpty(ctx context.Context, session string) (bool, error) {
    resp, err := h.do(ctx, "GET", "/session/"+session+"/todo", nil)
    if err != nil {
        return false, err
    }
    defer resp.Body.Close()
    var todos []json.RawMessage
    _ = json.NewDecoder(resp.Body).Decode(&todos)
    return len(todos) == 0, nil
}

func (h *ServerHandle) Abort(ctx context.Context, session string) {
    resp, err := h.do(ctx, "POST", "/session/"+session+"/abort", nil)
    if err == nil {
        resp.Body.Close()
    }
}

type Event struct {
    Kind string
    Data map[string]any
}

// RunEventLoop streams /event (SSE) and pushes parsed events to out until ctx
// is done or the stream closes. Caller owns stop logic via ctx cancellation.
func (h *ServerHandle) RunEventLoop(ctx context.Context, out chan<- Event) error {
    resp, err := h.do(ctx, "GET", "/event", nil)
    if err != nil {
        return err
    }
    defer resp.Body.Close()
    sc := bufio.NewScanner(resp.Body)
    sc.Buffer(make([]byte, 0, 1<<20), 1<<24)
    var evName, dataBuf string
    flush := func() {
        if dataBuf == "" {
            evName = ""
            return
        }
        var data map[string]any
        _ = json.Unmarshal([]byte(dataBuf), &data)
        kind, _ := data["type"].(string)
        if kind == "" {
            kind = evName
        }
        // opencode (validated 1.15.13) nests every event attribute under a
        // `properties` key; `type` is the only top-level field. Unwrap once
        // here so handlers read info/sessionID/part/delta directly — read them
        // at the top level and they are nil, the completion signal is never
        // seen, and every prompt hits its deadline ("context deadline
        // exceeded"). Fall back to the raw map if a build drops the envelope.
        payload := data
        if props, ok := data["properties"].(map[string]any); ok {
            payload = props
        }
        select {
        case out <- Event{Kind: kind, Data: payload}:
        case <-ctx.Done():
        }
        evName, dataBuf = "", ""
    }
    for sc.Scan() {
        if ctx.Err() != nil {
            return ctx.Err()
        }
        line := sc.Text()
        switch {
        case line == "":
            flush()
        case strings.HasPrefix(line, "event:"):
            evName = strings.TrimSpace(line[len("event:"):])
        case strings.HasPrefix(line, "data:"):
            dataBuf += strings.TrimSpace(line[len("data:"):])
        }
    }
    return sc.Err()
}

// Shutdown: DISPOSE → TERMINATE with watchdog on the process group.
func (h *ServerHandle) Shutdown(grace time.Duration) error {
    ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
    defer cancel()
    if resp, err := h.do(ctx, "POST", "/instance/dispose", nil); err == nil {
        resp.Body.Close()
    }
    done := make(chan error, 1)
    go func() { done <- h.cmd.Wait() }()
    pgid := -h.cmd.Process.Pid
    select {
    case <-done:
        return nil
    case <-time.After(grace):
        _ = syscall.Kill(pgid, syscall.SIGTERM)
    }
    select {
    case <-done:
    case <-time.After(5 * time.Second):
        _ = syscall.Kill(pgid, syscall.SIGKILL)
        <-done
    }
    return nil
}
```

### 6.3 Ruby — `opencode_server.rb`

```ruby
# Project-scoped, nono-sandboxed opencode server driver (net/http + SSE).
require "net/http"
require "json"
require "uri"
require "timeout"

module Harness
  class OpencodeServer
    attr_reader :base_url, :password

    # NonoWrap delegates to the skill's shared helper (nono-integration.md);
    # returns ["nono","run",...,"--","opencode","serve",...].
    def self.wrap_with_nono(argv, project_root)
      NonoWrap.call(argv, project_root)
    end

    def self.launch(project_root:, port:, password:)
      inner   = ["opencode", "serve", "--hostname", "127.0.0.1", "--port", port.to_s]
      wrapped = wrap_with_nono(inner, project_root)

      pid = Process.spawn(
        { "OPENCODE_SERVER_PASSWORD" => password, "OPENCODE_DISABLE_AUTOUPDATE" => "1" },
        *wrapped,
        chdir: project_root,        # §2: cwd MUST be project root
        pgroup: true,               # own process group
        in: "/dev/null"
      )
      server = new(pid: pid, port: port, password: password)
      server.wait_healthy(30)
      server
    rescue => e
      begin; Process.kill("KILL", -Process.getpgid(pid)); rescue; end if defined?(pid) && pid
      raise e
    end

    def initialize(pid:, port:, password:)
      @pid      = pid
      @pgid     = Process.getpgid(pid)
      @base_url = "http://127.0.0.1:#{port}"
      @password = password
    end

    def wait_healthy(budget_s)
      deadline = Time.now + budget_s
      loop do
        raise "opencode server failed health within budget" if Time.now > deadline
        begin
          resp = get("/global/health")
          return if resp.is_a?(Net::HTTPSuccess) && JSON.parse(resp.body)["healthy"] == true
        rescue
          # not up yet
        end
        sleep 0.2
      end
    end

    def create_session(title)
      body = JSON.parse(post("/session", { title: title }).body)
      body.fetch("id")
    end

    def prompt_async(session, agent, text)
      resp = post("/session/#{session}/prompt_async",
                  { agent: agent, parts: [{ type: "text", text: text }] })
      raise "prompt_async status #{resp.code}" unless resp.code.to_i == 204
    end

    def respond_permission(session, perm, decision)
      post("/session/#{session}/permissions/#{perm}",
           { response: decision, remember: decision == "always" })
    end

    def todo_empty?(session)
      JSON.parse(get("/session/#{session}/todo").body).empty?
    rescue
      true
    end

    def abort(session)
      post("/session/#{session}/abort", nil) rescue nil
    end

    # Streams /event (SSE), yielding [kind, data_hash] per event until the block
    # returns :stop or the stream closes. Run on its own thread for concurrency.
    def each_event
      uri = URI("#{@base_url}/event")
      Net::HTTP.start(uri.host, uri.port) do |http|
        req = Net::HTTP::Get.new(uri)
        req.basic_auth("opencode", @password)
        http.request(req) do |resp|
          ev_name = nil
          data    = +""
          resp.read_body do |chunk|
            chunk.each_line do |line|
              line = line.chomp
              if line.empty?
                unless data.empty?
                  parsed = JSON.parse(data) rescue {}
                  kind   = parsed["type"] || ev_name
                  # opencode (1.15.13) nests every attribute under
                  # "properties"; only "type" is top-level. Unwrap so the
                  # handler reads info/sessionID/part/delta directly, else
                  # completion is never detected and prompts hit their
                  # deadline. Fall back to the raw hash if the envelope is gone.
                  payload = parsed["properties"].is_a?(Hash) ? parsed["properties"] : parsed
                  break if yield(kind, payload) == :stop
                end
                ev_name, data = nil, +""
              elsif line.start_with?("event:")
                ev_name = line.sub("event:", "").strip
              elsif line.start_with?("data:")
                data << line.sub("data:", "").strip
              end
            end
          end
        end
      end
    end

    # DISPOSE -> TERMINATE with watchdog on the process group.
    def shutdown(grace_s = 10)
      post("/instance/dispose", nil) rescue nil
      return if reaped?(grace_s)
      kill_group("TERM")
      return if reaped?(5)
      kill_group("KILL")
      Process.wait(@pid) rescue nil
    end

    private

    def reaped?(timeout_s)
      Timeout.timeout(timeout_s) { Process.wait(@pid); true }
    rescue Timeout::Error
      false
    rescue Errno::ECHILD
      true
    end

    def kill_group(sig)
      Process.kill(sig, -@pgid)
    rescue Errno::ESRCH
      # already gone
    end

    def http_req(req)
      uri = URI(@base_url)
      Net::HTTP.start(uri.host, uri.port) do |http|
        req.basic_auth("opencode", @password)
        http.request(req)
      end
    end

    def get(path)
      http_req(Net::HTTP::Get.new(URI("#{@base_url}#{path}")))
    end

    def post(path, body)
      req = Net::HTTP::Post.new(URI("#{@base_url}#{path}"))
      if body
        req["Content-Type"] = "application/json"
        req.body = body.to_json
      end
      http_req(req)
    end
  end
end
```

---

## 7. Harness integration

How the opencode-server backend slots into the existing harness run:

- **One server per run, owned by the harness driver.** At run start (after the
  harness has resolved the project root and worktree), PREFLIGHT + LAUNCH the
  sandboxed server. The harness driver — not any agent, not a plugin — owns the
  handle and the watchdog. Put `shutdown` behind the run's defer/ensure/`Drop` so
  the server is disposed on every exit path (success, error, signal).
- **Backend selection.** Add a harness option `agent_host: claude-stream |
  opencode-server` (default unchanged). When `opencode-server`, the per-language
  streaming module's "dispatch a subagent" call is replaced by "create session +
  prompt the agent on the shared server." The rest of the harness (finding
  implementation gaps from logs/tests/spec-drift, the bug-burndown/iteratotron
  orchestration, the three harness types) is unchanged — only the dispatch
  primitive differs.
- **Worktree isolation still applies.** Parallel work items still run in their own
  git worktrees. With the server model the worktrees live **under the project root
  that the server is rooted at**, so they are inside the nono boundary
  automatically. (If a worktree is placed outside the project root, it falls
  outside the boundary and outside the server's project — keep worktrees under the
  root.)
- **Bounded parallelism.** Reuse the harness `N` cap: at most `N` concurrent
  sessions prompting at once, all on the one server. The server handles
  concurrency; the cap is about model/cost/rate-limit pressure, same as before.
- **Scope exhaustion → shutdown.** The run loop pulls work items off the queue,
  drives each to completion (§5), and when the queue is empty and all in-flight
  sessions are complete, it transitions DRAIN → DISPOSE → TERMINATE. A global run
  deadline aborts outstanding sessions (`/session/:id/abort`) before disposing.
- **Manifest.** Record, per run: opencode version, server port, the realized nono
  policy (granted paths + egress hosts), the permission decisions (allow/reject
  audit), and the teardown outcome (clean dispose vs. SIGTERM vs. SIGKILL). This
  keeps the provenance story honest about which boundary was enforced and whether
  shutdown was graceful.

---

## 8. `eval.yaml` assertions

Extend the skill's eval to enforce the server-path invariants. The core invariant
moves from per-invocation to the single server-launch site, which is easier to
assert:

- **bypass-iff-wrapped (server form).** Assert that any `opencode serve`
  invocation the harness emits is the tail of a `nono run … -- opencode serve …`
  command. A bare `opencode serve` (no `nono run` prefix) when permissions are not
  interactive is a failure. (Static check on the generated launcher + a runtime
  check that the server PID's ancestry includes the nono process.)
- **No agent traffic without a sandboxed server.** Assert the driver refuses to
  `POST /session/.../prompt*` unless a health-passing, nono-wrapped server handle
  exists. (No agent prompt may be sent to an unsandboxed or unverified server.)
- **cwd = project root.** Assert the launcher sets the child cwd to the project
  root (guards bug #14445 / permission-path mismatch).
- **loopback + auth.** Assert `--hostname 127.0.0.1` and that
  `OPENCODE_SERVER_PASSWORD` is set via env (not argv, not empty).
- **Clean teardown, no orphans.** After a simulated run (including a forced-error
  run), assert the server process and its group are gone (DISPOSE attempted, then
  SIGTERM→SIGKILL escalation), and that no `opencode`/bash/MCP descendants survive.
- **Permission policy is allowlist + audit, not blind allow.** Assert the driver
  responds to `permission.updated` from an explicit allowlist and logs every
  decision; a configuration of blanket `"permission":"allow"` without the nono
  wrapper is a failure.
- **Unsandboxed fallback keeps `ask`.** When `--allow-unsandboxed` is set, assert
  the server runs with interactive/`ask` permissions and never auto-bypass — same
  worst-of-both-worlds guard as the Claude Code path.
- **SSE completion is detected (the `properties`-envelope regression).** Assert a
  unit test drives a captured `GET /event` byte stream — including the real
  `{"type":"message.updated","properties":{"info":{"role":"assistant","time":{"completed":…}}}}`
  envelope — through the driver's SSE parser and confirms the three-way
  completion fires (msg-completed + idle + todo-empty) and the accumulated reply
  text is the assistant text only (no echoed prompt, no double-count). A driver
  that reads event fields at the top level instead of under `properties` makes
  every prompt time out with `"context deadline exceeded"`; this test is what
  catches it before a live run does. A live opt-in round-trip
  (`HARNESS_LIVE=1`) that sends one prompt and asserts `Completed == true`
  within seconds is the end-to-end backstop.

---

## 9. SKILL.md additions

Add to the skill body so the harness-building agent knows when and how to choose
this backend:

- **When to choose `opencode-server` over `claude-stream`:** choose the server
  backend when the run fans out many agents/sessions against one project and you
  want a single sandbox boundary, real-time SSE observability, programmatic
  permission control, and child-session (subagent) visibility. Choose
  `claude-stream` when you need the existing per-invocation `stream-json` contract
  or Claude-Code-specific behavior.
- **The one-server-per-project rule:** never share a server across project roots
  (the API is single-project; `POST /session` has no directory). One sandboxed
  server per project per run; harness owns its lifecycle.
- **The wrap-once invariant:** the nono boundary is applied at `opencode serve`
  launch and inherited by all children; do not attempt per-invocation wrapping on
  this backend. Per-tool inner narrowing is the optional opencode-plugin layer.
- **Lifecycle ownership:** the harness driver starts the server after resolving
  the worktree and disposes it on every exit path; agents only ever *connect*.
- Point to this file (`references/opencode-server-integration.md`) for the
  lifecycle, API contract, and per-language drivers, and to
  `references/nono-integration.md` for the policy flags.

---

## 10. Gotchas & version caveats

- **Fast-moving API.** Validated against opencode `1.17.x` / docs 2026-06-10.
  Re-check endpoints, the prompt body, and event names against `/doc` and the
  generated `types.gen.ts` for your pinned version. Pin the opencode version in
  the harness and set `OPENCODE_DISABLE_AUTOUPDATE=1`.
- **Event discriminator.** The driver reads a `type` field from the SSE `data`
  JSON and falls back to the SSE `event:` field. Confirm which your version uses;
  the skeletons handle both.
- **Event-vocabulary drift (the 2026-06-16 `session.next.*` hang).** The `type`
  *values* — not just where they live — drift across builds. opencode 1.16.x
  routes turn lifecycle through `session.next.*` (`tool.called`, `step.failed`,
  `text.delta`, …) and makes questions/permissions first-class
  (`question.asked`/`permission.asked`, **no** `permission.updated`). A driver
  keyed on an older build's names classifies them `Other`, never completes, and
  rides to the deadline (frozen `tool_calls`, pinned small `idle_secs` from the
  ~30s `server.heartbeat`). Validate against `/doc` per version; handle both
  tool vocabularies deduped by `callID`; add the progress-keyed stall watchdog +
  unhandled-kind tracking + forensic frame log. Full detail: §16.
- **The `properties` envelope (the canonical timeout incident — vulnmapper
  2026-06-12).** opencode 1.15.13 nests every event attribute under a
  `properties` key: `{"type":"message.updated","properties":{"info":{…}}}`. Only
  `type` is top-level. A driver that reads `data["info"]` / `data["delta"]` /
  `data["sessionID"]` at the top level gets `nil` for all of them — so
  `message.updated`'s completion is never seen, the three-way AND never fires,
  and **every prompt runs to its per-prompt deadline** and returns `"context
  deadline exceeded"`. The failure signature is a whole reviewer run where every
  batch fails identically at the deadline mark (28-for-28). Unwrap `properties`
  once at parse time (see §5/§6 skeletons). The envelope is **not** represented
  as a wrapper in the generated OpenAPI schema — only a live `GET /event`
  capture reveals it, so add a regression test that drives captured wire bytes
  through the SSE parser and asserts completion is detected.
- **`message.updated` fires for the user message too** (`info.role == "user"`,
  no `time.completed`). Guard the completion check on `role == "assistant"`. The
  user prompt also streams back as `message.part.*` under its own `messageID`;
  filter reply-text accumulation to the assistant `messageID` and take
  `message.part.delta` (`field == "text"`) only — mixing in the
  `message.part.updated` snapshots double-counts the text, and not filtering by
  message prepends the prompt to the answer.
- **SSE reliability.** There are open/closed bugs where `/event` closes right
  after `server.connected` or keeps emitting `message.part.updated` after a turn
  ends. Treat the **synchronous `/message` response** (or `message.updated` +
  `info.time.completed`) as the authoritative completion signal and `session.idle`
  as secondary; do not rely on idle alone.
- **`session.idle` can fire early** and server-side idle handlers are
  fire-and-forget — the driver owns the loop and re-arms detection after any
  follow-up prompt. The todo-empty check guards premature idle.
- **`serve` has no `--directory`.** cwd must be the project root; launching
  elsewhere can root the server at `/` and expose the filesystem via the file APIs
  (contained by nono, but still set cwd correctly to fix permission-path matching).
- **Port allocation — default to a free ephemeral port so multiple harnesses
  coexist.** A fixed port collides the moment a second harness (or a live test)
  runs against the same host. Resolve the port the harness/driver picks, not the
  one opencode announces on stdout: bind `127.0.0.1:0`, read the assigned port,
  close the listener, then pass that concrete number to **both** `opencode
  serve --port N` **and** nono `--open-port N`. This is required because nono
  must be told the port up front (it can't allow a port opencode hasn't bound),
  so you cannot let opencode pick `:0` itself and parse it back. There's a small
  TOCTOU window between picking and binding; on loopback it's rare, and
  `/global/health` gating turns a lost race into a clean launch failure rather
  than a hang. Expose the resolved port on the server handle and log it. Offer
  a fixed-port override (a non-zero flag) for operators who want a stable
  address. Helper:
  ```go
  func FreeLoopbackPort() (int, error) {
      l, err := net.Listen("tcp", "127.0.0.1:0")
      if err != nil { return 0, err }
      defer l.Close()
      return l.Addr().(*net.TCPAddr).Port, nil
  }
  ```
  Per-project Unix sockets also work and sidestep the TOCTOU entirely, but
  `opencode serve` binds TCP (`--hostname`/`--port`), so a free TCP port is the
  portable default; **never hardcode `/tmp/<name>.sock`** (it's bind-mounted
  differently in sandboxes — see SKILL Hard Anti-Patterns).
- **`agent` + `model` together:** the explicit `model` may be ignored in favor of
   the agent's fallback (issue #18615). Encode the model in the agent definition for
   determinism.
- **The `model` field is `{ providerID, modelID }` — both keys, always (the
  2026-06-16 reviewer-outage incident).** When the driver sends an explicit
  `model` in the prompt body, it MUST be the object `{ "providerID": "gitlab",
  "modelID": "duo-chat-haiku-4-5" }`. A bare `{ "modelID": "duo-chat-haiku-4-5" }`
  — or worse, a bare string — 400s **every** prompt with `BadRequest: Missing
  key at ["model"]["providerID"]`, which the reviewer reads as a total outage
  (correctly → `WorkRemaining`, never false-clean, but no progress). The CLI
  carries models as `provider/model`; split on the **first** `/` (so a modelID
  containing `/` survives) and emit both keys. Reject a bare model with no
  provider **loudly** at the driver, not by sending a body the server rejects.
  This is why the per-language skeletons that pass `model` explicitly use a
  `model_field("provider/model") -> { providerID, modelID }` helper, unit-tested
  (both keys present, first-slash split, bare-model rejected). A model default
  must therefore be **provider-qualified** (`gitlab/duo-chat-haiku-4-5`, not the
  bare `duo-chat-haiku-4-5` and certainly not `duo-workflow`).
- **Process-group kill is mandatory.** opencode forks bash/MCP/subagent children;
  signal the group (`killpg` / `-pgid`), not just the parent, or you leak orphans
  that the eval will flag.
- **No first-party Rust/Ruby SDK** in 1.17.x; raw HTTP+SSE is the portable path
  (shown above). Go has a generated SDK tracking `dev` if you prefer it over
  `net/http`.

## 13. Session & event-stream lifecycle

Two lifecycle hazards any multi-session harness hits unless it manages the
server explicitly. Both are *server-side* and neither shows up in unit tests:

1. **The `/event` listener leak** (§13.1, 2026-06-15) — fixed by holding one
   shared `/event` reader, not one per session.
2. **The session-store FK corruption** (§13.2, 2026-06-16) — caused by deleting
   sessions out-of-band; fixed by **not** doing that and reclaiming via server
   dispose.

Note the second one is a *reversal* of earlier guidance: a previous version of
§13.2 told you to delete every session, which is exactly what corrupts the
store. Read §13.2 before copying any older harness's teardown.

### 13.1 One shared `/event` connection — never one per session

opencode does **not** multiplex `/event`. Each `GET /event` connection adds a
listener to the server's internal event Bus (`MY` emitter). A harness whose
per-session observer opens its own `GET /event` (the naive `run_event_loop`
that takes a callback and connects every time) leaks one listener per session
for the whole run. After ~11, Node prints:

```
WARN opencode.serve.stderr: MaxListenersExceededWarning: Possible EventTarget
  memory leak detected. 11 event listeners added to [MY]. MaxListeners is
  undefined. Use events.setMaxListeners() to increase limit
```

That warning is the canary; the listeners keep growing for the rest of the run
and degrade the server.

**The fix — single long-lived reader + in-process fan-out.** Hold exactly one
`/event` connection per `ServerHandle` for the server's whole lifetime. Feed
every parsed frame into an in-process broadcast channel. Per-session observers
subscribe to the channel (free, in-process), filter by `sessionID`, and drop
their receiver when their completion gate fires. No session ever opens a
server-side stream.

```rust
// ServerHandle owns ONE reader, started lazily on first observe.
event_bus: TokioMutex<Option<broadcast::Sender<(String, Value)>>>,

async fn subscribe_events(&self) -> broadcast::Receiver<(String, Value)> {
    let mut g = self.event_bus.lock().await;
    if let Some(tx) = g.as_ref() { return tx.subscribe(); }   // reuse
    let (tx, rx) = broadcast::channel(4096);                  // generous buffer
    let (url, auth) = (format!("{}/event", self.base_url), http_basic(&self.password));
    let tx2 = tx.clone();
    std::thread::spawn(move || loop {                         // single connection
        let resp = match ureq::get(&url).header("Authorization", &auth)
            .config().timeout_global(None).build().call() {
            Ok(r) => r,
            Err(_) => { std::thread::sleep(Duration::from_secs(1));
                        if tx2.receiver_count() == 0 { return; } continue; }
        };
        let reader = BufReader::new(resp.into_body().into_reader());
        // …parse SSE frames, `let _ = tx2.send((kind, payload));`…
        if tx2.receiver_count() == 0 { return; }              // server gone
    });
    *g = Some(tx); rx
}
```

The per-session `run_event_loop` then just `subscribe_events().await` and reads
the receiver with a 500 ms `timeout` so it can still poll its `stop` flag.
Handle `broadcast::error::RecvError::Lagged(n)` by logging and continuing — the
completion gate is edge-triggered on `message.updated`/`session.idle`, which a
4096-frame buffer comfortably holds. Go: one goroutine reads `/event`, pushes
to a `[]chan event`; subscribers register/deregister under a mutex.

**Regression test:** assert that N concurrent `observe_session` calls open
**one** `/event` connection, not N. A fake SSE server that counts inbound
`GET /event` requests proves it; the count must stay at 1 regardless of session
count.

### 13.2 NEVER delete sessions out-of-band — reclaim via server lifecycle

> **Reversal (2026-06-16 FK-corruption incident).** Earlier guidance here told
> the driver to `DELETE /session/:id` after every session to "bound store
> growth." **That advice was wrong and is withdrawn.** The per-session delete
> *causes* the exact store failure it claimed to prevent. Do not add a
> `delete_session` to the driver. If an existing harness has one, removing it is
> a Family-3 audit fix.

opencode persists every session, message, and part to a SQLite-backed store
with a foreign-key chain: `part.message_id → message.id → session.id`. The
session store is the **server's private durable state**. The only supported way
to reclaim it is to dispose the *server instance* (`POST /instance/dispose`,
which the harness already does once at run shutdown) — never out-of-band row
surgery on individual sessions while the server is live.

**Why the delete corrupts the store.** Long-running turns are dispatched with
`prompt_async`: the call returns `204` immediately and the assistant keeps
streaming, so the server keeps writing that session's `message`/`part` rows in
the *background* after you've observed "completion". `observe_session` can also
return on a non-clean exit (deadline reached, `session.error` bail, question
budget) while the turn is still running. If the driver then deletes the parent
`session` row, the server's `SessionProcessor.cleanup` INSERT for the still
in-flight child rows fails:

```
WARN …opencode_server: session.error data=Object {"error": Object {"data":
  Object {"message": String("…FOREIGN KEY constraint failed…")},
  "name": String("UnknownError")}, "sessionID": String("ses_…")}
```

and — critically — once the store hits that error it **poisons inserts for
every *other* session too**, so the whole run wedges. The harness then either
spins (every later dispatch 500s) or hangs. The earlier 2026-06-15 "Failed to
execute statement" incident this delete was added to fix was the **same
self-inflicted wound**, misdiagnosed as capacity growth.

**The correct rule.** One server per run keeps the store bounded in practice
(sessions are small metadata + message rows; a run creates hundreds, not
millions). Do **not** delete sessions:

```rust
// observe_session teardown — NO delete. The store is reclaimed when the server
// instance is disposed at run shutdown.
let loop_result = server.run_event_loop(/* … */).await;   // capture, don't `?`
let todo_empty   = server.todo_empty(session_id).await.unwrap_or(true);
let tool_calls   = /* … read outcome … */;
loop_result?;                                             // propagate; no delete
Ok(SessionOutcome { /* … */ })
```

If a genuinely long-running campaign ever does need mid-run reclamation, the
correct lever is **server lifecycle**, not session deletes: dispose the server
and relaunch a fresh one between outer rounds, letting auto-resume carry the
persisted scope/iteration state across the restart. That reclaims the entire
store atomically without ever racing the server's own writes.

**Failure mode if you re-introduce the delete:** a long run looks healthy for a
while, then a deadline/error-bail delete races an in-flight `prompt_async`
write, the store throws `FOREIGN KEY constraint failed`, every *subsequent*
session 500s, the reviewer can't get a verdict, and — per §10 / the
global-fixpoint rule — a transport outage the loop misreads as "zero rejects"
can falsely declare the flow clean, or the loop spins/hangs against the dead
server.

> The shared `/event` reader (§13.1) is still mandatory and unrelated — it fixes
> the listener leak. The session-store fix is the **opposite** of what this
> section used to say: hold one server, dispose it at the end, and never delete
> a live session.

---

## 14. The interactive `question` tool stalls an autonomous session

A dispatched agent can call the interactive `question` tool (opencode's
`question`; the Claude-Code name is `AskUserQuestion`) when it hits a choice it
wants a human to make. In an interactive session a person answers and the turn
resumes. In a harness session there is no person. The tool call blocks the turn:
the agent never emits `message.updated{completed}`, never goes `session.idle`,
and the whole drive rides to its per-session deadline before bouncing as a
**false Timeout**. One agent stuck on a question can wedge a scope for the entire
session-timeout window, burning the most expensive part of the loop on nothing.
This is the stall the 2026-06-15 question incident left behind.

The fix has two halves, and you want both: tell the agent up front not to ask
(prompt guidance), and catch it when it asks anyway (driver auto-answer).

### 14.1 Prompt guidance — tell every agent it is on its own

Prepend a standing directive to **every** dispatched prompt (genesis, burndown,
review). It states plainly that the run is autonomous, that the `question` tool
will be cancelled, and how to decide instead:

- choose the option that best meets the documented intent and desired state —
  for a bug, the shape of the bug — weighing implementation complexity against
  fully satisfying that intent, and prefer the simplest change that meets the
  requirement without weakening it;
- only when a choice is genuinely load-bearing and can't be made safely from the
  docs, pick the most reversible option to keep moving **and** record the open
  decision in a short note (under `docs/decisions/` or the scope findings) for
  later human review — never block on it.

```rust
const AUTONOMOUS_DIRECTIVE: &str = "\
This is a fully autonomous run: there is NO human available and you must not \
stop to ask. Do NOT call the `question` / `AskUserQuestion` tool — it will be \
cancelled and you will be told to proceed. When a choice arises, decide for \
yourself: pick the option that best meets the documented intent and desired \
state (for a bug, the shape of the bug), weighing implementation complexity \
against fully satisfying that intent... Only if a choice is genuinely \
load-bearing and you cannot make it safely, choose the most reversible option \
AND record the open decision in a short note for later human review — never \
block on it.\n\n";
```

Guidance alone isn't enough — models still reach for the tool — so the driver
must handle the call when it comes.

### 14.2 Driver auto-answer — detect the call, inject a decision, keep moving

The `question` tool arrives as a tool-use part on `message.part.updated`: a
`part.type` of `tool`/`tool_use` whose `part.tool` is `question` (or
`AskUserQuestion`). Classify it **separately** from ordinary tool use so the
generic ToolUse arm doesn't swallow it:

```rust
pub fn is_question_tool(tool: &str) -> bool {
    let t = tool.to_ascii_lowercase();
    t == "question" || t == "askuserquestion" || t == "ask_user_question"
}
// in classify_event, inside the tool-use branch, BEFORE returning ToolUse:
if tool.as_deref().map(is_question_tool).unwrap_or(false) {
    return EventSignal::QuestionAsked { part_id, question /* best-effort text */ };
}
```

When the driver sees `QuestionAsked`, it unblocks the session:

1. **Dedupe** by part id — the server re-emits a streaming part many times, so
   one logical question must trigger one answer.
2. **Abort** the blocked turn (`POST /session/:id/abort`).
3. **Drain the buffered frames, then re-arm.** This is the order that matters
   (see 14.2.1). Drain every frame already in the observer's channel, *then*
   clear the `message.updated{completed}` and `session.idle` atomics.
4. **Re-prompt** the same session, as the same agent at the same tier, with the
   standing autonomous-decision answer (echo the question text for context), and
   set an `awaiting_fresh_turn` guard so the next completion edge is only honored
   once the re-prompted turn has actually produced output.
5. **Bound it.** Cap injections per session (3 is plenty). An agent that keeps
   asking after being told to decide is stuck on a real ambiguity or looping;
   abort and bail `Incomplete` so the caller bounces/escalates rather than spins.

```rust
EventSignal::QuestionAsked { part_id, question } => {
    if !question_parts.insert(part_id) { continue; }      // dedupe snapshots
    // Do NOT add this to tool_parts — see 14.2.2. A question is the canonical
    // no-op; counting it as work lets a question-only turn pass the no-op guard.
    match question_ctx {
        Some(ctx) if questions_answered < MAX_QUESTION_ANSWERS => {
            questions_answered += 1;
            self.abort(session).await;
            // 14.2.1: drain the aborted turn's settle frames BEFORE re-arming,
            // so its trailing idle/completed can't be read as the new turn's.
            while let Ok(_) = events.try_recv() { /* discard; Lagged → keep going */ }
            msg_complete.store(false, Ordering::SeqCst);  // re-arm AFTER drain
            idle.store(false, Ordering::SeqCst);
            awaiting_fresh_turn = true;                    // suppress break until output
            let answer = autonomous_decision_answer(question.as_deref());
            self.prompt_async(session, &ctx.agent, ctx.tier, &answer).await?;
        }
        _ => { self.abort(session).await; return Ok(()); } // over budget / no ctx
    }
}
```

Thread a small `QuestionContext { agent, tier }` from `prompt_and_drive` down to
the event loop so the re-prompt runs as the right agent. A lower-level entry
point with no context aborts the question and bails `Incomplete` instead.

#### 14.2.1 Drain settle frames before re-arming, and gate the break on fresh output

Aborting a turn makes it **settle**: opencode emits that turn's own
`session.idle` (and frequently a terminal `message.updated{completed}`) as a
consequence of the abort. Those frames are already buffered in the observer's
channel. If you re-arm the atomics and keep looping, the very next iterations
classify the aborted turn's death-rattle frames, re-set `idle`/`completed`, and
the loop breaks as a **false `Complete`** on a turn that did nothing but ask a
question. The no-op guard won't catch it either (see 14.2.2).

Two guards, both needed, because the settle frame can also arrive *after* you
drain (it was still in flight):

1. **Drain** the channel with `try_recv` until `Empty` immediately after the
   abort and *before* storing `false`. This clears the already-buffered settle
   frames.
2. **`awaiting_fresh_turn`** — a bool set true at re-prompt, cleared on the first
   genuine activity frame of the new turn (`ToolUse` or `StreamText`). Suppress
   the completion AND-break while it's true. This covers the in-flight settle
   frame the drain couldn't catch: a `completed`/`idle` seen before any new
   output belonged to the aborted turn, so don't honor it.

```rust
// where the loop decides to stop:
if !awaiting_fresh_turn
    && msg_complete.load(Ordering::SeqCst)
    && idle.load(Ordering::SeqCst) { break; }
// in the ToolUse and StreamText arms:
awaiting_fresh_turn = false;   // the re-prompted turn is really producing now
```

This is the 2026-06-16 false-clean-on-question-abort incident: a cold-context
review of the §14 fix itself found that re-arming bare atomics across an abort
boundary is unsound. Drain + gate is the fix.

#### 14.2.2 A question is a no-op — never count it as a tool call

It is tempting to insert the question part into `tool_parts` so a question-only
turn isn't flagged as a zero-tool-call no-op. **Don't.** That is backwards: a
question *is* the canonical no-op — the agent asked instead of doing the work.
Counting it inflates `tool_calls > 0`, and a turn that only asked questions
(asked → aborted → re-prompted → asked again → … → hit the cap → rode to a benign
completion) then launders past the §4.1 no-op guard as `Complete { tool_calls:
N>0 }`, reported as a successful fix that changed nothing. Track questions in
their own counter (the injection cap), surface them in the log, and let the no-op
guard see the turn for what it was. The false-Timeout worry the tool-count was
meant to fix is already handled by the re-prompt path; you do not also need to
fake a tool call. This is the HIGH-2 finding from the same 2026-06-16 review.

### 14.3 The defer-to-human escape hatch is real

The auto-answer is not "always guess and hope". It explicitly offers the agent a
second branch: when the choice is genuinely load-bearing, take the most
reversible option to stay unblocked **and** write the open decision down for a
human to review later. That keeps the loop moving without silently baking an
unreviewable architectural choice into the code. Pair this with the
`human-review` skill, which can later pick those notes up.

### 14.4 Tests (minimum)

- `question_tool_classified_separately_from_generic_tool_use` — a `tool` part
  named `question` → `QuestionAsked`, not `ToolUse`.
- `askuserquestion_alias_is_recognized_case_insensitively` — the Claude-Code
  name and casing variants are caught (a rename must not silently re-open the
  stall).
- `non_question_tool_use_still_classifies_as_tool_use` — the special case
  doesn't swallow ordinary tool calls.
- `autonomous_answer_states_no_human_and_offers_defer` — the injected text names
  the autonomy, both decision branches, and never tells the agent to wait.
- `both_prompts_carry_the_no_questions_directive` — every dispatched prompt
  carries the standing directive.
- `question_only_turn_is_a_no_op` (14.2.2) — a turn that emitted nothing but a
  question part yields `tool_calls == 0`, so the no-op guard catches it. Fails on
  the old code that inserted the question into `tool_parts`.
- `aborted_turn_settle_frames_do_not_complete_reprompt` (14.2.1) — after a
  question abort + re-prompt, a buffered `completed`+`idle` pair from the aborted
  turn (arriving before any new output) does NOT break the loop; only a fresh
  activity frame followed by the new turn's completion does.

**Reference implementation:** the reference harness — `EventSignal::QuestionAsked` and
`is_question_tool` in `src/opencode_server.rs`, the auto-answer arm in
`run_event_loop` (with the post-abort drain + `awaiting_fresh_turn` guard of
14.2.1 and the no-`tool_parts`-insert of 14.2.2), `with_autonomy_preamble` /
`AUTONOMY_PREAMBLE` / `QUESTION_AUTONOMY_REPROMPT` in `src/opencode_server.rs`,
wired into `render_genesis_prompt` / `render_burndown_prompt` in
`src/inner_loop.rs`. The anti-stall recurrence tracker
(`record_burndown_fingerprints`, `last_burndown_fingerprint`,
`burndown_recurrence`) lives in `src/state.rs` and is consumed in `burn_down`;
the change-scoped snapshot-drift wiring (`changed_paths` + pre/post set
difference) and the per-crate `capture_verification` are in `src/inner_loop.rs`
and `src/client.rs`.

---

## 15. The opencode API is flakey — bounded, transient-ONLY retry in the driver

A `session.error` can fire mid-drive after real progress (the 2026-06-16
burndown incident: eight productive tool calls, then a server-side error that
killed the whole iteration). The opencode gateway/store is not perfectly
reliable, so the driver must absorb a *transient* hiccup rather than throwing
away an entire expensive drive. But a blind retry is worse than none: it masks
the false-clean defects the global fixpoint (§ "Loop termination") exists to
prevent, and it burns budget re-attempting errors that will fail identically.

> **The rule.** Retry a `session.error` **only** when it is classified
> transient; a deterministic rejection fails fast. The classification, not the
> retry, is the load-bearing part.

### 15.1 Classify before you retry

Render the error first (§5 / `format_session_error` — name + `data.message` +
raw JSON, never an empty chain), then classify the rendered string:

- **Transient → retry (bounded, with backoff, recreating the session):**
  `502`/`503`/`504`/`gateway`, `timeout`/`timed out`, `connection
  reset`/`refused`/`closed`, `broken pipe`, `stream error`, `temporarily
  unavailable`, `overloaded`, `rate limit`/`too many requests`.
- **Deterministic → fail fast (retrying is pointless and hides a real bug):**
  `Unknown model ID` / `MODEL_MAPPINGS` (a version-skew config bug, §4.1 — fix
  the opencode build, never paper over it with retries), `BadRequest` /
  `Missing key`, `EACCES` (a missing nono grant — fix the profile, §
  session-create), `Unauthorized` / `Forbidden` / `invalid api key`,
  **`Failed to execute statement` / `FOREIGN KEY constraint failed` /
  `UnknownError` from the SQLite store.** A store-constraint failure is NOT a
  transient hiccup: it means the store is corrupt (almost always because a
  session was deleted out-of-band while a `prompt_async` turn was still writing
  — §13.2), and *every* subsequent session on that server will fail too.
  Retrying recreates a session into the same broken store and burns the budget.
  Fail fast and loud so the operator disposes the server (and its store) and
  relaunches; the genesis circuit breaker (consecutive server-failure count →
  abort) is the loop-level backstop for this exact case.
- **Unrecognized → deterministic (default).** Only retry errors you positively
  recognize as transient; an unknown error fails fast and loud rather than
  being silently retried into the budget. Deterministic markers take
  **precedence** over transient ones (a `MODEL_MAPPINGS` rejection wrapped in a
  5xx-shaped envelope must NOT be retried). The transient whitelist is the one
  knob to widen as new flakiness shapes appear.

### 15.2 What the retry must and must NOT do

- **Recreate a fresh session per attempt.** The errored session is dead;
  reusing its id retries into the same broken state. Create a new session for
  the retry — but do **not** `DELETE` the old one (that races in-flight writes
  and corrupts the store, §13.2); just abandon it and let server dispose reclaim
  it at run end. Bound the attempts (`MAX_DRIVE_ATTEMPTS`, ~3) with exponential
  backoff so a persistently-flakey API can't spin forever.
- **A timeout/abort is NOT a retryable error.** It already surfaces as
  `completed: false` (the deadline bounds it); re-driving just burns the same
  wall-clock again. Leave that path exactly as it was so the §5 completion
  gate and the downstream no-op guard are unchanged.
- **An exhausted transient retry is still an error → `WorkRemaining`.** Do not
  let "we retried 3× and gave up" collapse into zero-rejects/clean — that is
  the reviewer-outage false-clean (§ "Loop termination"). Surface the last
  error; the outer fixpoint re-attempts the work next round.
- **Put the retry in the driver, not per-caller.** `prompt_and_drive` owns
  session creation + the retry loop and takes a *title* (not a pre-created
  session id), so the reviewer, burndown, and genesis callers all get the
  policy uniformly and there is one place to test it. Callers no longer call
  `create_session` themselves.

### 15.3 Tests (minimum)

- `classify_session_error_retries_only_transient` — store/5xx/timeout/reset/
  rate-limit shapes classify transient; `MODEL_MAPPINGS`/`BadRequest`/`EACCES`/
  auth classify deterministic; a deterministic marker co-occurring with a
  transient one stays deterministic (precedence); an unrecognized error
  defaults to deterministic.
- A driver-level test (or live round-trip) that a transient error recreates the
  session and a deterministic one fails on the first attempt.

**Reference implementation:** gitlab-harness — `DriveError{Transient,
Deterministic}`, `classify_session_error`, `DETERMINISTIC_ERROR_MARKERS` /
`TRANSIENT_ERROR_MARKERS`, and the bounded retry loop in `prompt_and_drive`
(`src/opencode_server.rs`); the error arms wrap their rendered string in
`classify_session_error` and the loop downcasts to decide retry-vs-fail-fast.

---

## 16. The event vocabulary drifts across opencode builds — validate against `/doc`, never hardcode (the 2026-06-16 `session.next.*` hang)

The single most damaging way the SSE driver fails is **silently, by classifying
the wrong event names.** The §5 event list and the §6.1 skeleton were written to
one opencode build's vocabulary. A *different* build (or a different provider on
the same build) emits **different event `type` strings for the same logical
signals**, and a driver that hardcodes the old names sees those frames as
`Other`, advances nothing, never closes the three-way AND, and **rides every
session to its per-session deadline as a false Timeout** — exactly the
reviewer-outage false-clean the global fixpoint exists to prevent, except slower
and more expensive.

### 16.1 The incident

A genesis run wedged with a textbook signature in the `drive alive` heartbeat:

```
drive alive  elapsed_secs=780  idle_secs=9   tool_calls=600
drive alive  elapsed_secs=810  idle_secs=9   tool_calls=600   ← frozen
…19 minutes of idle_secs=9, tool_calls=600, riding to the 40-min deadline…
```

`tool_calls` frozen at a round number and `idle_secs` **pinned at a small
constant** (here 9) for the whole run is the fingerprint. A *constant* small
`idle_secs` means frames *are* still arriving (resetting the activity clock)
roughly once per heartbeat — that's the **~30s `server.heartbeat` keepalive**
(a real bus event, not an SSE `:`-comment) — but **none of them advance real
work.** The turn had ended/failed via events the classifier didn't recognize.

Root cause, found by capturing the live `/doc` Event union *and* teeing real
frames: opencode **1.16.2** emits turn lifecycle through a **`session.next.*`**
family that the driver (written to an older shape) ignored entirely:

| Logical signal | Old/assumed event | 1.16.2 | 1.17.x (verified 2026-07-09, GitLab Duo) |
|---|---|---|---|
| tool call | `message.part.updated` tool part only | `session.next.tool.called` (build A) **and** `message.part.updated` tool part (build B / Duo) | **only** `message.part.updated` with `part.type=="tool"` (`part.tool`, `part.callID`, `part.state.input`) — **0×** `session.next.tool.called` on the Duo build. Handle **both** names anyway; dedup by `callID`. |
| turn-end failure (cap/model-stop/provider error) | — (none) | `session.next.step.failed` with `error` | **`session.error`** with `error.data.message` (e.g. `ProviderModelNotFoundError`) **and** `session.next.step.failed`. Both must fail the drive fast. |
| step lifecycle | — | `session.next.step.started`/`.ended` | `session.next.step.started`/`.ended` (and bare `step-start`/`step-finish` message parts) |
| streamed text | `message.part.delta` | that **and** `session.next.text.delta` | `message.part.updated`/`.delta` text parts **and** `session.next.text.delta` |
| **interactive question** | a `message.part` tool named `question` | `question.asked` / `question.v2.asked` | **`question.v2.asked`** (first-class, `questions[]` + `id`); `question.asked` as fallback |
| **permission prompt** | `permission.updated` | `permission.asked` / `permission.v2.asked` | **`permission.v2.asked`** (`permission.updated` does **not** exist); `permission.asked` fallback |
| completion | `message.updated{assistant, time.completed}` + `session.idle` | same | same — these legs are **stable** across 1.15→1.17; the drift is all in tool/error/question/permission names |

Two compounding consequences:
- the §14 question handling was **dead** on 1.16.x (it watched for a tool part
  named `question`; the build emits `question.asked`), so an agent that asked
  would hang;
- the `message.part.updated` snapshot recount inflated `tool_calls` to 600 (the
  same call re-emitted ~585×), making the no-op guard meaningless.

### 16.2 The rule

> **Validate the driver's event names against the *running* server's `/doc`
> Event union for the pinned opencode version, and handle every vocabulary the
> target builds use — do not hardcode one build's names.** The `type`
> discriminators are the contract, and they drift release-to-release. Pull them
> live and reconcile the classifier on every opencode bump. The generated
> OpenAPI schema is the source of truth; the bundle strings and this doc's §5
> list are only a snapshot.
>
> **The schema shape itself drifted — walk it robustly.** In 1.17.x the Event
> union members are `$ref`s and the discriminator moved from `type.const` to
> `type.enum`. Pull the id list with:
> ```bash
> curl -s -u opencode:$PW http://127.0.0.1:$PORT/doc |
>   jq -r '.components.schemas
>          | to_entries[]
>          | .value.properties.type.enum[]? // .value.properties.type.const? // empty' |
>   sort -u
> ```
> (or resolve each `.components.schemas.Event.anyOf[].$ref` and read its
> `properties.type.enum[0]`). If a one-liner returns nothing, dump `/doc` and
> inspect `EventMessagePartUpdated`, `EventSessionNextToolCalled`,
> `EventSessionError`, `EventPermissionV2Asked`, `EventQuestionV2Asked` directly.
>
> **Also validate the MODEL id, not just events (the 2026-07-09 incident).**
> Pull `GET /config/providers` and read the actual model keys —
> `.providers[] | select(.id=="gitlab") | .models | keys` — because the Duo id
> has no `claude-` infix (`duo-chat-haiku-4-5`, not `duo-chat-claude-haiku-4-5`)
> and a wrong id 404s every prompt via `session.error`. Never hardcode the
> vendor infix; pick the Haiku-tier id from the live provider list.

Concretely, a robust classifier:
- handles **both** tool vocabularies — `session.next.tool.called` (keyed by
  `callID`) **and** `message.part.updated` tool parts (keyed by the part's
  `callID`, falling back to part `id`) — and **dedups by that id** so N
  snapshots of one call count once (not N). The drive loop keeps a
  `seen_tool_calls: HashSet<String>` and only increments on a fresh id;
- treats **`session.error`** (with the cause in `error.data.message`) **and**
  **`session.next.step.failed`** (and any `*.failed`) as a turn-end error that
  **fails the drive fast** — capture the message, abort, return it. A bad model
  id surfaces here and *only* here (no assistant message ever arrives), so a
  driver that watches only the completion legs rides the deadline (the
  2026-07-09 `tool_calls=0` hang). Transient-classified per §15;
- detects **`question.asked` / `question.v2.asked`** as the question signal
  (carrying `questions[0].question` + the request `id`) and replies via the
  1.16.x endpoint `POST /api/session/:id/question/request/:rid/reject` (reject
  with the autonomous-decision message — there is no human to pick an option, so
  the agent decides for itself and the turn runs on to normal completion; no
  abort/re-prompt needed, which also retires the §14.2.1 drain/re-arm fragility);
- detects **`permission.asked` / `permission.v2.asked`** and replies via `POST
  /api/session/:id/permission/request/:rid/reply` (legacy `/permissions/:id`
  fallback on 404);
- keeps `session.idle` + `message.updated{role:assistant, time.completed}` as
  the completion legs (those names are stable across the builds observed).

### 16.3 Two MANDATORY safety nets so the *next* drift is loud, not silent

Vocabulary drift will happen again on the next opencode bump. Two cheap guards
turn a silent multi-hour hang into an obvious, fast failure:

1. **Stall watchdog keyed on LIVENESS, with the keepalive as the ONLY inert
   frame.** Track `last_activity: Instant` and reset it on **every
   turn-attributable frame** — a new tool call, answer text, a *re-emitted* tool
   snapshot, a reasoning delta, `session.status`/`diff`/`updated`,
   `todo.updated`, anything — **except** the pure keepalive
   (`server.heartbeat`/`server.connected`). If `last_activity.elapsed() >
   STALL_TIMEOUT` (~5 min, well under the per-session deadline), abort and return
   `timed_out` (→ `WorkRemaining`). This is the bound that converts "ride 40 min
   to the deadline" into "fail in 5".

   > **⚠ Inert is a tiny DENYLIST, never an allowlist of "real work" (the
   > 2026-06-16 false-stall).** The first cut of this guard reset the clock
   > *only* on new-tool-call / answer-text / completion. That aborts a genuinely
   > busy agent: a long single tool call re-emits `message.part.updated` under
   > the *same* `callID` (deduped → counted once → no "progress"), and reasoning
   > deltas, `session.status`/`diff`/`updated`, and `todo.updated` all classify
   > `Other` — so a working agent (118 tool calls, 271 `message.part.updated`,
   > 184 `session.status` in the window) looked stalled and was killed at 5 min.
   > **Liveness ≠ progress.** The dedup that (correctly) keeps `tool_calls`
   > honest must NOT gate the stall clock; reset `last_activity` on the frame's
   > *arrival* (when its kind isn't inert), and advance `tool_calls` only on a
   > fresh id, as two independent decisions. Make `is_inert_kind` a denylist of
   > exactly the keepalive kinds so a future opencode build that adds new
   > turn-progress events counts as liveness **by default** — a vocabulary drift
   > must never silently resurrect the false-stall. The genuine-stall signal is
   > "nothing but `server.heartbeat` for `STALL_TIMEOUT`", i.e. the `idle_secs`
   > pin where the *only* arriving frame is the 30s keepalive.
2. **Track and surface unhandled event kinds.** Count every `Other`-classified
   `kind` in a `BTreeMap<String,u32>` and emit it in the heartbeat
   (`unhandled_kinds=N`) and, loudly, in the stall/abort log
   (`unhandled={session.next.tool.called: 412, …}`). The moment a drift recurs,
   the stuck run *names* the events it's dropping — no bundle-string
   archaeology. Pair with a **per-session forensic frame log**: tee every raw
   `{kind,payload}` to `<workdir>/.../frames/<session>.jsonl` so the exact wire
   shapes are on disk for the post-mortem (this is what made the 2026-06-16
   root-cause possible in one pass).

> **Size `SESSION_DEADLINE` and `STALL_TIMEOUT` to the workload (SKILL.md "Size
> the deadlines to the workload").** The `~5 min` stall / `~40 min` deadline
> above are *service-watchdog* values. On a build system or E2E harness an agent
> turn legitimately drives a multi-hour `nix build` / VM boot *inside one tool
> call*, so use `STALL_TIMEOUT` ≈ 20–30 min and `SESSION_DEADLINE` ≈ 2–4 h there.
> The deadline is a HARD anti-wedge backstop, not the normal turn end — keep it
> generous (a deadline that kills a *healthy* turn is the false-Timeout bug);
> only the stall window stays tight, and it is what converts "ride the deadline"
> into "fail fast". The two numbers move together: `STALL_TIMEOUT` must clear the
> longest single keepalive-only stretch a productive turn can have, and
> `SESSION_DEADLINE` must clear the longest *whole* productive turn.

### 16.4 Tests (minimum)

- `question_asked_event_classified` — `question.asked` (and the `.v2.asked`
  alias) → `QuestionAsked{request_id, question}`, reading `questions[0].question`.
- `session_next_tool_called_classifies_with_call_id` and
  `message_part_tool_classifies_with_call_id` — **both** tool vocabularies →
  `ToolUse{call_id,…}`, with `callID` preferred over part `id` for dedup.
- `session_next_step_failed_is_a_session_error` — turn-end failure surfaces as
  an error (then transient-classified per §15).
- `permission_asked_event_classified` — `permission.asked`/`.v2.asked` →
  `PermissionRequested`.
- `only_keepalive_frames_are_inert` — `is_inert_kind` is true for
  `server.heartbeat`/`server.connected` and **false** for every working kind
  (`message.part.updated`, `message.updated`, `session.status`, `session.diff`,
  `session.updated`, `todo.updated`, `message.part.delta`, `session.next.*`).
  This is the regression guard for the 2026-06-16 false-stall.
- A drive-level test (or live round-trip) asserting the stall watchdog fires on
  a synthetic stream of nothing-but-`server.heartbeat` within `STALL_TIMEOUT`,
  does **not** fire on a steady stream of re-emitted tool snapshots / status
  frames, and that `tool_calls` counts **distinct** `callID`s (N snapshots → 1).

**Reference implementation:** hardened-builds-harness — `classify_event` (both
tool vocabularies, `session.next.*`, first-class `question.asked`/
`permission.asked`, `error_message`), `is_inert_kind` (keepalive denylist), the
`seen_tool_calls`/`seen_questions` dedup sets + `last_activity` liveness stall
watchdog (reset on any non-inert frame, independent of the dedup) +
`other_kinds` tracking + the
`append_frame` forensic log in `drive_session`, and `reject_question` /
`reply_permission` in `src/opencode_server.rs`.
