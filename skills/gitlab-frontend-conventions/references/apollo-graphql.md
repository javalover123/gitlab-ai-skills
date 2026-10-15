# §3. Apollo + GraphQL

## Contents

- §3.1 Use smart queries, not imperative `this.$apollo.query()`
- §3.2 `update()` reshapes; `result()` runs side effects only
- §3.3 One `apollo:` entry per logical query
- §3.4 Loading: use `$apollo.queries.X.loading`, not a hand-rolled flag
- §3.5 `@client` state → tests drive via mutators or `cache.writeQuery`, not `setData`
- §3.6 Defer REST→GraphQL migration; use a client directive + fragment when payload bites

## §3.1 Use smart queries, not imperative `this.$apollo.query()`

**Rule.** Declare every server query as a component `apollo: { key: {...} }`
block. Use `update()` to reshape the response, `result()` for side effects,
`skip()` to short-circuit.

**Verbatim.** !227814 note 3171915847 (`graph_explorer.vue:126`):
> **Issue** I don't understand why we didn't went with a smart query here?
> Usually you use hardcoded query execution only if you need to break away
> from Apollo's declarative structure, which in my experience is basically
> never. What about:
> ```js
> apollo: {
>   groups: {
>     query: ownedNamespacesQuery,
>     variables() { return { first: 25 }; },
>     update(data) {
>       return (data?.groups?.nodes || []).map((g) => ({ ...shape... }));
>     },
>     result({ data, loading }) {
>       if (!loading && data?.groups?.nodes?.length > 0) {
>         this.$nextTick(() => this.$refs.graphCanvas?.setFullData());
>       }
>     },
>     skip() { return this.nodes.length > 0; },
>   },
> },
> ```

**Round-2 clarification.** !227814 note 3203845760:
> `results` is only for side effects and `update` is the method to map what
> we want the _property_ we are defining to hold.

**Bad.**
```js
async loadInitialGroups() {
  try {
    const { data } = await this.$apollo.query({ query: ownedNamespacesQuery, variables: { first: 25 } });
    const groups = data?.groups?.nodes || [];
    if (groups.length === 0) { this.initialLoading = false; return; }
    this.nodes = groups.map((g) => /* ...shape... */);
    this.$nextTick(() => { if (this.$refs.graphCanvas) this.$refs.graphCanvas.setFullData(); });
  } catch {
    // non-critical
  } finally {
    this.initialLoading = false;
  }
},
```

**Good.** (See the reviewer's block above.)

**Detection heuristic (verified — 56 files in monolith still use this).**
- `rg 'this\.\$apollo\.query\(' -g '*.vue'` — 56 hits.
- **Do NOT flag `this.$apollo.mutate(...)`** — mutations legitimately stay
  imperative (308 uses, all valid).

**Adoption:** ADOPTED in !227814.

## §3.2 `update()` reshapes; `result()` runs side effects only

**Rule.** Don't put response reshaping in `result()`. The `update()` hook's
return value becomes the component's data field.

**Verbatim.** !227814 note 3203845760 (post-refactor follow-up):
> `ownedGroups` is never used, but nodes is! So we'd put the maping we do
> below to `this.nodes` be the update hook return value (since this is a
> basically a computed of network returned value to UI data layer) and the
> rest would be result hook as side effect of the fetching having happened.

## §3.3 One `apollo:` entry per logical query

**Rule.** Never register two `apollo:` entries against the same imported
query document. Fetch once, derive via `update()`/computed.

**Verbatim.** !226946 note 3175303162:
> Okay first off, we were firing the same query twice for different
> properties. We gave them different data properties, but the graphql query
> used is the same, so we were effectively fetching this twice. Not only
> that, but we were also fetching `isMaximized` from the query, but we are
> getting it as a prop from the parent. So I've extracted `isMaximized`
> outside of the query, and I've made the component fetch the title and
> subtitle only once.

**Bad.**
```js
apollo: {
  panelTitle:    { query: panelStateQuery },  // same query
  panelSubtitle: { query: panelStateQuery },  // fired twice!
},
```

**Good.**
```js
apollo: {
  panelTitleState: {
    query: panelTitleQuery,
    update(data) { return data; },
  },
},
computed: {
  panelTitle()    { return this.panelTitleState?.panelTitle    || ''; },
  panelSubtitle() { return this.panelTitleState?.panelSubtitle || ''; },
},
```

**Detection heuristic.**
- Within each `<script>` block, grep for `query:\s+(\w+)` — duplicate
  identifier across two `apollo:` entries is the smell.

## §3.4 Loading: use `$apollo.queries.X.loading`, not a hand-rolled flag

**Rule.** Apollo already tracks loading. Wrap in a computed if needed. Do
not add an `isLoading` data property and flip it inside `result()`.

**Verbatim.** !223639 note 3152023815:
> **Issue** Apollo loading states are already tracked from the apollo store
> already `this.$apollo.queries.hasCredit.loading` will have the value and
> doesn't require any manual tracking. If you want you can make it into a
> computed which is a pretty common pattern:
> ```js
> areCreditsLoading() { return this.$apollo.queries.hasCredit.loading; }
> ```

**Bad.**
```js
data() { return { isCreditsLoading: true }; },
apollo: {
  hasCredits: {
    query: creditsQuery,
    result({ data }) {
      this.hasCredits = data?.gitlabCreditsAvailable;
      this.isCreditsLoading = false;  // hand-rolled
    },
  },
},
```

**Good.**
```js
apollo: { hasCredits: { query: creditsQuery, /* ... */ } },
computed: {
  areCreditsLoading() { return this.$apollo.queries.hasCredits.loading; },
},
```

## §3.5 `@client` state → tests drive via mutators or `cache.writeQuery`, not `setData`

**Rule.** For local (`@client`) state, either call the real mutator
(preferred) or `cache.writeQuery` on the `defaultClient` to seed the cache.
Never `wrapper.setData({...})`.

**Verbatim.** !226946 note 3167726995:
> **Issue** We never set the data property explicitly in tests or we are
> essentially overriding the component native behaviour, which weaken our
> tests considerably. Usually, you should be able to remove this and it
> should still pass. If it doesn't, it means you need to call `writeQuery`
> for your local directives `apolloProvider.clients.defaultClient.cache.writeQuery({...`

**Good.**
```js
const setPanelTitleAndSubtitle = async (title, subtitle) => {
  await mockApollo.defaultClient.cache.writeQuery({
    query: panelStateQuery,
    data: { panelTitle: title, panelSubtitle: subtitle, isMaximized: false },
  });
};
```

**Reactive-var escape hatch.** When `makeVar` is used but caches are not
shared across apps, fall back to `refetch()` AND leave a comment:
```js
setPanelTitle(title);
// Reactive vars are shared across apps but the Apollo cache is not,
// so cache.writeQuery would not reach the component under test.
await wrapper.vm.$apollo.queries.panelTitleState.refetch();
```
(The reviewer acknowledged this in !226946 note 3175303162.)

## §3.6 Defer REST→GraphQL migration; use a client directive + fragment when payload bites

**Rule.** Don't pre-optimize. When a REST endpoint's payload becomes a
problem, wrap it in a local graphql fragment + reusable `@client` directive
so Apollo caches the result and any Vue app can consume it declaratively.

**Verbatim.** !227814 note 3171181894 (`graph_transform.js:19`):
> For payload size, this is quite possibly an issue we'll face. If we do,
> then my suggestion would be to create a graphql fragment and reusable
> client directive where we create the field on the client side, but hit
> the rest point behind the scene. Then any Vue app that wants to use this
> field could include the directive amnd then the result would be added to
> Apollos cache.
> Similar to what we discussed in the previous MR, this is something I'd
> delay for as long as possible while we iterate to not over optimize too
> early.
