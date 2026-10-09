# §4. Reactivity / side effects

## §4.1 Side effects go in watchers

**Rule.** If a state flag triggers a persistent side effect (cookie, local
storage, analytics, body class), do it in a watcher keyed on that flag.
Guarantees consistency when the flag is set from any code path.

**Verbatim.** !227814 note 3171915876 (`graph_explorer.vue:202`):
> **Thought** usually side effects like this are really great as watchers.
> When banner dismissed changes to true, we set the cookie in the watcher
> so if we ever manually set this property without calling this method,
> still works.

**Bad.**
```js
dismissBanner() {
  this.bannerDismissed = true;
  setCookie('orbit_banner_dismissed', 'true', { expires: 365 });
},
```

**Good.**
```js
data() { return { bannerDismissed: getCookie('orbit_banner_dismissed') === 'true' }; },
watch: {
  bannerDismissed(dismissed) {
    if (dismissed) setCookie('orbit_banner_dismissed', 'true', { expires: 365 });
  },
},
methods: {
  dismissBanner() { this.bannerDismissed = true; },
},
```

## §4.2 Watchers fire only on change — drop `newVal !== oldVal` guards inside

**Confidence:** stale in current master (`ai_panel.vue` still contains
`if (newMode !== oldMode)` inside a watcher — apply to new code).

**Rule.** Vue watchers only fire when the watched value changes. The
`(newVal, oldVal) => { if (newVal !== oldVal) ... }` guard is dead code.

**Verbatim.** !226722 note 3178434098 (`ai_panel.vue:172`):
> **question** watchers are only called when the value changes. So the
> `new !== old` should be meaningless here because you never get here if
> that's not true right? Can we drop it?

**Bad.**
```js
watch: { activeTab(newVal, oldVal) { if (newVal !== oldVal) this.load(); } },
```

**Good.**
```js
watch: { activeTab() { this.load(); } },
```

## §4.3 Move DOM toggles to `utils/dom_utils`

**Rule.** Imperative DOM manipulation (`document.querySelector`, `classList`
toggle) belongs in a pure utility module, unit-testable in isolation.

**Verbatim.** !226946 notes 3167726945, 3171151027:
> **Thought** I'd be tempted to move this out to a `dom_utils` utility file.
> That way the logic to toggle the panel in the DOM is delegated out of
> the component, and we can reuse the same logic if we ever need it.
> […] Yes, so that the Dom logic can be tested in isolation.

**Bad.**
```js
// ai_panel.vue
watch: {
  isMaximized: {
    handler(m) { document.querySelector('.js-page-layout').classList.toggle('ai-panel-maximized', m); },
    immediate: true,
  },
},
```

**Good.**
```js
// utils/dom_utils.js
export const toggleAiPanelMaximizedClass = (isMaximized) => {
  document.querySelector('.js-page-layout')?.classList.toggle('ai-panel-maximized', isMaximized ?? false);
};
// ai_panel.vue
import { toggleAiPanelMaximizedClass } from '../utils/dom_utils';
apollo: {
  isMaximized: {
    query: isMaximizedQuery,
    result({ data }) { toggleAiPanelMaximizedClass(data?.isMaximized); },
  },
},
```

**Adoption:** ADOPTED in !226946.

## §4.4 Route through the declarative Vue pipeline

**Rule.** Method/computed/watcher split:
1. **Methods** — actions with specific arguments (fire-and-forget fetches).
2. **Computed** — derive data from what's been fetched.
3. **Watchers** — react to new data with side effects.

Don't write one 30-line method that fetches, transforms, assigns state,
pokes `$refs`, and clears loading flags all at once.

**Verbatim.** !227814 note 3171915902 (`graph_explorer.vue:271`):
> **Issue** I get that this is REST here behind the hood, but I'd love if
> all we did here was fetch the data. To follow the declarative nature of
> Vue: 1. Methods operate with specific arguments 2. Computed derive other
> data from what we've fetched 3. Watchers act after the arrival of the
> new data.

## §4.5 Separate parse and execute

**Rule.** Any method with two `try/catch` blocks is doing two jobs. Split.

**Verbatim.** !227814 note 3171915873:
> **Thought** I feel like this is doing two things that could be separated:
> 1. Parsing the query 2. Executing the query. I do wonder if the parsing
> could be separate here. […] having multiple try catch in teh same method
> is a pretty big red flag to me that we are doing multiple different
> operations in the same block that dont belong together.

**Good.**
```js
parseQuery() {
  if (typeof this.queryText === 'object' && this.queryText !== null) return this.queryText;
  try { return JSON.parse(this.queryText); }
  catch { createAlert({ message: s__('Orbit|Invalid JSON query.') }); return null; }
},
async executeCurrentQuery() {
  const parsed = this.parseQuery();
  if (!parsed) return;
  // ... just the network call ...
},
```

## §4.6 Don't split a single value across `data` and parse-on-demand

**Rule.** Keep the canonical object in `data`; derive serialized forms
(JSON stringification, formatted strings) in `computed`.

**Verbatim.** !227814 note 3171915776 (`graph_explorer.vue:44`):
> **Suggestion** we re-run this stringify operation also when selecting
> template, and generally I don't quite like having default in data
> properties that aren't just primitive values.

**Good.**
```js
data() { return { queryText: EXAMPLE_QUERIES[0].query }; },
computed: { stringifiedQueryText() { return JSON.stringify(this.queryText, null, 2); } },
```

## §4.7 Silent error swallowing belongs in the helper, not every caller

**Rule.** If a helper is named `safeX` / `tryX`, the `catch` lives once
inside the helper. Callers should not wrap it in another `catch`.

**Verbatim.** !229721 note 3218332995 (`ai_panel.vue:206`):
> **Question** Conceptually, shouldn't `safeRouterPush` do the silent error
> swallowing? That way we wouldn't need to do all of these catch?

## §4.8 Name mutator methods as mutators — no `check*` that also `this.X =`

**Rule.** Methods that mutate state get verb prefixes (`set`, `reset`,
`clear`, `mark`). `check*`, `is*`, `has*`, `should*`, `can*` are predicates
— reserve them for pure reads.

**Verbatim.** !223639 note 3152023826:
> **Issue/concern** This is a bit of an odd pattern. The `check` prefix
> was used to signal that we want to know if the credits are exhausted,
> but we are actually mutating the state! […] So my advice here is to call
> this `setOutOfCredits` or something, remove the conditionals and instead
> extract it out.

**Bad.**
```js
checkCreditsAvailability() {
  if (!this.hasCredits) { this.setChatState({ isEnabled: false, reason: ... }); }
},
// caller
if (event?.code === WS_CLOSE_POLICY_VIOLATION) {
  this.hasCredits = false;
  this.checkCreditsAvailability();
}
```

**Good.**
```js
setOutOfCredits() {
  this.hasCredits = false;
  this.setChatState({ isEnabled: false, reason: ... });
},
// caller
if (event?.code === WS_CLOSE_POLICY_VIOLATION) {
  this.setOutOfCredits();
}
```

**Detection heuristic (verified — 5 real offenders in monolith).**
- `rg 'check[A-Z]\w*\s*\(\)\s*\{' -g '*.vue'` then verify body mutates
  `this.*`. Real hits: `sign_in_form.vue`, `ci_cd_project_form.vue`,
  `import_by_url_form.vue`, `import_by_url_to_existing_project_form.vue`,
  `group_path_field.vue`.

## §4.9 Don't ignore error branches silently; surface them

**Rule.** Empty `.catch(() => {})` or silent `if (thing)` guards in click
handlers hide real state bugs. Either show an error, log it, or document
why swallowing is safe.

**Verbatim.**
- !227814 note 3171915815: "Do we really want to ignore the catch block?
  And maybe worth try/catch + async await here to get rid of the promise
  chaining?"
- !227814 note 3171915627 (`explorer_table_panel.vue:73`): "**Question**
  What happens when we don't have a query response? Do we really want to
  silently ignore this?"
- !227814 note 3171915911 (`graph_explorer.vue:275`): "Similar to other
  places here, what if we dont have a match? Why and how do we handle it
  here?"

**Bad.**
```js
mounted() { this.loadSchema().then(() => this.loadInitialGroups()).catch(() => {}); },
handleDownloadCsv() { if (this.queryResponse) downloadCsv(this.queryResponse); },
```

**Good.**
```js
async mounted() {
  await this.loadSchema();
  await this.loadInitialGroups();
},
// and on the template:
<gl-button :disabled="!queryResponse" @click="handleDownloadCsv">
```
