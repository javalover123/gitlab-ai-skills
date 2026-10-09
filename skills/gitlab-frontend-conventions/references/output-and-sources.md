# §14. Output format when applying this skill

Report fixes in this exact shape so the user can scan quickly:

```
## Unslop pass

### Fixed
- §1.1 explorer_query_panel.vue:35 — moved static `editorOptions` to $options
- §2.1 graph_canvas.vue — deleted <style scoped>, migrated min-height to gl-min-h-[5rem]
- §6.9 no_credits_empty_state_spec.js — replaced toMatchSnapshot with 5 explicit assertions
- §3.1 graph_explorer.vue:126 — rewrote loadInitialGroups as smart query
- §5.1 node_detail_overlay.vue:50 — collapsed early-return into `(props || {}).map`
- §4.8 duo_agentic_chat.vue:371 — renamed checkCreditsAvailability → setOutOfCredits, dropped caller guard

### Flagged (not fixed — out of scope)
- §1.3 ai_panel.vue:112 — absolute positioning flagged; kept for designed overlay, non-fixed
- §6.12 AI catalog integration spec — mounts leaf page, should mount SPA root (follow-up)

### Rules considered but not applied
- §1.8 ai_panel.vue:204 showLoadingState — the reviewer softened this in !226946; left as-is
```

---

# §15. Source MRs (for MR comment justifications)

Pin these when referencing a rule in your own MR note.

**Vue component / Apollo / Tailwind:**
- `gitlab!227814` — Orbit data explorer (foundational; most rules here).
- `gitlab!229375` — Orbit data layer, Three.js utilities (decomposition).
- `gitlab!223639` — `creditsAvailable` GraphQL field (Apollo defaults, `check*`→`set*`).
- `gitlab!226946` — Session management via GraphQL vars (dom_utils, duplicate queries).

**Testing:**
- `gitlab!229296` — AI Catalog CRUD integration tests (integration discipline).
- `gitlab!219578` — Chat empty states refactor (snapshots, `$options`).
- `gitlab!230984` — MSW integration test setup (`assignRouter`, `fullMount`).
- `gitlab!231612` — MSW helper follow-up (eslint scope, naming).
- `gitlab!227738` — `expectActions` helper follow-up (state-hash assertion helpers).
- `gitlab!230071` — WI header locked info (FF-named describes, `not.toHaveBeenCalled`).

**Architecture / misc:**
- `gitlab!226722`, `gitlab!229721` — AI Panel router refactors (watcher `newVal !== oldVal`, switch over if/else).
- `gitlab!226933` — Work item `features` field (find vs get, optional chain intent).
- `gitlab!231689` — Work plan item initialization (widget nullable as gate, `ee_component`).
- `gitlab!231938` — Type-is-one-of token fix (inline minor variants).
- `gitlab!231769` — Duo SA flow trigger fix (test negative branches).
- `gitlab!222232` — Group secret mutations (presentational + wrapper split).
- `gitlab!225094` — VertexAI self-hosted model (trigger submit without `.prevent`).
- `gitlab!225106` — Note preview aria-labels (`toBe` primitives, array-join composition).
- `gitlab!233053` — AgentPlan empty state (v-if/v-else template grouping).

**Docs consulted:**
- `doc/development/fe_guide/graphql.md:1573-1608` — `createMockApollo` canonical pattern.
- `doc/development/testing_guide/frontend_testing.md:1736-1862` — Snapshots section.
- `doc/development/contributing/merge_request_workflow.md:76-87` — MR size guidance.
- `doc/development/fe_guide/dark_mode.md:24-42` — Semantic tokens vs `dark:` prefix.

**Reference spec paths:**
- `spec/frontend/__helpers__/mock_apollo_helper.js` — `createMockApollo` helper.
- `ee/spec/frontend/msw_integration/work_items/` — Canonical MSW integration pattern.
- `spec/frontend/msw_integration/test_helpers.js` — exports `assignRouter` and `fullMount`.
- `app/assets/javascripts/groups/your_work/constants.js:51-72` — String-enum tab pattern.
