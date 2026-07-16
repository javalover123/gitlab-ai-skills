# Production Hardening

Security, logging, performance, versioning, and documentation patterns for production MCP servers.

## Security Checklist

### Input Validation

- Validate all tool parameters against schemas before processing
- Sanitize file paths — check for path traversal (`../`, symlink following)
- Sanitize URLs (validate scheme, host, reject internal IPs) and commands (never interpolate user input into shell commands)
- Reject oversized inputs early (before processing)

### Authentication

| Transport | Approach |
|-----------|----------|
| stdio | Credentials from environment variables (server runs locally) |
| Streamable HTTP | OAuth 2.0/OIDC with proper token validation |

- Never accept tokens not explicitly issued for your server
- Implement per-client consent where appropriate

### Network Security

- Streamable HTTP servers **must** validate `Origin` headers (DNS rebinding protection)
- Bind to `127.0.0.1`, **not** `0.0.0.0`, for local servers
- Use TLS for any non-localhost connections
- Use cryptographically secure session IDs (UUID v4 or JWT)

### Runtime Isolation

- Containerize servers with CPU/memory/network resource limits
- Use filesystem sandboxing (chroot, namespaces, or pledge/unveil on BSD)
- Drop privileges after initialization — don't run as root
- Limit network access to only required endpoints

### Supply Chain

- Pin dependency versions in `Cargo.lock`
- Run SAST/SCA in CI (`cargo audit`, `cargo deny`)
- Monitor CVEs for dependencies
- Review transitive dependencies periodically

## Logging and Observability

### stdio: All Logging to stderr

For stdio servers, **stdout is exclusively for JSON-RPC**. All logging must go to stderr:

```rust
tracing_subscriber::fmt()
    .with_writer(std::io::stderr)
    .with_env_filter(tracing_subscriber::EnvFilter::from_default_env())
    .with_ansi(false)
    .init();
```

**Never** use `println!()` in a stdio server. Use `eprintln!()` for quick debugging or `tracing::info!()` for structured logging.

### Protocol-Level Logging

Use MCP's `notifications/message` to send structured log messages to the client:

```rust
peer.notify_logging_message(LoggingMessageNotificationParam {
    level: LoggingLevel::Info,
    logger: None,
    data: serde_json::json!({"message": "Processing complete"}),
}).await;
```

### Production Logging

Emit structured JSON logs with:
- Trace IDs for request correlation
- Tool names for per-tool metrics
- Latency measurements
- Outcome status (success/error)

### Metrics to Track

| Metric | Why |
|--------|-----|
| Tool invocation counts | Usage patterns |
| Error rates per tool | Reliability |
| p50/p95/p99 latency | Performance |
| Active session counts | Capacity planning |

## Performance Considerations

### Token Budget

| Component | Token Cost |
|-----------|-----------|
| Tool schema | 50-100 tokens per tool |
| Tool description | 100-200 tokens per tool |
| 50 tools total | 7,500-15,000 tokens |

**Design implication:** Return paginated, filtered responses rather than large data dumps. The tool output warning threshold is **10,000 tokens**, with a hard limit at **25,000 tokens** by default.

### Transport Latency

| Transport | Latency | Best For |
|-----------|---------|----------|
| stdio | Microseconds | Local development, CLI tools |
| Streamable HTTP | Network-dependent | Remote deployment, multi-client |

### Long-Running Operations

For operations that take more than a few seconds, use the **tasks** primitive (spec 2025-11-25):

1. Create a task, return a `task_id`
2. Server sends progress notifications as work proceeds
3. Client polls or subscribes for status updates
4. Server delivers the final result when complete

## Versioning Strategy

### Protocol Versions

MCP protocol versions are date-based. Support the latest version as default but handle version negotiation gracefully for older clients.

### Server API Versioning

- Keep tool names and schemas stable
- Prefer additive changes (new tools, new optional parameters)
- Use `listChanged` notifications to update capabilities dynamically
- Document breaking changes with semantic version bumps, and if you must remove a tool, deprecate it first with a description noting the replacement

## Documentation Patterns

Every production MCP server needs:

### Tool Descriptions
- Format specifications for every parameter
- Constraints (min/max values, allowed patterns)
- Examples for non-obvious formats
- Workflow dependencies with other tools

### Server Instructions
- Cross-tool workflows and operational patterns
- Constraints and limitations
- Error handling expectations
- Performance tips

### README
- All tools with descriptions
- Required environment variables
- Configuration examples
- Build and test instructions

### Error Messages
- Structured, within tool results (not protocol-level)
- Actionable guidance ("File not found: config.toml. Check the path and try again.")
- Include error categories or codes for programmatic handling
- Don't leak internal details (stack traces, paths, credentials)

### Security Model
- Authentication requirements
- Data access patterns and boundaries
- Permission model
- Audit logging for sensitive operations
