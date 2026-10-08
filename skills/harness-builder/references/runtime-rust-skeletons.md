# Module Skeletons

Rust code for each of the seven harness modules. Adapted from the
working the reference harness binary (commits `7f99846` + `eed6326` in the
ExampleApp repo). Adapt the type names, RPC trait imports, and the drive
surface to match the target system. The structure stays.

## Cargo.toml

```toml
[package]
name = "<crate-name>"
version.workspace = true
edition.workspace = true
license.workspace = true
description = "Closed-loop quality harness — drives <system> with a fixed input, triages logs, feeds /bug-burndown."

[[bin]]
name = "<crate-name>"
path = "src/main.rs"

[dependencies]
# Target system's RPC crate (or its CLI if no RPC).
<target-rpc> = { path = "../<target-rpc>" }

# tarpc framing — match the daemon's feature set so the bincode
# framing lines up.
tarpc = { version = "0.37", default-features = false, features = ["serde1", "tokio1", "serde-transport", "serde-transport-bincode", "tcp", "unix"] }
tokio-serde = { version = "0.9", features = ["bincode"] }
tokio-util = { version = "0.7", features = ["codec"] }

tokio = { workspace = true, features = ["macros", "rt-multi-thread", "process", "signal", "fs", "io-util", "time"] }
serde = { workspace = true }
serde_json = { workspace = true }
chrono = { workspace = true }
uuid = { workspace = true }
anyhow = { workspace = true }
thiserror = { workspace = true }
tracing = { workspace = true }
tracing-subscriber = { workspace = true }
clap = { workspace = true }
regex = { workspace = true }    # pass 2 template fingerprinting + action_audit token extractor
nix = { version = "0.30", features = ["signal"] }
```

## src/main.rs

```rust
//! Closed-loop quality harness for <system>.

#![deny(clippy::unwrap_used, clippy::expect_used, clippy::panic)]

mod action_audit;
mod burndown;
mod client;
mod daemon;
mod findings;
mod log_capture;
mod reviewer;

use std::path::PathBuf;
use std::time::Duration;

use anyhow::{Context, Result};
use clap::Parser;
use tracing::{info, warn};

#[derive(Parser, Debug)]
#[command(name = "<crate-name>", about, version)]
struct Cli {
    /// Drive-surface input — what you feed the system on each iteration.
    #[arg(long, default_value = "<sensible default>")]
    input: String,

    /// Daemon config file. Same flag the daemon's own CLI accepts.
    #[arg(long, default_value = "config/development.toml")]
    config: PathBuf,

    /// Unix socket path. Default is project-local so it works in any
    /// environment (host shell, nix-shell, sandbox) without /tmp
    /// bind-mount surprises. Pass an absolute path to override.
    #[arg(long)]
    socket: Option<PathBuf>,

    /// Per-iteration artefact directory.
    #[arg(long, default_value = ".harness")]
    work_dir: PathBuf,

    /// Cold cargo build of the daemon can run several minutes — the
    /// default leaves headroom so the timeout only fires on a genuinely
    /// stuck daemon.
    #[arg(long, default_value_t = 300)]
    socket_wait_secs: u64,

    /// Idle-window seconds — no new log lines for this long means
    /// the daemon is in a terminal state.
    #[arg(long, default_value_t = 45)]
    idle_secs: u64,

    /// Per-iteration hard cap on wall-clock time. Even if the daemon
    /// never goes idle, the harness moves to triage at this point. 30 min
    /// suits a request/response service; for a daemon that drives long
    /// builds/migrations/E2E before settling, raise this so a healthy drive
    /// isn't cut short (see SKILL.md "Size the deadlines to the workload").
    #[arg(long, default_value_t = 30 * 60)]
    iteration_timeout_secs: u64,

    /// claude CLI binary used for both the reviewer and the burndown
    /// bridge. Override to point at a sandbox wrapper like `claude-bwrap`.
    #[arg(long, default_value = "claude")]
    claude_bin: String,

    /// `--permission-mode` for the reviewer's claude --print. Defaults
    /// to "bypassPermissions" because the harness always runs under
    /// `nono run` (see references/nono-integration.md). Pass
    /// "default" only when running without nono (not recommended).
    #[arg(long, default_value = "bypassPermissions")]
    reviewer_permission_mode: String,

    /// `--permission-mode` for the burndown bridge's claude --print.
    /// Defaults to "bypassPermissions" for the same reason as the
    /// reviewer. Pass "acceptEdits" only without nono.
    #[arg(long, default_value = "bypassPermissions")]
    burndown_permission_mode: String,

    /// When set, run without nono sandbox and keep permission_mode at
    /// acceptEdits. Not recommended for unattended loops. See
    /// references/nono-integration.md for the preflight policy.
    #[arg(long)]
    allow_unsandboxed: bool,

    /// `--network-profile` passed to nono run. Default "claude-code"
    /// allows api.anthropic.com. Dropped automatically on kernels
    /// without Landlock ABI v4+ (detected by the preflight).
    #[arg(long, default_value = "claude-code")]
    network_profile: String,

    /// Model for reviewer pass 1 (failure-shaped). Haiku is plenty
    /// for keyword + short-rubric pattern matching; ~10× cheaper
    /// than Sonnet on what's effectively a classification job.
    #[arg(long, default_value = "haiku")]
    reviewer_pass1_model: String,

    /// Model for reviewer pass 2 (silent-divergence). Haiku is the
    /// default; the intent-vs-observed judgement on a bounded prompt is
    /// well within its reach. Raise to Sonnet only for very complex,
    /// heavily-paraphrased divergence that Haiku misses. Never Opus.
    #[arg(long, default_value = "haiku")]
    reviewer_pass2_model: String,

    /// Model for the burndown bridge. Haiku is the default and handles
    /// the great majority of bug burns. Raise to Sonnet only for very
    /// complex agentic debugging where a wrong root-cause means iterating
    /// on the wrong fix. Never default to Opus — it's wasteful here.
    #[arg(long, default_value = "haiku")]
    burndown_model: String,

    /// Skip the bug-burndown phase — useful for one-off log triage.
    #[arg(long)]
    no_burndown: bool,

    /// Resume from an existing iteration directory whose daemon log
    /// is already captured. Skips pre-build, daemon spawn, and log
    /// capture; reads `<iter-dir>/server.log` directly and continues
    /// at the review phase. Use after a mid-iteration failure (e.g.
    /// reviewer JSON parse error) to retry the review without
    /// spending another half-hour re-running the daemon.
    #[arg(long, value_name = "ITER_DIR")]
    resume_iter: Option<PathBuf>,
}

#[tokio::main]
async fn main() -> Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| tracing_subscriber::EnvFilter::new("info")),
        )
        .init();

    let cli = Cli::parse();
    tokio::fs::create_dir_all(&cli.work_dir).await?;

    // Resolve socket to absolute path under work_dir if not overridden.
    let socket_path = match &cli.socket {
        Some(p) => p.clone(),
        None => tokio::fs::canonicalize(&cli.work_dir)
            .await
            .with_context(|| format!("canonicalize {}", cli.work_dir.display()))?
            .join("daemon.sock"),
    };

    info!(
        socket = %socket_path.display(),
        work_dir = %cli.work_dir.display(),
        input = %cli.input,
        claude_bin = %cli.claude_bin,
        "<crate-name> starting"
    );

    // Fail fast on a typoed --claude-bin instead of finding out 5+
    // minutes into iteration 1. See references/gotchas.md §
    // "Pre-flight --claude-bin check" for the function body.
    check_claude_bin(&cli.claude_bin).await?;

    // Resume mode short-circuits pre-build and daemon spawn on the
    // first iteration only. Subsequent iterations always start fresh.
    let resume_iter = cli.resume_iter.clone();

    if resume_iter.is_none() {
        // Pre-build the daemon so iteration 1 doesn't race the
        // socket-wait timer on a cold compile.
        info!("phase: pre-build (cargo build -p <daemon-crate>)");
        let build_started = std::time::Instant::now();
        let build_status = tokio::process::Command::new("cargo")
            .args(["build", "-p", "<daemon-crate>"])
            .status()
            .await
            .context("spawn cargo build")?;
        if !build_status.success() {
            return Err(anyhow::anyhow!(
                "cargo build -p <daemon-crate> failed with {build_status:?}"
            ));
        }
        info!(elapsed_secs = build_started.elapsed().as_secs(), "pre-build complete");
    } else {
        info!("phase: pre-build SKIPPED — --resume-iter is set");
    }

    let mut iteration: u32 = 0;
    let mut resume_iter = resume_iter;  // consume on first iteration
    loop {
        iteration += 1;
        let iter_started = std::time::Instant::now();
        info!("============================================================");
        info!(iteration, "STARTING ITERATION");
        info!("============================================================");

        let (iter_dir, log_path, lines) = if let Some(resume_dir) = resume_iter.take() {
            // Resume path: read the previously-captured log; no daemon.
            let log_path = resume_dir.join("daemon.log");
            info!(iteration, resume_from = %resume_dir.display(),
                  "phase: resume — reading captured log instead of spawning daemon");
            let lines = read_captured_log(&log_path).await
                .with_context(|| format!("read resume log {}", log_path.display()))?;
            info!(iteration, lines = lines.len(),
                  "captured log loaded from resume directory");
            (resume_dir, log_path, lines)
        } else {
            // Normal path: create iter-NNN/, spawn daemon, capture log.
            let iter_dir = cli.work_dir.join(format!("iter-{iteration:03}"));
            tokio::fs::create_dir_all(&iter_dir).await?;
            let log_path = iter_dir.join("daemon.log");
            info!(iter_dir = %iter_dir.display(), "iteration artefact directory ready");

            info!(iteration, "phase: spawn daemon");
            let mut daemon = daemon::Daemon::start(daemon::Spec {
                config: cli.config.clone(),
                socket: socket_path.clone(),
                log_file: log_path.clone(),
                cargo_log: iter_dir.join("cargo.log"),
            })
            .await
            .context("start daemon")?;

            info!(iteration, "phase: dispatch input + tail log");
            let ingest_outcome = run_one_iteration(&cli, &socket_path, &log_path).await;

            info!(iteration, "phase: shutdown daemon");
            if let Err(e) = daemon.shutdown(Duration::from_secs(30)).await {
                warn!(?e, "daemon shutdown returned non-zero");
            }

            let lines = ingest_outcome?;
            info!(iteration, captured = lines.len(), "captured daemon log lines");
            (iter_dir, log_path, lines)
        };

        // Two-pass review: pass 1 (failure-shaped) + pass 2 (silent
        // divergence). Each pass uses its own model — see Cli docs
        // and SKILL.md § "Model selection per phase" for rationale.
        info!(iteration,
              pass1_model = %cli.reviewer_pass1_model,
              pass2_model = %cli.reviewer_pass2_model,
              "phase: adversarial review (pass 1: failures, pass 2: silent divergence)");
        let mut verdicts = reviewer::review(
            &cli.claude_bin,
            &cli.reviewer_permission_mode,
            &cli.reviewer_pass1_model,
            &cli.reviewer_pass2_model,
            &lines,
        )
        .await
        .context("adversarial reviewer")?;

        // Structural anti-rationalization pass. Walks the captured
        // lines, counts hard-failure vs genuine-upstream-success
        // markers per `action=` / `task_kind=` token, and emits
        // synthetic rejects for actions that only ever failed.
        // Bypasses the LLM rubric — log-line euphemisms ("designed
        // error path", "served from cached entries", "Task completed
        // success=true") cannot talk the audit out of a verdict.
        // See SKILL.md § "Structural anti-rationalization pass" for
        // the canonical KEV incident that motivates this pass.
        let mut audit_verdicts = action_audit::audit(&lines);
        if !audit_verdicts.is_empty() {
            info!(
                iteration,
                audit_rejects = audit_verdicts.len(),
                "structural audit emitted synthetic rejects (zero-success actions)"
            );
            verdicts.append(&mut audit_verdicts);
        }

        let rejects: Vec<_> = verdicts.iter().filter(|v| v.is_reject()).collect();
        reviewer::log_reject_summary(&verdicts);
        info!(
            iteration,
            total = verdicts.len(),
            rejects = rejects.len(),
            iter_elapsed_secs = iter_started.elapsed().as_secs(),
            "review complete"
        );

        if rejects.is_empty() {
            info!("============================================================");
            info!(iteration, "ITERATION CLEAN — zero rejects, stopping loop");
            info!("============================================================");
            break Ok(());
        }

        if cli.no_burndown {
            info!(iteration, rejects = rejects.len(), "--no-burndown set: surfacing rejects and exiting");
            findings::dump_to_stdout(&rejects);
            break Ok(());
        }

        info!(iteration, "phase: write burndown session");
        let session_id = findings::write_burndown_session(&rejects, &log_path)
            .await
            .context("write burndown session")?;
        info!(%session_id, bugs = rejects.len(), "dispatching /bug-burndown");

        let burndown_log = iter_dir.join("burndown.log");
        let burndown_started = std::time::Instant::now();
        burndown::run(
            &cli.claude_bin,
            &cli.burndown_permission_mode,
            &cli.burndown_model,
            &session_id,
            &burndown_log,
        )
        .await
        .context("bug-burndown run")?;
        info!(
            %session_id,
            elapsed_secs = burndown_started.elapsed().as_secs(),
            burndown_log = %burndown_log.display(),
            "bug-burndown returned, looping back"
        );
    }
}

async fn run_one_iteration(
    cli: &Cli,
    socket: &std::path::Path,
    log_path: &std::path::Path,
) -> Result<Vec<String>> {
    daemon::wait_for_socket(socket, Duration::from_secs(cli.socket_wait_secs)).await?;
    let client = client::connect(socket).await.context("connect")?;
    let handle = client::drive(&client, &cli.input).await.context("drive RPC")?;
    info!(handle = ?handle, "input dispatched");

    log_capture::collect_until_idle(
        log_path,
        Duration::from_secs(cli.idle_secs),
        Duration::from_secs(cli.iteration_timeout_secs),
    )
    .await
}

/// Read an entire previously-captured daemon log for the resume path.
/// The live `collect_until_idle` tailer can't be reused here — it
/// waits at EOF for new lines, but the daemon's gone, so nothing is
/// coming. Just read the file once and split.
async fn read_captured_log(log_path: &std::path::Path) -> Result<Vec<String>> {
    let bytes = tokio::fs::read(log_path).await.with_context(|| {
        format!("open resume log {} — does the iteration directory exist?",
                log_path.display())
    })?;
    Ok(String::from_utf8_lossy(&bytes)
        .lines()
        .map(|l| l.to_string())
        .collect())
}
```

## src/daemon.rs

```rust
//! Daemon lifecycle: spawn, wait for socket, SIGTERM -> SIGKILL teardown.

use std::path::{Path, PathBuf};
use std::time::Duration;

use anyhow::{bail, Context, Result};
use nix::sys::signal::{kill, Signal};
use nix::unistd::Pid;
use tokio::process::{Child, Command};
use tokio::time::{sleep, Instant};
use tracing::{info, warn};

pub struct Spec {
    pub config: PathBuf,
    pub socket: PathBuf,
    pub log_file: PathBuf,
    /// Where cargo's own stdout/stderr lands. Empty in the happy path;
    /// gold for triage when the daemon never gets to its own logger.
    pub cargo_log: PathBuf,
}

pub struct Daemon {
    child: Option<Child>,
    socket: PathBuf,
}

impl Daemon {
    pub async fn start(spec: Spec) -> Result<Self> {
        let _ = tokio::fs::remove_file(&spec.socket).await;
        if let Some(parent) = spec.log_file.parent() {
            tokio::fs::create_dir_all(parent).await?;
        }
        if let Some(parent) = spec.cargo_log.parent() {
            tokio::fs::create_dir_all(parent).await?;
        }

        info!(
            socket = %spec.socket.display(),
            log = %spec.log_file.display(),
            cargo_log = %spec.cargo_log.display(),
            "spawning daemon"
        );

        let cargo_stdout = std::fs::File::create(&spec.cargo_log)
            .with_context(|| format!("create cargo log {}", spec.cargo_log.display()))?;
        let cargo_stderr = cargo_stdout
            .try_clone()
            .context("clone cargo log fd for stderr")?;

        let child = Command::new("cargo")
            .args(["run", "--quiet", "-p", "<daemon-crate>", "--", "--config"])
            .arg(&spec.config)
            .arg("--socket")
            .arg(&spec.socket)
            .arg("--log-file")
            .arg(&spec.log_file)
            .stdout(std::process::Stdio::from(cargo_stdout))
            .stderr(std::process::Stdio::from(cargo_stderr))
            .process_group(0)
            .spawn()
            .context("spawn cargo run")?;

        Ok(Self { child: Some(child), socket: spec.socket })
    }

    pub async fn shutdown(&mut self, grace: Duration) -> Result<()> {
        let Some(mut child) = self.child.take() else { return Ok(()); };
        let Some(pid) = child.id() else {
            let _ = child.wait().await;
            return Ok(());
        };

        info!(pid, "sending SIGTERM to daemon process group");
        let pgid = Pid::from_raw(-(pid as i32));
        if let Err(e) = kill(pgid, Signal::SIGTERM) {
            warn!(?e, "SIGTERM to pgid failed; trying single-pid");
            let _ = kill(Pid::from_raw(pid as i32), Signal::SIGTERM);
        }

        let deadline = Instant::now() + grace;
        loop {
            match tokio::time::timeout(Duration::from_millis(200), child.wait()).await {
                Ok(Ok(status)) => {
                    info!(?status, "daemon exited cleanly");
                    let _ = tokio::fs::remove_file(&self.socket).await;
                    return Ok(());
                }
                Ok(Err(e)) => bail!("waitpid: {e}"),
                Err(_) if Instant::now() >= deadline => break,
                Err(_) => {}
            }
        }

        warn!("grace expired, sending SIGKILL");
        let _ = child.kill().await;
        let _ = child.wait().await;
        let _ = tokio::fs::remove_file(&self.socket).await;
        Ok(())
    }
}

impl Drop for Daemon {
    fn drop(&mut self) {
        if let Some(child) = self.child.as_mut() {
            if let Some(pid) = child.id() {
                let pgid = Pid::from_raw(-(pid as i32));
                let _ = kill(pgid, Signal::SIGKILL);
            }
        }
    }
}

/// Polls for the listen socket. Returns when it exists, errors after
/// `timeout`. Heartbeats every 10 s during the wait.
pub async fn wait_for_socket(socket: &Path, timeout: Duration) -> Result<()> {
    let start = Instant::now();
    let mut last_heartbeat = Instant::now();
    info!(socket = %socket.display(), budget_secs = timeout.as_secs(), "waiting for daemon socket");
    loop {
        if tokio::fs::metadata(socket).await.is_ok() {
            info!(
                socket = %socket.display(),
                elapsed_secs = start.elapsed().as_secs(),
                "daemon socket appeared"
            );
            return Ok(());
        }
        if start.elapsed() >= timeout {
            bail!(
                "daemon socket {} did not appear within {:?}. Check the iteration's cargo.log and daemon.log.",
                socket.display(), timeout
            );
        }
        if last_heartbeat.elapsed() >= Duration::from_secs(10) {
            info!(
                elapsed_secs = start.elapsed().as_secs(),
                budget_secs = timeout.as_secs(),
                "still waiting for daemon socket"
            );
            last_heartbeat = Instant::now();
        }
        sleep(Duration::from_millis(250)).await;
    }
}
```

## src/client.rs

```rust
//! tarpc client over the daemon's Unix socket. Adapt the trait import
//! and the drive call (`drive(client, input)`) to the target system.

use std::path::Path;
use std::time::Duration;

use anyhow::{anyhow, Context, Result};
use <target-rpc>::types::{AuthCredentials, /* DriveHandle type */};
use <target-rpc>::<ServiceClient>;
use tarpc::context;
use tokio_util::codec::length_delimited;

const MAX_FRAME_BYTES: usize = 64 * 1024 * 1024;

pub async fn connect(socket: &Path) -> Result<<ServiceClient>> {
    let stream = tokio::net::UnixStream::connect(socket)
        .await
        .with_context(|| format!("dial {}", socket.display()))?;

    let mut frame_builder = length_delimited::Builder::new();
    frame_builder.max_frame_length(MAX_FRAME_BYTES);

    let framed = tarpc::serde_transport::new(
        frame_builder.new_framed(stream),
        tokio_serde::formats::Bincode::default(),
    );
    Ok(<ServiceClient>::new(tarpc::client::Config::default(), framed).spawn())
}

pub async fn drive(client: &<ServiceClient>, input: &str) -> Result</* DriveHandle */> {
    let mut ctx = context::current();
    ctx.deadline = std::time::Instant::now() + Duration::from_secs(120);

    let result = client
        .<drive_rpc>(ctx, AuthCredentials::default(), input.to_string(), None)
        .await
        .map_err(|e| anyhow!("tarpc transport error: {e}"))?;

    result.map_err(|e| anyhow!("drive RPC error: {e:?}"))
}
```

## src/log_capture.rs

```rust
//! Tail the daemon log; return on idle window or hard cap. Stream every
//! suspicious line via warn!() so the operator sees bugs in real time.

use std::path::Path;
use std::time::Duration;

use anyhow::{Context, Result};
use tokio::fs::File;
use tokio::io::{AsyncBufReadExt, AsyncSeekExt, BufReader, SeekFrom};
use tokio::time::{sleep, Instant};
use tracing::{debug, info, warn};

use crate::reviewer;

pub async fn collect_until_idle(
    log_path: &Path,
    idle_window: Duration,
    hard_cap: Duration,
) -> Result<Vec<String>> {
    let mut file = open_with_retry(log_path, Duration::from_secs(5)).await?;
    // Seek to EOF — we only want what happens AFTER drive dispatch.
    file.seek(SeekFrom::End(0)).await?;
    let mut reader = BufReader::new(file);

    let mut buf = String::new();
    let mut lines: Vec<String> = Vec::new();
    let mut suspicious_count: usize = 0;
    let mut last_line_at = Instant::now();
    let mut last_heartbeat = Instant::now();
    let session_start = Instant::now();

    info!(
        idle_window_secs = idle_window.as_secs(),
        hard_cap_secs = hard_cap.as_secs(),
        "tailing daemon log until idle"
    );

    loop {
        buf.clear();
        match reader.read_line(&mut buf).await? {
            0 => {
                if last_heartbeat.elapsed() >= Duration::from_secs(15) {
                    info!(
                        lines = lines.len(),
                        suspicious = suspicious_count,
                        idle_for_secs = last_line_at.elapsed().as_secs(),
                        "still tailing"
                    );
                    last_heartbeat = Instant::now();
                }
                if last_line_at.elapsed() >= idle_window {
                    info!(
                        lines = lines.len(),
                        suspicious = suspicious_count,
                        idle_for_secs = last_line_at.elapsed().as_secs(),
                        "daemon idle, treating as terminal"
                    );
                    return Ok(lines);
                }
                if session_start.elapsed() >= hard_cap {
                    info!(
                        lines = lines.len(),
                        suspicious = suspicious_count,
                        capped_at_secs = hard_cap.as_secs(),
                        "hard-cap fired, returning what we have"
                    );
                    return Ok(lines);
                }
                sleep(Duration::from_millis(250)).await;
            }
            _ => {
                last_line_at = Instant::now();
                let line = buf.trim_end_matches('\n').to_string();
                if reviewer::worth_reviewing(&line) {
                    suspicious_count += 1;
                    warn!(target: "harness.suspicious", seq = suspicious_count, "{}", line);
                } else {
                    debug!(line = %line, "captured");
                }
                lines.push(line);
                if lines.len().is_multiple_of(200) {
                    info!(lines = lines.len(), suspicious = suspicious_count, "captured progress");
                }
            }
        }
    }
}

async fn open_with_retry(path: &Path, timeout: Duration) -> Result<File> {
    let start = Instant::now();
    loop {
        match File::open(path).await {
            Ok(f) => return Ok(f),
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => {
                if start.elapsed() >= timeout {
                    return Err(e).with_context(|| format!("open {}", path.display()));
                }
                sleep(Duration::from_millis(200)).await;
            }
            Err(e) => return Err(e).with_context(|| format!("open {}", path.display())),
        }
    }
}
```

## src/reviewer.rs

Two-pass design. Pass 1 forwards failure-shaped lines to the LLM with
the failure rubric. Pass 2 normalises every INFO/DEBUG/TRACE line to a
template fingerprint, dedupes, and forwards unique templates to the LLM
with the silent-divergence rubric. See
[runtime-reviewer-rubric.md](runtime-reviewer-rubric.md) for both rubric system-prompt
strings (PASS1_SYSTEM, PASS2_SYSTEM) + the fingerprinting regex set +
the output-format prompt + `build_prompt` and `parse_verdicts`.

```rust
//! Adversarial reviewer: two-pass (failure + silent-divergence) via
//! claude --print. See reviewer-rubric.md for rubric text + regexes.

use std::collections::HashMap;
use std::process::Stdio;
use std::sync::LazyLock;

use anyhow::{anyhow, Context, Result};
use regex::Regex;
use serde::{Deserialize, Serialize};
use tokio::process::Command;
use tracing::{info, warn};

const BATCH_SIZE: usize = 300;       // pass-1 batch size
const MAX_PASS1_BATCHES: usize = 100; // pass-1 batch count ceiling
const MAX_PASS2_TEMPLATES: usize = 600;

// ---- pass 1 pre-filter --------------------------------------------------

pub(crate) fn worth_reviewing(line: &str) -> bool {
    if line.contains(" WARN ") || line.contains(" ERROR ") || line.contains(" FATAL ") {
        return true;
    }
    const SIGNALS: &[&str] = &[
        "panicked", "panic!", "stack backtrace", "FATAL",
        "Failed to", "failed to", "Error:", "Err(",
        "DatabaseError", "TransactionError", "DeadlineExceeded",
        "the request exceeded its deadline",
        "rejected", "dropped", "corrupt", "unreachable",
    ];
    SIGNALS.iter().any(|s| line.contains(s))
}

// ---- pass 2 candidate + template fingerprinting -------------------------

pub(crate) fn is_info_debug_candidate(line: &str) -> bool {
    if worth_reviewing(line) {
        return false;  // pass 1 already claimed it
    }
    line.contains(" INFO ") || line.contains(" DEBUG ") || line.contains(" TRACE ")
}

// See reviewer-rubric.md for the full set of regex declarations.
// Summary: TIMESTAMP_RE, UUID_RE, RECORD_ID_RE, HEX_BLOB_RE,
// NUM_UNIT_RE, NUM_RE — applied in order to normalise dynamic spans
// while preserving structural words / module paths / prose.

pub(crate) fn fingerprint_template(line: &str) -> String {
    let s = TIMESTAMP_RE.replace_all(line, "<ts>");
    let s = UUID_RE.replace_all(&s, "<uuid>");
    let s = RECORD_ID_RE.replace_all(&s, "$1:<id>");
    let s = HEX_BLOB_RE.replace_all(&s, "<hex>");
    let s = NUM_UNIT_RE.replace_all(&s, "<n>");
    let s = NUM_RE.replace_all(&s, "<n>");
    s.into_owned()
}

// ---- verdict shape ------------------------------------------------------

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Verdict {
    pub fingerprint: String,
    pub verdict: String,
    pub kind: String,        // pass 2 adds: silent-divergence,
                             // unimplemented-feature, contract-violation
    pub severity: String,
    pub reason: String,
    #[serde(default = "default_count")]
    pub count: u32,
    pub line: String,
}

fn default_count() -> u32 { 1 }

impl Verdict {
    pub fn is_reject(&self) -> bool { self.verdict.eq_ignore_ascii_case("reject") }
}

// ---- orchestrator -------------------------------------------------------

pub async fn review(
    claude_bin: &str,
    permission_mode: &str,
    pass1_model: &str,
    pass2_model: &str,
    lines: &[String],
) -> Result<Vec<Verdict>> {
    info!(total = lines.len(), pass1_model, pass2_model,
          "review starting (two-pass)");
    let started = std::time::Instant::now();
    let mut all = Vec::new();

    all.extend(review_pass1(claude_bin, permission_mode, pass1_model, lines).await?);
    all.extend(review_pass2(claude_bin, permission_mode, pass2_model, lines).await?);

    // Final dedupe across passes — fingerprint collision collapses to one.
    let mut by_fp: HashMap<String, Verdict> = HashMap::new();
    for v in all {
        by_fp.entry(v.fingerprint.clone())
            .and_modify(|e| e.count = e.count.saturating_add(v.count))
            .or_insert(v);
    }
    let deduped: Vec<Verdict> = by_fp.into_values().collect();
    info!(
        unique_rejects = deduped.len(),
        total_elapsed_secs = started.elapsed().as_secs(),
        "review done (both passes)"
    );
    Ok(deduped)
}

async fn review_pass1(claude_bin: &str, permission_mode: &str, lines: &[String]) -> Result<Vec<Verdict>> {
    let interesting: Vec<&String> = lines.iter().filter(|l| worth_reviewing(l)).collect();
    let raw_count = interesting.len();
    info!(total = lines.len(), worth_reviewing = raw_count,
          "pass 1 pre-filter done (failure-shaped)");
    if interesting.is_empty() {
        return Ok(Vec::new());
    }

    // Adaptive cap. Below ceiling: full-fidelity raw lines. Above:
    // fingerprint-group, keep top-N exemplars sorted desc, carry
    // per-exemplar counts through to the prompt as `seen:N`. See
    // gotchas.md § "Runaway candidate pools".
    let (capped, counts) = cap_and_dedup_failures(&interesting, MAX_PASS1_BATCHES, BATCH_SIZE);
    if counts.is_some() {
        info!(raw = raw_count, exemplars = capped.len(),
              max_batches = MAX_PASS1_BATCHES, max_batch_lines = BATCH_SIZE,
              "pass-1 candidates exceeded cap; deduplicated by fingerprint");
    }

    run_batches(claude_bin, permission_mode, PASS1_SYSTEM, "pass 1", &capped, counts.as_deref()).await
}

/// CapAndDedupFailures applies an adaptive cap to pass-1 input. When raw
/// record count exceeds `max_batches * max_batch_lines`, records are
/// grouped by `fingerprint_template`, the top-N most-frequent exemplars
/// are kept (sorted desc), and a parallel counts vector is returned so
/// the prompt can carry occurrence count into the LLM's reasoning. Below
/// the ceiling: records returned as-is, counts is None — full fidelity,
/// no behavior change. The fingerprinter is the same one pass 2 uses, so
/// the two passes agree on what counts as "the same line".
fn cap_and_dedup_failures<'a>(
    records: &[&'a String],
    max_batches: usize,
    max_batch_lines: usize,
) -> (Vec<&'a String>, Option<Vec<u64>>) {
    if max_batches == 0 || max_batch_lines == 0 {
        return (records.to_vec(), None);
    }
    let ceiling = max_batches.saturating_mul(max_batch_lines);
    if records.len() <= ceiling {
        return (records.to_vec(), None);
    }

    // group by fingerprint, preserve insertion order for stable tiebreak
    let mut groups: HashMap<String, (&'a String, u64)> = HashMap::new();
    let mut order: Vec<String> = Vec::new();
    for &line in records {
        let fp = fingerprint_template(line);
        match groups.get_mut(&fp) {
            Some(entry) => entry.1 += 1,
            None => {
                groups.insert(fp.clone(), (line, 1));
                order.push(fp);
            }
        }
    }

    // sort fingerprints by count desc, then fingerprint asc as tiebreak
    order.sort_by(|a, b| {
        let ca = groups[a].1;
        let cb = groups[b].1;
        cb.cmp(&ca).then_with(|| a.cmp(b))
    });
    if order.len() > ceiling {
        order.truncate(ceiling);
    }

    let mut out_records = Vec::with_capacity(order.len());
    let mut out_counts = Vec::with_capacity(order.len());
    for fp in &order {
        let (exemplar, count) = groups[fp];
        out_records.push(exemplar);
        out_counts.push(count);
    }
    (out_records, Some(out_counts))
}

async fn review_pass2(claude_bin: &str, permission_mode: &str, lines: &[String]) -> Result<Vec<Verdict>> {
    // Group by template fingerprint.
    let mut by_template: HashMap<String, TemplateGroup> = HashMap::new();
    for line in lines.iter().filter(|l| is_info_debug_candidate(l)) {
        let template = fingerprint_template(line);
        by_template.entry(template)
            .and_modify(|g| g.count = g.count.saturating_add(1))
            .or_insert_with(|| TemplateGroup { representative: line.clone(), count: 1 });
    }
    let mut templates: Vec<TemplateGroup> = by_template.into_values().collect();
    info!(unique_templates = templates.len(), "pass 2 dedupe done");
    if templates.is_empty() { return Ok(Vec::new()); }

    // Sort by count descending; truncate if pathologically diverse.
    templates.sort_by(|a, b| b.count.cmp(&a.count));
    if templates.len() > MAX_PASS2_TEMPLATES {
        warn!(unique_templates = templates.len(), cap = MAX_PASS2_TEMPLATES,
              "pass 2 template count exceeded cap — truncating");
        templates.truncate(MAX_PASS2_TEMPLATES);
    }

    // Decorate with [seen Nx] so the LLM sees occurrence counts.
    let decorated: Vec<String> = templates.iter()
        .map(|g| format!("[seen {}x] {}", g.count, g.representative))
        .collect();
    let refs: Vec<&String> = decorated.iter().collect();

    // Pass 2 already carries occurrence counts inline in the
    // representative string ([seen Nx] prefix), so the parallel
    // counts slice stays None for this caller.
    run_batches(claude_bin, permission_mode, PASS2_SYSTEM, "pass 2", &refs, None).await
}

struct TemplateGroup { representative: String, count: u32 }

async fn run_batches(
    claude_bin: &str,
    permission_mode: &str,
    system_prompt: &str,
    pass_label: &str,
    items: &[&String],
    counts: Option<&[u64]>, // parallel to items when pass-1 dedup engaged
) -> Result<Vec<Verdict>> {
    let total = items.len().div_ceil(BATCH_SIZE);
    let mut verdicts = Vec::new();
    for (idx, chunk) in items.chunks(BATCH_SIZE).enumerate() {
        let num = idx + 1;
        let chunk_counts = counts.map(|c| {
            let start = idx * BATCH_SIZE;
            &c[start..start + chunk.len()]
        });
        info!(pass = pass_label, batch = num, of = total, lines = chunk.len(),
              deduplicated = counts.is_some(),
              "judging batch via claude --print");
        let started = std::time::Instant::now();
        let batch = review_batch(claude_bin, permission_mode, system_prompt, chunk, chunk_counts).await?;
        info!(pass = pass_label, batch = num, of = total, rejects = batch.len(),
              elapsed_ms = started.elapsed().as_millis() as u64,
              "batch verdict received");
        verdicts.extend(batch);
    }
    Ok(verdicts)
}

/// Wrap a claude argv in `nono run --silent` when permission_mode is
/// bypassPermissions. Returns the original argv unchanged otherwise.
/// See references/nono-integration.md for policy and invariants.
fn wrap_with_nono(
    claude_argv: Vec<std::ffi::OsString>,
    allow_dirs: &[std::path::PathBuf],
    read_dirs: &[std::path::PathBuf],
    network_profile: Option<&str>,
) -> Vec<std::ffi::OsString> {
    let mut argv: Vec<std::ffi::OsString> = vec![
        "nono".into(), "run".into(), "--silent".into(),
    ];
    if let Some(p) = network_profile {
        argv.push("--network-profile".into()); argv.push(p.into());
    }
    for d in allow_dirs { argv.push("--allow".into()); argv.push(d.as_os_str().into()); }
    for d in read_dirs  { argv.push("--read".into());  argv.push(d.as_os_str().into()); }
    argv.push("--".into());
    argv.extend(claude_argv);
    argv
}

// Stream-json on both ends + --verbose is the contract. See
// references/nono-integration.md for the sandbox policy.
async fn review_batch(
    claude_bin: &str,
    permission_mode: &str,
    network_profile: Option<&str>,
    model: &str,
    system_prompt: &str,
    lines: &[&String],
    counts: Option<&[u64]>, // when Some, per-line seen counts > 1 land as `"seen": N`
) -> Result<Vec<Verdict>> {
    let prompt = build_prompt(system_prompt, lines, counts);

    // Wrap the prompt in a one-shot user-message envelope. claude
    // expects one JSON object per line on stdin when
    // --input-format=stream-json is set.
    let envelope = serde_json::json!({
        "type": "user",
        "message": {"role": "user", "content": prompt},
    });
    let payload = format!("{}\n", envelope);

    // Build claude argv then optionally wrap in nono.
    let claude_argv: Vec<std::ffi::OsString> = vec![
        claude_bin.into(),
        "--print".into(),
        "--input-format".into(), "stream-json".into(),
        "--output-format".into(), "stream-json".into(),
        "--verbose".into(),
        "--permission-mode".into(), permission_mode.into(),
        "--model".into(), model.into(),
    ];
    let allow_dirs = vec![std::path::PathBuf::from(".bug-burndown")];
    let read_dirs  = vec![
        dirs::home_dir().unwrap_or_default().join(".cargo/bin"),
        dirs::home_dir().unwrap_or_default().join(".rustup"),
    ];
    let final_argv = if permission_mode == "bypassPermissions" {
        wrap_with_nono(claude_argv, &allow_dirs, &read_dirs, network_profile)
    } else {
        claude_argv
    };

    let mut child = Command::new(&final_argv[0])
        .args(&final_argv[1..])
        // Force --pipe in any bwrap wrapper on PATH; nono preserves env.
        .env("CLAUDE_BWRAP_TTY", "0")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .with_context(|| "spawn nono+claude for reviewer batch")?;

    // Write the envelope then close stdin so claude sees EOF.
    {
        let mut stdin = child.stdin.take().expect("stdin piped above");
        stdin.write_all(payload.as_bytes()).await
            .context("write stream-json envelope to claude --print stdin")?;
    }

    let out = child.wait_with_output().await.context("wait claude --print")?;
    if !out.status.success() {
        warn!(status = ?out.status, stderr = %String::from_utf8_lossy(&out.stderr),
              "claude --print non-zero");
        return Err(anyhow!("claude --print exited with {:?}", out.status));
    }

    // claude emits one JSON event per line. The terminal result event's
    // `result` field carries the final assistant text. Fall back to
    // concatenated assistant text blocks if the stream truncates.
    let final_text = extract_stream_json_result(&out.stdout)?;
    parse_verdicts(&final_text)
}

pub fn log_reject_summary(verdicts: &[Verdict]) {
    let rejects: Vec<&Verdict> = verdicts.iter().filter(|v| v.is_reject()).collect();
    if rejects.is_empty() { info!("REJECT SUMMARY: 0 bugs found"); return; }
    info!("REJECT SUMMARY: {} unique bug class(es) found", rejects.len());
    let mut sorted = rejects.clone();
    sorted.sort_by_key(|v| match v.severity.to_ascii_lowercase().as_str() {
        "critical" => 0u8, "high" => 1, "medium" => 2, "low" => 3, _ => 4,
    });
    for (i, v) in sorted.iter().enumerate() {
        info!(target: "harness.rejects",
              rank = i + 1, severity = %v.severity, kind = %v.kind,
              count = v.count, fingerprint = %v.fingerprint, "{}", v.reason);
    }
}

// build_prompt + parse_verdicts + the regex statics + PASS1_SYSTEM +
// PASS2_SYSTEM: see reviewer-rubric.md.
```

## src/action_audit.rs

Mandatory structural anti-rationalization pass — see SKILL.md
§ "Structural anti-rationalization pass" for why this exists and
the canonical KEV incident that motivates it. The audit emits
synthetic `Verdict`s that land in the same reject set the LLM
reviewer produces, so downstream code (`log_reject_summary`,
the burndown session writer, the "ITERATION CLEAN" gate) handles
them without special-casing.

The three marker lists below are **project-specific defaults**. When
generating a harness for a new system, replace the example markers
with phrases that actually appear in the target daemon's logs. Keep
the same three-bucket shape (failure / success / fallback) — the
fallback list is the load-bearing one because it disqualifies success
markers that sit next to fallback wording.

```rust
//! Structural anti-rationalization pass — see SKILL.md.
//!
//! Walks captured log lines once, partitions by action token, and
//! emits synthetic Verdicts for actions that had failure evidence
//! and zero genuine upstream success. Deterministic, constant-cost,
//! no LLM calls. Immune to "designed error path" log wording
//! because it counts markers, not phrasings.

use std::collections::BTreeMap;
use std::sync::LazyLock;

use regex::Regex;

use crate::reviewer::Verdict;

#[allow(clippy::unwrap_used)]
static ACTION_TOKEN_RE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r#"\b(?:action|task_kind)=(?:"([^"]+)"|([A-Za-z_][A-Za-z0-9_\-]*))"#).unwrap()
});

// PROJECT-SPECIFIC: phrases the target system's error paths emit.
// Specific, not generic. `kind="*_error"` is good; bare `"error"`
// would catch `error_count=0` and dilute the signal.
const HARD_FAILURE_MARKERS: &[&str] = &[
    " WARN ", " ERROR ", " FATAL ",
    "Failed to", "failed to",
    "fetch failed", "refresh failed",
    "deferred to designed error path",
    "emitted error finding", "emitted no-op finding",
    "exhausted the retry budget",
    "DeadlineExceeded", "panicked",
    "_error\"", "_violation\"",
];

// PROJECT-SPECIFIC: phrases that prove the real upstream operation
// landed (NOT the workflow's self-stamped success flag).
const HARD_SUCCESS_MARKERS: &[&str] = &[
    "refresh succeeded", "fetch succeeded",
    "catalogue refreshed",
    "persisted from upstream", "wrote upstream entries",
    "live upstream entries persisted",
    "upstream returned valid",
];

// PROJECT-SPECIFIC but the names here are nearly universal — every
// system that has a fallback uses the same vocabulary.
const FALLBACK_MARKERS: &[&str] = &[
    "cache-fallback", "seed-fallback", "seed_fallback",
    "from cached entries", "served from cache",
    "last-good cache", "bundled seed",
    "build-time seed", "build-time snapshot",
    "designed fallback", "designed error path",
    "no-op finding",
];

#[derive(Debug, Default, Clone)]
struct ActionEvidence {
    hard_failures: u32,
    hard_successes: u32,
    representative_failure: Option<String>,
}

pub fn audit(lines: &[String]) -> Vec<Verdict> {
    let mut by_action: BTreeMap<String, ActionEvidence> = BTreeMap::new();
    for line in lines {
        for cap in ACTION_TOKEN_RE.captures_iter(line) {
            let action = cap.get(1).or_else(|| cap.get(2))
                .map(|m| m.as_str()).unwrap_or("");
            if action.is_empty() { continue; }
            let bucket = by_action.entry(action.to_string()).or_default();
            let is_failure = HARD_FAILURE_MARKERS.iter().any(|m| line.contains(m));
            let has_success = HARD_SUCCESS_MARKERS.iter().any(|m| line.contains(m));
            let has_fallback = FALLBACK_MARKERS.iter().any(|m| line.contains(m));
            if is_failure {
                bucket.hard_failures = bucket.hard_failures.saturating_add(1);
                if bucket.representative_failure.is_none() {
                    bucket.representative_failure = Some(line.chars().take(500).collect());
                }
            }
            if has_success && !has_fallback && !is_failure {
                bucket.hard_successes = bucket.hard_successes.saturating_add(1);
            }
        }
    }
    let mut verdicts = Vec::new();
    for (action, ev) in by_action {
        if ev.hard_failures == 0 || ev.hard_successes > 0 { continue; }
        verdicts.push(Verdict {
            fingerprint: format!("audit-action-only-failures-{action}"),
            verdict: "reject".to_string(),
            kind: "cascade-failure".to_string(),
            severity: "critical".to_string(),
            reason: format!(
                "structural audit: action=`{action}` has {} hard-failure line(s) and 0 \
                 upstream-success line(s) across the iteration. Fallback / cached / seed \
                 markers do not count as success — the real operation never landed. \
                 Fix the upstream failure; do not rationalize it with `designed error \
                 path` framing.",
                ev.hard_failures
            ),
            count: ev.hard_failures,
            line: ev.representative_failure.unwrap_or_default(),
        });
    }
    verdicts
}
```

**Mandatory unit tests** — name them exactly as below so future
maintainers can grep for the canonical coverage:

- `kev_failure_only_run_emits_synthetic_reject` (or
  `<action>_failure_only_run_emits_synthetic_reject` for a system-
  specific anchor) — input is the canonical failure-only shape from
  the target system's logs; verdict count ≥ 1, kind=cascade-failure,
  severity=critical.
- `cache_fallback_success_does_not_clear_failure` — input mixes a
  WARN failure with an INFO line whose `succeeded` sits next to a
  fallback marker; audit must still reject.
- `genuine_upstream_success_clears_failure` — input mixes a WARN
  failure with a real upstream-success line; audit stays silent.
- `non_action_lines_ignored` — lines without action tokens don't
  bucket into anything; audit stays silent.

The reference implementation in the reference harness's `action_audit` module
also includes `success_only_run_emits_nothing`,
`multiple_actions_audited_independently`, and
`task_kind_token_attributed_alongside_action` — copy them too if
the target system's action vocabulary spans multiple tokens.

## src/findings.rs

```rust
//! Convert rejects into a `.bug-burndown/<id>/` tree the skill can
//! resume from at Phase 5.

use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

use anyhow::{Context, Result};
use serde::Serialize;
use tokio::io::AsyncWriteExt;
use tracing::info;
use uuid::Uuid;

use crate::reviewer::Verdict;

#[derive(Debug, Serialize)]
struct Finding<'a> {
    id: String,
    source: &'a str,
    kind: &'a str,
    severity: &'a str,
    signal: &'a str,
    count: u32,
    confidence: &'a str,
    origin: &'a str,
    fingerprint: &'a str,
    representative_line: &'a str,
}

#[derive(Debug, Serialize)]
struct QueueEntry<'a> {
    bug_id: String,
    title: String,
    severity: &'a str,
    kind: &'a str,
    confidence: &'a str,
    sources: Vec<&'a str>,
    findings: Vec<String>,
    priority_rank: usize,
    status: &'a str,
    attempt_count: u32,
    blocks: Vec<String>,
    blocked_by: Vec<String>,
}

pub async fn write_burndown_session(rejects: &[&Verdict], daemon_log: &Path) -> Result<String> {
    let session_id = format!(
        "{}-{}",
        chrono::Utc::now().format("%Y%m%d-%H%M%S"),
        &Uuid::new_v4().simple().to_string()[..8]
    );
    let session_dir = PathBuf::from(".bug-burndown").join(&session_id);
    tokio::fs::create_dir_all(session_dir.join("findings")).await?;
    tokio::fs::create_dir_all(session_dir.join("worktrees")).await?;
    tokio::fs::create_dir_all(session_dir.join("reports")).await?;

    let baseline_sha = current_head_sha().await?;
    let manifest = format!(
        "session_id: {session_id}\n\
         start_time: {start}\n\
         time_budget_seconds: 14400\n\
         parallelism: 1\n\
         sources_enabled: [logs]\n\
         baseline_sha: {baseline_sha}\n\
         integration_branch: main\n\
         log_files:\n  - {log}\n\
         origin: <crate-name>\n\
         sandbox: \"{sandbox}\"\n\
         network_profile: \"{net_profile}\"\n\
         permission_mode: \"{perm_mode}\"\n",
        session_id = session_id,
        start = chrono::Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Secs, true),
        baseline_sha = baseline_sha,
        log = daemon_log.display(),
        // these come from the SandboxVerdict produced by check_sandbox_and_claude()
        sandbox = verdict.nono_version.as_deref().map_or("none (--allow-unsandboxed)".to_owned(), |v| format!("nono {v}")),
        net_profile = verdict.network_profile.as_deref().unwrap_or("none (Landlock ABI < 4)"),
        perm_mode = verdict.permission_mode,
    );
    write_file(&session_dir.join("manifest.yaml"), manifest.as_bytes()).await?;

    let mut sorted: Vec<&Verdict> = rejects.to_vec();
    sorted.sort_by(|a, b| sev_rank(&a.severity).cmp(&sev_rank(&b.severity)));

    let mut findings_buf = Vec::new();
    let mut finding_ids = Vec::with_capacity(sorted.len());
    for (i, v) in sorted.iter().enumerate() {
        let id = format!("F-{:03}", i + 1);
        finding_ids.push(id.clone());
        let f = Finding {
            id, source: "daemon.log", kind: &v.kind, severity: &v.severity,
            signal: &v.reason, count: v.count, confidence: "medium",
            origin: "<crate-name>", fingerprint: &v.fingerprint,
            representative_line: &v.line,
        };
        findings_buf.extend_from_slice(serde_json::to_string(&f)?.as_bytes());
        findings_buf.push(b'\n');
    }
    write_file(&session_dir.join("findings/harness.jsonl"), &findings_buf).await?;

    let mut queue_buf = Vec::new();
    for (i, (v, fid)) in sorted.iter().zip(finding_ids.iter()).enumerate() {
        let entry = QueueEntry {
            bug_id: format!("HARNESS-{:04}", i + 1),
            title: format!("{} ({})", v.reason, v.fingerprint),
            severity: &v.severity, kind: &v.kind, confidence: "medium",
            sources: vec!["logs"], findings: vec![fid.clone()],
            priority_rank: i + 1, status: "queued", attempt_count: 0,
            blocks: Vec::new(), blocked_by: Vec::new(),
        };
        queue_buf.extend_from_slice(serde_json::to_string(&entry)?.as_bytes());
        queue_buf.push(b'\n');
    }
    write_file(&session_dir.join("queue.jsonl"), &queue_buf).await?;
    write_file(&PathBuf::from(".bug-burndown/CURRENT"), session_id.as_bytes()).await?;

    info!(session_dir = %session_dir.display(), finding_count = sorted.len(), "wrote burndown session");
    Ok(session_id)
}

pub fn dump_to_stdout(rejects: &[&Verdict]) {
    println!("\n=== HARNESS REJECTS ({} total) ===", rejects.len());
    for v in rejects {
        println!("[{}] {} x{}: {} — {}", v.severity, v.fingerprint, v.count, v.kind, v.reason);
        println!("    line: {}", v.line);
    }
}

fn sev_rank(s: &str) -> u8 {
    match s.to_ascii_lowercase().as_str() {
        "critical" => 0, "high" => 1, "medium" => 2, "low" => 3, _ => 4,
    }
}

async fn current_head_sha() -> Result<String> {
    let output = tokio::process::Command::new("git")
        .args(["rev-parse", "HEAD"])
        .output().await.context("git rev-parse HEAD")?;
    if !output.status.success() {
        return Ok(format!("unknown-{}",
            SystemTime::now().duration_since(UNIX_EPOCH).map(|d| d.as_secs()).unwrap_or(0)));
    }
    Ok(String::from_utf8_lossy(&output.stdout).trim().to_string())
}

async fn write_file(path: &Path, bytes: &[u8]) -> Result<()> {
    if let Some(parent) = path.parent() {
        tokio::fs::create_dir_all(parent).await?;
    }
    let mut f = tokio::fs::File::create(path)
        .await.with_context(|| format!("create {}", path.display()))?;
    f.write_all(bytes).await?;
    f.flush().await?;
    Ok(())
}
```

## src/burndown.rs

Spawns `claude --print` with `--output-format stream-json --verbose`
so per-event JSON arrives live instead of buffering until exit.
Parses each line, routes to per-event tracing targets, tees raw
stream to `<iter>/burndown.log`. Sets two env vars that form a
contract with the bug-burndown skill's Stop hook (see gotchas.md §
"Distinguishing harness-driven from interactive bug-burndown").

```rust
//! Bridge to `/bug-burndown`: stream-json output, per-event tracing,
//! raw tee to burndown.log, env-var contract with the skill's hook.

use std::path::Path;
use std::process::Stdio;
use std::sync::Arc;

use anyhow::{Context, Result};
use serde_json::Value;
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tokio::process::Command;
use tokio::sync::Mutex;
use tracing::{debug, info, warn};

pub async fn run(
    claude_bin: &str,
    permission_mode: &str,
    network_profile: Option<&str>,
    model: &str,
    session_id: &str,
    log_path: &Path,
) -> Result<()> {
    let arg = format!("/bug-burndown resume:{session_id}");
    info!(%session_id, bin = %claude_bin, model, log = %log_path.display(),
          "spawning /bug-burndown (stream-json)");

    if let Some(parent) = log_path.parent() {
        tokio::fs::create_dir_all(parent).await?;
    }
    let file = tokio::fs::File::create(log_path).await
        .with_context(|| format!("create burndown log {}", log_path.display()))?;
    let file = Arc::new(Mutex::new(file));

    // Same stream-json envelope on stdin shape as the reviewer phase.
    let envelope = serde_json::json!({
        "type": "user",
        "message": {"role": "user", "content": arg},
    });
    let payload = format!("{}\n", envelope);

    // Build claude argv then optionally wrap in nono.
    // The burndown agent writes code in the current project tree, so we
    // allow `.` (the full project CWD) plus shared dotfile dirs.
    let claude_argv: Vec<std::ffi::OsString> = vec![
        claude_bin.into(),
        "--print".into(),
        "--permission-mode".into(), permission_mode.into(),
        "--model".into(), model.into(),
        "--input-format".into(), "stream-json".into(),
        "--output-format".into(), "stream-json".into(),
        "--verbose".into(),
    ];
    let allow_dirs = vec![
        std::path::PathBuf::from("."),           // project root (burndown writes fixes here)
        std::path::PathBuf::from(".bug-burndown"),
        std::path::PathBuf::from(".test-effectiveness"),
    ];
    let read_dirs = vec![
        dirs::home_dir().unwrap_or_default().join(".cargo/bin"),
        dirs::home_dir().unwrap_or_default().join(".rustup"),
    ];
    let final_argv = if permission_mode == "bypassPermissions" {
        wrap_with_nono(claude_argv, &allow_dirs, &read_dirs, network_profile)
    } else {
        claude_argv
    };

    let mut child = Command::new(&final_argv[0])
        .args(&final_argv[1..])
        // Env-var contract with the bug-burndown Stop hook (runtime-gotchas.md).
        // nono preserves the parent env so these survive the sandbox wrap.
        .env("BUG_BURNDOWN_HARNESS_DRIVEN", "1")
        .env("BUG_BURNDOWN_HARNESS_SESSION_ID", session_id)
        // Force --pipe in any bwrap wrapper on PATH.
        .env("CLAUDE_BWRAP_TTY", "0")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .with_context(|| "spawn nono+claude for /bug-burndown dispatch")?;

    // Write the envelope and close stdin so claude finalises input.
    {
        let mut stdin = child.stdin.take().expect("stdin piped above");
        stdin.write_all(payload.as_bytes()).await
            .context("write stream-json envelope to /bug-burndown stdin")?;
    }

    let stdout = child.stdout.take().context("stdout missing")?;
    let stderr = child.stderr.take().context("stderr missing")?;

    let file_out = Arc::clone(&file);
    let stdout_task = tokio::spawn(async move {
        let mut reader = BufReader::new(stdout).lines();
        while let Ok(Some(line)) = reader.next_line().await {
            // Always tee the raw JSON to burndown.log first.
            {
                let mut f = file_out.lock().await;
                let _ = f.write_all(line.as_bytes()).await;
                let _ = f.write_all(b"\n").await;
            }
            surface_stream_event(&line);
        }
    });
    // stderr task: same tee pattern as before, [stderr]-prefixed.

    let status = child.wait().await.context("wait burndown child")?;
    let _ = stdout_task.await;
    // ... flush + result handling
    Ok(())
}

/// Parse one stream-json line and route to tracing. Falls back to
/// `burndown.raw` for non-JSON lines (early init banners).
fn surface_stream_event(line: &str) {
    let trimmed = line.trim();
    if trimmed.is_empty() { return; }
    let event: Value = match serde_json::from_str(trimmed) {
        Ok(v) => v,
        Err(_) => {
            info!(target: "burndown.raw", "{}", trimmed);
            return;
        }
    };
    let event_type = event.get("type").and_then(|v| v.as_str()).unwrap_or("?");
    match event_type {
        "system" => info!(target: "burndown.event",
                          subtype = event.get("subtype").and_then(|v| v.as_str()).unwrap_or("?"),
                          "system event"),
        "assistant" => {
            // For each content block: text → burndown.assistant info,
            // tool_use → burndown.tool info with input summary,
            // thinking → burndown.thinking debug.
        }
        "user" => {
            // tool_result blocks → burndown.tool_result debug (truncated).
        }
        "result" => info!(target: "burndown.event",
                          subtype = event.get("subtype").and_then(|v| v.as_str()).unwrap_or("?"),
                          duration_ms = event.get("duration_ms").and_then(|v| v.as_i64()).unwrap_or(0),
                          session_cost_usd = event.get("total_cost_usd").and_then(|v| v.as_f64()).unwrap_or(0.0),
                          "burndown final result"),
        other => debug!(target: "burndown.event", event_type = other, "unhandled"),
    }
}
```

See the canonical the reference harness `burndown.rs` for the full assistant
event walker (text + tool_use + thinking blocks), the user event
walker (tool_result string-or-array handling), and the `format_tool_input`
helper that picks priority fields like `command` / `file_path` /
`pattern` first.

## Pre-flight check (in main.rs)

The preflight runs once at harness startup. It probes nono first (the
sandbox boundary), then confirms the claude binary is reachable. See
`references/nono-integration.md` for the full preflight algorithm.

```rust
/// Sandbox verdict — cached once per harness run and threaded through
/// to every review_batch and burndown::run call.
#[derive(Clone, Debug)]
pub struct SandboxVerdict {
    pub nono_version: Option<String>,
    pub network_profile: Option<String>,  // "claude-code" or None
    pub permission_mode: String,          // "bypassPermissions" or "acceptEdits"
}

impl SandboxVerdict {
    pub fn network_profile_ref(&self) -> Option<&str> {
        self.network_profile.as_deref()
    }
}

/// Run nono preflight then confirm the claude binary is reachable.
/// Returns a SandboxVerdict to thread through every spawn site.
async fn check_sandbox_and_claude(
    claude_bin: &str,
    allow_unsandboxed: bool,
    network_profile_default: &str,
) -> Result<SandboxVerdict> {
    // Step 1 — probe nono
    let nono_out = tokio::process::Command::new("nono")
        .arg("--version")
        .stdin(std::process::Stdio::null())
        .output()
        .await;

    let verdict = match nono_out {
        Ok(out) if out.status.success() => {
            let nono_version = String::from_utf8_lossy(&out.stdout).trim().to_owned();

            // Step 2 — check Landlock ABI for network-profile support
            let setup = tokio::process::Command::new("nono")
                .args(["setup", "--check-only"])
                .stdin(std::process::Stdio::null())
                .output()
                .await
                .context("nono setup --check-only")?;
            let setup_out = String::from_utf8_lossy(&setup.stdout);
            // Landlock ABI v4+ required for --network-profile (Linux 6.7+)
            let network_profile = if setup_out.contains("landlock_abi: 4")
                || setup_out.contains("landlock_abi: 5")
            {
                info!("[sandbox] nono {nono_version} — network-profile={network_profile_default}");
                Some(network_profile_default.to_owned())
            } else {
                warn!("[sandbox] Landlock ABI < 4 — dropping --network-profile");
                None
            };

            SandboxVerdict {
                nono_version: Some(nono_version),
                network_profile,
                permission_mode: "bypassPermissions".into(),
            }
        }
        _ => {
            if allow_unsandboxed {
                warn!(concat!(
                    "\n┌─────────────────────────────────────────────────────┐\n",
                    "│  RUNNING UNSANDBOXED — nono not found on PATH       │\n",
                    "│  permission_mode = acceptEdits (NOT bypassPerms)    │\n",
                    "│  Install: brew install nono                         │\n",
                    "│           nix shell nixpkgs#nono                    │\n",
                    "│           .deb from github.com releases             │\n",
                    "└─────────────────────────────────────────────────────┘"
                ));
                SandboxVerdict {
                    nono_version: None,
                    network_profile: None,
                    permission_mode: "acceptEdits".into(),
                }
            } else {
                anyhow::bail!(
                    "nono is required but not found on PATH.\n\
                     Install: brew install nono  |  nix shell nixpkgs#nono\n\
                     Pass --allow-unsandboxed to proceed without the sandbox\n\
                     (keeps permission_mode=acceptEdits; not recommended for\n\
                     unattended loops)."
                );
            }
        }
    };

    // Step 3 — confirm the claude binary is reachable
    if claude_bin.contains('/') {
        let metadata = tokio::fs::metadata(claude_bin).await
            .with_context(|| format!(
                "--claude-bin `{claude_bin}` not reachable. \
                 Check the path and that the wrapper is executable."
            ))?;
        if !metadata.is_file() {
            anyhow::bail!("--claude-bin `{claude_bin}` exists but is not a regular file");
        }
    } else {
        let out = tokio::process::Command::new(claude_bin)
            .arg("--version")
            .stdin(std::process::Stdio::null())
            .output()
            .await
            .with_context(|| format!(
                "--claude-bin `{claude_bin}` not found on PATH. \
                 Install claude or pass --claude-bin /abs/path."
            ))?;
        if !out.status.success() {
            anyhow::bail!(
                "--claude-bin `{claude_bin} --version` exited {:?}: {}",
                out.status,
                String::from_utf8_lossy(&out.stderr).trim()
            );
        }
    }
    info!(claude_bin, "pre-flight: claude binary reachable");
    Ok(verdict)
}
```

Called once at startup, before pre-build. See gotchas.md §
"Pre-flight --claude-bin check" for the failure mode this prevents.

## Unit tests (mandatory)

In `reviewer.rs`, append:

```rust
#[cfg(test)]
#[allow(clippy::unwrap_used)]
mod tests {
    use super::*;

    #[test]
    fn worth_reviewing_keeps_warn_and_error() {
        assert!(worth_reviewing("2026-01-01T00:00:00Z  WARN x: y"));
        assert!(worth_reviewing("2026-01-01T00:00:00Z ERROR x: y"));
    }

    #[test]
    fn worth_reviewing_keeps_failure_tokens_in_info() {
        assert!(worth_reviewing("2026-01-01T00:00:00Z  INFO x: Failed to do thing"));
        assert!(worth_reviewing("2026-01-01T00:00:00Z  INFO x: the request exceeded its deadline"));
    }

    #[test]
    fn worth_reviewing_drops_normal_info() {
        assert!(!worth_reviewing("2026-01-01T00:00:00Z  INFO x: listener bound"));
        assert!(!worth_reviewing("2026-01-01T00:00:00Z DEBUG x: tick"));
    }

    #[test]
    fn parse_verdicts_accepts_bare_array() {
        let raw = r#"[{"fingerprint":"x","verdict":"reject","kind":"panic",
                       "severity":"high","reason":"r","count":1,"line":"l"}]"#;
        let v = parse_verdicts(raw).unwrap();
        assert_eq!(v.len(), 1);
        assert!(v[0].is_reject());
    }

    #[test]
    fn parse_verdicts_strips_prose() {
        let raw = "Sure:\n```json\n[{\"fingerprint\":\"x\",\"verdict\":\"reject\",\
                   \"kind\":\"panic\",\"severity\":\"high\",\"reason\":\"r\",\
                   \"count\":1,\"line\":\"l\"}]\n```";
        let v = parse_verdicts(raw).unwrap();
        assert_eq!(v.len(), 1);
    }

    #[test]
    fn parse_verdicts_accepts_empty_array() {
        assert!(parse_verdicts("[]").unwrap().is_empty());
    }

    // ---- parser regression tests (mandatory — see gotchas.md
    //      § "String-blind JSON parsing"). Without these, swapping
    //      the parser for a string-blind walker silently passes CI.
    #[test]
    fn parse_verdicts_tolerates_brackets_inside_string_fields() {
        let raw = r#"[{"fingerprint":"x","verdict":"reject","kind":"panic",
                       "severity":"high","reason":"r","count":1,
                       "line":"WARN [example::sucrose]: Failed to [foo]"}]"#;
        let v = parse_verdicts(raw).unwrap();
        assert!(v[0].line.contains("[example::sucrose]"));
    }

    #[test]
    fn parse_verdicts_tolerates_escaped_quotes_inside_strings() {
        let raw = r#"[{"fingerprint":"x","verdict":"reject","kind":"panic",
                       "severity":"high","reason":"contained an escaped \"quote\"",
                       "count":1,"line":"l"}]"#;
        let v = parse_verdicts(raw).unwrap();
        assert!(v[0].reason.contains("escaped \"quote\""));
    }

    #[test]
    fn parse_verdicts_ignores_trailing_text_after_array() {
        let raw = r#"[{"fingerprint":"x","verdict":"reject","kind":"panic",
                       "severity":"high","reason":"r","count":1,"line":"l"}]
Trailing prose with brackets [oh hi] that would confuse a depth walker.
"#;
        let v = parse_verdicts(raw).unwrap();
        assert_eq!(v.len(), 1);
    }
}
```

Nine tests cover the parser surface. The three regression tests at
the bottom are non-optional — they catch the failure mode that hit
the canonical implementation on 2026-05-20 and ate an iteration.

## src/scenarios.rs — panic-safe scenario wrapper

Same intent as the Go variant (see go-skeletons.md): a panic in any
single scenario must not take the whole harness down. See gotchas.md
§ "Scenario panics must not kill the harness" for full rationale.

```rust
use std::panic::{catch_unwind, AssertUnwindSafe};
use std::backtrace::Backtrace;

#[derive(Debug, thiserror::Error)]
#[error("scenario {scenario} panicked: {message}")]
pub struct ScenarioPanicError {
    pub scenario: String,
    pub message: String,
    pub backtrace: String,
}

pub async fn run_scenario_safely(
    s: &Scenario,
    env: &Env,
) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let name = s.name.clone();
    // AssertUnwindSafe is load-bearing — most async futures aren't
    // UnwindSafe by default, but the recovery boundary here is explicit
    // and we discard the captured state on panic.
    let result = catch_unwind(AssertUnwindSafe(|| {
        futures::executor::block_on(s.run(env))
    }));
    match result {
        Ok(Ok(())) => Ok(()),
        Ok(Err(e)) => Err(e),
        Err(payload) => {
            let msg = panic_payload_to_string(&payload);
            let backtrace = Backtrace::force_capture().to_string();
            tracing::error!(
                scenario = %name,
                panic = %msg,
                backtrace = %backtrace,
                "scenario panicked — recovered"
            );
            Err(Box::new(ScenarioPanicError {
                scenario: name,
                message: msg,
                backtrace,
            }))
        }
    }
}

fn panic_payload_to_string(payload: &Box<dyn std::any::Any + Send>) -> String {
    if let Some(s) = payload.downcast_ref::<&'static str>() {
        (*s).to_string()
    } else if let Some(s) = payload.downcast_ref::<String>() {
        s.clone()
    } else {
        "non-string panic payload".to_string()
    }
}
```

`Backtrace::force_capture` ignores `RUST_BACKTRACE`'s default-off
state; the harness's reviewer needs the stack to file a useful
verdict, and the operator running locally is happy to pay the
capture cost. Drop to `Backtrace::capture()` if you want to honour
the env var.

For pure-sync scenarios (no `block_on`), the wrapper is even simpler
— just `catch_unwind(|| s.run(env))` directly.

## Workspace integration

Add the crate to the workspace `members = [...]` in `Cargo.toml`,
plus the project-local socket dir to `.gitignore`:

```
.harness/
```
