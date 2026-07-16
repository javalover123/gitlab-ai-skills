# Testing Strategies for MCP Servers

A complete guide to testing MCP servers at every level, from unit tests through production validation.

## Testing Pyramid

Build your test suite from the bottom up:

1. **Unit tests** — Call tool handlers directly, fast and focused
2. **In-process integration** — Full protocol via duplex channels, no subprocess
3. **Child process integration** — Test the compiled binary end-to-end
4. **MCP Inspector** — Interactive debugging and CI validation
6. **Claude Code end-to-end** — Real-world usage testing
7. **Conformance testing** — Official protocol compliance checks

## Unit Testing Tool Handlers

The simplest and fastest approach — call tool methods directly, bypassing transport:

```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_increment() {
        let server = Counter::new();
        let result = server.increment().await.unwrap();
        assert!(!result.is_error);
        // Verify content
    }

    #[tokio::test]
    async fn test_invalid_input() {
        let server = MyServer::new();
        let result = server.process_file("/nonexistent/path".into()).await;
        // Verify error handling
        assert!(result.unwrap().is_error);
    }
}
```

Unit tests should cover:
- Happy path for each tool
- Invalid inputs and edge cases
- Error conditions and error message quality
- State management (if server is stateful)

## In-Process Integration Testing with Duplex Channels

rmcp's transport abstraction accepts any `(AsyncRead, AsyncWrite)` pair. Using `tokio::io::duplex()`, you'll create in-process bidirectional channels that test the full protocol without subprocess or network overhead:

```rust
#[tokio::test]
async fn test_full_protocol() {
    let (client_read, server_write) = tokio::io::duplex(4096);
    let (server_read, client_write) = tokio::io::duplex(4096);

    // Start server
    let server = Counter::new();
    tokio::spawn(async move {
        server.serve((server_read, server_write)).await.unwrap()
            .waiting().await.unwrap();
    });

    // Connect client
    let client = ().serve((client_read, client_write)).await.unwrap();

    // Test tool listing
    let tools = client.list_tools(Default::default()).await.unwrap();
    assert!(tools.tools.iter().any(|t| t.name == "increment"));

    // Test tool calling
    let result = client.call_tool(CallToolRequestParam {
        name: "increment".into(),
        arguments: None,
    }).await.unwrap();
    assert!(!result.is_error);

    client.cancel().await;
}
```

This tests:
- Initialization handshake and capability negotiation
- Tool listing, discovery, and invocation
- Response serialization and JSON-RPC framing
- Error propagation through the full protocol stack

## Child Process Integration Testing

For testing the actual compiled binary as a subprocess:

```rust
use rmcp::transport::{TokioChildProcess, ConfigureCommandExt};
use tokio::process::Command;

#[tokio::test]
async fn test_binary() {
    let transport = TokioChildProcess::new(
        Command::new("./target/release/my-mcp-server")
    ).unwrap();
    let client = ().serve(transport).await.unwrap();
    let tools = client.list_tools(Default::default()).await.unwrap();
    // Verify tools...
    client.cancel().await;
}
```

The rmcp repo itself includes cross-language integration tests in `crates/rmcp/tests/test_with_python.rs`, demonstrating Rust client to Python server interoperability.

## MCP Inspector

The **MCP Inspector** is the official developer tool. You don't need to install it — just run it via npx:

### Interactive Mode

```bash
# Inspect a Rust server binary
npx @modelcontextprotocol/inspector ./target/release/my-mcp-server
```

Opens a React-based web UI (default port **6274**) with tabs for tools, resources, prompts, and notifications. Supports timeout configuration, config file persistence, and export to Claude Code / Cursor formats.

### CLI Mode (for CI)

```bash
# List tools
npx @modelcontextprotocol/inspector --cli ./target/release/my-mcp-server \
  --method tools/list

# Call a specific tool
npx @modelcontextprotocol/inspector --cli ./target/release/my-mcp-server \
  --method tools/call --tool-name increment
```

## Testing with Claude Code

```bash
# Add your dev server
claude mcp add --transport stdio my-server ./target/release/my-mcp-server

# Debug mode for detailed logs
claude --mcp-debug

# Check logs
cat ~/.claude/logs/mcp-debug.log
```

**Tips:**
- Always test manually in the terminal first
- Use absolute paths in configuration
- Rebuild after code changes, then reconnect (Cmd-R / Ctrl-R)
- Check `~/.claude/logs/mcp-debug.log` when tools aren't appearing

## Protocol Conformance Testing

The official `@modelcontextprotocol/conformance` package validates protocol compliance:

```bash
npx @modelcontextprotocol/conformance server \
  --url http://localhost:3000/mcp \
  --scenario server-initialize
```

The community `Janix-ai/mcp-validator` provides compliance testing for both stdio and HTTP transports.

## Mocking Strategies

Mock external dependencies at the service layer using trait objects or generics:

```rust
#[async_trait]
trait HttpClient: Send + Sync {
    async fn get(&self, url: &str) -> Result<String>;
}

struct RealClient;
struct MockClient { responses: HashMap<String, String> }

// Inject the appropriate client into your server
struct MyServer<C: HttpClient> {
    http: C,
    tool_router: ToolRouter<Self>,
}
```

For the MCP protocol layer itself, prefer in-process duplex testing over mocking — it'll test the real protocol without network overhead.

## Test Organization

```
tests/
├── unit/
│   ├── tools_test.rs          # Direct tool handler tests
│   └── models_test.rs         # Schema validation tests
├── integration/
│   ├── duplex_test.rs         # In-process protocol tests
│   └── binary_test.rs         # Child process tests
└── conformance/
    └── protocol_test.rs       # Spec compliance tests
```

Run the full suite in CI. Use `cargo test` for unit and integration tests, and npx commands for Inspector and conformance testing.
