# MCP Protocol Fundamentals

Complete reference for the Model Context Protocol architecture, lifecycle, message format, and primitives.

## Architecture

MCP follows a **client-host-server architecture** built on JSON-RPC 2.0. The **host** is the LLM application (e.g., Claude Code) that creates and manages **client** instances, each maintaining an isolated 1:1 connection to a **server**. Servers expose three core primitives:

- **Tools** (model-controlled) — invoked by the LLM to perform actions
- **Resources** (application-controlled) — read-only data identified by URIs
- **Prompts** (user-controlled) — explicit templates triggered by users
- **Instructions** (server-provided) — guidance injected into the LLM's system prompt

Two client features complement these:

- **Sampling** — servers requesting LLM completions from the client
- **Roots** — filesystem boundary hints (advisory, not security enforcement)

## Protocol Lifecycle

The lifecycle has three phases: **initialization**, **operation**, and **shutdown**.

### Initialization

1. Client sends `initialize` request with `protocolVersion`, `capabilities`, `clientInfo`
2. Server responds with its capabilities, implementation details, and optional `instructions`
3. Client sends `notifications/initialized` notification
4. Both sides enter the operation phase

**Version negotiation:** The client proposes its latest supported version. If the server supports it, it echoes it back; otherwise it responds with its own preferred version. If the client can't accept the server's version, it disconnects.

Current spec versions: **2024-11-05**, **2025-03-26**, **2025-06-18**, **2025-11-25**.

### Capability Negotiation

| Side | Capability | Description |
|------|-----------|-------------|
| Server | `tools` | Exposes callable tools with optional `listChanged` |
| Server | `resources` | Provides readable resources with optional `subscribe`, `listChanged` |
| Server | `prompts` | Offers prompt templates with optional `listChanged` |
| Server | `logging` | Emits structured log messages |
| Server | `completions` | Supports argument autocompletion |
| Client | `roots` | Provides filesystem root boundaries |
| Client | `sampling` | Supports LLM completion requests from servers |

### Shutdown

Transport-specific mechanisms:

- **stdio**: Client closes stdin, waits for server to exit, then sends SIGTERM followed by SIGKILL
- **HTTP**: Client sends HTTP DELETE or closes the connection

## JSON-RPC Message Format

All messages are UTF-8 encoded JSON-RPC 2.0. Three message types:

| Type | Has `id` | Expects Response | Fields |
|------|----------|-----------------|--------|
| Request | Yes (unique) | Yes | `method`, optional `params` |
| Response | Yes (matches request) | No | `result` (success) or `error` |
| Notification | No | No | `method`, optional `params` |

Since spec version 2025-03-26, **JSON-RPC batching** is supported — arrays of requests and notifications can be sent as a single message.

### Error Codes

| Code | Meaning |
|------|---------|
| -32700 | Parse error |
| -32600 | Invalid request |
| -32601 | Method not found |
| -32602 | Invalid params |
| -32603 | Internal error |
| -32000 to -32099 | MCP-specific server errors |

**Critical distinction:** Tool execution failures use a different mechanism — they return a successful response with `isError: true` in the `CallToolResult`, so the LLM can see and reason about the error. Reserve JSON-RPC error codes for protocol-level failures.

## Tools

Tools are declared via `tools/list` and invoked via `tools/call`.

### Tool Definition

Each tool includes:

- `name` — unique identifier (use snake_case)
- `description` — what the tool does (verb + resource structure)
- `inputSchema` — JSON Schema object type for parameters
- `annotations` — optional behavioral hints (readOnly, destructive, idempotent, openWorld)

Since 2025-03-26, tools support **annotations**:

| Annotation | Type | Description |
|-----------|------|-------------|
| `readOnlyHint` | bool | Tool doesn't modify state |
| `destructiveHint` | bool | Tool may delete or permanently modify data |
| `idempotentHint` | bool | Calling multiple times with same args has same effect |
| `openWorldHint` | bool | Tool interacts with external systems |

Since 2025-06-18, tools also support `title` (human-readable display name) and `outputSchema` (for structured JSON return values).

### Tool Results

Results contain an array of `content` items:

| Content Type | Description | Added |
|-------------|-------------|-------|
| `text` | Plain text | Original |
| `image` | Base64-encoded image | Original |
| `audio` | Base64-encoded audio | 2025-03-26 |
| `resource` | Embedded resource reference | Original |

The `isError` boolean distinguishes successful from failed tool executions.

## Resources

Resources are identified by URIs conforming to RFC 3986 (`file://`, `https://`, `git://`, or custom schemes).

| Operation | Method |
|-----------|--------|
| List | `resources/list` |
| Read | `resources/read` |
| Subscribe | `resources/subscribe` |

**Resource templates** use URI template syntax (e.g., `file:///{path}`) and support autocompletion through `completion/complete`.

## Prompts

Prompts are listed via `prompts/list` and retrieved via `prompts/get` with arguments.

Each prompt returns an array of `messages` with:
- `role` — "user" or "assistant"
- `content` — text, image, audio, or embedded resource

Prompts support parameterization through named arguments.

## Sampling

Sampling lets servers request LLM completions from clients via `sampling/createMessage`. The server specifies:

- `messages` — conversation history
- `systemPrompt` and `includeContext` — optional system prompt and context scope ("none", "thisServer", or "allServers")
- `maxTokens` — maximum response length
- Model preferences (hints, cost/speed/intelligence priority)

The **client** controls actual model selection and context inclusion — the server only provides preferences.

## Transport Mechanisms

### stdio (Primary for Local Servers)

The client spawns the server as a subprocess. JSON-RPC messages flow through stdin/stdout, delimited by newlines.

**Rules:**
- Servers **must never** write non-MCP content to stdout
- stderr is available for logging
- All tracing/logging output goes to stderr
- Exit cleanly when stdin closes (the client is shutting down)

### Streamable HTTP (Recommended for Remote)

Introduced in 2025-03-26, replacing HTTP+SSE. Uses a single HTTP endpoint supporting both POST and GET.

- Clients send messages via POST with `Accept: application/json, text/event-stream`
- Servers respond with JSON or SSE streams
- Session management uses `Mcp-Session-Id` header (must be cryptographically secure)
- Servers **must** validate `Origin` headers for DNS rebinding protection

### SSE (Deprecated)

The original HTTP transport from 2024-11-05. Still supported by many servers but deprecated in favor of Streamable HTTP.

## Utility Features

| Feature | Direction | Description |
|---------|-----------|-------------|
| Ping | Bidirectional | Health check (`ping` method) |
| Progress | Server → Client | `progressToken`, `progress`, `total`, `message` |
| Cancellation | Client → Server | `notifications/cancelled` with request ID |
| Logging | Server → Client | Structured log messages with severity levels |
| Completion | Server → Client | Argument autocompletion for resources and prompts |
| Pagination | Both | Cursor-based pagination for all list operations |
