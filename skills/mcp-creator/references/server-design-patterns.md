# Server Design Patterns

How to write effective server instructions, tool descriptions, and integrate with Claude Code's skill and hook systems.

## Server Instructions

Server instructions are the most powerful mechanism for teaching an AI assistant how to use your server. They're returned in the `instructions` field of the `initialize` response and get injected into the LLM's system prompt.

### What Instructions Should Cover

Focus on what tool schemas miss:

**Cross-feature relationships:**
```
Always call 'authenticate' before any 'fetch_*' tools.
The 'cache_clear' tool invalidates all 'fetch_*' results.
```

**Operational patterns:**
```
For best performance: use 'batch_fetch' for multiple items,
check 'rate_limit_status' before bulk operations.
Results are cached for 5 minutes.
```

**Constraints and limitations:**
```
File operations limited to workspace directory.
Binary files over 10MB will be rejected.
```

### Measured Impact

Testing on 40 PR review sessions showed server instructions improved workflow adherence from **60% to 85%** across models, with some models improving by +60 percentage points.

### Instruction Anti-Patterns

| Anti-Pattern | Why It's Bad |
|-------------|-------------|
| Repeating tool descriptions | Wastes tokens, already available from `tools/list` |
| Marketing language | Wastes tokens, confuses the model |
| Behavioral modification ("talk like a pirate") | Doesn't work reliably, wrong layer |
| Excessively long manuals | Exceeds context budget, dilutes key info |

## Writing Tool Descriptions

Tool descriptions serve **tool selection** (the LLM deciding which tool to use). Schema descriptions guide **proper usage** (constructing correct parameters).

### Description Best Practices

**Front-load important information** — agents may not read entire descriptions:

```
# BAD
This tool can be used for the purpose of creating a new channel
in the messaging system. It accepts various parameters...

# GOOD
Create a new messaging channel. Requires channel name and type.
```

**Use verb + resource structure:**

```
# BAD
"This tool is used for creating channels"

# GOOD
"Create a new channel"
```

**Specify workflow dependencies:**
```
Required workflow: Call discover_required_fields('Contact') first
to identify mandatory fields before calling create_contact.
```

**Disambiguate similar tools:**
```
List ALL calls in date range — no user/workspace filtering.
To filter by user/workspace, use search_calls_extensive instead.
```

### Naming Conventions

- Use **snake_case** for tool names — it tokenizes better for LLMs
- Keep names descriptive but concise
- Prefix related tools with a common noun (e.g., `channel_create`, `channel_delete`)
- Avoid dots, brackets, or spaces in names

### Schema Design

- Describe every parameter with `schemars(description = "...")` in Rust
- Include constraints (min/max values, allowed patterns)
- Provide examples for non-obvious parameter formats
- Be lenient in execution: advertise stricter schemas but accept variations

### Error Reporting

Return errors within the result object (with `isError: true`) rather than as protocol-level errors:

```rust
// GOOD - LLM can see and handle the error
Ok(CallToolResult::error(vec![
    Content::text("File not found: config.toml. Check the path and try again.")
]))

// BAD - protocol error, opaque to the LLM
Err(McpError::internal_error("file not found", None))
```

### Quality Research Findings

A study across **103 MCP servers / 856 tools** found that 97.1% of tool descriptions contain at least one quality issue. Most common problems:

| Issue | Frequency |
|-------|-----------|
| Unstated limitations | Very common |
| Missing usage guidelines | Very common |
| Opaque parameters | Common |
| No workflow context | Common |

## Claude Code Hooks Integration

Hooks are deterministic event handlers configured in `settings.json`.

### Key Hook Events

| Event | When It Fires | Can Block |
|-------|--------------|-----------|
| PreToolUse | Before tool calls | Yes (exit code 2) |
| PostToolUse | After tool completion | No |
| SessionStart | Session initialization | No (but can inject context) |
| Stop | Agent stop | Yes (can force continuation) |

Hooks receive JSON via stdin with session info, tool name, and tool input. Since v2.0.10+, hooks can modify tool inputs, enabling transparent sandboxing, security enforcement, and convention adherence.

MCP tool calls trigger PreToolUse/PostToolUse hooks — match on MCP tool names using the `matcher` regex field.

### Architectural Distinction

| Mechanism | Behavior | Reliability |
|-----------|----------|-------------|
| Hooks | Always execute (deterministic) | Guaranteed |
| Skills | Loaded by context match | Automatic expertise |
| CLAUDE.md/prompts | Suggestions | May or may not be followed |

## Tool Count and Token Budget

Tool definitions consume **50-100 tokens per tool** (schema) plus **100-200 tokens** (description). With 50+ tools, this can exceed 20K tokens.

When tool definitions exceed **10% of context window**, Claude Code activates **Tool Search** (v2.1.7+), which builds a lightweight index and uses semantic search (`MCPSearch`) to discover 3-5 relevant tools on demand, achieving ~85% reduction in token overhead.

**Design implication:** Keep your server focused. Expose only necessary tools rather than building a kitchen-sink server.
