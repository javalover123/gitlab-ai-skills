# Project Structure and Claude Code Integration

How to organize your MCP server project and configure it for use with Claude Code.

## Recommended Project Layout

For small servers, a single `main.rs` works fine. For larger projects:

```
my-mcp-server/
├── Cargo.toml
├── rust-toolchain.toml        # channel = "nightly"
├── src/
│   ├── main.rs                # Entry point, transport setup, tracing init
│   ├── server.rs              # ServerHandler impl, get_info()
│   ├── tools/
│   │   ├── mod.rs             # Tool router, re-exports
│   │   ├── weather.rs         # Individual tool implementations
│   │   └── search.rs
│   ├── resources/
│   │   └── mod.rs             # Resource handlers
│   ├── prompts/
│   │   └── mod.rs             # Prompt definitions
│   └── models.rs              # Request/response structs with schemars
```

### Key Files

**`Cargo.toml`** — Pin rmcp version, enable needed feature flags, include schemars v1.

**`rust-toolchain.toml`** — Must specify `channel = "nightly"` for Rust Edition 2024.

**`src/main.rs`** — Keep minimal: initialize tracing (to stderr!), create server, start transport, await shutdown.

**`src/server.rs`** — `ServerHandler` implementation with `get_info()` returning capabilities, version, and instructions.

**`src/tools/`** — One file per tool or per tool group. Use `#[tool_router]` on the impl block.

## Notable Reference Implementations

| Project | What It Demonstrates |
|---------|---------------------|
| `modelcontextprotocol/rust-sdk/examples/` | Official counter, calculator, SSE, Streamable HTTP examples |
| `Roblox/studio-rust-mcp-server` | Production MCP server for Roblox Studio integration |
| `Vaiz/rust-mcp-server` | Rust dev tools (cargo build/test/clippy) as MCP tools |
| `zeenix/rust-analyzer-mcp` | Wrapping rust-analyzer as an MCP server |
| `linux-china/mcp-rs-template` | Template project with modular handlers and JSON templates |
| `rust-mcp-stack/rust-mcp-filesystem` | Filesystem operations (Rust rewrite of JS reference) |

### Ecosystem Libraries

| Crate | Purpose |
|-------|---------|
| `rmcp-openapi` | Auto-generate MCP tools from OpenAPI specs |
| `rmcp-server-builder` | Builder pattern for composing servers |
| `rmcp-actix-web` | Actix Web backend for Streamable HTTP |

## Claude Code Configuration

### Configuration Scopes

Claude Code reads MCP config from four scope levels (highest precedence first):

1. **Enterprise managed** (can't be overridden)
2. **User** (`~/.claude/settings.json`)
3. **Project** (`.mcp.json` in project root, version-controlled)
4. **Local** (default)

### `.mcp.json` Format

```json
{
  "mcpServers": {
    "my-rust-server": {
      "command": "${HOME}/projects/my-server/target/release/my-mcp-server",
      "args": ["--config", "${PROJECT_ROOT}/config.toml"],
      "env": {
        "API_KEY": "${MY_API_KEY}"
      }
    }
  }
}
```

Environment variable expansion supports `${VAR}` and `${VAR:-default}` syntax in `command`, `args`, `env`, `url`, and `headers` fields.

### CLI Commands

```bash
# Add servers
claude mcp add --transport stdio my-server ./target/release/my-mcp-server
claude mcp add --transport http remote-api https://api.example.com/mcp
claude mcp add --transport stdio my-server --env API_KEY=xxx -- ./my-server --flag

# Manage servers
claude mcp list
claude mcp get my-server
claude mcp remove my-server
```

### In-Session Commands

| Command | Purpose |
|---------|---------|
| `/mcp` | Check server status |
| `@server:resource://path` | Reference a resource |
| Prompts appear as slash commands | Auto-discovered |

### Discovery and Connection Flow

At startup, Claude Code:

1. Merges configurations from all scopes
2. Prompts for approval of project-scoped servers (security measure)
3. For each server: spawns process (stdio) or connects to endpoint (HTTP)
4. Performs initialization handshake with version negotiation
5. Calls `tools/list` to discover tools
6. Registers tools for use

Servers supporting `listChanged` notifications can dynamically update their tool set without reconnection.

### Tool Search Optimization

When MCP tool definitions exceed **10% of context window**, Claude Code activates **Tool Search** (v2.1.7+):

- Builds lightweight index of tool names and descriptions
- Defers full tool definitions until needed
- Uses `MCPSearch` to discover 3-5 relevant tools on demand
- Achieves **~85% reduction in token overhead** (e.g., 77K → 8.7K tokens), and Opus 4 improved from **49% to 74%** accuracy with it enabled

### Key Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `MCP_TIMEOUT` | 30000 | Server startup timeout in milliseconds |
| `MAX_MCP_OUTPUT_TOKENS` | 25000 | Maximum tool output tokens (warning at 10000) |
| `CLAUDE_MCP_DEBUG` | unset | Enable detailed MCP debug logging |

### Debugging Tips

```bash
# Debug mode
claude --mcp-debug

# Check logs
cat ~/.claude/logs/mcp-debug.log
```

Always test manually in the terminal first. Use absolute paths in configuration. Rebuild and reconnect (Cmd-R / Ctrl-R) after code changes.
