# Go harness builder

Genesis-side orchestration crate for Go projects. Same shape as the
Rust builder (`references/implementation-rust.md`) — module names map
1:1 — but using Go's `os/exec` + goroutines instead of tokio.

## Module layout

```
<project>-genesis/
├── go.mod
├── cmd/
│   └── genesis/
│       └── main.go
└── internal/
    ├── state/state.go               # .iteratotron/state.json IO + atomic-rename
    ├── bootstrap/bootstrap.go       # Phase 0: doc detection + harness vector
    ├── gapanalysis/gapanalysis.go   # Phase 1: four-list inventory
    ├── plan/plan.go                 # Phase 2: vertical-slice ordering
    ├── innerloop/innerloop.go       # Phase 3: dispatcher state machine
    ├── constitution/check.go        # gates each iteratotron dispatch
    ├── streaming/streaming.go       # claude -p stream-json consumer
    ├── advreview/advreview.go       # Phase 7 cold-context reviewer
    ├── harness/runner.go            # Tier-1/2/3 invocation per language
    │                                #  ↳ flake.nix present ⇒ run every gate via
    │                                #    `nix develop --command bash -lc '…'`
    │                                #    (devShell holds gcc/cgo, golangci-lint,
    │                                #    govulncheck). See implementation-nix.md
    │                                #    § "Gate-execution contract".
    ├── done/predicate.go            # Phase 4 evaluator
    └── slsa/attest.go               # in-toto + cosign attestation
```

## go.mod essentials

```go
module <project>-genesis

go 1.24

require (
    github.com/spf13/cobra v1.10.0          // CLI
    github.com/rs/zerolog v1.34.0           // structured logging
    github.com/google/uuid v1.6.0
    golang.org/x/sync v0.10.0
)
```

## cmd/genesis/main.go

```go
package main

import (
    "context"
    "os"
    "os/signal"
    "syscall"
    "time"

    "github.com/rs/zerolog/log"
    "github.com/spf13/cobra"

    "<project>-genesis/internal/bootstrap"
    "<project>-genesis/internal/done"
    "<project>-genesis/internal/gapanalysis"
    "<project>-genesis/internal/innerloop"
    "<project>-genesis/internal/plan"
    "<project>-genesis/internal/state"
)

type Options struct {
    Parallel  int
    Inner     int
    TimeSecs  int
    BudgetUSD float64
    Resume    string
    DryRun    bool
}

func main() {
    var opts Options
    root := &cobra.Command{
        Use:   "genesis",
        Short: "whole-project genesis orchestrator",
        RunE: func(cmd *cobra.Command, args []string) error {
            return runGenesis(cmd.Context(), &opts)
        },
    }
    root.PersistentFlags().IntVar(&opts.Parallel, "parallel", 2, "outer iteratotron parallelism")
    root.PersistentFlags().IntVar(&opts.Inner, "inner", 3, "inner iterate parallelism per iteratotron session")
	// 7-day default: a converging build-system / E2E run is measured in days.
	// Size to the workload (see SKILL.md "Size the deadlines to the workload");
	// drop to 28800 (8h) only for a pure fast-feedback project.
	root.PersistentFlags().IntVar(&opts.TimeSecs, "time", 604800, "global wall-clock budget in seconds (default 7 days; size to the workload)")
    root.PersistentFlags().Float64Var(&opts.BudgetUSD, "budget-usd", 100, "global cost budget in USD")
    root.PersistentFlags().StringVar(&opts.Resume, "resume", "", "resume a prior session by ID")
    root.PersistentFlags().BoolVar(&opts.DryRun, "dry-run", false, "emit plan and exit")

    ctx, cancel := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
    defer cancel()
    if err := root.ExecuteContext(ctx); err != nil {
        log.Fatal().Err(err).Send()
    }
}

func runGenesis(ctx context.Context, opts *Options) error {
    var s *state.SessionState
    var err error
    if opts.Resume != "" {
        s, err = state.Resume(opts.Resume)
    } else {
        s, err = state.NewSession(opts.Parallel, opts.Inner, time.Duration(opts.TimeSecs)*time.Second, opts.BudgetUSD)
    }
    if err != nil { return err }

    if opts.Resume == "" {
        if err := bootstrap.Run(ctx, s); err != nil { return err }
        if err := gapanalysis.Run(ctx, s); err != nil { return err }
        if err := plan.Run(ctx, s); err != nil { return err }
    }

    if opts.DryRun {
        log.Info().Msg("dry run — plan written, no dispatch")
        return nil
    }

    if err := innerloop.Run(ctx, s); err != nil { return err }
    return done.EvaluateAndAttest(ctx, s)
}
```

## internal/streaming/streaming.go

```go
package streaming

import (
    "bufio"
    "context"
    "encoding/json"
    "fmt"
    "io"
    "os"
    "os/exec"
    "path/filepath"
    "strings"
    "sync"
    "syscall"
    "time"

    "github.com/rs/zerolog/log"
)

type Event struct {
    Type          string          `json:"type"`
    Subtype       string          `json:"subtype,omitempty"`
    Message       json.RawMessage `json:"message,omitempty"`
    Event         json.RawMessage `json:"event,omitempty"`
    TotalCostUSD  float64         `json:"total_cost_usd,omitempty"`
}

type SubagentHandle struct {
    Cmd        *exec.Cmd
    LogPath    string
    ResultSeen chan struct{}
    finishOnce sync.Once
}

// wrapWithNono prepends nono run --silent to a claude argv, deriving
// --allow entries from the same allowDirs that become --add-dir entries.
// Returns the original argv unchanged when permissionMode != bypassPermissions.
// See references/nono-integration.md for the --add-dir ↔ --allow invariant.
func wrapWithNono(claudeArgs, allowDirs, readDirs []string, networkProfile string) []string {
    argv := []string{"nono", "run", "--silent"}
    if networkProfile != "" {
        argv = append(argv, "--network-profile", networkProfile)
    }
    for _, d := range allowDirs {
        argv = append(argv, "--allow", d)
    }
    for _, d := range readDirs {
        argv = append(argv, "--read", d)
    }
    argv = append(argv, "--")
    return append(argv, claudeArgs...)
}

func Dispatch(ctx context.Context, prompt, logDir, model string, addDirs, disallowed []string, maxTurns int, budgetUSD float64, permissionMode, networkProfile string) (*SubagentHandle, error) {
    if err := os.MkdirAll(logDir, 0o755); err != nil { return nil, err }
    logPath := filepath.Join(logDir, fmt.Sprintf("%d.jsonl", time.Now().Unix()))
    logFile, err := os.Create(logPath)
    if err != nil { return nil, err }

    // Build the stream-json stdin envelope.
    envelope := map[string]any{
        "type": "user",
        "message": map[string]any{"role": "user", "content": prompt},
    }
    payload, err := json.Marshal(envelope)
    if err != nil { logFile.Close(); return nil, err }
    payload = append(payload, '\n')

    // Build claude argv. These become the tail after nono's "--" separator
    // when sandboxed, or the direct exec argv when unsandboxed.
    claudeArgs := []string{
        "claude",
        "--print",
        "--input-format", "stream-json",
        "--output-format", "stream-json",
        "--verbose",
        "--include-partial-messages",
        "--permission-mode", permissionMode,
        "--model", model,
        "--max-turns", fmt.Sprintf("%d", maxTurns),
        "--max-budget-usd", fmt.Sprintf("%.2f", budgetUSD),
    }
    for _, d := range addDirs { claudeArgs = append(claudeArgs, "--add-dir", d) }
    for _, t := range disallowed { claudeArgs = append(claudeArgs, "--disallowed-tools", t) }

    // Derive --allow from the same source as --add-dir plus shared dotfile dirs.
    // The --add-dir ↔ --allow invariant: nono-integration.md.
    allowDirs := append(append([]string{}, addDirs...),
        ".bug-burndown", ".test-effectiveness", ".iteratotron")
    readDirs := []string{
        os.ExpandEnv("$HOME/.cargo/bin"),
        os.ExpandEnv("$HOME/.rustup"),
    }

    var finalArgs []string
    if permissionMode == "bypassPermissions" {
        finalArgs = wrapWithNono(claudeArgs, allowDirs, readDirs, networkProfile)
    } else {
        finalArgs = claudeArgs
    }

    // nono is the direct child; Setpgid: true means syscall.Kill(-pid,…)
    // covers the whole group (nono + claude). nono forwards signals to claude.
    cmd := exec.CommandContext(ctx, finalArgs[0], finalArgs[1:]...)
    cmd.Stdin = bytes.NewReader(payload)
    cmd.Env = append(os.Environ(), "CLAUDE_BWRAP_TTY=0") // force --pipe in any bwrap wrapper on PATH
    cmd.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}

    stdout, err := cmd.StdoutPipe()
    if err != nil { logFile.Close(); return nil, err }
    cmd.Stderr = os.Stderr

    handle := &SubagentHandle{
        Cmd:        cmd,
        LogPath:    logPath,
        ResultSeen: make(chan struct{}, 1),
    }

    if err := cmd.Start(); err != nil { logFile.Close(); return nil, err }

    go consumeStdout(stdout, logFile, handle)
    return handle, nil
}

func consumeStdout(stdout io.ReadCloser, logFile *os.File, handle *SubagentHandle) {
    defer logFile.Close()
    scanner := bufio.NewScanner(stdout)
    // raise buffer cap so a large content_block_delta doesn't blow the default 64K limit
    scanner.Buffer(make([]byte, 0, 64*1024), 4*1024*1024)
    for scanner.Scan() {
        line := scanner.Bytes()
        // tee raw line to disk BEFORE filtering
        logFile.Write(line)
        logFile.Write([]byte{'\n'})
        if strings.Contains(string(line), `"type":"result"`) {
            handle.finishOnce.Do(func() { close(handle.ResultSeen) })
        }
    }
    if err := scanner.Err(); err != nil {
        log.Warn().Err(err).Msg("streaming scanner error")
    }
}

// WaitWithWatchdog handles the stream-json shutdown stall (runtime-gotchas.md
// § "Bridge subprocess hangs after stream-json result event"). SIGTERM goes to
// the nono PID and is forwarded to claude by nono's signal proxy.
func (h *SubagentHandle) WaitWithWatchdog(ctx context.Context, graceSecs int) error {
    done := make(chan error, 1)
    go func() { done <- h.Cmd.Wait() }()

    select {
    case err := <-done:
        return err
    case <-h.ResultSeen:
        // got the result event — give it `graceSecs` then escalate
        select {
        case err := <-done:
            return err
        case <-time.After(time.Duration(graceSecs) * time.Second):
            log.Warn().Str("log", h.LogPath).Msg("bridge subprocess hung after result event; SIGTERM")
            syscall.Kill(-h.Cmd.Process.Pid, syscall.SIGTERM)
            select {
            case err := <-done:
                return err
            case <-time.After(10 * time.Second):
                log.Warn().Str("log", h.LogPath).Msg("SIGTERM ignored; SIGKILL")
                syscall.Kill(-h.Cmd.Process.Pid, syscall.SIGKILL)
                return <-done
            }
        }
    }
}
```

## internal/innerloop/innerloop.go (pseudocode)

```go
func Run(ctx context.Context, s *state.SessionState) error {
    for !s.IsTerminal() && !s.BudgetExhausted() {
        dispatchable := s.SelectDispatchable(s.Budgets.ParallelOuter)
        var wg sync.WaitGroup
        for _, scope := range dispatchable {
            check, err := constitution.Run(ctx, scope)
            if err != nil { return err }
            if !check.Pass {
                s.ParkForHuman(scope, check.Violations)
                continue
            }
            worktree, err := s.CreateWorktree(scope)
            if err != nil { return err }
            prompt := renderIteratotronPrompt(scope, s)
            handle, err := streaming.Dispatch(ctx, prompt, worktree.LogDir, "haiku",
                s.AddDirs(), []string{"WebSearch"}, 80, 20.0)
            if err != nil { return err }
            wg.Add(1)
            go func(sc *state.Scope, wt *state.Worktree, h *streaming.SubagentHandle) {
                defer wg.Done()
                h.WaitWithWatchdog(ctx, 30)
                verdict := advreview.Run(ctx, sc, wt)
                switch verdict.Kind {
                case advreview.Approved: s.MergeWorktree(sc, wt)
                case advreview.Insufficient: s.RequeueScope(sc, verdict.Lessons)
                case advreview.NeedsHuman: s.ParkForHuman(sc, verdict.Reason)
                }
                harness.RunApplicableTiers(ctx, sc, s.HarnessVector)
            }(scope, worktree, handle)
        }
        wg.Wait()
        if len(s.BugQueue) > 0 { innerloop.DispatchBurndown(ctx, s) }
        s.Fsync()
    }
    return nil
}
```

## Composing with the runtime harness Go variant

Closed-loop-harness's Go harness lives at `cmd/harness/`. This genesis
harness lives at `cmd/genesis/`. They share no code but consume the
same `.bug-burndown/<session>/` and `.test-effectiveness/baseline.json`
formats. Both run from the project root.

---

## internal/harness/opencode_server.go — opencode server driver (opencode-server backend)

Generated alongside `internal/streaming/streaming.go` when `agent_host:
opencode-server` is selected. Full skeleton with all HTTP+SSE contracts, lifecycle
state machine, and the `RunEventLoop` / `Shutdown` implementations is in
`references/opencode-server-integration.md §6.2`. Uses only Go stdlib (`net/http`,
`bufio`, `encoding/json`, `syscall`) — no new `go.mod` deps.

Public surface (from the §6.2 skeleton):

```go
type Event struct { Kind string; Data map[string]any }

type ServerHandle struct { /* cmd, BaseURL, Password, hc */ }

func LaunchServer(ctx context.Context, projectRoot string, port int, password string) (*ServerHandle, error)
func (h *ServerHandle) CreateSession(ctx context.Context, title string) (string, error)
func (h *ServerHandle) PromptAsync(ctx context.Context, session, agent, text string) error
func (h *ServerHandle) RespondPermission(ctx context.Context, session, perm, decision string) error
func (h *ServerHandle) TodoEmpty(ctx context.Context, session string) (bool, error)
func (h *ServerHandle) Abort(ctx context.Context, session string)
func (h *ServerHandle) RunEventLoop(ctx context.Context, out chan<- Event) error
func (h *ServerHandle) Shutdown(grace time.Duration) error
```

## Agent host switch

Add to `internal/streaming/streaming.go`:

```go
type AgentHost string

const (
    AgentHostClaudeStream   AgentHost = "claude-stream"   // default
    AgentHostOpencodeServer AgentHost = "opencode-server"
)
```

Add `AgentHost AgentHost` and `Server *harness.ServerHandle` to `SessionState`.
Replace the `streaming.Dispatch(...)` call site in `internal/innerloop/innerloop.go`:

```go
switch s.AgentHost {
case AgentHostClaudeStream, "":
    // existing path — unchanged
    handle, err := streaming.Dispatch(ctx, prompt, worktree.LogDir,
        "haiku", s.AddDirs(), []string{"WebSearch"}, 80, 20.0,
        permMode, networkProfile)
    if err != nil { return err }
    handle.WaitWithWatchdog(ctx, 30)

case AgentHostOpencodeServer:
    sessionID, err := s.Server.CreateSession(ctx, scope.Title)
    if err != nil { return err }
    if err := s.Server.PromptAsync(ctx, sessionID, "build", prompt); err != nil {
        return err
    }
    if err := waitSessionComplete(ctx, s.Server, sessionID); err != nil {
        return err
    }
}
```

Three-way completion detection (required by `opencode-server-integration.md §5`):

```go
func waitSessionComplete(ctx context.Context, srv *harness.ServerHandle, sessionID string) error {
    events := make(chan harness.Event, 64)
    ctx2, cancel := context.WithCancel(ctx)
    defer cancel()
    go srv.RunEventLoop(ctx2, events) //nolint:errcheck — checked via ctx cancellation

    msgDone, idle := false, false
    for {
        select {
        case ev := <-events:
            switch ev.Kind {
            case "message.updated":
                if info, _ := ev.Data["info"].(map[string]any); info != nil {
                    if info["sessionID"] == sessionID {
                        t, _ := info["time"].(map[string]any)
                        if t["completed"] != nil && info["error"] == nil {
                            msgDone = true
                        }
                    }
                }
            case "session.idle":
                if ev.Data["sessionID"] == sessionID { idle = true }
            case "permission.updated":
                // match allowlist → RespondPermission("always" or "reject")
                // append every decision to the run manifest audit log
            case "session.error":
                return fmt.Errorf("session error: %v", ev.Data["error"])
            }
            if msgDone && idle {
                empty, _ := srv.TodoEmpty(ctx, sessionID)
                if empty { cancel(); return nil }
            }
        case <-ctx.Done():
            return ctx.Err()
        }
    }
}
```

## cmd/genesis/main.go — server lifecycle (agent_host: opencode-server)

Add to `Options`:

```go
AgentHost    string // "claude-stream" (default) | "opencode-server"
OpencodePort int    // port for opencode serve; default 7654
```

Add flags in `main()`:

```go
root.PersistentFlags().StringVar(&opts.AgentHost, "agent-host", "claude-stream",
    "agent host backend: claude-stream | opencode-server")
root.PersistentFlags().IntVar(&opts.OpencodePort, "opencode-port", 7654,
    "port for opencode serve (opencode-server backend only)")
```

Lifecycle wiring in `runGenesis()`, after worktree resolution:

```go
if opts.AgentHost == "opencode-server" {
    password := os.Getenv("OPENCODE_SERVER_PASSWORD")
    if password == "" { password = uuid.New().String() }
    s.Server, err = harness.LaunchServer(ctx, projectRoot, opts.OpencodePort, password)
    if err != nil { return fmt.Errorf("launch opencode server: %w", err) }
    // DISPOSE on every exit path — Go's defer fires on all return paths
    defer s.Server.Shutdown(10 * time.Second) //nolint:errcheck
}
s.AgentHost = AgentHost(opts.AgentHost)

if err := innerloop.Run(ctx, s); err != nil { return err }
return done.EvaluateAndAttest(ctx, s)
```

**Python and Nix harnesses** do not gain the `opencode-server` backend in this
release. Document in the generated README; note as a follow-up.
