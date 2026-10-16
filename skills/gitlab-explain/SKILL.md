---
name: gitlab-explain
description: "Explain a GitLab issue, epic, or merge request to a competent reader with no context in the area: one sentence, a bounded analogy, a dependency graph, the layers and repos touched marked new/changed/reused/untouched, where the work happens, how we will know it worked, and what is out of scope. Produces one self-contained HTML page from a fixed template with Mermaid diagrams and optional Chart.js charts. Read-only against GitLab; writes one local file for review. Use when asked to explain an issue/epic/MR, make an explainer, brief someone new on a change, or produce a shareable overview for a reviewer, manager, or onboarding engineer."
version: 1.0.0
category: Documentation
license: MIT
compatibility: opencode
argument-hint: "<issue | epic | MR url or reference>"
metadata:
  audience: developers
  workflow: gitlab
---

# GitLab Explain

Assume the reader is competent but **new to this area**: they don't know which repo holds what,
what the subsystem is called internally, or why the change matters. No jargon without a
plain-language gloss, no acronym unexpanded, no "simply" or "just".

The output is one HTML file, copied from [assets/explainer.html](assets/explainer.html). Markdown
already lives on the issue; HTML exists for what markdown does badly: a labelled graph,
colour-coded ownership, a side-by-side layer table.

## 1. Input and the one irreversible mistake

`$ARGUMENTS` is one URL or reference: `group/project#123`, `group/project!456`, or `group&789` for
an epic. Fetch the item's `confidential` flag first (`glab issue view`, `glab mr view`, or
`glab api graphql` for epics).

**Confidential source → say so and stop** unless the operator names the audience and confirms. An
explainer is written to be shared; explaining a confidential ask into a shareable file is the one
mistake here that cannot be undone.

## 2. Gather

- **The ask.** Title, description, acceptance criteria, labels, linked items. For an epic, its
  child issues and their state. For an MR, the description, the diff stat, and the discussions.
- **The code reality.** Find the real files: entry points, resolvers, services, models, workers,
  specs. Prefer `git grep -n` and targeted reads in the checkout over browsing. **Verify every
  path you will name exists**; a diagram with an invented file is worse than no diagram.
- **Team memory, if available.** If your environment has a team lessons/knowledge-base skill
  loaded, check it for the group and cite what you use. Skip if none exists — nothing else
  depends on it.
- **Who owns what,** when the item spans groups: `CODEOWNERS` and the stage/group labels.

Do not fetch more than this. Live data belongs on GitLab; the explainer links back to it.

## 3. Structure

The template fixes the order. Fill every section or delete it; never reorder.

1. **In one sentence** — what changes, for whom, why anyone cares. No implementation words.
2. **Analogy** — one, concrete, *load-bearing*: it must map onto the actual structure so the
   reader can reason with it. **Say where it breaks down**; a half-true analogy nobody corrects
   becomes a wrong mental model.
3. **How the pieces connect** — the dependency graph (see Diagrams below).
4. **Where the code lives** — layer table with the real directory per layer, marked
   `+ new` / `~ changed` / `= reused, unchanged` / `= untouched`. Layers are whatever the repo
   has (browser → API → services → models → DB for a typical monolith; adapt for other repos).
   Keep only the rows the change touches or deliberately leaves alone: a backend-only fix has no
   Frontend row, and says so in the repos section instead.
5. **Repos and projects affected** — usually one. If only one, say so explicitly; readers assume
   distributed change until told otherwise.
6. **Where the work happens** — issue or epic: delivery order and what blocks what, one card per
   step or MR. MR, or an issue with a single MR already open: the order a reviewer should read
   the diff in.
7. **How we will know it worked** — acceptance criteria in plain language, each paired with the
   spec, job, or check that proves it.
8. **What this is not** — the out-of-scope list; half of understanding a change is its edges.

## 4. Diagrams and charts

- **Graph: Mermaid `flowchart`,** 3–7 nodes. More is two diagrams; split by concern. Label every
  edge with its mechanism (`GraphQL query`, `calls`, `enqueues`, `reads`). State new / changed /
  reused / untouched in the node text. Colour only through the template's `classDef` palette, one
  class per *kind* of thing; do not add colours. Never write `{{ }}` inside a Mermaid block —
  Mermaid reads it as a hexagon node.
- **Plain-text labels only.** The template renders labels as SVG text (`htmlLabels:false`) so
  Safari draws them the same as Chrome; `<br/>` is the only markup that works in a label.
- **Show what is untouched.** An untouched node is how the reader sees the blast radius, and how
  a reuse claim is proved rather than asserted.
- **Chart: Chart.js, optional.** Keep the chart only when a real count earns it (files per layer,
  MRs per stage, criteria covered vs. not). Fill `data` with the counts you measured, or delete
  the figure and the script block that draws it. Two numbers are a sentence, not a chart.
- **Sequence over time** (delivery path, rollout) uses the stepped rail, not a graph.
- Every colour used appears in the legend paired with a word; colour is never the only signal.
- A `figcaption` says what the reader should take away. A diagram nobody can summarise is
  decoration.

## 5. Write the file

Copy [assets/explainer.html](assets/explainer.html) to a new file named after the source item —
the project slug, the item type, and its IID, e.g. `/tmp/gitlab-explain/skills-mr-139.html`
(create the directory if needed). The exact location doesn't matter; report whatever path you used.

Fill the placeholders with the `Edit` tool. `AUTHOR` is the person running the skill (`git config
user.name`), not the issue author. Keep the page under two screens of scroll (~2,000px at laptop
width); if it doesn't fit, the source item needs splitting, not smaller type. Keep the pinned CDN
script tags and their `integrity` attributes as they are.

## 6. Check before handing over

- Every file path and repo name verified to exist.
- Graph has labelled edges, 7 or less nodes, and an untouched node where that's true.
- Analogy stated *and* bounded (say where it breaks down).
- No `{{` left in the file: `grep -c '{{' <file>` prints `0`.
- A newcomer could say where they'd start reading code.
- No unexpanded acronym, no internal shorthand, no customer names.
- Confidential content: none, or explicit confirmation recorded in your report.

Open the file in a browser (or ask the operator to) and confirm the graph rendered — a Mermaid
syntax error renders as a visible error box, not silently.

## 7. Report

Three lines, nothing before them:

```
EXPLAINER: <path>
SOURCE:    <url> (<public | confidential, confirmed by operator>)
SAYS:      <one sentence — what a reader will take away>
```

Publishing the file anywhere (wiki, Pages, a shared doc) is a separate step this skill doesn't
take — hand the path to the operator and stop.
