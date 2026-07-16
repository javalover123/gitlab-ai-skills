import type { Plugin } from "@opencode-ai/plugin"
import { existsSync, readFileSync, readdirSync } from "node:fs"
import { homedir } from "node:os"
import { join } from "node:path"

/**
 * skill-hooks — a generic bridge that ties Claude Code-style skill hooks
 * into opencode's event listener.
 *
 * Claude Code lets a skill declare `hooks:` in its SKILL.md frontmatter
 * (SessionStart, PreToolUse, Stop, ...) that run shell commands at fixed
 * lifecycle points. opencode has no equivalent, so skills that depend on
 * those loops (autonomous completion loops, context watchdogs, session
 * handovers) don't work out of the box.
 *
 * This plugin closes that gap WITHOUT hardcoding any skill. A skill opts in
 * by shipping a `hooks.json` manifest next to its SKILL.md:
 *
 *   skills/<name>/hooks.json
 *   {
 *     "SessionStart": [{ "command": "python3 scripts/session-start.py" }],
 *     "PreToolUse":   [{ "command": "python3 scripts/watchdog.py", "timeout": 30 }],
 *     "Stop":         [{ "command": "python3 scripts/check-completion.py" }]
 *   }
 *
 * The plugin discovers manifests across the skill roots, maps each Claude
 * hook type onto the nearest opencode event, and runs the declared command
 * with the same stdin/stdout JSON contract Claude Code uses. See
 * doc/skill-hooks.md for the full contract.
 *
 * Hook-type -> opencode event mapping:
 *   SessionStart -> session.created (fires once when a session starts)
 *   PreToolUse   -> the `tool.execute.before` hook (fires before each tool)
 *   Stop         -> session.idle       (fires when the agent stops working)
 *
 * Safety:
 *   - SESSION-SCOPED GATING. A skill's hooks only run when THAT skill was
 *     loaded in the current session (detected from the transcript). A
 *     session that never loaded a hook-bearing skill is never touched. This
 *     stops project-scoped state left by one session from hijacking idle
 *     events in unrelated sessions.
 *   - Fails open on every error path: a missing manifest, an unreadable
 *     transcript, a crashing command, or a malformed result can never wedge
 *     or hijack a session.
 *   - Re-entrancy guard on the Stop loop so re-prompts can't stack faster
 *     than the agent works.
 *   - Kill switch: OPENCODE_SKILL_HOOKS=0 disables the plugin entirely.
 *   - OPENCODE_SKILL_HOOKS_NOGATE=1 bypasses session gating (legacy: run
 *     every discovered hook regardless of what the session loaded). Only
 *     useful when the message API is unavailable; not recommended.
 *   - OPENCODE_SKILLS_DIR points at the skill root explicitly.
 */

type HookType = "SessionStart" | "PreToolUse" | "Stop"

interface HookSpec {
  command: string
  timeout?: number
}

type HookManifest = Partial<Record<HookType, HookSpec[]>>

interface StopResult {
  decision?: "block" | "approve"
  reason?: string
}

const DEFAULT_TIMEOUT_MS = 60_000

/**
 * Candidate roots that may contain `<skill>/hooks.json`. Ordered
 * most-specific to most-global so an in-repo install wins over a user-wide
 * one. Mirrors the resolution order used by the skill distribution layout
 * (`.opencode/skills`, `.agents/skills`) plus the common global locations.
 */
function skillRoots(targetProject: string): string[] {
  const home = homedir()
  const roots = [
    process.env.OPENCODE_SKILLS_DIR,
    join(targetProject, ".opencode", "skills"),
    join(targetProject, ".agents", "skills"),
    join(targetProject, ".claude", "skills"),
    process.env.XDG_CONFIG_HOME
      ? join(process.env.XDG_CONFIG_HOME, "opencode", "skills")
      : join(home, ".config", "opencode", "skills"),
    join(home, ".claude", "skills"),
    join(home, ".agents", "skills"),
  ]
  return roots.filter((r): r is string => Boolean(r))
}

/** Resolve a skill's directory across the candidate roots. */
function resolveSkillDir(skill: string, targetProject: string): string | null {
  for (const root of skillRoots(targetProject)) {
    const dir = join(root, skill)
    if (existsSync(join(dir, "hooks.json"))) return dir
  }
  return null
}

/** Read and parse a skill's hooks.json. Returns null on any error. */
function readManifest(skillDir: string): HookManifest | null {
  try {
    const raw = readFileSync(join(skillDir, "hooks.json"), "utf8")
    const parsed = JSON.parse(raw)
    if (parsed && typeof parsed === "object") return parsed as HookManifest
  } catch {
    // fall through
  }
  return null
}

export const SkillHooksPlugin: Plugin = async ({ client, $, directory, worktree }) => {
  const enabled = process.env.OPENCODE_SKILL_HOOKS !== "0"
  const gate = process.env.OPENCODE_SKILL_HOOKS_NOGATE !== "1"
  const root = worktree || directory || process.cwd()

  // Guard against re-entrancy on the Stop loop: when we re-prompt a session
  // it goes idle again, and we mustn't stack prompts faster than the agent
  // can work.
  const inFlight = new Set<string>()

  /**
   * The set of skills actually loaded in a session, derived from its
   * transcript. A skill is "active" when the session contains either a tool
   * part with `tool === "skill"` and `state.input.name === skill`, or a user
   * text part naming `/<skill>` (a slash invocation).
   *
   * Returns an empty set on any API or shape error — fail open to "nothing
   * active" so a transient failure never runs a hook the session didn't ask
   * for.
   */
  async function activeSkills(sessionID: string): Promise<Set<string>> {
    const active = new Set<string>()
    try {
      const res: any = await client.session.messages({ path: { id: sessionID } })
      const messages: any[] = res?.data ?? res ?? []
      if (!Array.isArray(messages)) return active
      for (const entry of messages) {
        const parts: any[] = entry?.parts ?? entry?.message?.parts ?? []
        const role: string = entry?.info?.role ?? entry?.role ?? ""
        for (const part of Array.isArray(parts) ? parts : []) {
          if (part?.type === "tool" && part?.tool === "skill") {
            const name = part?.state?.input?.name
            if (typeof name === "string") active.add(name)
          } else if (part?.type === "text" && role === "user") {
            const text: string = part?.text ?? ""
            const m = text.match(/(?:^|\s)\/([a-z0-9][a-z0-9-]*)(?:\s|$)/g)
            if (m) {
              for (const hit of m) active.add(hit.trim().slice(1))
            }
          }
        }
      }
    } catch {
      return active
    }
    return active
  }

  /**
   * Run every command a set of skills declares for a given hook type.
   * Returns the parsed results paired with their originating skill.
   */
  async function runHooks(
    hookType: HookType,
    skills: string[],
    payload: Record<string, unknown>,
  ): Promise<Array<{ skill: string; result: StopResult | null }>> {
    const out: Array<{ skill: string; result: StopResult | null }> = []
    for (const skill of skills) {
      const skillDir = resolveSkillDir(skill, root)
      if (!skillDir) continue
      const manifest = readManifest(skillDir)
      const specs = manifest?.[hookType]
      if (!specs || !Array.isArray(specs)) continue

      for (const spec of specs) {
        if (!spec?.command) continue
        const timeoutMs = (spec.timeout ? spec.timeout * 1000 : DEFAULT_TIMEOUT_MS)
        const hookInput = Buffer.from(
          JSON.stringify({ ...payload, source: "opencode", cwd: root, skill }),
        )
        try {
          // Commands are run relative to the SKILL dir so relative script
          // paths (scripts/foo.py) resolve, but with cwd forced to the
          // target project via CLAUDE_PROJECT_DIR so gap analysis inspects
          // the user's code, not the skills install.
          //
          // The `$` API has no timeout method, so enforce the spec's `timeout`
          // by racing the shell promise against a timer: whichever settles
          // first wins. A hung hook can't block the session past `timeoutMs`
          // (the losing shell process is left to exit on its own). A `TIMEOUT`
          // sentinel distinguishes the timeout branch from a real empty result.
          const shellPromise = $`sh -c ${`cd ${JSON.stringify(skillDir)} && ${spec.command}`} < ${hookInput}`
            .cwd(root)
            .env({ ...process.env, CLAUDE_PROJECT_DIR: root })
            .nothrow()
            .quiet()
          let timer: ReturnType<typeof setTimeout> | undefined
          const timeoutPromise = new Promise<"TIMEOUT">((resolve) => {
            timer = setTimeout(() => resolve("TIMEOUT"), timeoutMs)
          })
          const raced = await Promise.race([shellPromise, timeoutPromise])
          if (timer) clearTimeout(timer)
          if (raced === "TIMEOUT") {
            out.push({ skill, result: null })
            continue
          }
          const proc = raced as { stdout?: { toString(): string } }
          const stdout = proc.stdout?.toString().trim() ?? ""
          let result: StopResult | null = null
          if (stdout) {
            const lastJson = stdout
              .split("\n")
              .filter((l) => l.trim().startsWith("{"))
              .pop()
            if (lastJson) {
              try {
                result = JSON.parse(lastJson) as StopResult
              } catch {
                result = null
              }
            }
          }
          out.push({ skill, result })
        } catch {
          // A missing script or a crashing command must not break the
          // session. Record a null result and carry on.
          out.push({ skill, result: null })
        }
      }
    }
    return out
  }

  /** Which skills' hooks should run, after applying the session gate. */
  async function gatedSkills(sessionID: string): Promise<string[] | null> {
    if (!gate) return null // null = "all discovered", caller handles it
    const active = await activeSkills(sessionID)
    return [...active]
  }

  return {
    "tool.execute.before": async (input, _output) => {
      if (!enabled) return
      const sessionID: string | undefined = (input as any)?.sessionID
      if (!sessionID) return
      const skills = await gatedSkills(sessionID)
      // With the gate on and nothing active, there's nothing to run.
      if (skills !== null && skills.length === 0) return
      // PreToolUse hooks are advisory here: we run them for their side
      // effects (watchdog logging, context checks). We deliberately do NOT
      // let them block tool execution — opencode's before-hook can throw to
      // deny, but a third-party skill script shouldn't be able to wedge
      // every tool call. Failures are swallowed by runHooks.
      if (skills === null) return // NOGATE + PreToolUse would run on every tool for every skill; skip.
      await runHooks("PreToolUse", skills, {
        tool: (input as any)?.tool,
        session_id: sessionID,
      })
    },

    event: async ({ event }) => {
      if (!enabled) return

      // SessionStart -> session.created
      if (event.type === "session.created") {
        const sessionID: string | undefined = (event as any).properties?.info?.id
          ?? (event as any).properties?.sessionID
        if (!sessionID) return
        // A brand-new session has no transcript yet, so gating would always
        // yield empty. SessionStart is inherently "this session is starting",
        // so we skip the gate and run any manifest that declares SessionStart
        // ONLY when NOGATE is set; otherwise we defer to the first idle,
        // where the transcript reveals which skill loaded. This keeps a fresh
        // session that never loads a hook skill completely untouched.
        if (gate) return
        const discovered = await discoverAllSkills()
        await runHooks("SessionStart", discovered, { session_id: sessionID })
        return
      }

      // Stop -> session.idle
      if (event.type !== "session.idle") return
      const sessionID: string | undefined = (event as any).properties?.sessionID
      if (!sessionID) return
      if (inFlight.has(sessionID)) return

      let skills = await gatedSkills(sessionID)
      if (skills === null) skills = await discoverAllSkills()
      if (skills.length === 0) return

      const results = await runHooks("Stop", skills, { session_id: sessionID })
      for (const { skill, result } of results) {
        if (!result || result.decision !== "block") continue

        // A Stop hook wants another pass. Re-prompt the session with the
        // hook's reason — the same guidance the Claude Stop hook injects.
        inFlight.add(sessionID)
        try {
          await client.app.log({
            body: {
              service: "skill-hooks",
              level: "info",
              message: `re-engaging ${skill} Stop hook`,
              extra: { sessionID },
            },
          })
          await client.session.prompt({
            path: { id: sessionID },
            body: {
              parts: [
                {
                  type: "text",
                  text:
                    `[skill-hooks: ${skill}] The Stop hook reports work ` +
                    `remains. Do not stop. Continue now.\n\n${result.reason ?? ""}`,
                },
              ],
            },
          })
        } catch {
          // If re-prompt fails (session gone, server busy), drop the lock so
          // the next idle can retry rather than wedging the loop shut.
        } finally {
          inFlight.delete(sessionID)
        }
        // Only one hook drives a given idle; others run next idle.
        break
      }
    },
  }

  /**
   * Enumerate every skill that ships a hooks.json across the roots. Used
   * only in the NOGATE path; the gated path derives skills from the session
   * transcript instead.
   */
  async function discoverAllSkills(): Promise<string[]> {
    const found = new Set<string>()
    for (const rootDir of skillRoots(root)) {
      if (!existsSync(rootDir)) continue
      try {
        // readdirSync avoids a shell dependency and the platform-varying,
        // silently-failing behaviour of `ls` on unusual paths.
        for (const name of readdirSync(rootDir)) {
          if (existsSync(join(rootDir, name, "hooks.json"))) found.add(name)
        }
      } catch {
        // ignore unreadable root
      }
    }
    return [...found]
  }
}
