# §1. Vue component authoring

## Contents

- §1.1 Static values live in `$options`, not `computed` or `data`
- §1.2 Emit events in `kebab-case`, never colon-prefixed
- §1.3 Absolute positioning is a last resort
- §1.4 Split fat components by null-guard count
- §1.5 Don't wrap setters in no-op guards — the caller decides
- §1.6 Data-driven templates, not copy-pasted markup
- §1.7 Split v-if / v-else-if into `<template>` groups when same boolean gates several siblings
- §1.8 `has*` vs `show*` — name capability vs visibility correctly
- §1.9 Remove unused computeds entirely; don't leave scaffolding
- §1.10 Interactive controls must have real behavior
- §1.11 Event-listener arg guards belong at the emit site, not at every listener

## §1.1 Static values live in `$options`, not `computed` or `data`

**Rule.** Only use `computed` for values whose result depends on reactive
state. Constants, imported arrays, config objects, static translated strings,
and helpers that read module-level state only — all belong on the component
options object (any custom key sibling to `data`/`computed`), referenced as
`$options.<key>` in templates.

**Verbatim.**
- !227814 note 3171915371 (`explorer_graph_toolbar.vue:33`):
  > **Suggestion** If this is static, which it seems to be, there's no reason
  > to compute this here and make it reactive. Let's move it to the
  > `$options` of the component to pass it to the template only.
- !227814 note 3171915777 (`graph_explorer.vue:67`): "Not a computed! To
  Options we go!"
- !227814 note 3171915795: "Static value => To options!"
- !227814 note 3171915804: "Static value => To options!"
- !227814 summary (3171916100, item 3): "Only use computed properties for
  reactivity. Constants/hardcoded values should go in $options"
- !219578 note 3031081107 (`no_credits_empty_state.vue:30`): "**Suggestion**
  I am not sure why this is a computed. looking into this, there doesn't
  seem to be any reactive data? If I am correct, could we move this to
  `$options`?"

**Bad.**
```js
computed: {
  dimensionItems() {
    return DIMENSION_OPTIONS;  // never changes
  },
  isDarkMode() {
    return darkModeEnabled();  // not reactive to component state
  },
  editorOptions() {
    return { minimap: { enabled: false }, lineNumbers: 'on', ... };
  },
},
```

**Good.**
```js
export default {
  name: 'ExplorerGraphToolbar',
  dimensionItems: DIMENSION_OPTIONS,
  isDarkMode: darkModeEnabled(),
  editorOptions: { minimap: { enabled: false }, lineNumbers: 'on', ... },
  // ...
};
// template:  :items="$options.dimensionItems"
```

**Do.**
- Put imported constants, literal configs, `i18n: {}` translation blocks, and
  helper outputs with no reactive deps on the component options.
- Reference them in templates as `$options.<key>` or
  `$options.i18n.<key>` / `this.$options.i18n.<key>`.

**Don't.**
- Wrap a constant in `computed` "just in case" someone later makes it
  dynamic.
- Put `i18n: { ... }` translation blocks under `computed:` — they're static.
- Let a `computed` call `s__`/`__`/`sprintf`/`helpPagePath` with only literal
  inputs. If no `this.<reactive>` is referenced, it's not a computed.

**Detection heuristic (verified).**
- Grep `*.vue` for `computed: {` blocks, scan bodies for methods that do not
  contain `this.` — candidates for `$options` migration.
- For i18n specifically: `rg "computed:\s*\{" -A 10 -g '*.vue' | rg "s__\("`.

**Edge cases.**
- If the string genuinely depends on props or data
  (`sprintf(s__('Hello %{name}'), { name: this.name })`), a computed is
  correct.

**Adoption:** ADOPTED widely in !227814, !219578 final merged state. 5+
canonical in-tree examples: `kubernetes_pods.vue:233`, `your_work/app.vue:55`,
`credentials_filter_sort_app.vue:88`, `security_patch_upgrade_alert_modal.vue:135`,
`keep_latest_artifact_toggle.vue:101`.

## §1.2 Emit events in `kebab-case`, never colon-prefixed

**Rule.** Reserve `update:<prop>` for `v-model`/`.sync`-style two-way bindings.
Regular bubble-up events use kebab-case: `update-search-query`, not
`update:search-query`.

**Verbatim.** !227814 note 3171915352 (`explorer_graph_toolbar.vue:30`):
> **Nit** Stylistically, I don't think we tend to use the `:` for events
> emitting as we go with `kebab-case` so `update-search-query` would align
> with other events here.

**Bad.**
```js
emits: ['update:search-query', 'select-dimension'],
```
```vue
@input="$emit('update:search-query', $event)"
```

**Good.**
```js
emits: ['update-search-query', 'select-dimension'],
```

**Detection heuristic (verified — 0 hits in monolith, so this is preventative).**
- `rg "\$emit\(['\"][^'\"]*:" -g '*.vue'` — any colon inside an emit string
  not backed by a real two-way contract.
- Note: `@sm:`, `@md:`, `@lg:` are Tailwind container-query prefixes, not
  event bindings. Do not flag them.

**Adoption:** ADOPTED in !227814.

## §1.3 Absolute positioning is a last resort

**Rule.** Default to natural DOM flow + flex/grid. Use `gl-absolute` /
`position: absolute` only when the design genuinely overlays.

**Verbatim.** !227814 note 3171915390 (`explorer_graph_toolbar.vue:48`):
> **question** Do we really need this to be absolutely positioned? I will
> explore this locally when I can, but it's worth asking because AI tends to
> _love_ absolute positions, but we really should default to natural DOM
> flow whenever possible.

**Bad.**
```vue
<div class="gl-z-10 gl-absolute gl-left-0 gl-right-0 gl-top-0 gl-flex gl-items-center">
```

**Good.**
```vue
<div class="gl-flex gl-items-center gl-gap-2 gl-p-3">
```

**Detection heuristic (verified).**
- Smell (raw CSS): `rg 'position:\s*absolute' -g '*.vue' -g '!vendor/**'` —
  10 hits in monolith, most legitimate overlays. Audit each.
- Don't flag `gl-absolute` blanket — 125 legitimate uses. Flag
  `gl-absolute.*gl-(top|bottom|left|right)-0` combinations as load-bearing
  layout that likely could be flex/grid.

**Adoption:** ADOPTED in !227814 (absolute toolbar removed).

## §1.4 Split fat components by null-guard count

**Confidence:** stale in current master (Codex verified `graph_canvas.vue` still
carries multiple `if (!this.graph)` guards with a justifying comment — apply
to new code, don't retrofit without context).

**Rule.** If a component has more than two methods/watchers that start with
`if (!this.graph) return` (or similar), split it: a **parent** that owns and
fetches state, and a **child** rendered with `v-if="graph"` that assumes
data is present.

**Verbatim.**
- !227814 note 3171915668 (`graph_canvas.vue:48`):
  > **Thought** I feel like if there is no graph, we have a bit of a larger
  > issue. This is acting on a watch, which is not immediate, so it will
  > only ever runs after the initial mounted hook is called right? So what
  > are we guarding against? If the initial set operation failed, shouldn't
  > we handle it in the mount with a User error instead?
- !227814 note 3171915759: "So if this _can_ happen maybe we need this to
  become two components: one parent that sets the graph, and then we use a
  v-if=graph for the rendering."

**Bad.**
```js
watch: {
  selectedNodeId(id) {
    if (!this.graph) return;          // guard 1
    /* ... */
  },
  viewMode(mode) {
    if (this.graph) this.graph.setViewMode(mode);  // guard 2
  },
},
methods: {
  setFullData() {
    if (this.graph && this.nodes.length > 0) {     // guard 3
      this.graph.setData(this.nodes, this.edges);
    }
  },
},
```

**Good.**
```vue
<!-- parent.vue -->
<graph-canvas v-if="graph" :graph="graph" :selected-node-id="selectedNodeId" />
```
Child treats `this.graph` as guaranteed; owner handles init failure with a
visible error.

**Detection heuristic.**
- `rg -U 'if \(!?this\.\w+\)\s*return' -g '*.vue'` — count per file; 3+ in
  the same component = split candidate.

## §1.5 Don't wrap setters in no-op guards — the caller decides

**Confidence:** stale in current master (current `graph_canvas.vue` still
guards `setFullData()`/`addData()` internally — apply to new code; overlaps
with §1.4).

**Rule.** A setter should always perform its action. Push precondition checks
to the caller. Makes debugging much easier — a setter call in a log means
the set actually happened.

**Verbatim.** !227814 note 3171915753 (`graph_canvas.vue:103`):
> **Suggestion** I find methods that start with a potential no-op tends to
> cause more issues than it solves. The callers of this method should do
> the check themselves as to when to call the setter here, so the setter
> truly maps to -> When calls, set.

**Bad.**
```js
setFullData() {
  if (this.graph && this.nodes.length > 0) {
    this.graph.setData(this.nodes, this.edges);
  }
},
```

**Good.**
```js
setFullData() {
  this.graph.setData(this.nodes, this.edges);
},
// caller:
if (this.$refs.graphCanvas && this.nodes.length > 0) {
  this.$refs.graphCanvas.setFullData();
}
```

## §1.6 Data-driven templates, not copy-pasted markup

**Rule.** When the same element repeats with different copy/classes, model it
as an array and loop with `v-for`.

**Verbatim.**
- !227814 note 3171915453 (`explorer_hero_banner.vue:52`): "if the template
  is going to be exactly the same, let's make this data driven with an array
  of the buttons and then we loop over it to render the buttons."
- !227814 note 3171916036 (`schema_detail_panel.vue:82`): "**Suggestion**
  lots of duplication in the template, maybe more data driven here with:"
  (follows full `tableColumns` computed example)
- !227814 note 3171916020 (`node_detail_overlay.vue:52`): "**Suggestion** we
  can make this more functional and data driven"

**Bad.**
```vue
<gl-button variant="link">{{ s__('Orbit|CLI') }}</gl-button>
<gl-button variant="link">{{ s__('Orbit|REST API') }}</gl-button>
<gl-button variant="link">{{ s__('Orbit|MCP') }}</gl-button>
<gl-button variant="link" :href="learnMorePath">{{ s__('Orbit|Docs') }}</gl-button>
```

**Good.**
```js
$options: {
  resourceLinks: [
    { label: s__('Orbit|CLI'),      href: null },
    { label: s__('Orbit|REST API'), href: null },
    { label: s__('Orbit|MCP'),      href: null },
    { label: s__('Orbit|Docs'),     href: () => `${DOCS_URL}/user/orbit/` },
  ],
}
```
```vue
<gl-button
  v-for="link in $options.resourceLinks"
  :key="link.label"
  variant="link"
  :href="link.href"
>
  {{ link.label }}
</gl-button>
```

**Adoption:** ADOPTED in !227814 (`$options.resourceLinks`).

## §1.7 Split v-if / v-else-if into `<template>` groups when same boolean gates several siblings

**Rule.** When the same boolean gates 2+ sibling elements, wrap siblings in
a single `<template v-if>` and mirror with `<template v-else>` so branches
stay visibly paired.

**Verbatim.** !233053 note 3279866813 (`agent_plan.vue:87`):
> **Suggestion** `isEditing` is used in both branches, so I think we could
> have a more encompassing conditional templates for when not editing and
> when editing. That way the second branch can use v-else and stay in sync
> with the first.

**Bad.**
```vue
<h2 v-if="!isEditing">{{ title }}</h2>
<p  v-if="!isEditing">{{ description }}</p>
<button-row v-if="!isEditing" />
<form v-if="isEditing" @submit="save" />
<textarea v-if="isEditing" v-model="draft" />
```

**Good.**
```vue
<template v-if="!isEditing">
  <h2>{{ title }}</h2>
  <p>{{ description }}</p>
  <button-row />
</template>
<template v-else>
  <form @submit="save" />
  <textarea v-model="draft" />
</template>
```

## §1.8 `has*` vs `show*` — name capability vs visibility correctly

**Rule.** `has<Feature>` / `supports<Feature>` = "this component is capable
of X". `show<Feature>` / `is<Feature>Visible` = "currently render X" with
all other conditions already satisfied.

**Verbatim.** !226946 note 3177633200 (`ai_panel.vue:204`):
> **Suggestion** the name is a bit misleading here because this is more "Do
> we want a loading state for this page" right? so `showLoadingState` could
> be true, but we wouldn't be showing the skeleton loader because it's not
> currently loading?
> Should we name this `hasLoadingState`?

**Detection heuristic.**
- Any `show<X>` prop gated inside the template by a second condition
  (`v-if="showX && !loaded"`) is mis-named. Should be `hasX`.

**Adoption:** DEFERRED in !226946 (not renamed in the final state; the reviewer
posted late).

## §1.9 Remove unused computeds entirely; don't leave scaffolding

**Rule.** After inlining a one-liner computed or collapsing into
`v-bind="obj"`, delete the computed entry. Unused computeds rot.

**Verbatim.** !226946 note 3167726963 (`ai_panel.vue:181`):
> And then we could remove the computed altogether!

**Detection heuristic.**
- For each `computed: { foo() ... }` entry, grep the rest of the SFC for
  references to `foo` / `this.foo` / `{{ foo }}`. Zero hits = delete.

## §1.10 Interactive controls must have real behavior

**Confidence:** hard.

**Rule.** Any button, link-variant button, or other interactive control must
wire to a real action: `@click` handler, `href`, `:to`, or a directive like
`v-gl-modal`. Placeholder buttons that only look interactive ship confusion.

**Verbatim.** !227814 note 3171915453 (`explorer_hero_banner.vue:52`):
> **Suggestion - non blocking** These currently don't have any actions tied
> to them but they are buttons with link variant. So are we planning to
> add the actions later?

**Bad.**
```vue
<gl-button variant="link">CLI</gl-button>
<gl-button variant="link">REST API</gl-button>
<gl-button variant="link">MCP</gl-button>
```

**Good.**
```vue
<gl-link :href="cliDocsPath">CLI</gl-link>
<gl-button variant="link" @click="openRestDocs">REST API</gl-button>
<gl-button variant="link" :to="{ name: 'mcp-docs' }">MCP</gl-button>
```

**Do.**
- Wire every interactive control to a real action.
- If the action is "not yet implemented", use a `:disabled` state with a
  tooltip explaining the FF or timing — don't ship a live-looking button
  that does nothing.

**Don't.**
- Ship `<gl-button variant="link">Label</gl-button>` with no `@click`,
  `href`, `:to`, or `v-gl-modal`.

**Detection heuristic.**
- `rg -n '<gl-button[^>]*variant="link"' -g '*.vue'` — then audit each hit
  for missing `@click` / `href` / `:to` / modal directive.

## §1.11 Event-listener arg guards belong at the emit site, not at every listener

**Confidence:** hard (the reviewer phrased as **Question** but the correctness framing is sharp).

**Rule.** If you find yourself writing `if (!node) return` at the top of a
`@node-selected` handler, the uncertainty belongs upstream. The emitter
either always sends a valid payload (drop every listener guard) or
sometimes sends `undefined` (fix the emitter). Don't scatter the guard.

**Verbatim.** !227814 note 3171915894 (`graph_explorer.vue:222`):
> **Question** seems odd that a listener might not have a defined event?
> shouldn't node be always defined?

**Bad.**
```js
// graph_canvas.vue (emitter)
methods: {
  onClick(node) {
    this.$emit('node-selected', node); // node may be undefined
  },
},
```
```js
// graph_explorer.vue (every listener has to guard)
methods: {
  handleNodeSelected(node) {
    if (!node) return;
    this.selectedNode = node;
    this.focusNode(node.id);
  },
},
```

**Good.**
```js
// graph_canvas.vue — guard once at the emit site, document the contract
export default {
  emits: {
    'node-selected': (node) => Boolean(node),
  },
  methods: {
    onClick(node) {
      if (!node) return;
      this.$emit('node-selected', node);
    },
  },
};
```
```js
// graph_explorer.vue — listener trusts the contract
methods: {
  handleNodeSelected(node) {
    this.selectedNode = node;
    this.focusNode(node.id);
  },
},
```

**Do.**
- Document the emit contract with an `emits: { 'name': (payload) => ... }`
  runtime validator.
- Put the `if (!value) return` once, at the emitter.
- Trust the contract on the listener side.

**Don't.**
- Pepper every `handleX` method with `if (!arg) return`. It spreads the
  uncertainty instead of killing it.

**Detection heuristic.**
- `ast-grep -p 'methods: { $HANDLER($ARG) { if (!$ARG) return; $$$ } }'`
  — sample each; most should move to the emit site or be deleted.
- `rg -n 'handle[A-Z]\w*\(\w+\)\s*\{[\s\n]*if\s*\(!' -g '*.vue'`

**Related.** §1.5 is about setter no-op guards (callee-side); this rule is
about event-listener guards (caller-side contract). Same spirit, different
code location.
