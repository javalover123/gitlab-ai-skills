# Go Module Skeletons

The closed-loop pattern is language-agnostic. This document covers the
Go variant — same seven-module structure, same architecture, same
rubric. Only the language-specific bits change: `go build` instead of
`cargo build`, `os/exec` instead of `tokio::process`, gRPC or HTTP
instead of tarpc, JSON-aware pre-filter for Go structured loggers.

**The harness binary can be Go even if the system under test is Rust,
and vice versa.** They're independent. Pick the language that matches
the codebase you'll be poking at the most.

See [runtime-rust-skeletons.md](runtime-rust-skeletons.md) for the canonical Rust
implementation — the architecture sections (workflow, gotchas, rubric)
all apply unchanged. This document covers only the Go-specific diffs.

## Layout

```
<binary-name>/
├── go.mod
├── README.md
└── cmd/<binary-name>/
    ├── main.go         # outer loop + CLI + pre-flight check
    ├── daemon.go       # spawn / SIGTERM / SIGKILL teardown
    ├── client.go       # talk to the system under test
    ├── log.go          # tail until idle + heartbeats
    ├── reviewer.go     # two-pass review + fingerprinting
    ├── action_audit.go # structural anti-rationalization pass (mandatory)
    ├── findings.go     # write the bug-burndown session
    └── burndown.go     # /bug-burndown bridge with log tee
```

## go.mod

```go
module github.com/<org>/<binary-name>

go 1.22

require (
    google.golang.org/grpc v1.62.0          // or net/http if HTTP-only
    google.golang.org/protobuf v1.33.0
    github.com/google/uuid v1.6.0
    github.com/spf13/cobra v1.8.0            // CLI parser
    go.uber.org/zap v1.27.0                  // structured logging
    github.com/rs/zerolog v1.32.0            // alternative — pick one
)
```

For pre-Go-1.22 codebases use `slog` from the standard library and
drop the zap/zerolog deps.

## main.go — CLI + pre-flight

```go
package main

import (
    "context"
    "errors"
    "fmt"
    "log/slog"
    "os"
    "os/exec"
    "path/filepath"
    "regexp"
    "strconv"
    "strings"
    "time"

    "github.com/spf13/cobra"
)

type config struct {
    input                   string
    daemonConfig            string
    socket                  string
    workDir                 string
    socketWaitSecs          int
    idleSecs                int
    iterationTimeoutSecs    int
    claudeBin               string
    reviewerPermissionMode  string
    burndownPermissionMode  string
    allowUnsandboxed        bool
    networkProfile          string
    reviewerPass1Model      string  // default "haiku"
    reviewerPass2Model      string  // default "haiku"
    burndownModel           string  // default "haiku"
    noBurndown              bool
}

func main() {
    var c config
    cmd := &cobra.Command{
        Use:   "<binary-name>",
        Short: "Closed-loop quality harness",
        RunE:  func(cmd *cobra.Command, args []string) error { return run(c) },
    }
    cmd.Flags().StringVar(&c.input, "input", "<sensible default>", "drive-surface input")
    cmd.Flags().StringVar(&c.daemonConfig, "config", "config/development.toml", "daemon config")
    cmd.Flags().StringVar(&c.socket, "socket", "", "Unix socket path (default: <work-dir>/daemon.sock)")
    cmd.Flags().StringVar(&c.workDir, "work-dir", ".harness", "artefact directory")
    cmd.Flags().IntVar(&c.socketWaitSecs, "socket-wait-secs", 300, "")
    cmd.Flags().IntVar(&c.idleSecs, "idle-secs", 45, "")
    // 1800s (30 min) suits a request/response service; for a daemon that drives
    // long builds/migrations/E2E before settling, raise it so a healthy drive
    // isn't cut short (SKILL.md "Size the deadlines to the workload").
    cmd.Flags().IntVar(&c.iterationTimeoutSecs, "iteration-timeout-secs", 1800, "per-iteration hard cap; size to the workload")
    cmd.Flags().StringVar(&c.claudeBin, "claude-bin", "claude", "claude binary")
    cmd.Flags().StringVar(&c.reviewerPermissionMode, "reviewer-permission-mode", "bypassPermissions",
        "permission-mode for reviewer; defaults to bypassPermissions (harness uses nono sandbox)")
    cmd.Flags().StringVar(&c.burndownPermissionMode, "burndown-permission-mode", "bypassPermissions",
        "permission-mode for burndown bridge; same rationale as reviewer")
    cmd.Flags().BoolVar(&c.allowUnsandboxed, "allow-unsandboxed", false,
        "run without nono sandbox (keeps permission_mode=acceptEdits; not recommended)")
    cmd.Flags().StringVar(&c.networkProfile, "network-profile", "claude-code",
        "nono --network-profile; dropped on Landlock ABI < 4 (auto-detected)")
    cmd.Flags().StringVar(&c.reviewerPass1Model, "reviewer-pass1-model", "haiku",
        "model for pass 1 (failure-shaped) — see SKILL.md § Model selection")
    cmd.Flags().StringVar(&c.reviewerPass2Model, "reviewer-pass2-model", "haiku",
        "model for pass 2 (silent-divergence) — Haiku default, raise to Sonnet only for very complex divergence; never Opus")
    cmd.Flags().StringVar(&c.burndownModel, "burndown-model", "haiku",
        "model for the burndown bridge — Haiku default, raise to Sonnet only for very complex debugging; never Opus")
    cmd.Flags().BoolVar(&c.noBurndown, "no-burndown", false, "")
    if err := cmd.Execute(); err != nil {
        os.Exit(1)
    }
}

func run(c config) error {
    log := slog.Default()

    if err := os.MkdirAll(c.workDir, 0o755); err != nil {
        return fmt.Errorf("mkdir work-dir: %w", err)
    }
    socketPath := c.socket
    if socketPath == "" {
        abs, err := filepath.Abs(c.workDir)
        if err != nil { return fmt.Errorf("abs work-dir: %w", err) }
        socketPath = filepath.Join(abs, "daemon.sock")
    }

    log.Info("<binary-name> starting",
        "socket", socketPath, "work_dir", c.workDir,
        "input", c.input, "claude_bin", c.claudeBin)

    // Pre-flight check — fail fast on a wrong --claude-bin instead
    // of finding out 5+ minutes into iteration 1.
    if err := checkClaudeBin(context.Background(), c.claudeBin); err != nil {
        return err
    }

    // Pre-build the daemon. `go run` would build inside the spawn,
    // racing the socket-wait timer.
    log.Info("phase: pre-build (go build)")
    buildStart := time.Now()
    if err := exec.Command("go", "build", "-o",
        filepath.Join(c.workDir, "daemon"),
        "./cmd/daemon").Run(); err != nil {
        return fmt.Errorf("go build daemon: %w", err)
    }
    log.Info("pre-build complete", "elapsed_secs", time.Since(buildStart).Seconds())

    // Outer loop — same shape as the Rust version.
    for iteration := 1; ; iteration++ {
        iterStart := time.Now()
        log.Info("============================================================")
        log.Info("STARTING ITERATION", "iteration", iteration)
        log.Info("============================================================")

        iterDir := filepath.Join(c.workDir, fmt.Sprintf("iter-%03d", iteration))
        if err := os.MkdirAll(iterDir, 0o755); err != nil {
            return fmt.Errorf("mkdir iter-dir: %w", err)
        }
        logPath := filepath.Join(iterDir, "daemon.log")

        // ... daemon spawn, ingest, review, burndown — see Rust
        // version for full structure; Go translates directly.
        _ = iterStart
        _ = logPath
    }
}

// SandboxVerdict holds the outcome of the preflight check.
// Thread it through to every reviewBatch and burndown call.
type SandboxVerdict struct {
    NonoVersion    string  // empty if unsandboxed
    NetworkProfile string  // "claude-code" or "" (no profile)
    PermissionMode string  // "bypassPermissions" or "acceptEdits"
}

// checkSandboxAndClaude probes nono, determines network-profile support,
// then confirms the claude binary is reachable. See nono-integration.md.
func checkSandboxAndClaude(ctx context.Context, claudeBin string, allowUnsandboxed bool, networkProfileDefault string) (SandboxVerdict, error) {
    verdict := SandboxVerdict{PermissionMode: "acceptEdits"}

    // Step 1 — probe nono
    nonoOut, nonoErr := exec.CommandContext(ctx, "nono", "--version").Output()
    if nonoErr != nil {
        if allowUnsandboxed {
            slog.Warn("RUNNING UNSANDBOXED — nono not found on PATH; permission_mode=acceptEdits")
            slog.Warn("Install: brew install nono | nix shell nixpkgs#nono | .deb from releases")
        } else {
            return verdict, fmt.Errorf(
                "nono is required but not found on PATH.\n" +
                "Install: brew install nono  |  nix shell nixpkgs#nono\n" +
                "Pass --allow-unsandboxed to proceed without the sandbox.")
        }
    } else {
        verdict.NonoVersion = strings.TrimSpace(string(nonoOut))

        // Step 2 — check Landlock ABI. Parse the version and compare >= 4 so
        // future ABIs (6+) still qualify for --network-profile.
        setupOut, _ := exec.CommandContext(ctx, "nono", "setup", "--check-only").Output()
        abiMatch := regexp.MustCompile(`landlock_abi:\s*(\d+)`).FindSubmatch(setupOut)
        abiOK := false
        if abiMatch != nil {
            if v, err := strconv.Atoi(string(abiMatch[1])); err == nil && v >= 4 {
                abiOK = true
            }
        }
        if abiOK {
            verdict.NetworkProfile = networkProfileDefault
            slog.Info("[sandbox] nono ready", "version", verdict.NonoVersion,
                "network_profile", verdict.NetworkProfile)
        } else {
            slog.Warn("[sandbox] Landlock ABI < 4 — dropping --network-profile")
        }
        verdict.PermissionMode = "bypassPermissions"
    }

    // Step 3 — confirm claude binary is reachable
    if strings.Contains(claudeBin, "/") {
        info, err := os.Stat(claudeBin)
        if err != nil {
            return verdict, fmt.Errorf("--claude-bin %q not reachable: %w", claudeBin, err)
        }
        if !info.Mode().IsRegular() {
            return verdict, fmt.Errorf("--claude-bin %q is not a regular file", claudeBin)
        }
    } else {
        out, err := exec.CommandContext(ctx, claudeBin, "--version").CombinedOutput()
        if err != nil {
            return verdict, fmt.Errorf(
                "--claude-bin %q not found on PATH: %w: %s",
                claudeBin, err, strings.TrimSpace(string(out)))
        }
    }
    slog.Info("pre-flight: claude binary reachable", "claude_bin", claudeBin)
    return verdict, nil
}

// wrapWithNono prepends nono run --silent to a claude argv when sandboxed.
// See references/nono-integration.md for the --add-dir ↔ --allow invariant.
func wrapWithNono(claudeArgs, allowDirs, readDirs []string, networkProfile string) []string {
    argv := []string{"nono", "run", "--silent"}
    if networkProfile != "" {
        argv = append(argv, "--network-profile", networkProfile)
    }
    for _, d := range allowDirs { argv = append(argv, "--allow", d) }
    for _, d := range readDirs  { argv = append(argv, "--read",  d) }
    argv = append(argv, "--")
    return append(argv, claudeArgs...)
}
```

## daemon.go — process group + SIGTERM/SIGKILL

```go
package main

import (
    "context"
    "fmt"
    "log/slog"
    "os"
    "os/exec"
    "path/filepath"
    "syscall"
    "time"
)

type daemonSpec struct {
    binaryPath string         // pre-built binary, NOT `go run`
    config     string
    socket     string
    logFile    string
    cargoLog   string         // misnomer for Go; rename to `buildLog`
}

type daemon struct {
    cmd     *exec.Cmd
    socket  string
}

func spawnDaemon(ctx context.Context, spec daemonSpec) (*daemon, error) {
    log := slog.Default()
    // Clear stale socket from prior iteration.
    _ = os.Remove(spec.socket)
    if dir := filepath.Dir(spec.logFile); dir != "" {
        _ = os.MkdirAll(dir, 0o755)
    }

    // Pipe daemon stdout/stderr to a per-iteration log file. Don't
    // /dev/null these — when the daemon dies before its own logger
    // initialises, this file is the only forensic record.
    buildLog, err := os.Create(spec.cargoLog)
    if err != nil {
        return nil, fmt.Errorf("create build log: %w", err)
    }

    cmd := exec.CommandContext(ctx, spec.binaryPath,
        "--config", spec.config,
        "--socket", spec.socket,
        "--log-file", spec.logFile,
    )
    cmd.Stdout = buildLog
    cmd.Stderr = buildLog
    // Setpgid: true puts the daemon in its own process group so
    // SIGTERM to -pid hits the whole tree.
    cmd.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}

    log.Info("spawning daemon",
        "socket", spec.socket, "log", spec.logFile,
        "build_log", spec.cargoLog)
    if err := cmd.Start(); err != nil {
        return nil, fmt.Errorf("start daemon: %w", err)
    }
    return &daemon{cmd: cmd, socket: spec.socket}, nil
}

func (d *daemon) shutdown(grace time.Duration) error {
    log := slog.Default()
    if d.cmd == nil || d.cmd.Process == nil {
        return nil
    }
    pgid, err := syscall.Getpgid(d.cmd.Process.Pid)
    if err == nil {
        log.Info("sending SIGTERM to daemon process group", "pgid", pgid)
        _ = syscall.Kill(-pgid, syscall.SIGTERM)
    } else {
        _ = d.cmd.Process.Signal(syscall.SIGTERM)
    }
    done := make(chan error, 1)
    go func() { done <- d.cmd.Wait() }()
    select {
    case <-done:
        _ = os.Remove(d.socket)
        return nil
    case <-time.After(grace):
        log.Warn("grace period expired, SIGKILL")
        _ = d.cmd.Process.Kill()
        <-done
        _ = os.Remove(d.socket)
        return nil
    }
}

func waitForSocket(ctx context.Context, socket string, budget time.Duration) error {
    log := slog.Default()
    start := time.Now()
    lastHeartbeat := start
    log.Info("waiting for daemon socket", "socket", socket, "budget_secs", budget.Seconds())
    for {
        if _, err := os.Stat(socket); err == nil {
            log.Info("daemon socket appeared", "elapsed_secs", time.Since(start).Seconds())
            return nil
        }
        if time.Since(start) >= budget {
            return fmt.Errorf("daemon socket %s did not appear within %v", socket, budget)
        }
        if time.Since(lastHeartbeat) >= 10*time.Second {
            log.Info("still waiting for daemon socket",
                "elapsed_secs", time.Since(start).Seconds(),
                "budget_secs", budget.Seconds())
            lastHeartbeat = time.Now()
        }
        select {
        case <-ctx.Done():
            return ctx.Err()
        case <-time.After(250 * time.Millisecond):
        }
    }
}
```

## client.go — gRPC drive surface

```go
package main

import (
    "context"
    "fmt"
    "net"
    "time"

    "google.golang.org/grpc"
    "google.golang.org/grpc/credentials/insecure"

    pb "github.com/<org>/<target-system>/proto"
)

func connect(socket string) (pb.<ServiceClient>, *grpc.ClientConn, error) {
    conn, err := grpc.NewClient(
        "unix:"+socket,
        grpc.WithTransportCredentials(insecure.NewCredentials()),
        grpc.WithContextDialer(func(ctx context.Context, addr string) (net.Conn, error) {
            return (&net.Dialer{}).DialContext(ctx, "unix", socket)
        }),
    )
    if err != nil {
        return nil, nil, fmt.Errorf("dial %s: %w", socket, err)
    }
    return pb.New<ServiceClient>(conn), conn, nil
}

func drive(ctx context.Context, client pb.<ServiceClient>, input string) (string, error) {
    ctx, cancel := context.WithTimeout(ctx, 120*time.Second)
    defer cancel()
    resp, err := client.<DriveMethod>(ctx, &pb.<DriveRequest>{Input: input})
    if err != nil {
        return "", fmt.Errorf("drive RPC: %w", err)
    }
    return resp.GetTaskId(), nil
}
```

For an HTTP service replace the gRPC client with `net/http`. The
drive function signature stays the same.

## reviewer.go — JSON-aware pre-filter

Go's structured loggers (zap, zerolog, slog with JSON handler) emit
one JSON object per line instead of human-readable text. The pre-filter
needs to parse `"level":"WARN"` from the JSON keys rather than relying
on `" WARN "` substring matching.

```go
package main

import (
    "encoding/json"
    "regexp"
    "strings"
)

// worthReviewing — pass 1 candidate filter.
// Handles both plain-text logs (slog text handler, fmt-style) AND
// JSON-structured logs (zap, zerolog, slog JSON handler).
func worthReviewing(line string) bool {
    // Plain-text path: tracing/text-handler-style severity tokens.
    if strings.Contains(line, " WARN ") ||
        strings.Contains(line, " ERROR ") ||
        strings.Contains(line, " FATAL ") {
        return true
    }
    // JSON path: parse the line, check `level` or `severity` fields.
    if strings.HasPrefix(strings.TrimSpace(line), "{") {
        var entry map[string]any
        if err := json.Unmarshal([]byte(line), &entry); err == nil {
            for _, key := range []string{"level", "severity", "lvl"} {
                if v, ok := entry[key].(string); ok {
                    switch strings.ToUpper(v) {
                    case "WARN", "WARNING", "ERROR", "FATAL", "PANIC", "DPANIC", "CRITICAL":
                        return true
                    }
                }
            }
        }
    }
    // Failure-token denylist — works for both formats.
    signals := []string{
        "panic:", "panicked", "stack trace", "goroutine ", "runtime error",
        "Failed to", "failed to", "Error:",
        "context deadline exceeded", "context canceled",
        "rejected", "dropped", "corrupt", "unreachable",
    }
    for _, s := range signals {
        if strings.Contains(line, s) {
            return true
        }
    }
    return false
}

// isInfoDebugCandidate — pass 2 candidate filter. Same dual-mode
// (plain text + JSON) handling.
func isInfoDebugCandidate(line string) bool {
    if worthReviewing(line) {
        return false
    }
    if strings.Contains(line, " INFO ") ||
        strings.Contains(line, " DEBUG ") ||
        strings.Contains(line, " TRACE ") {
        return true
    }
    if strings.HasPrefix(strings.TrimSpace(line), "{") {
        var entry map[string]any
        if err := json.Unmarshal([]byte(line), &entry); err == nil {
            for _, key := range []string{"level", "severity", "lvl"} {
                if v, ok := entry[key].(string); ok {
                    switch strings.ToUpper(v) {
                    case "INFO", "DEBUG", "TRACE":
                        return true
                    }
                }
            }
        }
    }
    return false
}
```

Go-specific failure tokens to add to `signals`:

- `panic:` — go runtime panic prefix
- `panicked` — same, alternate phrasing
- `goroutine ` — appears at the top of a goroutine stack trace
- `runtime error` — `panic: runtime error: nil pointer dereference` etc
- `context deadline exceeded` — Go's RPC-deadline equivalent
- `context canceled` — cooperative-cancel evidence (sometimes benign,
  sometimes a stuck-workflow symptom; let the LLM decide)

## Template fingerprinting (Go)

Same regex set as Rust, just Go syntax. Order matters: longer/specific
patterns first.

```go
var (
    timestampRe = regexp.MustCompile(`\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?`)
    uuidRe      = regexp.MustCompile(`\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b`)
    recordIDRe  = regexp.MustCompile(`\b([a-z_][a-z0-9_]*):([0-9a-z]{12,24})\b`)
    hexBlobRe   = regexp.MustCompile(`\b[0-9a-fA-F]{16,}\b`)
    numUnitRe   = regexp.MustCompile(`\b\d+[a-zA-Z]{1,4}\b`)
    numRe       = regexp.MustCompile(`\b\d+\b`)
)

func fingerprintTemplate(line string) string {
    s := timestampRe.ReplaceAllString(line, "<ts>")
    s = uuidRe.ReplaceAllString(s, "<uuid>")
    s = recordIDRe.ReplaceAllString(s, "$1:<id>")
    s = hexBlobRe.ReplaceAllString(s, "<hex>")
    s = numUnitRe.ReplaceAllString(s, "<n>")
    s = numRe.ReplaceAllString(s, "<n>")
    return s
}
```

## Adaptive cap on pass-1 candidates (Go)

Pass 1's pre-LLM cap protects against the runaway-pool failure mode
where one upstream defect emits tens of thousands of failure-shaped
lines in a single iteration (see
[runtime-gotchas.md § Runaway candidate pools](runtime-gotchas.md)). Mirrors pass 2's
template cap; uses the same `fingerprintTemplate` function so the
two passes agree on what counts as "the same line".

```go
// CapAndDedupFailures applies an adaptive cap to pass-1 input.
// When raw record count exceeds maxBatches*maxBatchLines, records
// are grouped by fingerprintTemplate, the top-N most-frequent
// exemplars are kept (sorted descending), and a parallel counts
// slice is returned so the prompt can carry occurrence count
// into the LLM's reasoning. Below the ceiling: records returned
// as-is, counts is nil — full fidelity, no behavior change.
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
        fp := fingerprintTemplate(r.Msg)
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

Thread the parallel `counts` slice into the prompt builder so
exemplars carry `"seen": N` in the per-line JSON. The pass-1 rubric
already has the paragraph telling the LLM how to weigh them — see
[runtime-reviewer-rubric.md § Adaptive cap on pass 1](runtime-reviewer-rubric.md).

```go
func buildFailurePrompt(records []Record, maxLineChars int, counts []int64) string {
    body := serialiseRecordsIndexed(records, maxLineChars, counts)
    header := "Here are the log records to judge — one JSON object per line, indexed.\n"
    if hasMultiSeen(counts) {
        header += "Lines tagged with \"seen\": N were deduplicated by fingerprint; treat them as N occurrences when weighing severity and setting count.\n"
    }
    return failureRubric + "\n" + header + body + verdictFormat
}

func serialiseRecordsIndexed(records []Record, maxLineChars int, counts []int64) string {
    var b strings.Builder
    for i, r := range records {
        rec := map[string]any{
            "idx":   i + 1,
            "level": r.Level,
            "msg":   truncate(r.Msg, maxLineChars),
        }
        if i < len(counts) && counts[i] > 1 {
            rec["seen"] = counts[i]
        }
        bs, _ := json.Marshal(rec)
        b.Write(bs)
        b.WriteByte('\n')
    }
    return b.String()
}
```

Defaults: `MaxBatchLines = 300`, `MaxBatches = 100`. Expose both as
CLI flags so an operator can dial the trade-off without recompiling.

For JSON-structured logs, the dynamic spans are JSON field values
(timestamps in `"ts":1716182400`, request IDs in `"req_id":"..."`).
Normalisation works the same way — the regexes match anywhere in the
string, and JSON object boundaries (`{`, `:`, `,`, `}`) survive
intact, so the resulting template still has enough JSON structure for
the LLM to recognise.

## reviewer.go — orchestrator + LLM call

The two-pass orchestration in Go is structurally identical to Rust.
Use `os/exec.CommandContext` with `context.WithTimeout` for the
`claude --print` call wrapped in `wrapWithNono` when sandboxed. See
`references/nono-integration.md` for the sandbox contract.

This excerpt continues `reviewer.go`; the dispatch below feeds stdin with
`bytes.NewReader`, so the file's import block needs `"bytes"`, `"context"`,
and `"os/exec"` alongside the imports already shown above (the full block is
in the `implementation-go.md` skeleton).

```go
func reviewBatch(
    ctx context.Context,
    claudeBin, permissionMode, networkProfile, model, systemPrompt string,
    lines []string,
) ([]verdict, error) {
    prompt := buildPrompt(systemPrompt, lines)

    envelope := map[string]any{
        "type": "user",
        "message": map[string]any{"role": "user", "content": prompt},
    }
    payload, err := json.Marshal(envelope)
    if err != nil {
        return nil, fmt.Errorf("marshal stream-json envelope: %w", err)
    }
    payload = append(payload, '\n')

    // Build claude argv then optionally wrap in nono.
    claudeArgs := []string{
        claudeBin,
        "--print",
        "--input-format", "stream-json",
        "--output-format", "stream-json",
        "--verbose",
        "--permission-mode", permissionMode,
        "--model", model,
    }
    allowDirs := []string{".bug-burndown"}
    readDirs  := []string{
        os.ExpandEnv("$HOME/.cargo/bin"),
        os.ExpandEnv("$HOME/.rustup"),
    }
    var finalArgs []string
    if permissionMode == "bypassPermissions" {
        finalArgs = wrapWithNono(claudeArgs, allowDirs, readDirs, networkProfile)
    } else {
        finalArgs = claudeArgs
    }

    cmd := exec.CommandContext(ctx, finalArgs[0], finalArgs[1:]...)
    cmd.Stdin = bytes.NewReader(payload)
    cmd.Env = append(os.Environ(), "CLAUDE_BWRAP_TTY=0") // force --pipe in any bwrap on PATH
    var stdout, stderr bytes.Buffer
    cmd.Stdout = &stdout
    cmd.Stderr = &stderr
    if err := cmd.Run(); err != nil {
        return nil, fmt.Errorf(
            "nono+claude reviewer batch: %w (stderr: %s)",
            err, strings.TrimSpace(stderr.String()))
    }
    finalText, err := extractStreamJSONResult(stdout.Bytes())
    if err != nil {
        return nil, fmt.Errorf("extract stream-json result: %w", err)
    }
    return parseVerdicts(string(finalText))
}
```

Rest of the architecture maps 1:1 from the Rust version. Use
`encoding/json` for verdict serde and `sync.Mutex` instead of
`tokio::sync::Mutex` for the burndown.log writer.

## action_audit.go — structural anti-rationalization pass (MANDATORY)

See SKILL.md § "Structural anti-rationalization pass" for the why.
The Go shape mirrors the Rust reference in
the reference harness's `action_audit` module — same three marker lists, same
verdict shape, same four mandatory test cases. The audit emits
`Verdict` values that merge into the same reject set the LLM passes
produce.

```go
package main

import (
    "fmt"
    "regexp"
    "sort"
    "strings"
)

var actionTokenRE = regexp.MustCompile(`\b(?:action|task_kind)=(?:"([^"]+)"|([A-Za-z_][A-Za-z0-9_\-]*))`)

// PROJECT-SPECIFIC: phrases the target system's error paths emit.
var hardFailureMarkers = []string{
    " WARN ", " ERROR ", " FATAL ",
    "Failed to", "failed to",
    "fetch failed", "refresh failed",
    "deferred to designed error path",
    "emitted error finding", "emitted no-op finding",
    "exhausted the retry budget",
    "DeadlineExceeded", "panicked",
    `_error"`, `_violation"`,
}

// PROJECT-SPECIFIC: phrases that prove the real upstream operation
// landed. NOT the workflow's self-stamped success flag.
var hardSuccessMarkers = []string{
    "refresh succeeded", "fetch succeeded",
    "catalogue refreshed",
    "persisted from upstream", "wrote upstream entries",
    "live upstream entries persisted",
    "upstream returned valid",
}

// PROJECT-SPECIFIC but the vocabulary is nearly universal.
var fallbackMarkers = []string{
    "cache-fallback", "seed-fallback", "seed_fallback",
    "from cached entries", "served from cache",
    "last-good cache", "bundled seed",
    "build-time seed", "build-time snapshot",
    "designed fallback", "designed error path",
    "no-op finding",
}

type actionEvidence struct {
    hardFailures           uint32
    hardSuccesses          uint32
    representativeFailure  string
}

func containsAny(s string, needles []string) bool {
    for _, n := range needles {
        if strings.Contains(s, n) {
            return true
        }
    }
    return false
}

// Audit walks the captured log lines and synthesizes Verdicts for
// actions that never produced an upstream success. Verdicts use the
// same Verdict shape the LLM reviewer emits.
func Audit(lines []string) []Verdict {
    byAction := map[string]*actionEvidence{}
    for _, line := range lines {
        for _, m := range actionTokenRE.FindAllStringSubmatch(line, -1) {
            action := m[1]
            if action == "" {
                action = m[2]
            }
            if action == "" {
                continue
            }
            ev := byAction[action]
            if ev == nil {
                ev = &actionEvidence{}
                byAction[action] = ev
            }
            isFailure := containsAny(line, hardFailureMarkers)
            hasSuccess := containsAny(line, hardSuccessMarkers)
            hasFallback := containsAny(line, fallbackMarkers)
            if isFailure {
                ev.hardFailures++
                if ev.representativeFailure == "" {
                    cut := line
                    if len(cut) > 500 {
                        cut = cut[:500] + " …<truncated>"
                    }
                    ev.representativeFailure = cut
                }
            }
            if hasSuccess && !hasFallback && !isFailure {
                ev.hardSuccesses++
            }
        }
    }
    var keys []string
    for k := range byAction {
        keys = append(keys, k)
    }
    sort.Strings(keys)
    var verdicts []Verdict
    for _, action := range keys {
        ev := byAction[action]
        if ev.hardFailures == 0 || ev.hardSuccesses > 0 {
            continue
        }
        verdicts = append(verdicts, Verdict{
            Fingerprint: fmt.Sprintf("audit-action-only-failures-%s", action),
            Verdict:     "reject",
            Kind:        "cascade-failure",
            Severity:    "critical",
            Reason: fmt.Sprintf(
                "structural audit: action=`%s` has %d hard-failure line(s) and 0 "+
                    "upstream-success line(s) across the iteration. Fallback / cached / "+
                    "seed markers do not count as success — the real operation never "+
                    "landed. Fix the upstream failure; do not rationalize it with "+
                    "`designed error path` framing.",
                action, ev.hardFailures,
            ),
            Count: ev.hardFailures,
            Line:  ev.representativeFailure,
        })
    }
    return verdicts
}
```

Wire it into the outer loop **between** the LLM review and the
burndown bridge, mirroring the Rust pattern:

```go
verdicts, err := reviewer.Review(ctx, ...)
if err != nil { return err }
verdicts = append(verdicts, Audit(lines)...)
rejects := filterRejects(verdicts)
```

**Mandatory unit tests** (Go-named): `TestAudit_FailureOnlyRunEmitsSyntheticReject`,
`TestAudit_CacheFallbackSuccessDoesNotClearFailure`,
`TestAudit_GenuineUpstreamSuccessClearsFailure`,
`TestAudit_NonActionLinesIgnored`. Mirror the four required cases
from the Rust reference; the inputs are identical (log lines are
language-agnostic).

### Whole-log oscillation pass (MANDATORY second structural pass)

The `Audit` above tallies failures **per operation**. It does not catch
divergence that lives **between** lines across the whole run — where every
single line is a benign INFO and the bug is a key whose state oscillates
(revisits a value it already left). Add a second whole-log pass and wire it in
the same place (between LLM review and burndown). Canonical instance: an
advisory's identity migrating `CVE → vendor-alias → CVE → alias` repeatedly
because two ingest paths disagree on the canonical id.

```go
// AuditOscillation correlates a structured key across the ENTIRE record set and
// flags any key whose state sequence revisits a value it had already left
// (A→B→A). One-way convergence (A→B, never back) is never flagged. Consecutive
// identical re-emits collapse (idempotent, not oscillation).
func AuditOscillation(records []Record) []Verdict {
    type churn struct {
        seq      []string
        seen     map[string]struct{}
        revisits int
        first    string
    }
    by := map[string]*churn{}
    var order []string
    for _, r := range records {
        if !isMigrationLine(strings.ToLower(r.Msg)) { // project-specific marker(s)
            continue
        }
        key, state := correlate(r) // e.g. (cve attr, alias-it-migrated-to; "" sentinel for "back to base")
        if key == "" || state == "" {
            continue
        }
        c := by[key]
        if c == nil {
            c = &churn{seen: map[string]struct{}{}}
            by[key] = c
            order = append(order, key)
        }
        if n := len(c.seq); n > 0 && c.seq[n-1] == state {
            continue // consecutive duplicate snapshot — not a revisit
        }
        if _, ok := c.seen[state]; ok {
            c.revisits++ // reappeared after we left it → oscillation
        }
        c.seq = append(c.seq, state)
        c.seen[state] = struct{}{}
        if c.first == "" {
            c.first = trunc(r.Level+" "+r.Msg, 480)
        }
    }
    sort.Strings(order)
    var verdicts []Verdict
    for _, key := range order {
        c := by[key]
        if c.revisits < 1 { // minOscillations
            continue
        }
        verdicts = append(verdicts, Verdict{
            Fingerprint: "audit-oscillation-" + key, // per-key stable → burndown dedups
            Verdict:     "reject",
            Kind:        "silent-divergence",
            Severity:    "high",
            Reason: fmt.Sprintf("%s oscillated across the run (sequence: %s). Two paths "+
                "disagree on the canonical id; each pass undoes the other's migration — "+
                "wasted re-writes and a non-converging identity. Read the FULL iteration "+
                "log for %s, find the competing sites, and make the decision deterministic "+
                "and idempotent.", key, strings.Join(c.seq, " → "), key),
            Count: c.revisits,
            Line:  c.first,
        })
    }
    return verdicts
}
```

Wire it: `verdicts = append(verdicts, AuditOscillation(records)...)`. The
burndown bridge prompt must, for these `silent-divergence` findings, point the
agent at the **complete iteration log** (not the exemplar) and ask for a
structural, idempotent fix with a **re-ingest-twice** regression test.

**Mandatory unit tests** (by name): `TestAuditOscillation_BackAndForthIsFlagged`,
`TestAuditOscillation_OneWayConvergenceNotFlagged`,
`TestAuditOscillation_DuplicateSnapshotsIgnored`,
`TestAuditOscillation_DistinctCVEsNotConflated`,
`TestAuditOscillation_NoCVEIgnored` (correlation key absent → ignored, no panic).
This is the 2026-06-17 alias-oscillation incident.

## burndown.go — log tee and burndown bridge

`bufio.Scanner` on each stream, write each line to the log file AND
emit via `slog`. Two goroutines run concurrently (`sync.WaitGroup`
for join). See `references/nono-integration.md` for the sandbox contract.

```go
func runBurndown(
    ctx context.Context,
    claudeBin, permissionMode, networkProfile, model, sessionID string,
    logPath string,
) error {
    arg := fmt.Sprintf("/bug-burndown resume:%s", sessionID)
    slog.Info("spawning /bug-burndown", "session", sessionID, "log", logPath)

    if err := os.MkdirAll(filepath.Dir(logPath), 0o755); err != nil {
        return fmt.Errorf("mkdir burndown log dir: %w", err)
    }
    logFile, err := os.Create(logPath)
    if err != nil { return fmt.Errorf("create burndown log: %w", err) }

    envelope, _ := json.Marshal(map[string]any{
        "type": "user",
        "message": map[string]any{"role": "user", "content": arg},
    })
    payload := append(envelope, '\n')

    claudeArgs := []string{
        claudeBin,
        "--print", "--permission-mode", permissionMode,
        "--model", model,
        "--input-format", "stream-json",
        "--output-format", "stream-json", "--verbose",
    }
    // Allow project CWD (burndown writes code fixes) + shared dotfile dirs.
    allowDirs := []string{".", ".bug-burndown", ".test-effectiveness"}
    readDirs  := []string{
        os.ExpandEnv("$HOME/.cargo/bin"),
        os.ExpandEnv("$HOME/.rustup"),
    }
    var finalArgs []string
    if permissionMode == "bypassPermissions" {
        finalArgs = wrapWithNono(claudeArgs, allowDirs, readDirs, networkProfile)
    } else {
        finalArgs = claudeArgs
    }

    cmd := exec.CommandContext(ctx, finalArgs[0], finalArgs[1:]...)
    cmd.Stdin = bytes.NewReader(payload)
    // Env-var contract with the bug-burndown Stop hook; nono preserves env.
    cmd.Env = append(os.Environ(),
        "CLAUDE_BWRAP_TTY=0",
        "BUG_BURNDOWN_HARNESS_DRIVEN=1",
        "BUG_BURNDOWN_HARNESS_SESSION_ID="+sessionID,
    )
    cmd.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}
    stdout, err := cmd.StdoutPipe()
    if err != nil { logFile.Close(); return err }
    if err := cmd.Start(); err != nil { logFile.Close(); return err }

    var wg sync.WaitGroup
    wg.Add(1)
    go func() {
        defer wg.Done()
        scanner := bufio.NewScanner(stdout)
        for scanner.Scan() {
            line := scanner.Text()
            fmt.Fprintln(logFile, line) // tee BEFORE filtering
            surfaceStreamEvent(line)
        }
        logFile.Close()
    }()

    wg.Wait()
    return cmd.Wait()
}
```

## scenarios.go — panic-safe wrapper around Scenario.Run

Every per-scenario call goes through this wrapper. A scenario that
panics is itself a bug worth filing — the wrapper turns the panic
into a returned error with the full stack, so the outer loop logs
it, records an outcome, and moves on. See gotchas.md § "Scenario
panics must not kill the harness" for full rationale.

```go
import (
    "context"
    "fmt"
    "log/slog"
    "runtime"
)

type ScenarioPanicError struct {
    Scenario string
    Value    any
    Stack    string
}

func (e *ScenarioPanicError) Error() string {
    return fmt.Sprintf("scenario %q panicked: %v", e.Scenario, e.Value)
}

func runScenarioSafely(ctx context.Context, s Scenario, env *Env) (err error) {
    defer func() {
        if r := recover(); r != nil {
            stack := captureStack()
            slog.Error("scenario panicked — recovered",
                "phase", string(s.Phase),
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

Outer loop calls `runScenarioSafely` instead of `s.Run(ctx, env)`
directly. Everything else stays the same: the returned error (real
or panic-wrapped) flows into the Outcome, then into the captured
log, then into the reviewer's pass-1 input. The reviewer's rubric
already lists `kind: panic` as a high-severity verdict, so no
rubric change is needed.

## Workspace integration

Add the harness binary to your `go.work` if you're using a workspace:

```go
go 1.22

use (
    ./<target-system>
    ./<binary-name>
)
```

And add `.harness/` to `.gitignore` — same per-machine noise as the
Rust variant.

## What stays the same

- The reviewer rubric file ([runtime-reviewer-rubric.md](runtime-reviewer-rubric.md))
  is unchanged. Rubrics judge log lines, not source code.
- The gotchas file ([runtime-gotchas.md](runtime-gotchas.md)) applies to both
  languages. Every fix forensics there is implementation-language
  independent.
- The bug-burndown session format (`.bug-burndown/<id>/` tree) is
  unchanged — the skill on the other side reads it identically.
- The `harness.suspicious` / `harness.rejects` / `burndown.stdout` /
  `burndown.stderr` log targets are convention-based, not
  language-specific. Use the same target strings in `slog.With` to
  match the Rust filtering behaviour.

## What changes per-language

- Build invocation (`go build` vs `cargo build`)
- Drive client (gRPC client vs tarpc client)
- Subprocess lifecycle (`os/exec` vs `tokio::process`)
- Signal handling (`syscall.Kill(-pgid, SIGTERM)` vs `nix::sys::signal::kill`)
- Pre-filter JSON-awareness (Go's structured loggers default to JSON;
  Rust's `tracing` defaults to text)
- Concurrency primitives (`goroutine + channel` vs `tokio::spawn`)
- Regex syntax (Go's RE2 vs Rust's regex — patterns are identical for
  the fingerprinter though, both accept the same syntax for our needs)
