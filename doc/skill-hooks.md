# Skill hooks (opencode)

Some skills need to run deterministic logic at fixed points in an agent's
lifecycle — a completion checker that keeps an autonomous loop going until the
work is actually done, a context watchdog, a session-start handover. Claude
Code supports this through a `hooks:` block in a skill's frontmatter. opencode
has no built-in equivalent.

The [`skill-hooks`](../.opencode/plugins/skill-hooks.ts) plugin bridges the gap.
It ties Claude Code-style hooks into opencode's event listener so the same
skill works in both tools without change. A skill opts in by shipping a
`hooks.json` manifest; the plugin discovers it, maps each Claude hook type onto
the nearest opencode event, and runs the declared command with the same
stdin/stdout JSON contract Claude Code uses.

## Opting in: `hooks.json`

Place a `hooks.json` next to the skill's `SKILL.md`:

```
skills/<name>/
├── SKILL.md
├── hooks.json          # opt-in hook manifest
└── scripts/
    └── check-completion.py
```

```json
{
  "SessionStart": [{ "command": "python3 scripts/session-start.py" }],
  "PreToolUse":   [{ "command": "python3 scripts/watchdog.py", "timeout": 30 }],
  "Stop":         [{ "command": "python3 scripts/check-completion.py" }]
}
```

Each hook type maps to an array of specs so a skill can declare more than one.
A spec has:

| Field | Required | Meaning |
|-------|----------|---------|
| `command` | yes | Shell command, run with `cwd` = the skill directory (so `scripts/foo.py` resolves). |
| `timeout` | no | Seconds the plugin waits for the command before giving up on it and moving on. Defaults to 60. |

Commands run with `CLAUDE_PROJECT_DIR` set to the **target project**, so a
checker inspects the user's code, not the skills install.

## Hook types and event mapping

| Claude hook | opencode event | When it fires | Can drive a loop? |
|-------------|----------------|---------------|-------------------|
| `SessionStart` | `session.created` | Once, when a session starts | No |
| `PreToolUse` | `tool.execute.before` | Before each tool call | No (advisory only) |
| `Stop` | `session.idle` | When the agent stops working | **Yes** |

`Stop` is the load-bearing one. When its command returns `{"decision":
"block"}`, the plugin re-prompts the session with the hook's `reason`, so the
agent keeps going instead of returning to the user — the opencode equivalent of
Claude Code's Stop-hook loop.

## The command contract

A hook command reads a JSON object on **stdin** and prints a JSON object on
**stdout** (the last line beginning with `{` is used). Input:

```json
{
  "session_id": "ses_...",
  "source": "opencode",
  "cwd": "/abs/path/to/target/project",
  "skill": "<name>"
}
```

`PreToolUse` input also carries a `tool` field. opencode has no transcript path
to hand a checker, so transcript-based scans in a ported Claude checker should
degrade gracefully (no-op) when `transcript_path` is absent.

Output (only `Stop` output is acted on):

```json
{ "decision": "block", "reason": "3 gaps remain: ..." }
```

- `decision: "block"` — work remains; the plugin re-prompts the session.
- `decision: "approve"` (or any other value, or no output) — done; nothing
  happens.

A checker **must self-gate**: return `approve` unless its own project-scoped
state says the loop is genuinely active. The plugin's session gate is a second
line of defence, not a substitute.

## Safety model

The plugin fails open on every error path and is safe to ship enabled:

- **Session-scoped gating.** A skill's hooks only run when that skill was
  actually loaded in the current session (detected from the transcript — a
  `skill` tool call or a `/<name>` slash invocation). A session that never
  loaded a hook-bearing skill is never touched, so project-scoped state left by
  one session can't hijack idle events in another.
- **Fail-open.** A missing manifest, unreadable transcript, crashing command,
  or malformed result yields "do nothing" — never a wedged or hijacked session.
- **Re-entrancy guard** on the Stop loop stops re-prompts stacking faster than
  the agent works.
- **`PreToolUse` cannot block** tool execution; it runs for side effects only.

## Environment variables

| Variable | Effect |
|----------|--------|
| `OPENCODE_SKILL_HOOKS=0` | Disable the plugin entirely. |
| `OPENCODE_SKILLS_DIR=<dir>` | Point at the skill root explicitly (the dir containing `<skill>/hooks.json`). |
| `OPENCODE_SKILL_HOOKS_NOGATE=1` | Bypass session gating: run every discovered hook. Only for when the message API is unavailable; not recommended. |

## Skill-root resolution order

The plugin looks for `<skill>/hooks.json` in, most-specific first:

1. `$OPENCODE_SKILLS_DIR`
2. `<project>/.opencode/skills/`
3. `<project>/.agents/skills/`
4. `<project>/.claude/skills/`
5. `$XDG_CONFIG_HOME/opencode/skills/` (or `~/.config/opencode/skills/`)
6. `~/.claude/skills/`
7. `~/.agents/skills/`

## Testing

The gating logic has a standalone regression test that needs no opencode
server:

```bash
node .opencode/plugins/__tests__/skill-hooks.test.mjs
```

If you change the transcript-parsing in the plugin, mirror the change in the
test's `activeSkillsFrom` helper.
