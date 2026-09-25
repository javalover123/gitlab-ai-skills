# MCP Server Review Checklist

Systematic review criteria for evaluating Rust MCP server implementations.

## Protocol Compliance

- [ ] Correct initialization handshake (responds to `initialize` with capabilities)
- [ ] Capability declaration matches actual features (don't declare `resources` if you don't implement them)
- [ ] Correct JSON-RPC error codes for protocol errors
- [ ] Tool errors via `isError: true` in `CallToolResult` (not protocol errors)
- [ ] Pagination support in list operations (if more than ~50 items possible)
- [ ] Proper shutdown handling (graceful cleanup on transport close)
- [ ] Responds correctly to `ping` method
- [ ] Handles unknown methods gracefully (returns method-not-found error)
- [ ] Implements `listChanged` notifications if tools are dynamic
- [ ] Version negotiation works for supported spec versions

## Tool Quality

### Naming
- [ ] Uses snake_case (no spaces, dots, or brackets)
- [ ] Names are descriptive but concise
- [ ] No naming collisions with other likely MCP servers

### Descriptions
- [ ] Verb + resource structure ("Create a new channel", not "This tool creates channels")
- [ ] Front-loaded important information (first sentence is most useful)
- [ ] Disambiguated from similar tools (when applicable)
- [ ] Workflow dependencies documented ("Call X before Y")
- [ ] Limitations stated explicitly

### Input Schema
- [ ] All parameters described with `schemars(description = "...")`
- [ ] Types are correct and specific (not just `String` for everything)
- [ ] Constraints documented (min/max, patterns, allowed values)
- [ ] Optional vs required parameters correctly marked
- [ ] Examples provided for non-obvious formats

### Annotations
- [ ] `readOnlyHint` set for read-only tools
- [ ] `destructiveHint` set for tools that delete or permanently modify data
- [ ] `idempotentHint` set where applicable
- [ ] `openWorldHint` set for tools interacting with external systems

### Design
- [ ] Each tool performs a single, well-scoped task (atomic design)
- [ ] No "god tools" that do too many things
- [ ] Appropriate granularity (not too fine, not too coarse)

## Rust-Specific Patterns

### Logging
- [ ] Uses `tracing` crate (not `println!` or `log`)
- [ ] stderr writer configured (never writes to stdout in stdio servers)
- [ ] `with_ansi(false)` for clean log output
- [ ] Appropriate log levels (info for operations, warn for issues, error for failures)

### Async Patterns
- [ ] No blocking operations in async contexts (no `std::thread::sleep`, no blocking I/O)
- [ ] Uses `tokio` runtime consistently
- [ ] Spawns blocking work with `tokio::task::spawn_blocking` when necessary
- [ ] Proper cancellation handling

### Error Handling
- [ ] Uses `?` operator with proper `From` implementations or `.map_err()`
- [ ] Maps domain errors to appropriate `McpError` variants
- [ ] Tool execution errors return `CallToolResult::error()` (LLM-visible)
- [ ] Protocol errors return proper JSON-RPC error codes
- [ ] No `unwrap()` or `expect()` in production code paths

### State Management
- [ ] Thread-safe state: `Arc<Mutex<T>>` or `Arc<RwLock<T>>`
- [ ] Mutex held for minimal duration (no await while holding non-async mutex)
- [ ] Uses `tokio::sync::Mutex` for state held across `.await` points
- [ ] No deadlock potential from nested locks

### rmcp Usage
- [ ] `#[tool_router]` on impl block with tool methods
- [ ] `#[tool_handler]` on `impl ServerHandler`
- [ ] `schemars` v1 for JSON Schema generation
- [ ] Proper `serde` derivations (`Deserialize` for inputs, `Serialize` for outputs)
- [ ] `ToolRouter<Self>` stored in server struct

## Security Review

### Input Validation
- [ ] All inputs validated against schemas before processing
- [ ] Path traversal checks for file operations (reject `../`)
- [ ] URL validation (scheme, host, no internal IPs)
- [ ] Command injection prevention (no shell interpolation of user input)
- [ ] Size limits on inputs

### Secrets
- [ ] Loaded from environment variables (not hardcoded)
- [ ] Not logged or included in error messages
- [ ] Not returned in tool results
- [ ] Configuration examples use placeholders

### Transport Security
- [ ] HTTP servers validate `Origin` headers
- [ ] Binds to `127.0.0.1` for local servers (not `0.0.0.0`)
- [ ] Session IDs are cryptographically secure
- [ ] TLS for remote connections

### Data Safety
- [ ] No sensitive data leaked in error messages
- [ ] No sensitive data in logs
- [ ] Destructive operations require explicit confirmation or are clearly annotated
- [ ] File operations constrained to expected directories

## Testing Coverage

- [ ] Unit tests for each tool handler
- [ ] Integration tests using `tokio::io::duplex()` (full protocol)
- [ ] Error case coverage (invalid inputs, missing parameters)
- [ ] Edge cases tested (empty inputs, oversized inputs, concurrent access)
- [ ] CI pipeline runs all tests
- [ ] Server tested with MCP Inspector
- [ ] Tested in Claude Code with realistic prompts
