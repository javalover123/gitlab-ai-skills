# Usage Reference

Use this reference for quoting, temporary files, and command examples. Follow
[the skill](../SKILL.md) for execution decisions, output behavior, and timeouts.

## Quoting Rule

Only wrap the command in single quotes when it contains inner quotes or special
shell characters (`"`, `'`, `$`, `` ` ``, `\`). For simple commands with no
special characters, pass arguments directly. This produces cleaner command
patterns for permission matching.

```bash
# Simple command
run-in-tmux-pane mise doctor

# Command with inner quotes
run-in-tmux-pane 'claude -p "Hello, how are you?"'
```

## Temporary Files

- Use `$TMPDIR` for helper scripts and temporary files, falling back to `/tmp`
  when it is unset (`${TMPDIR:-/tmp}`).
- Do not guess a machine-specific temp directory.
- Expand temporary paths in the calling shell. The pane's login shell can set a
  different `$TMPDIR` from the agent's shell.
- Clean up temporary scripts after the command completes.

```bash
# Outer double quotes: the calling shell expands the path before the pane starts
run-in-tmux-pane "python3 '${TMPDIR:-/tmp}/my-script.py'"
rm -f "${TMPDIR:-/tmp}/my-script.py"
```

## Examples

```bash
# A tool that needs shims or PATH entries from the login shell
run-in-tmux-pane mise doctor

# A command that needs shell aliases or functions
run-in-tmux-pane gdk start rails

# A repository-specific function: select the checkout inside the command
run-in-tmux-pane 'cd /path/to/repo && my-push-function'

# A long-running command: raise the pane timeout and the shell tool timeout
TMUX_PANE_TIMEOUT=600 run-in-tmux-pane 'cd /path/to/repo && make test'
```
