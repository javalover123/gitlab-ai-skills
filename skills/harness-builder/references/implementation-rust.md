# Rust harness builder

When iteratotron runs in genesis mode against a Rust project (Cargo workspace), Phase 0
scaffolds a workspace crate that owns the genesis-side orchestration
specific to this codebase. The crate is named `<project>-genesis` and
sits alongside the rest of the workspace; it composes with
the sibling runtime harness scaffold (when present) and is meant to
be **owned by the project**, not the iteratotron skill — once scaffolded,
it lives in the repo and evolves with the codebase.

The pattern mirrors `references/runtime-rust-skeletons.md (this skill)`
shape but solves a different problem: the runtime harness scaffold drives a
running daemon and feeds log lines to bug-burndown; this harness drives
the *implementation* loop, dispatching iteratotron subagents and
gathering their verdicts.

## Crate layout

```
<project>-genesis/
├── Cargo.toml
├── README.md                       # operator-facing
└── src/
    ├── main.rs                     # outer loop + CLI + pre-flight
    ├── state.rs                    # .iteratotron/state.json IO + atomic-rename
    ├── bootstrap.rs                # Phase 0: doc detection + harness vector
    ├── gap_analysis.rs             # Phase 1: four-list inventory
    ├── plan.rs                     # Phase 2: vertical-slice ordering
    ├── inner_loop.rs               # Phase 3: dispatcher state machine
    ├── constitution_check.rs       # gates each iteratotron dispatch
    ├── streaming.rs                # claude -p stream-json consumer
    ├── adversarial_review.rs       # Phase 7 cold-context reviewer
    ├── harness_runner.rs           # Tier-1/2/3 invocation per language
    │                               #  ↳ flake.nix present ⇒ gates via
    │                               #    `nix develop --command` (pinned
    │                               #    toolchain). See implementation-nix.md
    │                               #    § "Gate-execution contract".
    ├── done_predicate.rs           # Phase 4 evaluator
    └── slsa.rs                     # in-toto + cosign attestation
```

## Cargo.toml essentials

```toml
[package]
name = "<project>-genesis"
version = "0.1.0"
edition = "2024"
publish = false                     # internal harness, not for crates.io

[dependencies]
tokio = { version = "1.50", features = ["rt-multi-thread", "macros", "process", "io-util", "signal", "sync", "time"] }
tokio-util = "0.7"
serde = { version = "1", features = ["derive"] }
serde_json = "1"
clap = { version = "4", features = ["derive"] }
tracing = "0.1"
tracing-subscriber = { version = "0.3", features = ["env-filter", "fmt"] }
chrono = { version = "0.4", features = ["serde"] }
uuid = { version = "1", features = ["v4", "serde"] }
ratatui = { version = "0.30", optional = true }                  # for the streaming TUI
crossterm = { version = "0.27", optional = true }
anyhow = "1"
nix = { version = "0.30", features = ["signal"] }                # for SIGTERM / SIGKILL
sha2 = "0.10"
hex = "0.4"

[features]
tui = ["ratatui", "crossterm"]
default = []

[lints.clippy]
pedantic = { level = "warn", priority = -1 }
unwrap_used = "deny"
expect_used = "deny"
panic = "deny"
todo = "deny"
dbg_macro = "deny"
undocumented_unsafe_blocks = "deny"
```

## main.rs — outer loop

```rust
use anyhow::Result;
use clap::Parser;
use std::path::PathBuf;
use tracing::info;

#[derive(Debug, Parser)]
#[command(name = "<project>-genesis")]
struct Cli {
    /// outer iteratotron parallelism
    #[arg(long, default_value_t = 2)]
    parallel: usize,

    /// inner iterate parallelism per iteratotron session
    #[arg(long, default_value_t = 3)]
    inner: usize,

    /// Global wall-clock budget in seconds. Default 7 days: a converging
    /// implementation run on a real build system (heavy builds, VM/E2E tests,
    /// multi-round burndown) is measured in days, not hours. This is the
    /// practical stop bound; `--max-rounds` is only the anti-runaway ceiling.
    /// Size to the workload — see SKILL.md "Size the deadlines to the workload";
    /// drop to 28_800 (8h) only for a pure fast-feedback project.
    #[arg(long, default_value_t = 604_800)]   // 7 days
    time: u64,

    /// global cost budget in USD
    #[arg(long, default_value_t = 100.0)]
    budget_usd: f64,

    /// resume a prior session by ID
    #[arg(long)]
    resume: Option<String>,

    /// dry run — emit plan and exit without dispatching
    #[arg(long)]
    dry_run: bool,
}

#[tokio::main]
async fn main() -> Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(tracing_subscriber::EnvFilter::from_default_env())
        .init();
    let cli = Cli::parse();

    let state = if let Some(id) = cli.resume {
        state::resume(&id)?
    } else {
        let mut s = state::new_session(&cli)?;
        bootstrap::run(&mut s).await?;
        gap_analysis::run(&mut s).await?;
        plan::run(&mut s).await?;
        s
    };

    if cli.dry_run {
        info!("dry run — plan written, no dispatch");
        return Ok(());
    }

    inner_loop::run(state).await?;
    done_predicate::evaluate_and_attest().await?;

    Ok(())
}
```

## streaming.rs — `claude -p` consumer

The single most important module — every subagent dispatch goes through
this. It owns the `nono` sandbox wrapper, the stream-json parser, the
bridge watchdog, and the per-subagent log tee. See
`references/nono-integration.md` for the full sandbox contract and
policy rationale.

```rust
use anyhow::{Context, Result};
use serde::Deserialize;
use std::ffi::OsString;
use std::path::{Path, PathBuf};
use std::process::Stdio;
use tokio::io::{AsyncBufReadExt, BufReader};
use tokio::process::{Child, Command};
use tokio::sync::Notify;
use tokio::time::{sleep, Duration};

#[derive(Debug, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum Event {
    System { subtype: String, /* ... */ },
    Assistant { message: serde_json::Value },
    User { message: serde_json::Value },
    StreamEvent { event: serde_json::Value },
    Result { subtype: String, total_cost_usd: f64, /* ... */ },
}

pub struct StreamedSubagent {
    pub child: Child,
    pub log_path: std::path::PathBuf,
    pub result_signal: std::sync::Arc<Notify>,
}

/// Prepend `nono run --silent` to a claude argv, deriving `--allow` entries
/// from the same `allow_dirs` that will become `--add-dir` entries.
/// Returns the original claude argv unchanged when `network_profile` is
/// `None` and `allow_dirs` is empty — useful when the preflight verdict is
/// `acceptEdits` (unsandboxed fallback). In that case the caller passes the
/// original argv directly to `Command::new("claude")`.
///
/// See `references/nono-integration.md` for the --add-dir ↔ --allow invariant.
pub fn wrap_with_nono(
    claude_argv: &[OsString],
    allow_dirs: &[PathBuf],
    read_dirs: &[PathBuf],
    network_profile: Option<&str>,
) -> Vec<OsString> {
    let mut argv: Vec<OsString> = vec![
        OsString::from("nono"),
        OsString::from("run"),
        OsString::from("--silent"),
    ];
    if let Some(profile) = network_profile {
        argv.push(OsString::from("--network-profile"));
        argv.push(OsString::from(profile));
    }
    for d in allow_dirs {
        argv.push(OsString::from("--allow"));
        argv.push(d.as_os_str().into());
    }
    for d in read_dirs {
        argv.push(OsString::from("--read"));
        argv.push(d.as_os_str().into());
    }
    argv.push(OsString::from("--"));
    argv.extend_from_slice(claude_argv);
    argv
}

pub async fn dispatch(
    prompt: &str,
    log_dir: &Path,
    model: &str,
    add_dirs: &[&str],
    disallowed_tools: &[&str],
    max_turns: u32,
    max_budget_usd: f64,
    permission_mode: &str,
    sandbox_network_profile: Option<&str>,
) -> Result<StreamedSubagent> {
    std::fs::create_dir_all(log_dir)?;
    let log_path = log_dir.join(format!("{}.jsonl", chrono::Utc::now().timestamp()));

    // Build the claude argv first — same shape regardless of sandbox.
    let mut claude_argv: Vec<OsString> = vec![
        "claude".into(), "-p".into(), prompt.into(),
        "--output-format".into(), "stream-json".into(),
        "--verbose".into(),
        "--include-partial-messages".into(),
        "--permission-mode".into(), permission_mode.into(),
        "--model".into(), model.into(),
        "--max-turns".into(), max_turns.to_string().into(),
        "--max-budget-usd".into(), max_budget_usd.to_string().into(),
    ];
    let allow_dirs: Vec<PathBuf> = {
        let mut v: Vec<PathBuf> = add_dirs.iter().map(PathBuf::from).collect();
        // shared dotfile dirs the harness writes to
        v.push(PathBuf::from(".bug-burndown"));
        v.push(PathBuf::from(".test-effectiveness"));
        v.push(PathBuf::from(".iteratotron"));
        v
    };
    for d in add_dirs { claude_argv.push("--add-dir".into()); claude_argv.push(d.into()); }
    for t in disallowed_tools { claude_argv.push("--disallowed-tools".into()); claude_argv.push(t.into()); }

    // Wrap with nono when sandbox is active (permission_mode == bypassPermissions).
    // --allow and --add-dir are derived from the same `allow_dirs` variable —
    // the --add-dir ↔ --allow invariant (nono-integration.md).
    let read_dirs = vec![
        dirs::home_dir().unwrap_or_default().join(".cargo/bin"),
        dirs::home_dir().unwrap_or_default().join(".rustup"),
    ];
    let final_argv = if permission_mode == "bypassPermissions" {
        wrap_with_nono(&claude_argv, &allow_dirs, &read_dirs, sandbox_network_profile)
    } else {
        claude_argv
    };

    let mut cmd = Command::new(&final_argv[0]);
    cmd.args(&final_argv[1..])
        .env("CLAUDE_BWRAP_TTY", "0")  // force --pipe in any bwrap wrapper on PATH
        .stdin(Stdio::null())           // wrappers waiting on EOF need this
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());

    // When sandboxed, nono is the direct child (the nono PID) and claude
    // runs as nono's child. The watchdog targets the nono PID — SIGTERM sent
    // to nono is forwarded to claude by nono's signal proxy.
    let mut child = cmd.spawn().context("spawn nono+claude subagent")?;
    let stdout = child.stdout.take().context("child stdout missing")?;
    let result_signal = std::sync::Arc::new(Notify::new());

    let log = std::fs::File::create(&log_path)?;
    let log_writer = std::sync::Arc::new(std::sync::Mutex::new(log));

    let signal = result_signal.clone();
    let log_writer_clone = log_writer.clone();
    tokio::spawn(async move {
        let mut lines = BufReader::new(stdout).lines();
        while let Ok(Some(line)) = lines.next_line().await {
            // tee raw line to disk BEFORE filtering
            use std::io::Write;
            if let Ok(mut w) = log_writer_clone.lock() {
                let _ = writeln!(*w, "{line}");
            }
            // detect the `result` event so the watchdog can fire
            if line.contains(r#""type":"result""#) {
                signal.notify_one();
            }
        }
    });

    Ok(StreamedSubagent { child, log_path, result_signal })
}

/// Wait for the subagent (nono PID) with a watchdog that fires on stream-json shutdown stall.
/// SIGTERM sent to the nono PID is forwarded to claude by nono's signal proxy.
pub async fn wait_with_watchdog(mut subagent: StreamedSubagent, grace_secs: u64) -> Result<()> {
    let signal = subagent.result_signal.clone();
    let pid = subagent.child.id().map(nix::unistd::Pid::from_raw);

    tokio::select! {
        status = subagent.child.wait() => {
            let _ = status?;
        }
        _ = async {
            signal.notified().await;
            sleep(Duration::from_secs(grace_secs)).await;
        } => {
            // graceful: SIGTERM → nono (forwarded to claude) then SIGKILL after 10s
            if let Some(pid) = pid {
                let _ = nix::sys::signal::kill(pid, nix::sys::signal::Signal::SIGTERM);
                sleep(Duration::from_secs(10)).await;
                let _ = nix::sys::signal::kill(pid, nix::sys::signal::Signal::SIGKILL);
            }
        }
    }
    Ok(())
}
```

## inner_loop.rs — the dispatcher

Pseudo-code (full implementation is project-specific):

```rust
pub async fn run(mut state: state::SessionState) -> Result<()> {
    while !state.is_terminal() && !state.budget_exhausted() {
        // 1. fill outer slots (iteratotron sessions) up to parallel cap
        let dispatchable = state.scope_queue.iter()
            .filter(|s| s.status == "queued" && state.blockers_satisfied(s))
            .take(state.budgets.parallel_outer)
            .collect::<Vec<_>>();

        let mut handles = Vec::new();
        for scope in &dispatchable {
            // Constitution Check before dispatch
            let check = constitution_check::run(scope).await?;
            if !check.pass {
                state.park_for_human(scope, &check.violations);
                continue;
            }

            // create worktree, dispatch iteratotron
            let worktree = state.create_worktree(scope).await?;
            let prompt = render_iteratotron_prompt(scope, &state);
            let subagent = streaming::dispatch(&prompt, &worktree.log_dir, "haiku",
                &state.add_dirs(), &["WebSearch"], 80, 20.0).await?;
            handles.push((scope.id.clone(), worktree, subagent));
        }

        // 2. wait for any subagent to finish, then run Phase 7 adversarial review
        for (scope_id, worktree, subagent) in handles {
            streaming::wait_with_watchdog(subagent, 30).await?;
            let verdict = adversarial_review::run(&scope_id, &worktree).await?;
            match verdict {
                Verdict::Approved => state.merge_worktree(&scope_id, &worktree).await?,
                Verdict::Insufficient(lessons) => state.requeue_scope(&scope_id, lessons).await,
                Verdict::NeedsHuman(reason) => state.park_for_human(&scope_id, &reason),
            }
            // tier escalation
            harness_runner::run_applicable_tiers(&scope_id, &state.harness_vector).await?;
        }

        // 3. interleave bug-burndown when bug_queue non-empty
        if !state.bug_queue.is_empty() {
            inner_loop::dispatch_burndown(&mut state).await?;
        }

        state.fsync()?;
    }
    Ok(())
}
```

## How this composes with the runtime harness

When the project already has a `<project>-harness` (also generated by
`harness-builder`, but from the runtime workflow under
`references/runtime-*.md`), the implementation harness from this builder
**does not replace it** — they cooperate:

- `<project>-genesis` drives the implementation loop (orchestrates iteratotron + bug-burndown).
- `<project>-harness` drives the runtime loop (daemon watcher + reviewer + bug-burndown bridge).
- Both write findings to the same `.bug-burndown/<session-id>/` format; bug-burndown closes findings from either source.
- Both consume `.test-effectiveness/baseline.json` for mutation / CRAP / coverage data.

The two harnesses can run in different terminals on the same repo
without colliding — iteratotron owns `.iteratotron/`, the runtime harness
owns `.harness/`, bug-burndown owns `.bug-burndown/`. The shared files
are read-mostly (baseline.json) or append-only (bug-burndown session dirs).

## Scaffolding the harness

Phase 1 of iteratotron (in genesis mode) runs:

```bash
# detect existing harness
if ! [ -d "<project>-genesis" ]; then
  # scaffold from this reference
  cargo new --lib <project>-genesis
  # copy module skeletons from this file (references/implementation-rust.md)
  # add to workspace Cargo.toml's [workspace.members]
  # commit as the first commit of the genesis session
fi
```

The skeleton is committed as the genesis session's first commit. Subsequent
session commits (worktree merges from iteratotron) layer on top. The
harness itself is iteratively extended — when genesis discovers it needs
a project-specific tool integration (a custom Toxiproxy wrapper, a
project-native nixosTest helper), the change goes into the harness
crate via a normal iteratotron scope.

---

## opencode_server.rs — opencode server driver (opencode-server backend)

Generated alongside `streaming.rs` when `agent_host: opencode-server` is selected.
Full skeleton with all HTTP+SSE contracts, lifecycle state machine, and the
`run_event_loop` / `shutdown` implementations is in
`references/opencode-server-integration.md §6.1`. Wire it to the harness's
existing logging and `wrap_with_nono` helper.

Add to `Cargo.toml` when generating this module:

```toml
reqwest = { version = "0.12", features = ["json", "stream"] }
eventsource-stream = "0.2"
futures-util = "0.3"
```

Public surface the driver exposes (from the §6.1 skeleton):

```rust
pub struct ServerHandle { /* child, pgid, base_url, password, http */ }

impl ServerHandle {
    pub async fn launch(project_root: &str, port: u16, password: &str) -> Result<Self>
    pub async fn create_session(&self, title: &str) -> Result<String>
    pub async fn prompt_async(&self, session: &str, agent: &str, text: &str) -> Result<()>
    pub async fn respond_permission(&self, session: &str, perm: &str, decision: &str) -> Result<()>
    pub async fn todo_empty(&self, session: &str) -> Result<bool>
    pub async fn abort(&self, session: &str) -> Result<()>
    pub async fn run_event_loop<F, S>(&self, on_event: F, should_stop: S) -> Result<()>
    pub async fn shutdown(mut self, grace: Duration) -> Result<()>
}
```

## agent_host backend switch

Add to `streaming.rs`:

```rust
#[derive(Clone, Debug, Default)]
pub enum AgentHost {
    #[default]
    ClaudeStream,
    OpencodeServer,
}
```

Add `agent_host: AgentHost` and `server: Option<Arc<opencode_server::ServerHandle>>`
to `SessionState` (state.rs). Replace the `streaming::dispatch()` call site in
`inner_loop.rs` with this branch:

```rust
match &state.agent_host {
    AgentHost::ClaudeStream => {
        // existing path — unchanged
        let subagent = streaming::dispatch(
            &prompt, &worktree.log_dir, model,
            &state.add_dirs(), &["WebSearch"], 80, 20.0,
            permission_mode, sandbox_network_profile,
        ).await?;
        streaming::wait_with_watchdog(subagent, 30).await?;
    }
    AgentHost::OpencodeServer => {
        let sv = state.server.as_ref()
            .ok_or_else(|| anyhow!("no server handle for opencode-server backend"))?;
        let session_id = sv.create_session(&scope.title).await?;
        sv.prompt_async(&session_id, "build", &prompt).await?;
        wait_session_complete(sv, &session_id).await?;
    }
}
```

Three-way completion detection (required by `opencode-server-integration.md §5`):

```rust
async fn wait_session_complete(
    sv: &opencode_server::ServerHandle,
    session_id: &str,
) -> Result<()> {
    let (mut msg_complete, mut idle) = (false, false);
    sv.run_event_loop(
        |kind, data| match kind {
            "message.updated" => {
                let info = data.get("info");
                let our_session = info
                    .and_then(|i| i.get("sessionID"))
                    .and_then(Value::as_str) == Some(session_id);
                if our_session {
                    let completed = info
                        .and_then(|i| i.get("time"))
                        .and_then(|t| t.get("completed"))
                        .is_some();
                    let no_error = info.and_then(|i| i.get("error")).is_none();
                    if completed && no_error { msg_complete = true; }
                }
            }
            "session.idle" => {
                if data.get("sessionID").and_then(Value::as_str) == Some(session_id) {
                    idle = true;
                }
            }
            "permission.updated" => {
                // match allowlist → respond_permission("always" or "reject")
                // append every decision to the run manifest audit log
            }
            "session.error" => { /* record + break */ }
            _ => {}
        },
        || msg_complete && idle,
    ).await?;
    // third leg: todo must be empty before declaring completion
    if !sv.todo_empty(session_id).await? {
        return Err(anyhow!("session {session_id}: idle but todo non-empty"));
    }
    Ok(())
}
```

## main.rs — server lifecycle (agent_host: opencode-server)

Extend `Cli`:

```rust
/// agent host backend: "claude-stream" (default) | "opencode-server"
#[arg(long, default_value = "claude-stream")]
agent_host: String,

/// port for the opencode serve process (opencode-server backend only)
#[arg(long, default_value_t = 7654)]
opencode_port: u16,
```

Lifecycle wiring in `main()`, after preflight and worktree resolution:

```rust
let server = match cli.agent_host.as_str() {
    "opencode-server" => {
        let password = std::env::var("OPENCODE_SERVER_PASSWORD")
            .unwrap_or_else(|_| uuid::Uuid::new_v4().to_string());
        let sv = opencode_server::ServerHandle::launch(
            &project_root, cli.opencode_port, &password,
        ).await.context("launch opencode server")?;
        Some(sv)
    }
    _ => None,
};

let result = inner_loop::run(state).await;
// DISPOSE on every exit path — success, error, or early return
if let Some(sv) = server {
    sv.shutdown(Duration::from_secs(10)).await.ok();
}
result?;
done_predicate::evaluate_and_attest().await
```

`SessionState` carries `server: Option<Arc<opencode_server::ServerHandle>>` so
`inner_loop` reaches it without threading a separate parameter.

**Python and Nix harnesses** do not gain the `opencode-server` backend in this
release. Document this in the generated README; note it as a follow-up.
