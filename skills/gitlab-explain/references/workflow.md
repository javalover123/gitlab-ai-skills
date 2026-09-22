# Full workflow detail

## Gather

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

## Structure

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

## Diagrams and charts

- **Graph: Mermaid `flowchart`,** 3–7 nodes. More is two diagrams; split by concern. Label every
  edge with its mechanism (`GraphQL query`, `calls`, `enqueues`, `reads`). State new / changed /
  reused / untouched in the node text. Colour only through the template's `classDef` palette, one
  class per *kind* of thing; do not add colours. Never write `{{ }}` inside a Mermaid block —
  Mermaid reads it as a hexagon node.
- **Show what is untouched.** An untouched node is how the reader sees the blast radius, and how
  a reuse claim is proved rather than asserted.
- **Chart: Chart.js, optional.** Keep the chart only when a real count earns it (files per layer,
  MRs per stage, criteria covered vs. not). Fill `data` with the counts you measured, or delete
  the figure and the script block that draws it. Two numbers are a sentence, not a chart.
- **Sequence over time** (delivery path, rollout) uses the stepped rail, not a graph.
- Every colour used appears in the legend paired with a word; colour is never the only signal.
- A `figcaption` says what the reader should take away. A diagram nobody can summarise is
  decoration.
