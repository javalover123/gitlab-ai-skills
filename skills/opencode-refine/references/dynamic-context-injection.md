# Dynamic context injection

### Dynamic context injection (DCI)

Claude Code can run a shell command at skill-load time and splice its output into
the `SKILL.md`. Write `` !`command` `` inline (the `!` must be at the start of a
line or after whitespace) or a ` ```! ` fenced block for multi-line commands. See
the [Claude Code docs](https://code.claude.com/docs/en/skills#inject-dynamic-context).

- **Use it for context that goes stale** — CLI `--help` output, version strings,
  environment info. It replaces a hand-maintained flag list with the live one.
- **Safe for multi-agent.** On non-Claude-Code agents (OpenCode, pi) the markup
  isn't expanded; the agent sees the literal placeholder and runs the command
  itself. Validated across haiku/sonnet/opus with zero hallucinations.
- **Use judgment.** Inject where help output replaces a manually-maintained list.
  Keep non-discoverable gotchas/traps (confusing arg order, wrong-flag warnings)
  as **static** text — a `--help` dump won't surface them.
- **Mind the length budget.** If injecting help would push a `SKILL.md` over the
  150-line ceiling, put the DCI in a reference file and link to it instead.

