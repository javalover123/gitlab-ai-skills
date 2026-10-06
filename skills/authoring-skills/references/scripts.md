# Scripts, tools, and dependencies

Applies to anything under `scripts/` and to skills that drive CLIs or MCP tools.
For this repo's shell rules (`set -Eeuo pipefail`, shellcheck, tests) see the
root `AGENTS.md`.

## When to ship a script

Ship one when a step is deterministic, error-prone to regenerate, or checked
repeatedly. A pre-made script is more reliable than regenerated code, costs no
context tokens for its body (only its output), and behaves the same every run.
Prefer a validator script over prose for critical checks.

## Run or read?

Say which in the instructions:

- Run: "Run `scripts/analyze.sh input > fields.json` to extract fields."
- Read: "See `scripts/analyze.sh` for the extraction algorithm."

Document usage, flags, and output format next to the command. Paths are
relative to the skill root.

## Solve, don't defer

Handle expected errors in the script (missing file, bad permission, empty
input) with a clear message or a sane fallback instead of crashing and leaving
the agent to guess. Make validators verbose and specific so the agent can fix
the cause on the next loop.

## Justify constants

No unexplained magic numbers. If a timeout, retry count, or threshold exists,
comment why that value. If you can't justify it, the agent can't tune it.

## Verifiable output

For batch or high-stakes operations, have the script emit an intermediate plan
file, validate it, then apply (see *Workflows and feedback loops* in
`body-patterns.md`). Where inputs can be rendered as images, a render step lets
a vision-capable agent inspect layout.

## Dependencies and tools

- Never assume a package or CLI is installed: name it and give the install
  command, or say how to detect it.
- Some runtimes have no network or package installation *(Claude API sandbox)*;
  state such requirements in a body "Prerequisites" line (the repo's current
  `compatibility` convention is in `frontmatter.md`).
- Reference MCP tools by fully qualified name, `ServerName:tool_name`
  *(Claude-specific syntax)*; in other agents use that agent's naming. Unqualified
  names fail when several servers are connected.
- Check tool-name casing against the server docs.
