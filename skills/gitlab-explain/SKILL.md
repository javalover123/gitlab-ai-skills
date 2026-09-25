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

## 2. Gather, structure, and diagram

Full detail — what to gather, the fixed 8-section order, and the Mermaid/Chart.js rules — is in
[references/workflow.md](references/workflow.md). Summary:

- Gather the ask (title, description, acceptance criteria, linked items) and the code reality
  (real files, verified to exist — a diagram with an invented path is worse than no diagram).
- Fill every section of the fixed template order or delete it; never reorder.
- One Mermaid `flowchart`, 3–7 nodes, every edge labelled with its mechanism, new/changed/
  reused/untouched stated in the node text. A Chart.js chart only when a real measured count
  earns it.

## 3. Write the file

```sh
OUT=/tmp/gitlab-explain; mkdir -p "$OUT"
D=<project-slug>; F=<issue|epic|mr>-<iid>.html
cp assets/explainer.html "$OUT/$D-$F"
```

Fill the placeholders with the `Edit` tool. `AUTHOR` is the person running the skill (`git config
user.name`), not the issue author. Keep the page under two screens of scroll (~2,000px at laptop
width); if it doesn't fit, the source item needs splitting, not smaller type. Keep the pinned CDN
script tags and their `integrity` attributes as they are.

## 4. Check before handing over

- Every file path and repo name verified to exist.
- Graph has labelled edges, 7 or less nodes, and an untouched node where that's true.
- Analogy stated *and* bounded (say where it breaks down).
- No `{{` left in the file: `grep -c '{{' <file>` prints `0`.
- A newcomer could say where they'd start reading code.
- No unexpanded acronym, no internal shorthand, no customer names.
- Confidential content: none, or explicit confirmation recorded in your report.

Open the file in a browser (or ask the operator to) and confirm the graph rendered — a Mermaid
syntax error renders as a visible error box, not silently.

## 5. Report

Three lines, nothing before them:

```
EXPLAINER: <path>
SOURCE:    <url> (<public | confidential, confirmed by operator>)
SAYS:      <one sentence — what a reader will take away>
```

Publishing the file anywhere (wiki, Pages, a shared doc) is a separate step this skill doesn't
take — hand the path to the operator and stop.
