// Regression tests for skill-hooks.ts session-scoped gating.
//
// `activeSkillsFrom` MIRRORS the transcript-parsing logic in `activeSkills()`
// in ../skill-hooks.ts. It exists so the gate can be tested without a live
// opencode server + model call. If you change the parsing in the plugin,
// mirror it here. Run: `node skill-hooks.test.mjs`
//
// The load-bearing case is `unrelated-session-empty`: a session that only ran
// non-hook tools must yield an empty active set so the gate returns without
// running any hook — the whole point of the session-scoped gate.

function activeSkillsFrom(messages) {
  const active = new Set()
  if (!Array.isArray(messages)) return active
  for (const entry of messages) {
    const parts = entry?.parts ?? entry?.message?.parts ?? []
    const role = entry?.info?.role ?? entry?.role ?? ""
    for (const part of Array.isArray(parts) ? parts : []) {
      if (part?.type === "tool" && part?.tool === "skill") {
        const name = part?.state?.input?.name
        if (typeof name === "string") active.add(name)
      } else if (part?.type === "text" && role === "user") {
        const text = part?.text ?? ""
        const m = text.match(/(?:^|\s)\/([a-z0-9][a-z0-9-]*)(?:\s|$)/g)
        if (m) {
          for (const hit of m) active.add(hit.trim().slice(1))
        }
      }
    }
  }
  return active
}

let pass = 0, fail = 0
function eq(name, got, want) {
  const g = [...got].sort().join(","), w = [...want].sort().join(",")
  if (g === w) { pass++; console.log(`ok   - ${name}`) }
  else { fail++; console.log(`FAIL - ${name}: got [${g}] want [${w}]`) }
}

// 1. skill tool load (envelope form)
eq("skill-tool-load", activeSkillsFrom([
  { info: { role: "assistant" }, parts: [{ type: "tool", tool: "skill", state: { input: { name: "iterate" } } }] },
]), new Set(["iterate"]))

// 2. slash invocation in user text
eq("slash-invocation", activeSkillsFrom([
  { info: { role: "user" }, parts: [{ type: "text", text: "please /bug-burndown the repo" }] },
]), new Set(["bug-burndown"]))

// 3. THE BUG CASE: session that only ran unrelated tools — no hook skill
eq("unrelated-session-empty", activeSkillsFrom([
  { info: { role: "user" }, parts: [{ type: "text", text: "the build seems stuck" }] },
  { info: { role: "assistant" }, parts: [{ type: "tool", tool: "bash", state: { input: { command: "ps aux" } } }] },
]), new Set())

// 4. assistant text mentioning /iterate must NOT activate (only user text)
eq("assistant-mention-ignored", activeSkillsFrom([
  { info: { role: "assistant" }, parts: [{ type: "text", text: "you could run /iterate next" }] },
]), new Set())

// 5. flat parts array (no envelope) with skill tool
eq("flat-parts-skill", activeSkillsFrom([
  { role: "assistant", parts: [{ type: "tool", tool: "skill", state: { input: { name: "spec-review" } } }] },
]), new Set(["spec-review"]))

// 6. malformed entries fail safe
eq("malformed-safe", activeSkillsFrom([null, { parts: "nope" }, {}, { parts: [{ type: "tool", tool: "skill" }] }]), new Set())

// 7. multiple skills across the session
eq("multi-skill", activeSkillsFrom([
  { info: { role: "assistant" }, parts: [{ type: "tool", tool: "skill", state: { input: { name: "iteratotron" } } }] },
  { info: { role: "assistant" }, parts: [{ type: "tool", tool: "skill", state: { input: { name: "bug-burndown" } } }] },
]), new Set(["iteratotron", "bug-burndown"]))

// 8. multiple slash invocations in one user message
eq("multi-slash", activeSkillsFrom([
  { info: { role: "user" }, parts: [{ type: "text", text: "/spec-review then /adr-review please" }] },
]), new Set(["spec-review", "adr-review"]))

console.log(`\n${pass} passed, ${fail} failed`)
process.exit(fail ? 1 : 0)
