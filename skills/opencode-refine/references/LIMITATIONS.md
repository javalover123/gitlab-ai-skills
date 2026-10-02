# Limitations Reference

## `question` Tool in Non-Interactive Runs

On OpenCode 2, `opencode run` cancels any question the agent asks. The `question`
tool call fails with an error saying the run cannot ask the user, and the agent
continues without an answer. The run does not hang, but the agent may guess or
stop short of the behavior you meant to test.

**Symptom:** a `question` tool call with an error status in `--format json`
output, or a response that asks you something.

**Workaround:** Write prompts that don't require clarification.

On OpenCode 1.x, the process can hang waiting for input instead. Wrap calls with
a timeout:

```bash
timeout 30 opencode run 'your prompt' || echo "Timed out: agent may have tried to ask a question"
```

On macOS, install coreutils (`brew install coreutils`) and use `gtimeout`.

## Permissions Depend on `opencode.json`

The behavior of shell-invoking prompts depends on your actual shell permission
configuration (`bash` in V1-style config, `shell` in V2 `permissions`). Inspect
the resolved permissions with:

```bash
opencode debug config | jq '.[].info.permissions'
```

Rules that resolve to `ask` are rejected automatically in `opencode run`. That
includes `ask` rules for file paths: a test prompt that reads a file guarded by
an `ask` rule fails unless you pass `--auto`.

## Config File Locations

`opencode` merges config from several sources. Settings in a config closer to
the working directory override matching settings from the global
`~/.config/opencode/opencode.json`. See the
[OpenCode config docs](https://opencode.ai/v2/docs/config/) for the full
precedence rules, including environment variables and managed settings.

List the sources that apply to a directory:

```bash
opencode debug config | jq -r '.[].path'
```

On OpenCode 1.x, run with `--print-logs` and search for `service=config` to see
which files are loaded.
