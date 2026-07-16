---
name: mcp-creator
description: "Guides building production-quality MCP servers in Rust using the rmcp crate. Covers protocol design, tool implementation, testing, security hardening, and AI-tool integration. Use when building an MCP server, creating MCP tools, implementing MCP in Rust, adding tools/resources/prompts to an MCP server, or starting a new MCP project."
version: 1.0.0
license: MIT
category: Development Workflow
compatibility: opencode
metadata:
  audience: developers
  workflow: rust
---

# MCP Server Creator

Build MCP servers in Rust with the official `rmcp` crate, following protocol
best practices and production-quality patterns. The `SKILL.md` is the lean
entry point; each phase links to a reference file for the deep detail.

## When to use

- Building a new MCP server from scratch in Rust.
- Adding tools, resources, or prompts to an existing MCP server.
- Implementing MCP protocol features (transport, capabilities, lifecycle).
- Integrating an MCP server with an AI coding tool (opencode, Claude Code, …).

## Workflow

### Phase 1 — Discovery

Before writing code, clarify (ask the user): what the server does and what
data/services it exposes; which primitives it needs (**tools** = actions,
**resources** = read-only data, **prompts** = templates); transport (**stdio**
for local, **Streamable HTTP** for remote/multi-client, or both); state needs
(stateless / session / persistent); external dependencies; and deployment
target.

### Phase 2 — Architecture

Pick primitives and transport from the discovery answers:

| Need | Primitive | | Scenario | Transport (rmcp feature) |
|---|---|---|---|---|
| Actions with side effects | Tools | | Local CLI | stdio (`transport-io`) |
| Read structured data | Resources | | Remote service | Streamable HTTP (`transport-streamable-http-server`) |
| Conversation templates | Prompts | | Legacy | SSE (`transport-sse-server`) |

State: stateless (independent calls), session (`Arc<Mutex<T>>` / `Arc<RwLock<T>>`
in the server struct), or persistent (a pooled DB connection, e.g. `sqlx`).
Plan the `instructions` field — cross-tool workflows the LLM can't infer from
schemas. See [references/server-design-patterns.md](references/server-design-patterns.md).

### Phase 3 — Project setup

`cargo init`, pin nightly in `rust-toolchain.toml` (rmcp needs it), and add
`rmcp` (with the transport feature), `tokio`, `serde`, `serde_json`, `schemars`,
`anyhow`, `tracing`, `tracing-subscriber`. Layout and the full feature-flag
list: [references/project-and-integration.md](references/project-and-integration.md)
and [references/rmcp-implementation.md](references/rmcp-implementation.md).

### Phase 4 — Implementation

Order: (1) server struct with `ToolRouter<Self>` + shared state; (2)
`#[tool_router]` impl with `#[tool(description = "…")]` methods; (3)
`#[tool_handler]` on `ServerHandler`, wiring `get_info()` with capabilities and
instructions; (4) `main.rs` — tracing **to stderr**, transport, `serve().waiting()`.

Rules: every parameter needs a `#[schemars(description = "…")]`; tool-execution
errors → `CallToolResult::error()` (LLM sees them), protocol errors →
`McpError::*` (opaque); never `unwrap()`/`expect()` in production paths; return
actionable messages. **stdout is sacred** on stdio servers — only JSON-RPC goes
there, all logging via `tracing`. Examples and the macro system:
[references/rmcp-implementation.md](references/rmcp-implementation.md).

### Phase 5 — Testing

Bottom-up: unit tests calling tool methods directly; integration tests over
`tokio::io::duplex` channels; the MCP Inspector for interactive and CI checks
(`npx @modelcontextprotocol/inspector [--cli] ./target/release/<bin>`). Register
the built binary in your AI tool to test end-to-end — in opencode add it under
`mcp` in `opencode.json` (`{"mcp": {"my-server": {"type": "local", "command":
["./target/release/my-mcp-server"], "enabled": true}}}`, see
[opencode.ai/docs/mcp-servers](https://opencode.ai/docs/mcp-servers/)); in Claude
Code use `claude mcp add`. Full guide:
[references/testing-strategies.md](references/testing-strategies.md).

### Phase 6 — Production readiness

Validate all tool inputs (paths, URLs, commands); load secrets from env; for
HTTP validate `Origin`, bind to `127.0.0.1`, use secure session IDs. Document
tool descriptions, server instructions, and a README. Security checklist and
production patterns: [references/production-hardening.md](references/production-hardening.md).

### Phase 7 — Validation

Run the full quality gate before calling the server done — protocol compliance,
tool quality, Rust quality (`cargo clippy -- -W clippy::pedantic`, no
`unwrap()`, tracing to stderr), security, testing, and docs. The complete
checklist lives in [references/review-checklist.md](references/review-checklist.md).

## Anti-patterns

- **Writing to stdout** on a stdio server — breaks JSON-RPC framing. Use
  `tracing::info!`, never `println!`.
- **Protocol errors for tool failures** — the LLM can't see `McpError`; return
  `CallToolResult::error(...)` so it can reason about the failure.
- **Kitchen-sink servers** — 50 tools burn tokens and blur purpose; keep each
  server focused (e.g. `analyze_query`, `explain_plan`, `suggest_index`).
- **Skipping server instructions** — without them the LLM can't chain tools;
  say how they compose.

## Reference files

- [references/protocol-fundamentals.md](references/protocol-fundamentals.md) — architecture, lifecycle, JSON-RPC, primitives, transports
- [references/server-design-patterns.md](references/server-design-patterns.md) — instructions, tool descriptions, naming
- [references/rmcp-implementation.md](references/rmcp-implementation.md) — SDK install, macros, complete examples, error handling
- [references/project-and-integration.md](references/project-and-integration.md) — layout, reference implementations, tool config
- [references/testing-strategies.md](references/testing-strategies.md) — unit, integration, Inspector, conformance
- [references/production-hardening.md](references/production-hardening.md) — security, logging, performance, versioning
- [references/review-checklist.md](references/review-checklist.md) — full quality review criteria
