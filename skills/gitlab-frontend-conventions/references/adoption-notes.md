# §11. Review adoption notes (when the reviewer softened vs held firm)

Treat **softened** rules as preferences, not blockers. Treat **firmly
adopted** rules as hard requirements for new code.

**Firmly adopted (verified in final merged state):**
- Scoped styles → Tailwind (!227814 — zero `<style>` blocks remain)
- Static values → `$options` (!227814, !219578)
- Smart Apollo queries over imperative (!227814)
- Snapshots removed (!219578 — zero remain)
- `trigger()` over `.emit()` in integration specs (!229296)
- DOM utils extraction (!226946 `dom_utils.js`)
- Nested describe + beforeEach + terse it (!229296)
- Utility decomposition (!229375 most extractions landed)
- kebab-case events (!227814)
- Tab enum constants (!227814)
- Smart Apollo `result()` for side effects, `update()` for shape (!227814)

**Softened / explicitly deferred:**
- `hasCredits` default to `false` — the reviewer withdrew (!223639 note 3155526192)
- `hasLoadingState` vs `showLoadingState` rename — not landed (!226946)
- Drop optional chaining in show page — the reviewer marked non-blocking (!226946 note 3187545598)
- Some class-method decomposition in `three_graph.js` — the reviewer's examples
  framed as "AI-made illustrations", not all landed (!229375 note 3204025050)
- Full `wrapper.vm.$toast` removal in integration — accepted as "next
  iteration" pending jsdom toast support (!229296 note 3240928243)
- `mockClear` removal in !223639 — not adopted, not reopened
