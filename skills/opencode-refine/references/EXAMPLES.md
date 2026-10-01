# Examples Reference

Use this reference for concrete `opencode run` testing patterns. The examples
use OpenCode 2 flags; see [the skill](../SKILL.md#useful-flags) for OpenCode 1.x
differences.

## Write a Test Prompt

The prompt should be specific enough to trigger the exact behavior you want to
verify. Think of it as a test case.

```bash
# Bad: too vague, so the agent may ask a clarifying question (which hangs)
opencode run --standalone 'do something with files'

# Good: exercises the specific behavior and is self-contained
opencode run --standalone 'run ls -al and tell me what you see'
```

## Fast Loop

```bash
# Edit the config, skill, or prompt, then immediately test:
opencode run --standalone 'your test prompt'

# Use a small model for faster iterations (list models with `opencode models`)
opencode run --standalone -m <provider/small-model> 'your test prompt'
```

## Debug Config Loading

Server logs only reach `--print-logs` with `--standalone`.

```bash
opencode run --standalone --print-logs 'your test prompt' 2>debug.log
```

Review debug logs for:

- loaded config files
- applied permissions
- tool registry startup
- shell executions and exit codes

## Test Project-Specific Config

Each directory can have its own `opencode.json`. Run from that directory to
test it in context:

```bash
(cd ~/workspace/my-project && opencode run --standalone 'run git status')
```

## Refine a System Prompt

```bash
# Edit ~/.config/opencode/agent/your-agent.md, then test the behavior you changed:
opencode run --standalone 'what tools do you have access to?'
# Check: does the agent describe its environment correctly?

opencode run --standalone 'I need help with a task'
# Check: does the agent follow the collaboration style you defined?
```

## Test Permissions

After editing permission rules in `opencode.json`:

```bash
# If the shell permission resolves to "ask", the request is auto-rejected
opencode run --standalone 'run git status'

# --auto approves anything that is not explicitly denied
opencode run --standalone --auto 'run git status'
```

Use `--print-logs` to see which rules are applied, and see
[the limitations reference](LIMITATIONS.md#permissions-depend-on-opencodejson)
to inspect the resolved permissions.

## Multi-Turn Refinement

Use `--continue` to build context across multiple runs:

```bash
opencode run --standalone "I am working in directory ${TMPDIR:-/tmp}/myproject. Run git init there."
opencode run --standalone --continue 'now create a README.md and commit it'
opencode run --standalone --continue 'run git log and show me what happened'
```

## JSON Event Stream

`--format json` emits newline-delimited JSON events. Parse them with `jq`:

```bash
# Extract just the text response
opencode run --standalone --format json 'what is 2+2?' |
  jq -r 'select(.type == "text") | .part.text'

# Get token usage from a run
opencode run --standalone --format json 'run date' |
  jq -c 'select(.type == "step_finish") | .part.tokens'

# Capture the session ID for continuation
SESSION_ID=$(opencode run --standalone --format json 'set up scenario X' |
  jq -r 'select(.sessionID) | .sessionID' | head -n 1)
opencode run --standalone --session "$SESSION_ID" 'now test variation Y'
```

## Attach Files

```bash
opencode run --standalone -f /path/to/file.md 'summarize this file'

# Multiple files
opencode run --standalone -f file1.md -f file2.md 'compare these files'
```
