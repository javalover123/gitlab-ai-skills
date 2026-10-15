# §5. Data transformation / utilities

## Contents

- §5.1 Sane defaults over early returns
- §5.2 `forEach` is for side effects, not transformations
- §5.3 Avoid double defaults
- §5.4 Break large utility files into single-responsibility helpers
- §5.5 Animation/tick loops should be thin dispatchers
- §5.6 Split data preparation from side effects (CSV / download case)
- §5.7 Hard `typeof` checks at utility entry points
- §5.8 JSDoc every exported factory with pipeline context
- §5.9 Inline minor variants, factor only differing values
- §5.10 String composition: `[parts].filter(Boolean).join(' ')`
- §5.11 Find vs Get — array vs object convention
- §5.12 Presentational components don't consume domain context; wrap
- §5.13 Extract unreadable inline helper calls into named computeds
- §5.14 Name inline numeric literals as module-scope constants

## §5.1 Sane defaults over early returns

**Rule.** `(x || []).map(...)` beats `if (!x || x.length === 0) return []`.
Both branches produce the same shape — let the functional API handle it.

**Verbatim.**
- !227814 summary 3171916100 item 4: "Data processing on the client side
  is much safer when we don't hard return out of conditions. It may be
  required in a few places, but overall preferring `(myData || []).map`
  over `if(!myData || myData.length === 0) return []`"
- !227814 note 3171916011: "we often just want to use sane defaults as
  value and let the functional methods like `map, reduce, filter` to
  operate either on the whole data or the empty array instead of doing the
  early returns."

**Bad.**
```js
sidebarProperties() {
  if (!this.node?.properties) return {};
  const display = {};
  Object.entries(this.node.properties).forEach(([k, v]) => {
    if (v !== null && v !== undefined && v !== '') display[k.replace(/_/g, ' ')] = v;
  });
  return display;
},
```

**Good.**
```js
sidebarProperties() {
  return Object.fromEntries(
    Object.entries(this.node?.properties || {})
      .filter(([, v]) => v !== null && v !== undefined && v !== '')
      .map(([k, v]) => [k.replace(/_/g, ' '), v]),
  );
},
```

## §5.2 `forEach` is for side effects, not transformations

**Rule.** Building a new array/object? Use `.map` / `.filter` / `.reduce` /
`Object.fromEntries`. `.forEach` with an outer `const result = []` is a
tell that you should be using `.map`.

**Verbatim.** !227814 summary 3171916100 item 5:
> data transformation rarely should use `forEach`. If it's truly "for each"
> value then `.map` is better and if we filter then either .map + filter or
> reduce.

## §5.3 Avoid double defaults

**Rule.** Don't mix "funnel missing key into `'default'`" with "fall back
to `.default`". Pick one strategy.

**Verbatim.** !227814 note 3171915488:
> **Suggestion** this feels more complex than it needs to be. The second
> half especialyl, we either use the key _or_ the `.default` property but
> we already use default as a fallback to the key variable?

**Bad.**
```js
const key = (this.node.type || 'default').toLowerCase();
return this.entityColors[key] || ENTITY_TYPE_COLORS[key] || ENTITY_TYPE_COLORS.default;
```

**Good.**
```js
const key = this.node.type?.toLowerCase() || 'default';
return this.entityColors[key] || ENTITY_TYPE_COLORS[key];
```

## §5.4 Break large utility files into single-responsibility helpers

**Rule.** A 200-line util function doing "group + filter + compute + place"
is un-reviewable. Split at every comment boundary.

**Verbatim.** !229375 note 3204024614 (`graph_layout.js:174`):
> **Suggestion** I do think these type of data factory functions need to
> be extremely lean and single purposed, with a lot of chaining or we risk
> being unable to test them and maintain them properly.

**Bad: one 50-line function doing three things.**

**Good: three named helpers + a 5-line orchestrator.**
```js
function groupNodesByType(nodes) { /* ... */ }
function buildUnknownTypeIndex(types) { /* ... */ }
function placeClusterRing(nodes, indices, center) { /* ... */ }

export function placeNodeClusters(nodes) {
  const groups = groupNodesByType(nodes);
  const unknownIndex = buildUnknownTypeIndex(Object.keys(groups));
  for (const [type, indices] of Object.entries(groups)) {
    const center = resolveCenter(type, unknownIndex);
    placeClusterRing(nodes, indices, center);
  }
}
```

Same pattern applied in !229375: `computeFlatLayout` split into
`buildSimulationInput` → `runD3Simulation` → `scaleSimResultsToNodes`.
`createArcCurve` split into `angleBetween` + `createShortArc` +
`buildArcControlPoints`. `buildConnections` split into
`clearConnectionGroups` + `makeEdgeKey` + `createEdgeLine` +
`createDirectionalArrow` + `buildConnection`.

**Note.** The reviewer's !229375 note 3204025050: "all of the code examples to
break the code smaller is AI made, so to be taken with some grain of salt,
it was more so that I could give quick examples to illustrate what we
could do, but feel free to diverge." — take the decomposition *boundaries*
as the rule, not the exact names/shapes.

**Adoption:** ADOPTED for utilities in !229375; partial for class methods
(`three_graph.js` kept some large methods — non-blocking "Thought"s).

## §5.5 Animation/tick loops should be thin dispatchers

**Rule.** Any function called from `requestAnimationFrame` should do one
thing: register the next frame, dispatch to `tickX()` helpers, and call
renderer. No inline geometry, no inline per-object caches.

**Verbatim.** !229375 note 3204024936:
> Looking at the file content I already have, `runAnimation` does three
> distinct things: 1. Advancing impulse particles along their curves
> 2. Auto-rotating the globe when idle in 3D mode 3. Counter-scaling node
> labels in 2D mode to stay readable at any zoom.

## §5.6 Split data preparation from side effects (CSV / download case)

**Rule.** If a function name contains "and" (or could), split it. The pure
half is unit-testable without DOM; the side-effect half is a thin wrapper.

**Verbatim.** !229375 note 3204024529 (`csv_export.js:12`):
> **thought** The _and_ in the description makes me think, should this be
> a combination of two different utils: a query response data transform,
> and then the download triggered? From a testing PoV and general
> maintenance, I'd like to keep the data preparation and the actual
> download separated.

**Adoption:** ADOPTED in !229375 (`prepareCsvRows` + `triggerCsvDownload` +
composed `downloadCsv`).

## §5.7 Hard `typeof` checks at utility entry points

**Rule.** Exported utilities with concrete type contracts should throw
`TypeError` with the offending `typeof` in the message. Prevents silent
coercion of garbage.

**Verbatim.** !229375 note 3204024570 (`graph_layout.js:137`):
> Do you think we should do hard type checks here with `typeof` and throw
> with invalid ones?

**Good.**
```js
export function runBFS(startIndex, adjacencyMap) {
  if (typeof startIndex !== 'number') {
    throw new TypeError(`runBFS: startIndex must be a number, got ${typeof startIndex}`);
  }
  if (!(adjacencyMap instanceof Map)) {
    throw new TypeError('runBFS: adjacencyMap must be a Map');
  }
  // ...
}
```

## §5.8 JSDoc every exported factory with pipeline context

**Rule.** A module-level JSDoc summarizing the pipeline, plus per-function
JSDoc with "where in the pipeline" + "why" + `@mutates` when applicable.

**Verbatim.** !227814 note 3171916057:
> **Concern** Do we really want to maintain all of this data processing?
> At the minimum, we should JSDOC each function with a rational of _how_ we
> parse the data and where in the data pipeline it sits and why.

**Good.**
```js
/**
 * Groups nodes by entity type and places each cluster around its
 * assigned lat/lng anchor on the sphere.
 * Pipeline stage: 2 of 3 (after anchors resolved, before adjacency built).
 * @mutates nodes — positions are set in place for performance.
 */
export function placeNodeClusters(nodes) { /* ... */ }
```

## §5.9 Inline minor variants, factor only differing values

**Rule.** Two branches producing the same object except for one property?
Build one object and conditionally set that property.

**Verbatim.** !231938 note 3262476881 (`planning_view.vue:835`):
> **Suggestion** Both tokens are the same albeit the operator. We can
> probably inline it.

**Bad.**
```js
if (ff) tokens.push({ type, title, icon, operators: A });
else    tokens.push({ type, title, icon, operators: B });
```

**Good.**
```js
tokens.push({ type, title, icon, ...(ff ? {} : { operators: OPS_IS_NOT_OR }) });
```

## §5.10 String composition: `[parts].filter(Boolean).join(' ')`

**Rule.** Prefer array-filter-join over nested ternaries inside template
literals for composite strings.

**Verbatim.** !225106 note 3143100573 (`note_actions.vue:274`):
> WDYT of using an array to store each part of the string, and then combine
> them at the end with `join`?

**Bad.**
```js
`${a}${b ? `, @${b}` : ''}${c}`
```

**Good.**
```js
[a, b && `@${b}`, c].filter(Boolean).join(', ');
```

## §5.11 Find vs Get — array vs object convention

**Rule.** `findX` prefix is for array traversal (`findAssignees`). For
direct object property access, use `getX` or drop the wrapper entirely and
access the property directly if the type supports it.

**Verbatim.** !226933 note 3155548186:
> I would at least rename this as `find` is array heavily connoted to
> Array structures, and instead `get` prefixes, and then we make them have
> really good error handling and defaults!

**Bad.** `findAssigneesWidget(this.workItem)?.assignees`
**Good.** `this.workItem?.features?.assignees` (nullable field IS the
"is supported" check).

## §5.12 Presentational components don't consume domain context; wrap

**Rule.** If a Vue component behaves differently for Admin/Group/Project
scope, do NOT plumb `isGroup`/`isProject` props through it. Keep the
presentational component pure; create thin wrappers
(`GroupSecretForm.vue`, `ProjectSecretForm.vue`) that inject domain
behavior via props.

**Verbatim.** !222232 note 3076274791 (`secret_form.vue:78`):
> **Thought** When we have vue components that need to behave differently
> for Admin/Group/Project level, it becomes a high maintenance burden to
> have your presentational components having to get access to _context_
> as opposed to data. […] We could instead extract everything that is
> specific to the domain (project/group) and put it in a wrapper that
> does all of the domain specific logic. Then this wrapper renders the
> shared component.

## §5.13 Extract unreadable inline helper calls into named computeds

**Confidence:** hard.

**Rule.** When an inline helper call (`...cloudPlatformFormFields(this.X)`)
inside an object literal or template expression makes the surrounding
shape hard to scan, bind the helper result to a named computed first.

**Verbatim.** !225094 note 3128213672 (`self_hosted_model_form.vue:191`):
> the formatting here is a bit crazy and makes this hard to read.

**Bad.**
```js
computed: {
  formFields() {
    return {
      ...baseFormFields,
      ...cloudPlatformFormFields(this.cloudPlatformIdentifierPrefix),
    };
  },
}
```

**Good.**
```js
computed: {
  cloudPlatformFields() {
    return cloudPlatformFormFields(this.cloudPlatformIdentifierPrefix);
  },
  formFields() {
    return {
      ...baseFormFields,
      ...this.cloudPlatformFields,
    };
  },
}
```

**Do.**
- Name the helper result once when the inline call obscures the return
  shape.
- Keep the tiny one-liners inline if they're genuinely one-line and obvious.

**Don't.**
- Force reviewers to parse nested helper calls inside a large return
  object.

**Detection heuristic.**
- `rg -n '\.\.\.[A-Za-z_][A-Za-z0-9_]*\(this\.[A-Za-z_][A-Za-z0-9_]*\)' -g '*.vue'`

## §5.14 Name inline numeric literals as module-scope constants

**Confidence:** hard. Recurs implicitly in every !229375 decomposition note —
every rewrite the reviewer proposed turned raw numbers (`0.001`, `0.5`, `300`,
`0x999999`) into `UPPER_SNAKE_CASE` identifiers at module scope.

**Rule.** Any numeric literal that encodes a threshold, a tuning factor, a
scale multiplier, a frame budget, an opacity, a color, or a timeout gets a
name. Put the name at module scope, not inside the function. Let the
function body read as math over named quantities.

**Verbatim illustrations** (sampled from the reviewer's rewrites in !229375 — all
AI-generated sketches, but the renaming intent is consistent across every
note):

- !229375 note 3204024614 (`graph_layout.js:174`):
  > `const r = CLUSTER_SPREAD * spreadScale * (CLUSTER_RADIUS_MIN + Math.random() * CLUSTER_RADIUS_VARIANCE);`

- !229375 note 3204024657 (`graph_layout.js:307`):
  > `return d > OVERLAP_THRESHOLD ? normalize({…}, 1) : normalize({…}, 1);`
  > `const pushStrength = (MIN_NODE_DISTANCE - d) * REPULSION_PUSH_FACTOR + REPULSION_PUSH_MIN;`

- !229375 note 3204024692 (`graph_layout.js:316`):
  > `.distance(SPHERE_RADIUS * D3_LINK_DISTANCE_FACTOR)`
  > `.strength(nodeCount < D3_SMALL_GRAPH_THRESHOLD ? D3_CHARGE_SMALL : D3_CHARGE_LARGE)`
  > `for (let i = 0; i < D3_SIMULATION_TICKS; i += 1) simulation.tick();`

- !229375 note 3204024744 (`three_edges.js:47`):
  > `const numSegments = angle > Math.PI / 2 ? ARC_LONG_THRESHOLD_SEGMENTS : ARC_SHORT_THRESHOLD_SEGMENTS;`

- !229375 note 3204024789 (`three_edges.js:172`):
  > `opacity: darkMode ? EDGE_OPACITY : LIGHT_MODE_EDGE_OPACITY,`
  > `new THREE.ConeGeometry(ARROW_RADIUS, ARROW_HEIGHT, ARROW_RADIAL_SEGMENTS)`
  > `const connectionColor = darkMode ? CONNECTION_COLOR_DARK : CONNECTION_COLOR_LIGHT;`

- !229375 note 3204024891 (`three_graph.js:381`):
  > `maxExtent / Math.tan(fovRad) + CAMERA_2D_FIT_PADDING`
  > `CAMERA_DEFAULT_Z * CAMERA_2D_MIN_FIT_FACTOR`

- !229375 note 3204024936 (`three_graph.js:490`):
  > `if (idleTime > IDLE_TIMEOUT_MS && !this.selectedNode && this.viewMode === '3d') {`

**Bad.**
```js
// graph_layout.js
const d = distance(nodes[a].position, nodes[b].position);
if (d < 0.05) {
  const pushStrength = (0.05 - d) * 0.5 + 0.01;
  const na = normalize(nodes[a].position, 1);
  const nb = normalize(nodes[b].position, 1);
  const pushDir = d > 0.001 ? { /* ... */ } : { /* ... */ };
  // ...
}

const simulation = forceSimulation(simNodes)
  .force('link', forceLink(simLinks).distance(SPHERE_RADIUS * 0.6))
  .force('charge', forceManyBody().strength(nodes.length < 15 ? -100 : -200))
  .force('collide', forceCollide(SPHERE_RADIUS * 0.2).strength(1))
  .stop();
for (let i = 0; i < 300; i += 1) simulation.tick();

opacity: darkMode ? 0.7 : 0.999999,
color: darkMode ? 0xffffff : 0x999999,
```

**Good.**
```js
// graph_layout.js — module scope, above the first function
const MIN_NODE_DISTANCE        = 0.05;
const OVERLAP_THRESHOLD        = 0.001;
const REPULSION_PUSH_FACTOR    = 0.5;
const REPULSION_PUSH_MIN       = 0.01;

const D3_LINK_DISTANCE_FACTOR  = 0.6;
const D3_COLLIDE_RADIUS_FACTOR = 0.2;
const D3_SMALL_GRAPH_THRESHOLD = 15;
const D3_CHARGE_SMALL          = -100;
const D3_CHARGE_LARGE          = -200;
const D3_SIMULATION_TICKS      = 300;

// three_edges.js / three_graph.js
const EDGE_OPACITY             = 0.7;
const LIGHT_MODE_EDGE_OPACITY  = 0.999999;
const CONNECTION_COLOR_DARK    = 0xffffff;
const CONNECTION_COLOR_LIGHT   = 0x999999;
```

Function bodies then read as math:
```js
const d = distance(nodes[a].position, nodes[b].position);
if (d < MIN_NODE_DISTANCE) {
  const pushStrength = (MIN_NODE_DISTANCE - d) * REPULSION_PUSH_FACTOR + REPULSION_PUSH_MIN;
  const dir = d > OVERLAP_THRESHOLD ? /* ... */ : /* ... */;
}

for (let i = 0; i < D3_SIMULATION_TICKS; i += 1) simulation.tick();
```

**Do.**
- Extract thresholds, tuning factors, tick counts, timeouts, opacities,
  colors, and camera values to module-scope `const` bindings before they
  appear in the function body.
- Use `UPPER_SNAKE_CASE` for the constant, and name by role (`IDLE_TIMEOUT_MS`,
  `D3_SIMULATION_TICKS`, `AUTO_ROTATE_SPEED`) not by value.
- Group related constants into labeled blocks at the top of the file
  (`// Geometry`, `// D3 simulation tuning`, `// Camera`, `// Palette`).
- Prefer suffixes that describe the unit: `_MS` for milliseconds, `_FACTOR`
  for multipliers, `_THRESHOLD` for boundaries, `_OFFSET` / `_PADDING` for
  spatial offsets.

**Don't.**
- Inline magic literals mid-expression (`for (let i = 0; i < 300; i += 1)`
  tells a reviewer nothing about what 300 means).
- Name a constant by its value (`TICKS_300`, `OPACITY_0_7`). Rename if the
  value changes; the role should stay stable.
- Declare the constant inside a function just so "it's close to the use
  site". If the constant is tuning, a reviewer can't find it later.

**Detection heuristic.**
- `rg -n '(?:<|>|>=|<=|\*|\+|-|===|!==)\s*-?\d+(?:\.\d+)?(?!\s*[a-zA-Z_])' -g '*.js' -g '*.vue'`
  — find comparisons and arithmetic against bare numeric literals inside
  `app/assets/javascripts/` and `ee/app/assets/javascripts/`. Audit each.
- `rg -n '0x[0-9a-fA-F]{6}' -g '*.js' -g '*.vue'` — hex colors inline;
  most should move to a palette module.
- `rg -n 'setTimeout\(|setInterval\(' -g '*.js' -g '*.vue' -A 1` — every
  timer literal (`300`, `5000`, `15_000`) deserves a name like
  `IDLE_TIMEOUT_MS` or `DEBOUNCE_RESIZE_MS`.

**Edge cases / when this rule relaxes.**
- Array indices (`arr[0]`, `arr.length - 1`) don't need names.
- Math identities (`Math.PI / 2`, `Math.PI * 2`) are fine inline —
  `angle > Math.PI / 2` is self-documenting.
- Unit bytes / unit conversions inside a single expression (`1024 * 1024`,
  `1000 * 60`) are usually clear; if they repeat across the file, extract.
- `0`, `1`, `-1`, and `0.5` at the identity-math level (`* 0.5` to halve)
  are fine; tuning factors that happen to be `0.5` are not.

**Related.** The reviewer applies this pattern inside every decomposition in §5.4.
This rule pulls it out so the ask is visible on its own.
