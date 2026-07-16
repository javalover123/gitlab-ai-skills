---
name: mcp-review
description: "Reviews and improves existing MCP server implementations for protocol compliance, tool quality, Rust best practices, security, and testing coverage. Lists available MCP servers for selection when none specified. Use when reviewing an MCP server, auditing MCP tool quality, checking protocol compliance, improving MCP server code, or when the user mentions MCP review, MCP audit, or MCP server quality."
version: 1.0.0
license: MIT
category: Development Workflow
compatibility: opencode
metadata:
  audience: developers
  workflow: rust
---

# MCP Server Reviewer

Review and improve MCP server implementations against protocol standards, Rust
best practices, and production quality. Pairs with the `mcp-creator` skill (same
reference set).

## When to use

- Reviewing an existing MCP server for quality and protocol compliance.
- Auditing MCP tool descriptions, input schemas, and error handling.
- Checking Rust patterns in async MCP handlers (state, concurrency, logging).
- Assessing an MCP server's security posture and test coverage before deploying.

## Workflow

### Phase 0 — Server selection

If not told which server to review, discover candidates: `grep -rl "rmcp"
--include="Cargo.toml" .` and look for MCP config (`.mcp.json`,
`opencode.json` `mcp`, `mcp-config.*`). Present the options and let the user
pick.

### Phase 1 — Scope

Clarify: full review or specific areas (protocol / tools / security / testing);
priority concerns; whether breaking changes are acceptable; deployment context
(local, production, distributed).

### Phase 2 — Automated analysis

Run these first and report the results before manual review — surface quick wins
early:

```bash
cargo build 2>&1
cargo clippy -- -W clippy::pedantic 2>&1
cargo test 2>&1
cargo audit 2>&1
npx @modelcontextprotocol/inspector --cli ./target/release/<bin> --method tools/list
```

### Phase 3 — Protocol compliance

Check `get_info()` capabilities match actual features (nothing declared but
unimplemented, or vice versa); `protocolVersion` set; server instructions
present and useful. Flag the classic anti-pattern of returning protocol errors
(`McpError::*`) for **tool** failures — those must go through
`CallToolResult::error(...)` so the LLM can see them. For each tool: snake_case
verb+resource name, every parameter has `schemars(description = "…")`,
appropriate annotations (`readOnlyHint`, `destructiveHint`), single purpose.

### Phase 4 — Rust quality

- **Logging:** stdio servers must keep stdout clean — search for `println!` /
  `print!`; tracing configured to stderr with `with_ansi(false)`.
- **Async:** no `std::thread::sleep` (use `tokio::time::sleep`), no blocking I/O
  without `spawn_blocking`, no `std::sync::Mutex` held across `.await` (use
  `tokio::sync::Mutex`).
- **Errors:** no `unwrap()`/`expect()` in production paths; `?` propagation;
  tool errors via `CallToolResult::error()`; messages actionable, no internal
  leakage.
- **State:** thread-safe types, minimal lock duration, no nested-lock deadlocks.
- **rmcp macros:** `#[tool_router]` on the impl, `#[tool_handler]` on
  `impl ServerHandler`, `ToolRouter<Self>` in the struct, `schemars` v1.

### Phase 5 — Security

Input validation on every tool parameter (path traversal, URL scheme/host, no
shell injection, size limits); secrets from env, never logged or returned in
results/errors; HTTP servers validate `Origin`, bind `127.0.0.1`, use secure
session IDs and TLS; dependencies pinned, `cargo audit` clean. Full list:
[references/production-hardening.md](references/production-hardening.md).

### Phase 6 — Testing coverage

Compare the test suite against the exposed tools — every tool wants a happy-path
unit test, an error-case unit test, and integration coverage through the full
protocol (the `tokio::io::duplex()` pattern). For stateful servers, concurrent
access tests. Two higher-order checks worth running:

- **Mutation testing** — `cargo mutants --in-diff <(git diff origin/main)
  --timeout-multiplier 2.0` should show zero surviving mutants on changed
  tool-handler code. Catches integration tests that assert on JSON-RPC
  envelopes without checking the tool did anything useful.
- **Complexity/coverage** — dispatch tables and tool routers are high-cyclomatic
  and easy to under-test with a single golden-path test; flag handlers that lean
  on one integration test.

Details: [references/testing-strategies.md](references/testing-strategies.md).

### Phase 7 — Feedback

Structure findings by severity and cite exact locations with a concrete fix:

- **Critical (must fix):** protocol violations, security holes, stdout pollution
  on stdio, build/clippy failures.
- **Important (should fix):** missing/poor tool descriptions, no server
  instructions, `unwrap()` in production, missing tests, blocking in async.
- **Suggestions:** better annotations, richer instructions, more coverage.

Prefer specific over vague — cite `src/tools/search.rs:45`, show the `unwrap()`,
and give the `.map_err(...) + CallToolResult::error()` replacement.

### Phase 8 — Implementation

Ask which issues to prioritize and whether to implement or let the user review
first. When fixing: critical → important → suggestions, re-running `cargo
clippy` and `cargo test` after each change.

## Common findings

| Finding | Frequency | Fix |
|---|---|---|
| `println!` in stdio server | Very common | `tracing::info!` to stderr |
| Protocol errors for tool failures | Very common | `CallToolResult::error()` |
| Missing tool descriptions | Common | `schemars(description = "…")` on all params |
| No server instructions | Common | Add `instructions` in `get_info()` |
| `unwrap()` in production paths | Common | `?` + proper error mapping |
| No integration tests | Common | Add duplex-channel tests |
| Blocking in async context | Occasional | `tokio::task::spawn_blocking` |
| Hardcoded secrets | Occasional | Move to environment variables |

## Report format

Open with an assessment summary (Excellent / Good / Needs Work / Critical
Issues, plus top strengths and issues), then issues by priority with file
locations and code, then next steps. The full per-dimension quality checklist
lives in [references/review-checklist.md](references/review-checklist.md).

## Reference files

- [references/protocol-fundamentals.md](references/protocol-fundamentals.md) — architecture, lifecycle, JSON-RPC, primitives
- [references/server-design-patterns.md](references/server-design-patterns.md) — instructions, tool descriptions, naming
- [references/rmcp-implementation.md](references/rmcp-implementation.md) — SDK patterns, macros, examples
- [references/project-and-integration.md](references/project-and-integration.md) — layout, tool config
- [references/testing-strategies.md](references/testing-strategies.md) — unit, integration, Inspector, conformance
- [references/production-hardening.md](references/production-hardening.md) — security, logging, performance
- [references/review-checklist.md](references/review-checklist.md) — full quality review criteria
