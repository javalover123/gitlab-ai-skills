# Interview flow

Three `AskUserQuestion` calls dispatch the harness scaffold. Run them
in order, skipping any question whose answer is already supplied as an
argument.

## Question 1 — Harness type

Header: `"Harness type"` | `multiSelect: false`

```
Q: What kind of harness do you want to build?

  - Runtime quality harness — spawns the daemon, watches logs, judges with
    an adversarial LLM reviewer, loops until clean. Use when you have a
    long-running service and want it driven and audited continuously.

  - Implementation harness — drives the project from documentation through
    code through verification. Orchestrates iteratotron + bug-burndown via
    in-session agents. Use when you're building a project to ship-ready.

  - Both — scaffolds both crates side-by-side. The implementation harness
    drives the project to a working state; the runtime harness keeps
    watching it once it's running.

  - Bugfix-bridge only — minimal scaffold that dispatches to /bug-burndown
    when triggered by an external signal (CI log, test failure, etc.). Use
    when the project already has its own driver.
```

## Question 2 — Orchestration

Header: `"Orchestration"` | `multiSelect: true`

```
Q: Which orchestration operations should the generated harness invoke?

  - iteratotron in genesis mode — full bootstrap (constitution check,
    harness vector composition, doc creation, SLSA-attestable done
    predicate). Use when the project needs to be driven from documentation.

  - iteratotron in sweep mode — completion-readiness burndown on an existing
    documented project. Use when docs are current and you're closing gaps.

  - bug-burndown — finding closure for defects surfaced by the harness
    (rejects from the runtime reviewer, or stop-bias findings from the
    implementation pipeline). Use whenever you want the harness to fix what
    it finds, not just report.

  - None — generate scaffolds without orchestration bridges. The harness
    produces findings but doesn't dispatch any closure agents.
```

Multi-select is allowed. Runtime harnesses typically pair
`runtime + bug-burndown`. Greenfield projects typically pair
`implementation + iteratotron-genesis + bug-burndown`.

## Question 3 — Language

Header: `"Language"` | `multiSelect: false`

```
Q: What language should the harness be written in?

  - Rust — canonical for both harness types. Strong ecosystem coverage
    (tokio for runtime, crane for nix integration, full Tier-3 support
    via shuttle/madsim/loom).

  - Go — first-class alternative. Native goroutines, rapid+gremlins
    Tier-1, godog for Tier-2, native fuzz for Tier-3.

  - Python — implementation harnesses via opencode session agents. Runtime
    harnesses aren't supported — pick Rust or Go for runtime.

  - Ruby — implementation harness only. Mutant for mutation testing,
    Brakeman for SAST.

  - Nix — implementation harness wraps the project's primary language
    via crane / buildRustPackage / nix2container.
```

## Disallowed combinations

| Type | Language | Result |
|---|---|---|
| `runtime` | `python`, `ruby`, `nix` | Reject; re-prompt for language |
| `both` | `python`, `ruby`, `nix` | Accept implementation; warn runtime unavailable; reduce type to `implementation` |
| `implementation` | any | Accept |
| `bugfix-bridge` | any | Accept |
