# Gotchas

Every item here cost a real debug cycle on the reference harness. If you
hit any of these symptoms in your own build, the fix is below.

## The pre-build trap

**Symptom**: harness reports `daemon socket /tmp/<name>.sock did not
appear within 60s` and `.harness/iter-001/server.log` doesn't exist
at all.

**Cause**: the harness ran `cargo run -p <daemon>` inside the daemon
spawn. `cargo run` builds the binary if it's not already built. On a
cold or recently-invalidated compilation cache (BUG-230's example-graph
changes invalidated thousands of object files), the build alone
takes several minutes. The socket-wait timer doesn't distinguish
"daemon is starting" from "cargo is still compiling", so it fires
and kills the spawn before the daemon even exists.

**Fix**: run `cargo build -p <daemon>` synchronously BEFORE iteration
1. The build phase's output streams to the operator's terminal so
they can see compilation progress, and the socket-wait timer starts
only when the binary is guaranteed to exist:

```rust
info!("phase: pre-build (cargo build -p <daemon-crate>)");
let build_started = std::time::Instant::now();
let build_status = tokio::process::Command::new("cargo")
    .args(["build", "-p", "<daemon-crate>"])
    .status()
    .await?;
if !build_status.success() {
    return Err(anyhow!("cargo build failed"));
}
info!(elapsed_secs = build_started.elapsed().as_secs(), "pre-build complete");
```

Subsequent iterations are fast — the build is incremental from here.

## The stale-binary trap (a fix that never runs)

**Symptom**: you fix a defect in the harness's own source, the source
clearly contains the fix, the tests pass — but the next harness run
behaves exactly as before the fix. A guard you added doesn't fire; a
prompt you changed still shows its old token count; captured findings
are still left unfixed. Nothing in the logs mentions your change.

**Cause**: the harness drives its agent **in-process** (the burndown
dispatch is a method call on the server handle, not a subprocess), so
the behaviour is whatever the *running binary* contains — not what the
source tree contains. If the running binary was built **before** your
edit, your fix is invisible at runtime. This bites hardest with
**uncommitted** edits: the source mtime can be *older* than the moment
the (stale) process started, so a freshness gate that only compares
"source mtime vs process-start time" sees "unchanged since start" and
happily runs the stale binary.

This is the iter-002/003 vulnmapper failure: the iter-001 burndown fixes
(skill provisioning, load-and-run invocation, the zero-tool-call no-op
guard) were all in the source tree, but the harness that ran iter-002/003
predated them. It re-ran the **old** one-line `/bug-burndown resume:<id>`
prompt (the burndown.log shows ~15 input tokens, 0 output, 0 tool calls,
immediate idle), the not-yet-compiled no-op guard never fired, and the
loop reported success and advanced — leaving every captured finding
unfixed, identically to iter-001.

**Fix**: the freshness gate must track **three** signals, not two, and
re-exec via `go run .` / `cargo run` (a fresh compile) if **any** moved:

1. `processStartTime` — newest source mtime *after* process start. Catches
   an edit that landed mid-run (e.g. a subagent's fix).
2. `headSHA` — `git rev-parse HEAD` differs from the start-of-process SHA.
   Catches a landed commit that didn't move working-tree mtimes.
3. **`binaryBuildTime`** — newest source mtime is newer than the **running
   binary itself** (`os.Executable()` mtime, resolved through symlinks),
   regardless of when the process started. **This is the signal that
   catches the stale-binary-at-launch case**, and the one most harnesses
   omit. A pre-built or cached binary launched against newer source trips it.
   **BUT under `go run`/`cargo run` it is a FALSE POSITIVE** — see the
   relaunch-loop trap immediately below; you must suppress `binaryStale` when
   the running binary is itself a `go run` artefact.

```go
// Pure predicate — unit-test it directly with synthetic times.
func stalenessSignals(newestSrc, procStart, binBuild time.Time) (sourceStale, binaryStale bool) {
    if newestSrc.IsZero() {
        return false, false // scan failed → no signal (never false-positive)
    }
    sourceStale = !procStart.IsZero() && newestSrc.After(procStart)
    binaryStale = !binBuild.IsZero() && newestSrc.After(binBuild) // the missing one
    return
}
// re-exec if sourceStale || binaryStale || headChanged
```

Run the gate **both** at pre-flight (before iter 1, so a stale launch is
caught immediately) **and** between iterations. Each comparison must
degrade to `false` when its reference time is zero (capture failed) so a
missing signal can't trigger a re-exec loop. Unit-test the predicate with
the three cases: stale-binary-at-launch (edit < procStart but > binBuild
⇒ binaryStale), mid-run edit (edit > procStart ⇒ both), and fresh binary
(no staleness).

> **The deeper rule:** any time the harness fixes *its own* code, assume
> the running process is stale until the freshness gate (or an explicit
> rebuild) proves otherwise. An in-process agent dispatch makes "the source
> says X" and "the running harness does X" two different facts.

### The freshness relaunch loop (binaryStale under `go run`)

**Symptom**: the harness relaunches itself every iteration and never makes
progress — `binary freshness: source … newer than the running binary —
re-launching via go run` on a loop, or it exits and the outer wrapper restarts
it into the same relaunch. This is the 2026-06-15 vulnmapper incident.

**Cause (two compounding bugs):**

1. **`binaryStale` is a false positive under `go run`.** When the harness is
   itself a `go run`/`cargo run` artefact, the binary was compiled from the
   current source *at launch* — so `binaryStale` (source mtime > binary mtime)
   can only be a false signal. It fires anyway because the Go **build cache**
   can stamp the cached artefact with an mtime *older* than a source file that
   was nonetheless compiled into it. Acting on it execs `go run`, which serves
   the **same cached artefact**, which still looks "stale" → infinite relaunch.

2. **A failed relaunch that propagates an error loops via the wrapper.** If
   `relaunchHarnessSelf` can't exec (`go` not on PATH in the sandbox, exec
   error) and returns that error, the loop aborts; the outer wrapper
   (`harness.sh` / the iterate loop) restarts a fresh process; freshness fires
   again → loop without ever doing work.

**Fix:**

- **Suppress `binaryStale` when running under `go run`.** Detect it by
  classifying `os.Executable()` (resolved through symlinks): a `go run` binary
  lives under a path segment beginning `go-build` (`<cache>/go-build/…` or the
  TMPDIR `go-buildNNNN/…` work dir). Keep the genuine mid-run signals
  (`sourceStale`, `headChanged`) — only `binaryStale` is the false one here.

  ```go
  // pure + unit-testable: classify the executable path
  func isGoRunPath(exe string) bool {
      for _, seg := range strings.FieldsFunc(exe, func(r rune) bool {
          return r == '/' || r == filepath.Separator
      }) {
          if strings.HasPrefix(seg, "go-build") { return true }
      }
      return false
  }
  // at the call site:
  if binaryStale && runningUnderGoRun() { binaryStale = false } // false positive
  ```

- **A failed relaunch must NOT propagate an error — continue with the current
  binary.** Running slightly-stale code for one iteration is strictly better
  than a relaunch spin-loop. Log loudly and return nil:

  ```go
  if err := relaunchHarnessSelf(ctx, nextIter); err != nil {
      slog.Error("re-launch failed; continuing with current (possibly stale) binary "+
          "rather than spin-looping", "error", err)
      return nil // do NOT bubble — that restarts-and-retriggers via the wrapper
  }
  ```

**Required unit tests:** `isGoRunPath` (go-build cache + TMPDIR work-dir paths →
true; installed/`result/bin`/`/usr/local/bin` paths → false); and the
`stalenessSignals` cases unchanged (the suppression is applied at the call site,
not in the pure predicate, so both stay testable).

## The /tmp bind-mount surprise

**Symptom**: harness works on the host but fails in Claude Code's
bash tool / a sandboxed shell / a container with "daemon socket did
not appear" even though everything else looks fine.

**Cause**: `/tmp` is bind-mounted differently in sandboxed
environments. The daemon binds the socket at the host's `/tmp/X.sock`,
the harness dials at the sandbox's `/tmp/X.sock`, and they're not the
same file.

**Fix**: project-local socket path under `<work_dir>/`, resolved to
absolute via `canonicalize`. The project directory is bind-mounted
identically across sandbox and host:

```rust
let socket_path = match &cli.socket {
    Some(p) => p.clone(),
    None => tokio::fs::canonicalize(&cli.work_dir)
        .await?
        .join("daemon.sock"),
};
```

Default `--work-dir .harness`, default socket
`<workspace>/.harness/daemon.sock`. The operator can override with
`--socket /any/absolute/path` if they have a reason to.

## Cargo's silent stdout/stderr

**Symptom**: the daemon never starts, but `server.log` is empty AND
there's nothing in the harness's own log explaining why.

**Cause**: cargo's stdout and stderr were piped to `/dev/null`. Any
build error, panic before tracing init, or "binary not found" message
went to the void.

**Fix**: pipe to a per-iteration `cargo.log` file:

```rust
let cargo_stdout = std::fs::File::create(&spec.cargo_log)?;
let cargo_stderr = cargo_stdout.try_clone()?;

let child = Command::new("cargo")
    .args(["run", "--quiet", "-p", "<daemon-crate>", ...])
    .stdout(std::process::Stdio::from(cargo_stdout))
    .stderr(std::process::Stdio::from(cargo_stderr))
    .process_group(0)
    .spawn()?;
```

Empty file in the happy path. Full forensic record when the daemon
fails before its own logger initialises.

## The no-timeout HTTP client hangs forever after "opencode server listening"

**Symptom**: the harness logs `opencode server listening on http://127.0.0.1:NNNNN`,
then **never** logs `opencode server healthy`. It sits there doing nothing and
eventually dies only when the outer wrapper / signal kills it — minutes or hours
later, not at the health-check budget. The operator reports "it just stalls
after launching opencode". This is the 2026-06-16 health-probe-hang incident.

**Cause (two, often together):**

1. **The server HTTP client has no timeout AND `waitHealthy` passes a
   deadline-less context.** `&http.Client{}` / `reqwest::Client::builder().build()`
   has no per-request bound. `waitHealthy` checks its budget only *between*
   probes (`for time.Now().Before(deadline)`), so if a *single* probe blocks
   inside `client.Do(req)` it never returns and the budget is never enforced.
   The nono supervisor proxy can hold a loopback connection open indefinitely in
   the moment right after `listening` while it finishes wiring up the port — the
   first probe is exactly where this bites.

2. **`&http.Client{}` uses `http.DefaultTransport`, which a runtime harness has
   often globally replaced.** Many harnesses install a process-wide transport
   guard at startup (a dry-run guard that blocks mutating calls to the project's
   real API host — vulnmapper installs a `DryRunTransport` over
   `http.DefaultTransport`). After that:
   - opencode's own loopback traffic routes through that guard (wrong — it should
     never be subject to the project-API guard), and
   - a "fix" that builds the client via
     `http.DefaultTransport.(*http.Transport).Clone()` **panics** at launch:
     `interface conversion: http.RoundTripper is *DryRunTransport, not *http.Transport`.
     The panic looks like a totally different failure but has the same root: the
     server client must not depend on the mutated global default.

**Fix**: a dedicated constructor that (a) builds a **fresh** `*http.Transport`
(never clone/assert the global default), (b) sets a header-wait bound, not a
client-level `Timeout` (which would sever the long-lived `/event` SSE body), and
(c) is used by **both** `LaunchServer` and the test handle so tests exercise the
real client. Plus a per-probe context in `waitHealthy` as a second, independent
guard. Full Go + Rust code: `opencode-server-integration.md` §6.1
(`newHarnessHTTPClient` / `controlResponseHeaderTimeout`) and §6 `waitHealthy`.

```go
const controlResponseHeaderTimeout = 15 * time.Second

func newHarnessHTTPClient() *http.Client {
    tr := &http.Transport{ // FRESH transport, NOT http.DefaultTransport
        Proxy:                 http.ProxyFromEnvironment,
        ResponseHeaderTimeout: controlResponseHeaderTimeout, // bounds headers, not SSE body
    }
    return &http.Client{Transport: tr}
}
```

**Regression tests** (by behaviour): the constructor does not panic when
`http.DefaultTransport` has been replaced by a guard transport; the client has
`Timeout == 0` (SSE runs long) but `Transport.ResponseHeaderTimeout` set.

**Why not a blanket `http.Client.Timeout`?** It covers the *entire* exchange
including body read, so it would kill the `/event` SSE stream the driver holds
open for the whole session. `ResponseHeaderTimeout` (Go) /
`connect_timeout` + `read_timeout` (reqwest) bound only the dial and the
header/inter-byte wait — the actual hang points — while a steadily-streaming SSE
body runs unbounded.

## The silent multi-minute phase

**Symptom**: operator says "is it actually doing anything?" The
harness is in the middle of `cargo build`, or `wait_for_socket`, or
the log-idle wait, or one of N `claude --print` calls — but it looks
identical to "deadlocked" from outside.

**Cause**: only iteration boundaries and phase transitions log. The
phases themselves are silent.

**Fix**: four kinds of progress signal, layered:

### 1. Phase banners

At every phase transition, an `info!` line with a literal `"phase: ..."`
prefix the operator can grep for:

```rust
info!("phase: pre-build (cargo build -p <daemon-crate>)");
info!(iteration, "phase: spawn daemon");
info!(iteration, "phase: dispatch input + tail log");
info!(iteration, "phase: adversarial review");
info!(iteration, "phase: write burndown session");
```

### 2. Iteration banners

Visual separators at iteration start and end:

```rust
info!("============================================================");
info!(iteration, "STARTING ITERATION");
info!("============================================================");
```

End-of-iteration: same shape, replacing STARTING with the outcome
(CLEAN or ROUND COMPLETE).

### 3. Heartbeats in waiting phases

Every 10–15 seconds during a wait, an info line with elapsed/budget
counters. Two examples — socket wait and log-tail idle:

```rust
if last_heartbeat.elapsed() >= Duration::from_secs(10) {
    info!(
        elapsed_secs = start.elapsed().as_secs(),
        budget_secs = timeout.as_secs(),
        "still waiting for daemon socket"
    );
    last_heartbeat = Instant::now();
}
```

```rust
if last_heartbeat.elapsed() >= Duration::from_secs(15) {
    info!(
        lines = lines.len(),
        suspicious = suspicious_count,
        idle_for_secs = last_line_at.elapsed().as_secs(),
        "still tailing"
    );
    last_heartbeat = Instant::now();
}
```

### 4. Per-event streaming

Every suspicious line surfaces in real time via `warn!()` on a
dedicated `harness.suspicious` target. The operator sees bugs as
they're captured, before the LLM judges them:

```rust
if reviewer::worth_reviewing(&line) {
    suspicious_count += 1;
    warn!(target: "harness.suspicious", seq = suspicious_count, "{}", line);
}
```

A running tally every 200 captured lines covers the no-suspicious path
so even quiet phases show forward motion:

```rust
if lines.len().is_multiple_of(200) {
    info!(lines = lines.len(), suspicious = suspicious_count, "captured progress");
}
```

The reviewer phase gets per-batch progress (`info!(batch=N, of=total, ...)`),
not the debug-level "review batch" log the canonical example originally
shipped with.

## Reject summary placement

**Symptom**: bug-burndown ran on a candidate list the operator never
saw. When something gets misfiled (false positive promoted to bug,
real bug dropped), the operator can't tell whether the LLM made a
weird call or the harness mishandled the verdict.

**Cause**: reject summary printed AFTER burndown dispatch, or not at
all.

**Fix**: emit the summary AFTER `reviewer::review` returns but BEFORE
`burndown::run` is called. Operator sees the bug list, can hit
Ctrl-C if it looks wrong, only then does fixing happen:

```rust
let verdicts = reviewer::review(&cli.claude_bin, &lines).await?;
let rejects: Vec<_> = verdicts.iter().filter(|v| v.is_reject()).collect();
reviewer::log_reject_summary(&verdicts);  // ← this line, here, in this order.
// ... then dispatch burndown.
```

`log_reject_summary` sorts by severity and prints one info line per
unique fingerprint on the `harness.rejects` target.

## Pre-filter and rubric drift

**Symptom**: bugs that show up in production logs never make it to
the queue, even though the LLM rubric clearly says to reject them.

**Cause**: `worth_reviewing`'s `SIGNALS` constant doesn't include the
substring. The LLM never sees the line because the cheap pre-filter
dropped it.

**Fix**: every substring the rubric talks about must also be in
`SIGNALS`. Add them at the same time. Both live in `reviewer.rs`. The
pre-filter unit tests catch regressions where someone changes one
without the other:

```rust
#[test]
fn worth_reviewing_keeps_failure_tokens_in_info() {
    assert!(worth_reviewing("2026-01-01T00:00:00Z  INFO x: Failed to do thing"));
    assert!(worth_reviewing("2026-01-01T00:00:00Z  INFO x: the request exceeded its deadline"));
}
```

Add a test case for every substring you add to either the rubric or
the pre-filter.

## Daemon process group

**Symptom**: harness sends SIGTERM, the cargo wrapper exits, but the
daemon (which cargo execed) is still running and holding the socket.
Next iteration's daemon fails to bind.

**Cause**: SIGTERM was sent only to the cargo wrapper process. The
daemon, being a child but in the same process group, didn't get the
signal.

**Fix**: spawn with `.process_group(0)` so cargo gets its own group,
then SIGTERM the *negative* PID to hit the whole tree:

```rust
let child = Command::new("cargo")
    .args(...)
    .process_group(0)
    .spawn()?;

// To shutdown:
let pgid = Pid::from_raw(-(pid as i32));  // negative = process group
kill(pgid, Signal::SIGTERM)?;
```

If 30 seconds pass without exit, SIGKILL the same pgid. The `Drop`
impl on `Daemon` does a best-effort SIGKILL on the pgid in case the
explicit shutdown was skipped (e.g. an `?` propagated an error past
it).

## Bridge subprocess hangs after stream-json `result` event

**Symptom**: the burndown bridge logs a clean `burndown final result
subtype=success` event from the stream-json parser, then the harness
goes silent. No exception, no next-iteration banner, no "bug-burndown
returned, looping back" message. `ps` shows `claude --print
"/bug-burndown ..."` still alive minutes (or hours) later. The outer
harness loop hangs indefinitely.

**Cause**: `claude --print` doesn't always close stdout cleanly after
emitting its final stream-json `result` event. Telemetry flush, MCP
server shutdown, or stream-json-mode shutdown stalling can keep the
process alive with no further output. The harness's
`child.wait().await` blocks on the kernel waitpid; the stdout reader
task is parked on `read_line()` because the write end of the pipe
hasn't closed. Neither makes progress. Outer-loop deadlock.

**Fix**: pair the bridge's stdout reader with a watchdog. When the
reader sees the `result` event, fire a notify; the watchdog wakes,
sleeps `post_result_grace` (default 30s), sends SIGTERM, sleeps 10s,
sends SIGKILL. The escalation only fires on the hang path because
the watchdog is aborted normally when `child.wait()` returns on its
own.

```rust
use std::sync::Arc;
use std::time::Duration;
use tokio::sync::Notify;

let saw_result = Arc::new(Notify::new());
let child_pid = child.id();

// In the stdout reader loop, AFTER surface_stream_event(&line):
if is_result_event(&line) {
    saw_result.notify_one();
}

// Helper — keep it strict (false positive would SIGKILL claude
// mid-session).
fn is_result_event(line: &str) -> bool {
    let trimmed = line.trim();
    if !trimmed.starts_with('{') { return false; }
    serde_json::from_str::<serde_json::Value>(trimmed)
        .ok()
        .and_then(|v| v.get("type").and_then(|t| t.as_str()).map(str::to_owned))
        .as_deref() == Some("result")
}

let watchdog = {
    let saw_result = Arc::clone(&saw_result);
    let grace = Duration::from_secs(30);
    tokio::spawn(async move {
        saw_result.notified().await;
        tokio::time::sleep(grace).await;
        if let Some(pid) = child_pid {
            let pid = nix::unistd::Pid::from_raw(pid as i32);
            let _ = nix::sys::signal::kill(pid, nix::sys::signal::Signal::SIGTERM);
            tokio::time::sleep(Duration::from_secs(10)).await;
            let _ = nix::sys::signal::kill(pid, nix::sys::signal::Signal::SIGKILL);
        }
    })
};

let status = child.wait().await?;
watchdog.abort();
```

**Sanity checks for `is_result_event`**:

- Must reject truncated JSON (`{"type":"result` without closing brace) — a false positive would SIGKILL claude mid-session.
- Must reject other event types — only `"type":"result"` arms the watchdog.
- Must tolerate non-JSON lines (init banners, wrapper output).

Worked example: the reference harness commit `88bdb0a`. The bug surfaced
after a 35-minute burndown completed cleanly and the harness hung
on the wait. Operator was forced to `pkill -9 -f 'claude.*bug-burndown'`
to make wait() return. Add this pattern from day one — it costs
~40 lines and prevents an indefinite-hang failure mode the
implementer's own tests can't catch (the test would have to spawn
a real claude --print and observe the hang).

**Operator-facing flag**: expose the grace period as
`--burndown-post-result-grace-secs` (default 30) so slow CI hosts
can extend it without recompile.

## --no-burndown for dry runs

**Symptom**: operator wants to see what the harness would flag without
auto-fixing. There's no good way to inspect the candidate list before
the burndown runs.

**Fix**: ship `--no-burndown`. When set, after the reject summary the
harness prints the full reject list to stdout and exits. No burndown
session is written. Good for tuning the rubric:

```rust
if cli.no_burndown {
    info!(iteration, rejects = rejects.len(),
          "--no-burndown set: surfacing rejects and exiting");
    findings::dump_to_stdout(&rejects);
    break Ok(());
}
```

## Outer loop must be serial

**Symptom**: someone tries to parallelise the outer harness loop.
Two daemons fight over the same socket / DB / on-disk state.

**Rule**: outer loop is serial. ONE daemon up at a time. The inner
`bug-burndown` skill can fan out to parallel `bugfix` subagents in
isolated worktrees — that's its job — but the harness's own iteration
loop must not.

Don't add `--parallelism` to the harness CLI. The temptation will
return; resist it.

## Socket-wait budget tuning

**Symptom**: daemon takes 90+ seconds to apply migrations on a
populated SurrealDB, harness times out at 60.

**Fix**: `--socket-wait-secs` operator-tunable, default 300. The 300
seconds rarely fires in practice because the heartbeat shows the
operator what's happening:

```rust
#[arg(long, default_value_t = 300)]
socket_wait_secs: u64,
```

Don't lower the default. Cold migration runs on populated DBs really
do take that long sometimes, and the heartbeat keeps the operator
informed.

## Per-iteration artefact layout

**Rule**: every iteration writes to its own directory. Don't share
files across iterations.

```
.harness/
├── iter-001/
│   ├── server.log     # daemon tracing
│   └── cargo.log       # cargo's own stdout/stderr
├── iter-002/
│   ├── server.log
│   └── cargo.log
└── ...
```

When something goes wrong on iteration 7, the iter-007 directory has
exactly the forensic record from that run. The `.bug-burndown/`
sessions land in their own canonical location and reference back to
the iteration log via the manifest's `log_files:` field.

`.harness/` goes in `.gitignore` — it's noisy and per-machine.

## Sandbox, permission modes, and stdio alignment

All of this content moved to `references/nono-integration.md`. nono is
the canonical sandbox layer — the sandbox wrapper / systemd-run / PTY
alignment table and the full permission-mode rationale all live there.

The one debug-only tip that belongs here: when a path comes back EPERM
during a run, use `nono why --self --json` to see exactly which policy
rule denied it.

## Burndown.log tee

**Symptom**: operator runs the harness in tmux / under `nohup` /
with stderr captured to a file. `/bug-burndown` is invoked. The
operator wants to `tail -f` what bug-burndown is doing in real time
— but the only place that output exists is mixed into the harness's
own stderr stream, which is going somewhere they can't see live.

**Fix**: tee every line of the `claude --print "/bug-burndown ..."`
subprocess to a per-iteration `<iter>/burndown.log` AND emit through
tracing. The operator can `tail -f .harness/iter-NNN/burndown.log`
from any shell:

```rust
let file = tokio::fs::File::create(log_path).await?;
let file = Arc::new(Mutex::new(file));

let file_out = Arc::clone(&file);
let stdout_task = tokio::spawn(async move {
    let mut reader = BufReader::new(stdout).lines();
    while let Ok(Some(line)) = reader.next_line().await {
        info!(target: "burndown.stdout", "{}", line);
        let mut f = file_out.lock().await;
        let _ = f.write_all(line.as_bytes()).await;
        let _ = f.write_all(b"\n").await;
    }
});
// stderr task writes "[stderr] " prefix before each line to make the
// merged file readable.
```

Both streams hit the same file. Chronological order is preserved
because the writer is mutex-guarded.

## Pre-flight --claude-bin check

**Symptom**: operator passes `--claude-bin /home/r0/.local/bin/claude-bwrap`
(wrong user prefix; actual home is `/home/james/`). Iteration 1 runs
pre-build (3 min), spawns daemon (15 s), tails log to idle (45 s),
collects rejects, THEN tries to spawn the reviewer and fails with
`No such file or directory (os error 2)` after ~5 minutes of wasted
work.

**Fix**: validate the binary at startup, BEFORE any of the expensive
phases. ~30 lines:

```rust
async fn check_claude_bin(claude_bin: &str) -> Result<()> {
    if claude_bin.contains('/') {
        // Absolute or relative path — stat it.
        let metadata = tokio::fs::metadata(claude_bin).await
            .with_context(|| format!(
                "--claude-bin `{claude_bin}` not reachable. \
                 Check the path and that the wrapper is executable."
            ))?;
        if !metadata.is_file() {
            return Err(anyhow!(
                "--claude-bin `{claude_bin}` is not a regular file"
            ));
        }
    } else {
        // Bare name — exercise PATH lookup with --version.
        let out = tokio::process::Command::new(claude_bin)
            .arg("--version")
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::piped())
            .output()
            .await
            .with_context(|| format!(
                "--claude-bin `{claude_bin}` not found on PATH. \
                 Install claude or pass --claude-bin /abs/path."
            ))?;
        if !out.status.success() {
            return Err(anyhow!(
                "`{claude_bin} --version` exited {:?}: {}",
                out.status,
                String::from_utf8_lossy(&out.stderr).trim()
            ));
        }
    }
    Ok(())
}
```

Failure takes <1 second instead of 5 minutes. The operator's typo is
caught while their terminal is still in front of them, not after the
build phase has scrolled off.

## String-blind JSON parsing

**Symptom**: `Error: adversarial reviewer / Caused by: unbalanced
JSON array in reviewer output` even though the JSON the LLM emitted
looked fine to the eye.

**Cause**: the original `parse_verdicts` walked the raw output
counting `[` and `]` characters to find the array boundary. That
walk was string-blind — every bracket counted equally, whether it
was JSON syntax or literal text inside a JSON string. Tracing log
lines almost always include literal brackets in the verdict's
`line` field:

```
WARN [app_agents::worker]: Failed to ...
```

When this lands in `"line":"WARN [app_agents::worker]: ..."`,
the parser sees `[` (depth → 1) then `[` again (depth → 2) then `]`
(depth → 1) and decides the array ends there — well before the real
end. Or it stays at depth 1 forever and reports "unbalanced".

**Fix**: hand the slice to `serde_json::Deserializer` instead of
walking it manually. The Deserializer parses one full JSON value
(the array) with proper string + escape awareness and stops. Any
trailing markdown / prose after the array is silently ignored —
same lenient surface, resilient internals:

```rust
let json_start = raw.find('[').ok_or_else(|| anyhow!("no JSON array"))?;
let mut de = serde_json::Deserializer::from_str(&raw[json_start..]);
Vec::<Verdict>::deserialize(&mut de)
    .with_context(|| format!("parse reviewer JSON"))
```

Regression tests guard the seam: brackets-inside-strings, escaped-
quotes-inside-strings, trailing-text-after-array. All three are
realistic LLM outputs; all three break the string-blind walker; all
three work fine through `Deserializer`.

### …but the model also emits genuinely-invalid JSON — recover, don't drop the batch

String-aware parsing fixes the *finding* step. It does not fix JSON
the model emitted that is **invalid by the spec**, which the strict
decoder then rejects outright. Observed, recurring LLM JSON defects —
each loses a whole reviewer batch if you bail on first decode error:

1. **Stray escape sequences *between* structural tokens** — the model
   emits `[\r\n  {\r\n …` where each `\r` is the two characters `\`+`r`,
   not a real CR. Invalid outside a string. Symptom:
   `invalid character '\\' looking for beginning of value`.
2. **Raw control characters *inside* a string value** — a literal
   newline / tab / CR inside a long `reason` or a captured multi-line
   `line` field. RFC 8259 §7 forbids unescaped control chars in strings.
   Worse, the raw newline desynchronises a hand-rolled string tracker so
   the *next* escaped `\"` is misread in key position — surfacing as the
   misleading `invalid character '\\' looking for beginning of object
   key string`. This is the 2026-06-16 reviewer-JSON-decode incident.
3. **Invalid backslash escapes inside a string** — a Windows path or a
   regex passed through verbatim (`C:\Temp`, `\d+`). Symptom:
   `invalid character 'd' in string escape code`.

**Fix: a cumulative recovery ladder.** On first decode failure, run a
sequence of **string-aware** cleanup passes and re-decode after each;
return on the first success. Each rung is a no-op on input that doesn't
exhibit its defect, so the ladder is safe to always run and rungs
compose (a payload with two defects is still recovered). Order:
(1) strip stray escapes outside strings → (2) escape raw control chars
inside strings (`\n`/`\r`/`\t`/`\u00XX`) → (3) escape invalid backslash
escapes inside strings. Treating a model formatting tic as a lost batch
is strictly worse than these safe repairs. **Never** silently swallow a
total parse failure as "zero rejects" — that's the reviewer-outage rule
(a batch that never parsed is `WorkRemaining`, not `Clean`); the ladder
*reduces* outages, it doesn't license treating a real one as clean.

Canonical Go implementation: `vulnmapper pkg/harness/reviewer.go`
(`ParseVerdicts` recovery ladder, `escapeControlCharsInStrings`,
`escapeBadEscapesInStrings`, `stripBareEscapes`). The Rust equivalent
runs the same three passes before `Deserializer`.

```go
// On first decode error, walk the ladder; each fn is string-state-aware.
ladder := []struct{ name string; fn func(string) string }{
    {"stray-escapes-outside-strings", stripBareEscapes},
    {"control-chars-in-strings",      escapeControlCharsInStrings},
    {"bad-escapes-in-strings",        escapeBadEscapesInStrings},
}
cleaned := slice
for i, rung := range ladder {
    next := rung.fn(cleaned)
    if next == cleaned { continue }       // no-op rung; try the next
    cleaned = next
    if vs, err := decodeVerdicts(cleaned); err == nil {
        slog.Warn("reviewer JSON recovered after cleanup",
            "rung", rung.name, "rungs_applied", i+1)
        return vs, nil
    }
}
return nil, fmt.Errorf("parse reviewer JSON: %w …", firstErr) // exhausted → real failure
```

**Required regression tests** (by name): `recovers_from_literal_escapes_outside_strings`,
`recovers_from_raw_newline_in_string_value` (the incident),
`recovers_from_bad_escape_in_string_value`, plus no-op guards
(`escape_control_chars_leaves_valid_json_unchanged`,
`escape_bad_escapes_preserves_valid_escapes`) so the cleanup never
corrupts well-formed JSON or mistakes a `\"` for a string terminator.

## Burndown subprocess streams JSON, not text

**Symptom**: the burndown phase shows nothing in `burndown.log` for
30+ minutes, then dumps a wall of text at the end. Hard to tell if
claude is actually working or wedged on something.

**Cause**: default `claude --print` uses `--output-format text` —
the final assistant message is emitted at exit, all at once. The
harness's line reader doesn't get anything to forward until then.

**Fix**: spawn with `--output-format stream-json --verbose`. Claude
emits one JSON event per line as work happens — session init,
assistant message chunks, tool calls, tool results, final result.
Parse each line and route to per-event tracing targets:

```rust
.arg("--output-format").arg("stream-json")
.arg("--verbose")  // required to actually stream (otherwise buffered)
```

Per-line parser switches on `type`:

  - `system` → `info!(target: "burndown.event", subtype, ...)`
  - `assistant.message.content[].type=text` → `info!(target: "burndown.assistant", ...)`
  - `assistant.message.content[].type=tool_use` → `info!(target: "burndown.tool", tool=name, "{input summary}")`
  - `assistant.message.content[].type=thinking` → `debug!(target: "burndown.thinking", ...)` (extended thinking blocks)
  - `user.message.content[].type=tool_result` → `debug!(target: "burndown.tool_result", ...)` (truncated)
  - `result` → final outcome with cost + duration

Non-JSON lines (early init banners, wrapper output before the stream
begins) go to `info!(target: "burndown.raw", ...)`. Always tee the
raw stream to `burndown.log` first so the forensic record is
complete — the tracing surface is a human-readable abstraction over
the JSON.

**Costs**: stream-json output is bigger (MB-scale for long burndowns
vs KB for text mode). Token billing is unchanged — same model
output, just streamed instead of buffered.

**Don't enable `--include-partial-messages` by default.** It emits
one event per ~10-20 tokens, which is overwhelming. Make it an
operator-tunable flag if you need per-token streaming.

## Distinguishing harness-driven from interactive bug-burndown

**Symptom**: every harness run leaves a `.bug-burndown/<id>/` session
behind. Subsequent interactive Claude Code sessions in the same
project see that session via `.bug-burndown/CURRENT` and the
bug-burndown Stop hook blocks the interactive session on the
harness's leftover work.

**Cause**: the bug-burndown autonomy contract enforces "every queue
entry must reach a terminal state before stop" — fine when the
session was explicitly invoked, broken when an unrelated Claude
session inherits the session pointer.

**Fix**: env-var contract between the harness and the bug-burndown
skill's Stop hook. The harness sets two env vars on its `claude
--print` invocation:

```rust
.env("BUG_BURNDOWN_HARNESS_DRIVEN", "1")
.env("BUG_BURNDOWN_HARNESS_SESSION_ID", session_id)
```

And writes `origin: the reference harness` (or `<toolname>-harness`) into
the session manifest. The Stop hook's decision matrix:

| `BUG_BURNDOWN_HARNESS_DRIVEN=1` | `manifest.origin` contains "harness" | Hook |
|---|---|---|
| Yes | (any) | BLOCK — this IS the spawned subprocess |
| No | Yes | SKIP — different session looking at leftover |
| No | No | BLOCK — direct interactive invocation |

Inside the harness-spawned `claude --print` subprocess the env var
IS set (passed through by `Command::env`), so the hook fires the
autonomy contract normally and drives the queue to terminal status.
Outside (interactive Claude Code, other tools, this conversation),
the env var is unset, the hook reads the manifest's harness origin,
and skips the block.

The contract is one env var and one manifest field — any harness in
any language can implement it. The bug-burndown skill's
`scripts/check-completion.py` reads both; see that file for the
exact logic.

## Resuming from a failed iteration

**Symptom**: the harness fails mid-iteration — typically in the
reviewer phase or burndown dispatch — after spending 20–40 minutes
on pre-build + daemon spawn + log capture. Re-running from scratch
repeats all of that.

**Fix**: `--resume-iter <ITER_DIR>` flag. Skips pre-build, daemon
spawn, and log capture entirely; reads the already-captured
`<iter-dir>/server.log` and continues at the review phase.

```rust
#[arg(long, value_name = "ITER_DIR")]
resume_iter: Option<PathBuf>,
```

```rust
// Inside main loop, on the FIRST iteration only:
let (iter_dir, log_path, lines) = if let Some(resume_dir) = resume_iter.take() {
    let log_path = resume_dir.join("server.log");
    info!(resume_from = %resume_dir.display(),
          "phase: resume — reading captured log instead of spawning daemon");
    let lines = read_captured_log(&log_path).await?;
    (resume_dir, log_path, lines)
} else {
    // Normal path: create iter-NNN/, spawn daemon, capture log.
    ...
};
```

`read_captured_log` is just `tokio::fs::read` + `split('\n')` — the
live tail logic doesn't apply when the daemon's gone and no new
lines are coming.

After the resumed iteration finishes (review + maybe burndown),
subsequent iterations always start fresh at iter-N+1 with full
daemon spawn. Resume only short-circuits the first pass.

Common cases this handles:

- **Reviewer JSON parse failure**: fix the parser, point at the
  same iter directory, re-review the captured log. No daemon rerun.
- **`claude --print` exited non-zero**: the wrapper had a config
  problem, fix it, resume against the same captured log.
- **Network blip during a `claude --print` call**: same.
- **Operator-initiated abort**: re-run with `--resume-iter` to
  finish triaging the captured log without paying the daemon cost.

What resume DOESN'T cover:

- Failures DURING daemon spawn or log capture — there's no captured
  log to resume from yet; just re-run normally.
- Failures inside `/bug-burndown` itself — that skill's own
  resume-by-session-id path handles those (`bug-burndown
  resume:<session-id>`). The harness's `--resume-iter` is for
  harness-side failures only.

## Spawn-error context phrasing

**Symptom**: a real error message like

```
Error: adversarial reviewer
Caused by:
    0: spawn /home/r0/.local/bin/claude-bwrap --print
    1: No such file or directory (os error 2)
```

makes the operator reasonably ask "is the harness gluing `--print`
onto the binary path?" The answer is no — `--print` was a separate
`.arg()` call — but the context format string `"spawn {claude_bin}
--print"` reads as if it were one string.

**Fix**: phrase the context so the path/flag boundary is
unambiguous. Backticks around the path, prose for the flag:

```rust
.with_context(|| format!(
    "spawn claude binary `{claude_bin}` for reviewer batch"
))?
```

vs the burndown bridge:

```rust
.with_context(|| format!(
    "spawn claude binary `{claude_bin}` for /bug-burndown dispatch"
))?
```

Different context per call site so the operator knows which spawn
failed without reading the stack.

## Scenario panics must not kill the harness

**Symptom**: harness exits with a multi-line Go panic / Rust panic /
Python traceback after the first scenario crashes. Subsequent
scenarios never run. The full iteration log is missing because the
process died before flushing capture. The reviewer never sees the
bug because there's no log to review.

Canonical Go example, from vulnmapper-harness's first real run:

```
ERROR msg="failed to retrieve Aws Inspector findings"
      error="...api error UnrecognizedClientException: The security
             token included in the request is invalid."
panic: runtime error: invalid memory address or nil pointer dereference
[signal SIGSEGV: segmentation violation code=0x1 addr=0x8 pc=0x190a122]
goroutine 1 [running]:
  pkg/sources/vulns.(*VulnerabilityProviderAwsInspector).Refresh(0x...)
    .../pkg/sources/vulns/aws_inspector.go:113 +0x4c2
  pkg/harness.IngestScenarios.func11(...)
    .../pkg/harness/scenario_defs.go:130 +0x22
  pkg/harness.(*Runner).Run(...)
    .../pkg/harness/scenarios.go:121 +0x592
  ...
exit status 2
```

The 403 is a real bug — the operator's AWS token is bad. The
nil-deref is a second, distinct bug — the provider's error path
forgot to short-circuit before touching a response field. Without
recovery, the harness reports only "process exited 2" and the
operator has to read the panic by hand. With recovery, both bugs
land in the reject queue as separate verdicts.

**Cause**: each per-scenario / per-task call was invoked directly,
with no panic boundary between it and the outer loop. Any unhandled
runtime failure in the system-under-test code propagates up through
the harness's call stack and terminates the process.

**Fix**: wrap every per-scenario call in a recovery boundary that
captures the panic-as-error with the full stack trace, then continues
the loop.

### Go pattern

```go
type ScenarioPanicError struct {
    Scenario string
    Value    any    // whatever panic() passed
    Stack    string // runtime.Stack output at recover time
}

func (e *ScenarioPanicError) Error() string {
    return fmt.Sprintf("scenario %q panicked: %v", e.Scenario, e.Value)
}

func runScenarioSafely(ctx context.Context, s Scenario, env *Env) (err error) {
    defer func() {
        if r := recover(); r != nil {
            stack := captureStack()
            slog.Error("scenario panicked — recovered",
                "scenario", s.Name,
                "panic", fmt.Sprintf("%v", r),
                "stack", stack)
            err = &ScenarioPanicError{
                Scenario: s.Name,
                Value:    r,
                Stack:    stack,
            }
        }
    }()
    return s.Run(ctx, env)
}

func captureStack() string {
    for size := 8 * 1024; size <= 256 * 1024; size *= 2 {
        buf := make([]byte, size)
        n := runtime.Stack(buf, false)
        if n < size {
            return string(buf[:n])
        }
    }
    return "<stack exceeded 256 KiB>"
}
```

The buffer growth handles the rare case where the stack is bigger
than 8 KiB (deep call chains through middleware + RPC layers). Cap
at 256 KiB so a pathological stack can't OOM the harness.

### Rust pattern

```rust
use std::panic::{catch_unwind, AssertUnwindSafe};

#[derive(Debug, thiserror::Error)]
#[error("scenario {scenario} panicked: {message}")]
pub struct ScenarioPanicError {
    pub scenario: String,
    pub message: String,
    pub backtrace: Backtrace,
}

async fn run_scenario_safely(
    s: &Scenario,
    env: &Env,
) -> Result<(), ScenarioPanicError> {
    let scenario_name = s.name.clone();
    match catch_unwind(AssertUnwindSafe(|| futures::executor::block_on(s.run(env)))) {
        Ok(Ok(())) => Ok(()),
        Ok(Err(e)) => Err(ScenarioPanicError {
            scenario: scenario_name,
            message: e.to_string(),
            backtrace: Backtrace::capture(),
        }),
        Err(payload) => {
            let msg = if let Some(s) = payload.downcast_ref::<&'static str>() {
                (*s).to_string()
            } else if let Some(s) = payload.downcast_ref::<String>() {
                s.clone()
            } else {
                format!("non-string panic payload")
            };
            tracing::error!(scenario = %scenario_name, panic = %msg, "scenario panicked — recovered");
            Err(ScenarioPanicError {
                scenario: scenario_name,
                message: msg,
                backtrace: Backtrace::capture(),
            })
        }
    }
}
```

`AssertUnwindSafe` is load-bearing — most async futures aren't
`UnwindSafe`, but the harness's recovery boundary is explicit, so the
assertion is correct. Use `Backtrace::capture()` for the captured
stack; it respects `RUST_BACKTRACE=1` at runtime.

### What this buys you

1. **Every scenario runs.** A panic in scenario 2 of 10 doesn't hide
   bugs in scenarios 3 through 10.
2. **The reviewer sees the panic.** The recovered stack trace lands
   in the iteration log under `kind=panic` (severity=critical by the
   default rubric). `/bug-burndown` gets a real fix candidate
   instead of an opaque "harness died" stderr trace.
3. **Two bugs surface where one used to mask the other.** In the
   AWS Inspector example: bug #1 = bad token (operator action),
   bug #2 = nil-deref in error path (code fix). Without recovery,
   bug #2 is invisible.

### Anti-patterns

**Don't recover at the outer loop level.** A `defer recover` in
`main()` catches the panic but loses scenario identity — by the time
the recover fires, the per-scenario context is gone. Wrap at the
narrowest call site that still has access to the scenario metadata
(name, phase, required keys).

**Don't try to keep the scenario state across the panic.** The
provider that panicked is in an undefined state. Treat the rest of
the iteration as you would after any other scenario failure: log,
record an outcome, move on to the next scenario.

**Don't swallow the panic silently.** Log at ERROR level WITH the
full stack. The reviewer's rubric needs the stack text to file a
high-quality verdict; truncating to "scenario X panicked" loses the
diagnostic.

**Don't suppress panics inside the recovery boundary's own logging.**
If your slog handler can itself panic (rare, but possible in custom
handlers), wrap the `slog.Error(...)` call in another recover or use
a fallback `os.Stderr` write. A panic during panic recovery is the
one failure mode the harness genuinely can't survive — but you can
make it loud instead of silent.

### Unit test

Mandatory regression coverage:

```go
func TestRunner_RecoversFromScenarioPanic(t *testing.T) {
    scenarios := []Scenario{
        {Name: "pass-one", Run: func(...) error { return nil }},
        {Name: "explode", Run: func(...) error {
            var p *struct{ X int }
            _ = p.X    // nil deref
            return nil
        }},
        {Name: "pass-two", Run: func(...) error {
            // proves the loop continued past the panic
            return nil
        }},
    }
    outcomes := (&Runner{Scenarios: scenarios}).Run(ctx)
    require.Len(t, outcomes, 3)
    require.Equal(t, ResultPass, outcomes[0].Result)
    require.Equal(t, ResultFail, outcomes[1].Result)
    var panicErr *ScenarioPanicError
    require.ErrorAs(t, outcomes[1].Err, &panicErr)
    require.Contains(t, panicErr.Stack, "TestRunner_RecoversFromScenarioPanic")
    require.Equal(t, ResultPass, outcomes[2].Result)
}
```

The third scenario running after the second panicked is the
load-bearing assertion. Without recovery it never reaches that
outcome and `outcomes` has length 2.

## Runaway candidate pools blow review wall-time

**Symptom**: an iteration logs something like
`failure_candidates=185490, batch=1/1240` and the reviewer phase
then takes most of a day to finish. No `/bug-burndown` runs. The
operator hits Ctrl-C and the next iteration starts with the same
185 000 candidates because nothing got fixed.

**Cause**: one upstream defect (canonical case: a DB connection
pool exhaustion that cascaded through every subsequent query in
that iteration) emitted tens of thousands of WARN/ERROR lines.
The pass-1 pre-filter forwarded every single one. At 150 lines per
batch that's 1240+ `claude --print` calls, each taking 20-60 s
wall time and ~$0.50 in tokens. The reviewer is doing pattern
matching the same defect would have been caught by in the first
batch.

**Why this doesn't fix itself**: pass 2 has always capped templates
at ~600 by deduplicating with `fingerprint_template`. Pass 1 didn't.
A retry storm becomes a wall-time storm.

**Fix**: adaptive pre-LLM dedup on pass 1, mirroring pass 2's
template cap. When raw pass-1 candidates would produce more than
`MaxBatches × MaxBatchLines` batches (defaults: 100 × 300 = 30 000
ceiling), fingerprint-group the failures and keep the top-N
most-frequent exemplars. Forward the per-exemplar `seen:N` count
into the prompt so the LLM weighs by occurrence. Below the
ceiling, behavior is unchanged — full-fidelity raw-line review.

See [runtime-reviewer-rubric.md § Adaptive cap on pass 1](runtime-reviewer-rubric.md)
for the implementation pattern + rubric paragraph that has to
match it.

**Why the cap engages and disengages naturally**: an iteration
that finds a connection-exhaustion cascade compresses 185 000
candidates onto a few exemplars. `/bug-burndown` fixes the
cascade. The next iteration's pool is well under the ceiling and
dedup stops engaging — full-fidelity review returns automatically
as the burndown progresses. The cap is the rate-limiter, not the
review strategy.

**Don't set MaxBatches=0 ("uncapped") as a default.** That's how
185 000-candidate runs land in production. If an operator
explicitly wants every line reviewed for a small clean pool, they
can opt out per-invocation — but the default has to be safe under
the cascading-failure case, not the happy-path case.

**Don't double-dedup.** The post-LLM merge in `mergeAndKeepRejects`
sums counts on reject verdicts. The pre-LLM cap dedups raw input.
They do different jobs and both have to run. Don't try to fold one
into the other.

### Unit test

The test catches the original failure mode literally — 185 000
identical-template records reduce to a single exemplar with
count=185000:

```go
func TestCapAndDedupFailures_LargeInputBoundedToCap(t *testing.T) {
    records := make([]Record, 185_000)
    for i := range records {
        records[i] = Record{
            Level: "ERROR",
            Msg:   "sorry, too many clients already on conn " + strconv.Itoa(i%50),
        }
    }
    out, counts := CapAndDedupFailures(records, 100, 300)
    require.NotNil(t, counts, "dedup should activate")
    require.LessOrEqual(t, len(out), 100*300)
    // FingerprintTemplate strips numbers, so all 185k collapse to
    // exactly one exemplar regardless of the seeded conn IDs.
    require.Len(t, out, 1)
    require.Equal(t, int64(185_000), counts[0])
}
```

The "FingerprintTemplate strips numbers so all 185k collapse to
one" property is the load-bearing one. If your fingerprinter
diverges (different regex set, different language), the test still
expresses the contract: a single-template cascade must collapse
to a single exemplar with its full count.

## The verification surface must respect the project's own test scoping

**Symptom**: the harness drives the project's test surface with a blanket
`cargo test --workspace` (or `go test ./...`, or the language equivalent) on
every burndown pass. On a large workspace this runs for many minutes with no
harness-level log line, so it *looks* frozen — and worse, it can blow the
per-iteration memory or time budget the project's own docs warn against. The
canonical case: a 35-crate Rust workspace whose `CLAUDE.md` explicitly forbids
`--workspace` test runs (per-crate rustc peak RSS and wall-time are far lower),
yet `capture_verification` hardcoded `cargo test --workspace --no-fail-fast`
twice per round.

**Rule**: the verification surface drives the project **the way the project
says to drive it**. Read the project's own build/test guidance (`CLAUDE.md`,
`AGENTS.md`, the CI config) and honour it. The common shape:

- Build once, cheaply (incremental `cargo build --workspace` is fine — a compile
  error anywhere is a reject regardless of which crates you go on to test).
- **Scope the test step to what changed.** Derive the changed crates/targets
  from git (`git status --porcelain` + `git diff --name-only HEAD`), map each
  changed path to its owning unit (nearest `Cargo.toml` with `[package] name`,
  the owning Go package, etc.), and run only those (`cargo test -p <crate>`).
- **Clean tree → skip the test step** entirely; nothing changed to exercise.
- **Degrade safe**: if git is unavailable or a changed path can't be mapped, fall
  back to the full-workspace run rather than silently narrowing coverage. The
  fallback is the slow-but-correct path, not the default.
- **Log what you run** — "building workspace", "testing changed crates: a, b",
  "working tree clean — skipping tests". The silent multi-minute phase
  (see above) is exactly what a hardcoded `--workspace` produces.

This both fixes the apparent hang and stops the harness from fighting the
project's documented resource envelope. The "looks frozen" report is almost
always this: the loop isn't stuck, it's grinding a workspace test run that
should have been three `-p` invocations.

## Scoping "what this turn changed" — pre/post dirty-set difference

**Symptom**: any audit or heuristic that reasons about "the files the fix turn
touched" reads the whole dirty worktree (`git diff HEAD` / `git status`) and
attributes *everything uncommitted* to the current turn — including a `.snap`
left dirty by an earlier phase, a prior un-committed round, or operator state.
A change-scoped structural audit (snapshot-drift, churn gating) then fires on
state the turn never touched. Combined with "burndown that found a reject always
returns WorkRemaining", a deterministic false reject like this wedges the loop to
`max_rounds` and exits NOT-done.

**Rule**: capture the dirty set **before** dispatching the fix turn, capture it
**after**, and feed the audit only the **set difference** — the paths that
became dirty because of this turn.

```rust
let pre = changed_paths(root).await;          // immediately before dispatch
// … dispatch + drive the fix turn …
let post = changed_paths(root).await;
let pre_set: BTreeSet<_> = pre.iter().collect();
let turn_changed: Vec<_> = post.into_iter().filter(|p| !pre_set.contains(p)).collect();
scan_snapshot_drift(&turn_changed);            // only THIS turn's churn
```

`changed_paths` shells `git diff --name-only HEAD` + `git status --porcelain`
(taking the post-rename name from `old -> new`), and returns an empty list on any
git failure so the audit degrades to "found nothing", never a false reject. This
is the diff-scoping rule applied to *audits*; the same git-derived changed-set
also drives per-crate test scoping (above). Keep one helper.

## Build the harness in a worktree when the root checkout is contended

**Symptom**: you (or the auditor) edit a harness source file, the tests pass, and
moments later the edit has vanished — `git status` shows nothing, the file is
back to its prior form. This happens when the harness is **running against its
own repo**: a live genesis/burndown run merges its agent worktrees back into the
root checkout, and any *uncommitted* edit sitting in the root is clobbered by the
next merge or reset.

**Rule**: when building or auditing a harness whose project is being driven by a
concurrent run on the same checkout, do the work in a dedicated git worktree
(`git worktree add -d /tmp/work HEAD`), with its **own** `--target-dir` so cargo
doesn't fight the running build's lock, and commit there. This is the same
worktree-isolation discipline the harness imposes on its own dispatched agents —
apply it to yourself. Merge to the default branch when the live run isn't
mid-merge. (Resolving the symlinked-gcc / broken-`cc` toolchain in a fresh shell
is a separate, common stumble: a Nix box may have `cc`→clang but the project's
`.cargo/config.toml` pins `CC=gcc`; put a real `gcc` on `PATH` before building.)

## The completion-loop plugin must gate on per-session skill activation

**Symptom**: a harness operator working in a repo that has *ever* run `/iterate`,
`/iteratotron`, or `/bug-burndown` finds **unrelated** opencode sessions getting
re-prompted with `[completion-loop: iterate] … work remains. Do not stop.` — even
a session that only ran a one-off harness edit. The session is hijacked into a
loop it never started.

**Cause**: the opencode completion-loop plugin (the `session.idle` equivalent of
Claude Code's Stop hook) ran the loop checkers gated only on the presence of
**project-scoped** marker dirs (`.iterate/`, `.iteratotron/`, `.bug-burndown/`).
Those dirs persist for the life of the repo, so once any session created them,
every later idle in that repo tripped the checker — regardless of which skill the
current session actually loaded.

**Rule (for the plugin, not the harness)**: gate each checker on whether **this
session** loaded that skill, read from the session transcript
(`client.session.messages`): a tool part with `tool === "skill"` and
`state.input.name === <skill>`, or a user text part naming `/<skill>`. A session
with no loop skill loaded is never re-prompted. Fail open to "not active" on any
API/parse error so a transient failure can't hijack a session. This is the
2026-06-16 plugin-hijack incident; the fix lives in
`.opencode/plugins/completion-loop.ts`. Relevant to harness operators because the
spurious re-prompts look like the harness misbehaving when they're the plugin.
