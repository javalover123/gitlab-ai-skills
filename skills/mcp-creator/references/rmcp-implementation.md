# rmcp Implementation Guide

Complete reference for building MCP servers with the official Rust SDK.

## Why rmcp

The `rmcp` crate is the **official Rust SDK** maintained under `github.com/modelcontextprotocol/rust-sdk` with **3,000+ GitHub stars** and **308,000+ crate downloads**. Originally created by developer `4t145`, it's now merged into the official MCP organization. It implements the **2025-11-25 specification** and supports tools, resources, prompts, tasks, OAuth, and all transport mechanisms.

The closest alternative, `rust-mcp-sdk` (126 stars), is community-maintained and self-describes as "under development, use at your own risk."

## Installation

```toml
[dependencies]
rmcp = { version = "0.15", features = ["server", "transport-io"] }
tokio = { version = "1", features = ["full"] }
serde = { version = "1", features = ["derive"] }
serde_json = "1"
schemars = "1.0"
anyhow = "1.0"
tracing = "0.1"
tracing-subscriber = { version = "0.3", features = ["env-filter"] }
```

**Critical:** rmcp requires **Rust Edition 2024** (nightly toolchain). Add a `rust-toolchain.toml`:

```toml
[toolchain]
channel = "nightly"
```

## Feature Flags

| Flag | Purpose |
|------|---------|
| `server` | Server functionality |
| `client` | Client functionality |
| `macros` | Proc macros (enabled by default) |
| `transport-io` | stdio transport |
| `transport-streamable-http-server` | Modern HTTP with axum |
| `transport-sse-server` | Legacy SSE transport |
| `transport-child-process` | Spawn servers as child processes (testing) |
| `auth` | OAuth 2.1 support |
| `schemars` | JSON Schema generation |

## Core Architecture

The central trait is `ServerHandler`, with default implementations for all methods. You'll only need to override what you actually use:

```rust
pub trait ServerHandler: Sized + Send + Sync + 'static {
    fn get_info(&self) -> ServerInfo;  // Required: server identity

    // Tools
    async fn list_tools(&self, ...) -> Result<ListToolsResult, McpError>;
    async fn call_tool(&self, ...) -> Result<CallToolResult, McpError>;

    // Resources
    async fn list_resources(&self, ...) -> Result<ListResourcesResult, McpError>;
    async fn read_resource(&self, ...) -> Result<ReadResourceResult, McpError>;

    // Prompts
    async fn list_prompts(&self, ...) -> Result<ListPromptsResult, McpError>;
    async fn get_prompt(&self, ...) -> Result<GetPromptResult, McpError>;

    // Lifecycle and notifications
    async fn initialize(&self, ...) -> Result<InitializeResult, McpError>;
    async fn on_roots_list_changed(&self, ...);
}
```

The `ServiceExt` trait provides `.serve(transport)` to start the server on any transport. The `Peer` handle enables server-to-client communication (logging, progress notifications, sampling requests).

## The Macro System

Three proc macros handle tool routing, so you won't need to write most of the boilerplate:

### `#[tool_router]`

Place on an `impl` block. Scans for `#[tool]`-annotated methods, generates a `ToolRouter<Self>` and `Self::tool_router()` constructor.

### `#[tool(description = "...")]`

Place on methods to mark them as MCP tools with metadata.

### `#[tool_handler]`

Place on `impl ServerHandler` to auto-generate `list_tools` and `call_tool` dispatching to the tool router.

## Parameter Patterns

### Aggregate Parameters (Struct)

Best for tools with multiple related parameters:

```rust
#[derive(Debug, serde::Deserialize, schemars::JsonSchema)]
pub struct SumRequest {
    #[schemars(description = "the left operand")]
    pub a: i32,
    #[schemars(description = "the right operand")]
    pub b: i32,
}

#[tool(description = "Calculate the sum of two numbers")]
async fn sum(&self, #[tool(aggr)] SumRequest { a, b }: SumRequest) -> String {
    (a + b).to_string()
}
```

### Individual Parameters

Best for tools with one or two simple parameters:

```rust
#[tool(description = "Get weather alerts for a US state")]
async fn get_alerts(
    &self,
    #[tool(param)]
    #[schemars(description = "two-letter US state code")]
    state: String,
) -> String { /* ... */ }
```

## Return Types

| Return Type | Behavior |
|------------|----------|
| `String` | Auto-wraps into `CallToolResult::success` with text content |
| `Result<CallToolResult, McpError>` | Full control over success/error responses |
| `Result<Json<T>, String>` | Structured output (T must impl `Serialize + JsonSchema`) |

## Complete Server Example

```rust
use rmcp::{
    ServerHandler, ServiceExt,
    handler::server::tool::ToolRouter,
    model::*,
    tool, tool_handler, tool_router,
    transport::stdio,
    ErrorData as McpError,
};
use std::sync::Arc;
use tokio::sync::Mutex;

#[derive(Clone)]
pub struct Counter {
    count: Arc<Mutex<i32>>,
    tool_router: ToolRouter<Self>,
}

#[tool_router]
impl Counter {
    fn new() -> Self {
        Self {
            count: Arc::new(Mutex::new(0)),
            tool_router: Self::tool_router(),
        }
    }

    #[tool(description = "Increment the counter and return its new value")]
    async fn increment(&self) -> Result<CallToolResult, McpError> {
        let mut count = self.count.lock().await;
        *count += 1;
        Ok(CallToolResult::success(vec![Content::text(count.to_string())]))
    }

    #[tool(description = "Get the current counter value")]
    async fn get_value(&self) -> Result<CallToolResult, McpError> {
        let count = self.count.lock().await;
        Ok(CallToolResult::success(vec![Content::text(count.to_string())]))
    }
}

#[tool_handler]
impl ServerHandler for Counter {
    fn get_info(&self) -> ServerInfo {
        ServerInfo {
            protocol_version: ProtocolVersion::V_2025_03_26,
            capabilities: ServerCapabilities::builder().enable_tools().build(),
            server_info: Implementation {
                name: "counter".to_string(),
                version: env!("CARGO_PKG_VERSION").to_string(),
                ..Default::default()
            },
            instructions: Some(
                "A simple counter server. Use 'increment' to advance the count \
                 and 'get_value' to check it. The counter persists within a session."
                    .to_string(),
            ),
        }
    }
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt()
        .with_writer(std::io::stderr)  // Never write to stdout!
        .with_ansi(false)
        .init();

    let service = Counter::new().serve(stdio()).await?;
    service.waiting().await?;
    Ok(())
}
```

## Transport Implementations

### stdio

```rust
use rmcp::transport::stdio;
let service = my_server.serve(stdio()).await?;
service.waiting().await?;
```

### Streamable HTTP (axum)

Requires feature `transport-streamable-http-server`:

```rust
use rmcp::transport::streamable_http_server::{
    StreamableHttpService, session::local::LocalSessionManager,
};

let service = StreamableHttpService::new(
    || Ok(MyServer::new()),                // Factory: new instance per session
    LocalSessionManager::default().into(), // Session management
    Default::default(),                    // Options
);

let router = axum::Router::new().nest_service("/mcp", service);
let listener = tokio::net::TcpListener::bind("127.0.0.1:8000").await?;
axum::serve(listener, router).await?;
```

## Error Handling

`rmcp::ErrorData` (commonly aliased as `McpError`) maps to JSON-RPC error codes:

| Constructor | Use When |
|------------|----------|
| `McpError::invalid_params("msg", None)` | Client sent bad parameters |
| `McpError::internal_error("kind", Some(json))` | Server-side failure |
| `McpError::invalid_request("msg")` | Malformed request |
| `CallToolResult::error(vec![Content::text("msg")])` | Tool execution failed (LLM-visible) |

**Remember:** Tool execution errors go through `CallToolResult::error()`, not `McpError`. That's how the LLM can see and reason about the failure.

## Server-to-Client Communication (Peer)

The `RequestContext` and `NotificationContext` provide a `peer` handle:

```rust
// Send a log message to the client
peer.notify_logging_message(LoggingMessageNotificationParam {
    level: LoggingLevel::Info,
    logger: None,
    data: serde_json::json!({"message": "Processing complete"}),
}).await;
```

Use the peer for:
- Sending log messages (`notify_logging_message`)
- Reporting progress (`notify_progress`)
- Requesting LLM completions (`create_message` — if the client supports sampling)
- Notifying clients when tool lists change (`notify_tools_list_changed`)
