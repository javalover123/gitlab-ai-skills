---
name: gitlab-frontend-conventions
description: "Review and clean up frontend code in the GitLab monolith (Vue, Apollo, Jest/VTU/MSW, JS utilities) against rules distilled from real merge request reviews, fixing typical AI-generated slop such as scoped styles, imperative Apollo queries, reactive constants, hand-set Apollo data in specs, and defensive optional chaining. Use when writing or reviewing code under app/assets/javascripts, ee/app/assets/javascripts, spec/frontend or ee/spec/frontend, or when asked to unslop, lint the Vue, or prep a frontend MR for review. Not for MR sequencing, review workflow, or backend code."
version: 1.0.0
license: MIT
category: Development Workflow
compatibility: opencode
metadata:
  audience: gitlab-contributors
  origin: "Adapted from the 'unslop frontend' snippet by Angelo Rivera (michaelangeloio): https://gitlab.com/gitlab-org/orbit/knowledge-graph/-/snippets/5985527"
---

# GitLab Frontend Conventions

A rulebook for Vue, Apollo, Jest and utility code in `gitlab-org/gitlab`,
distilled from 100+ review comments by one frontend maintainer ("the reviewer"
in the references) across 20+ MRs, mostly Orbit and AI Catalog work. Nearly every
rule cites its source MR and note. Where this conflicts with the official
`doc/development/fe_guide/` and `testing_guide/` docs, the official docs win.
Detection counts and helper names are a snapshot (2026-04-23); re-run the
heuristics before trusting them.

Frontend code only: not for MR sequencing, review workflow, or backend code.

## When to Use

- Writing or reviewing `*.vue`, `*.js`, `*.ts` in `app/assets/javascripts/`
  or `ee/app/assets/javascripts/`.
- Writing Jest specs in `spec/frontend/`, `ee/spec/frontend/`, or any
  `msw_integration/` / `integration/` folder.
- AI-generated UI work about to land in a monolith MR.
- Triggers: "unslop", "lint the vue", "prep for frontend review".

## Confidence tags

Rules without a tag count as **hard** unless the adoption notes list them as
softened.

- **hard**: firmly adopted in the merged state, broadly applicable.
- **softened**: the reviewer withdrew or marked it non-blocking at least once;
  treat as a preference. See [adoption notes](references/adoption-notes.md).
- **stale in current master**: master still violates it; apply to new code,
  don't retro-fix large trees without discussion.

## Philosophy

1. Reactive is expensive. Put static things in `$options`.
2. Let Vue and Apollo do the work: methods fetch, computed shape, watchers react.
3. Stay inside Pajamas. Tailwind utilities and semantic tokens, not scoped styles.
4. Assert what users see. Integration tests touch the DOM, not `wrapper.vm`.
5. One responsibility per function. Red flags: two `try/catch`, many null
   guards, a `check*` that mutates.
6. Defaults over early returns: `(x || []).map` beats `if (!x) return []`.
7. Name for intent, not transport: `saveFoo`, not `saveFooViaGraphQL`.
8. Distrust `!== undefined` and defensive optional chaining.

## How to apply

1. Run the [detection heuristics](references/detection-heuristics.md) on the
   changed files: add the changed paths to each `rg` command (in #10, before
   the `|`; in #17, in place of `spec ee/spec`). Verify an anti-pattern really
   exists before "fixing" it.
2. Work through the [checklist](references/checklist.md) in order of impact;
   it points to the detailed rule (`§3.1` style IDs) for each fix.
3. Treat **softened** rules as non-blocking.
4. Report using the format in
   [output and sources](references/output-and-sources.md), citing the rule
   section and the source MR.

## Rule reference (load only the section you need)

| Rules | File |
|---|---|
| §1 Vue component authoring | [vue-components.md](references/vue-components.md) |
| §2 Pajamas, Tailwind, styling | [styling.md](references/styling.md) |
| §3 Apollo and GraphQL | [apollo-graphql.md](references/apollo-graphql.md) |
| §4 Reactivity and side effects | [reactivity.md](references/reactivity.md) |
| §5 Data transformation and utilities | [utilities.md](references/utilities.md) |
| §6 Tests (Jest, VTU, Apollo, MSW) | [testing.md](references/testing.md) |
| §7 Types and null handling, §8 architecture, §9 naming, §10 i18n | [types-architecture-naming.md](references/types-architecture-naming.md) |
| §11 When rules were softened | [adoption-notes.md](references/adoption-notes.md) |
| §12 Detection heuristics | [detection-heuristics.md](references/detection-heuristics.md) |
| §13 Auto-fix checklist | [checklist.md](references/checklist.md) |
| §14 Output format, §15 source MRs | [output-and-sources.md](references/output-and-sources.md) |

## Agent Guidelines

- Cite the rule ID for every finding. Don't cite IDs that don't exist; label
  findings outside the rulebook as such.
- Don't flag `this.$apollo.mutate`; only imperative `query()` calls are in scope.
- Prefer fixing the files the MR touches; flag, don't fix, unrelated code.

## Contributing Improvements

This skill started as a snippet by Angelo Rivera (link in `metadata.origin`).
This repository is now where to edit it; the original author may keep refining
it here. Bump `version` with any change.
