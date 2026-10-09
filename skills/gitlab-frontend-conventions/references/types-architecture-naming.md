# §7. Types / null handling

## Contents

- §7.1 Don't pepper optional chaining across a component
- §7.2 Signal nullability at the real boundary, not the parent
- §7.3 Match the null check to the shape of the value — `!= null` covers `undefined` too
- §8.1 Backend widget shape is the source of truth; no FE FF + permission combos
- §8.2 EE→CE separation via `ee_component` alias, never move CE→EE
- §8.3 Route/tab mappings as lookup tables, not `if/else` ladders
- §9.1 Scope data names to their component unless the name will cross boundaries
- §9.2 No "what" comments
- §10.1 Import translation helpers from `~/locale`
- §10.2 Inline vs `$options.i18n` copy — pick one per component

## §7.1 Don't pepper optional chaining across a component

**Rule.** `?.` is for values that are genuinely nullable at runtime. If
the parent is guaranteed non-null post-load, drop the chain and guard once
at the boundary.

**Verbatim.** !226946 note 3167726985:
> **Thought** aren't we just doing a bunch of type safety here? Do we
> even _need_ to make all of these optional chaining? `agentFlow` is
> guaranteed to have most of these for sure, and if it doesn't have it it
> means the query failed right?

**Follow-up (non-blocking).** !226946 note 3187545598:
> my comment was non blocking here, it's mostly just adding complexity
> for no good reason, and if we realize we do need all of these safety
> checks, then something deeper is the problem.

**Bad.**
```js
status: this.agentFlow?.status || '',
humanStatus: formatAgentStatus(this.agentFlow?.humanStatus),
canUpdate: this.agentFlow?.userPermissions?.updateDuoWorkflow || false,
```

**Good.**
```js
if (this.loading || !this.agentFlow) return emptyProps;
return {
  status: this.agentFlow.status,
  humanStatus: formatAgentStatus(this.agentFlow.humanStatus),
  canUpdate: this.agentFlow.userPermissions?.updateDuoWorkflow ?? false,
};
```

## §7.2 Signal nullability at the real boundary, not the parent

**Rule.** Put the `?.` on the property that can be `undefined`, not on a
guaranteed parent. Communicates intent: "this exact field might be missing".

**Verbatim.** !226933 note 3155205184 (`work_item_note.vue:339`):
> **Nit** I know it won't throw an error here since workItem is guaranteed
> to be defined, so this check would give us undefined, but I like to
> signal intent with the optional chaining since what we _want_ to signal
> is that features might be undefined
> `const editedFeatures = this.workItem?.features`

## §7.3 Match the null check to the shape of the value — `!= null` covers `undefined` too

**Confidence:** softened (the reviewer phrased as **Question**, but the underlying
correctness concern is real).

**Rule.** `if (id !== null) { ... }` fires on `undefined`, `''`, `0`,
`false`, and every truthy value. If `undefined` should gate the same way
`null` does (props not yet bound, Apollo not resolved, `$refs` not mounted),
use `== null` / `!= null`, or narrow explicitly with `typeof` / `.length` /
`Number.isFinite`. If `!== null` is genuinely what you want, leave a
comment explaining why `undefined` passes through.

**Verbatim.** !227814 note 3171915683 (`graph_canvas.vue:50`):
> **Question** So if id any value other than `null` _including `undefined`_,
> we want this block to execute? If not we might need to update the
> condition.

**Bad.**
```js
watch: {
  selectedNodeId(id) {
    if (id !== null) {
      this.highlightNode(id); // also runs when id is undefined, '', 0, false
    }
  },
},
```

**Good — cover both null and undefined with `!= null`.**
```js
watch: {
  selectedNodeId(id) {
    if (id == null) return; // loose equality intentionally matches null + undefined
    this.highlightNode(id);
  },
},
```

**Good — explicit shape narrowing when only a real id is meaningful.**
```js
watch: {
  selectedNodeId(id) {
    if (typeof id !== 'string' || id.length === 0) return;
    this.highlightNode(id);
  },
},
```

**Good — explicit numeric narrowing.**
```js
if (!Number.isFinite(numericId)) return;
```

**Do.**
- Write the predicate that actually reflects your intent.
- For "nothing selected", prefer `== null` / `!= null`.
- For "no valid id", narrow by shape (`typeof`, `.length`, `Number.isFinite`).
- If you keep `!== null`, add a one-line comment stating why `undefined`
  is allowed through.

**Don't.**
- Use `!== null` as a casual "truthy gate" when `undefined` is equally
  reachable.
- Chain `if (x !== null && x !== undefined)` — collapse to `x != null`.

**Detection heuristic.**
- `rg '!==\s*null' -g '*.vue' -g '*.js' -g '*.ts'` — audit each hit for
  whether `undefined` should also gate.
- `rg '!==\s*null\s*&&\s*\w+\s*!==\s*undefined' -g '*.vue' -g '*.js' -g '*.ts'`
  — exact "collapse to `!= null`" pattern.

**Related.** §7.1 covers over-defensive optional chaining. This rule is
about the explicit-null-only trap (`!== null` missing `undefined`).

---

# §8. Architecture / scope

## §8.1 Backend widget shape is the source of truth; no FE FF + permission combos

**Rule.** When the backend hands you a nullable widget/permission object,
the nullable field IS the "is supported" check. Don't add a
frontend-side `glFeatures.X && userHasRole` combo for the same gate.

**Verbatim.** !231689 note 3257934275:
> Ideally if we can avoid permissions check client side and get this
> straight out of the widgets (and `features` as we are currently
> refactoring the whole Work Item data to use features).

**Bad.** `v-if="glFeatures.agentPlan && currentUser.canUseDuo"`.
**Good.** `v-if="workItem.widgets.agentPlan"`.

## §8.2 EE→CE separation via `ee_component` alias, never move CE→EE

**Rule.** EE components are imported into CE via the dynamic `ee_component`
webpack alias, which returns a renderless empty Vue component when the EE
file does not exist. **Legal constraint:** Free-tier code can never be
demoted to paid — plan file layout accordingly.

**Verbatim.** !231689 note 3266831706:
> The pattern that has become more and more common (for better or worse)
> is to import the EE components dynamically with an alias `ee_component`
> which only imports the component if it exists, or otherwise return a
> renderless empty Vue component. […] adding to CE is **not** as we
> legally can never move anything from a Free tier to a paid tier because
> of open source licenses.

## §8.3 Route/tab mappings as lookup tables, not `if/else` ladders

**Rule.** When you see 3+ `else if` clauses all returning constants, use
an object literal or `switch`.

**Verbatim.** !229721 note 3218333005 (`router/utils.js:58`):
> **Nit** this is 100000% a switch case in hiding. I personally _like_
> switch/case […], but it might be worth switching for semantic clarity.

---

# §9. Naming / comments / conventions

## §9.1 Scope data names to their component unless the name will cross boundaries

**Rule.** Inside `AiPanel.vue`, use `isMaximized`. When the name crosses
into other components or packages, include the subject:
`isAiPanelMaximized`.

**Verbatim.** !226946 note 3167726954, 3170828884.

## §9.2 No "what" comments

**Rule.** Delete comments that restate the adjacent code. Keep comments
that explain *why*: hidden constraint, upstream bug, intentional exclusion.

**Verbatim.** !223639 note 3101411276 (`duo_agentic_chat_spec.js:4068`):
> This is always the case for all onMount API mocking, so imo this
> comment can be removed.

---

# §10. i18n + translations

## §10.1 Import translation helpers from `~/locale`

**Rule.** `import { s__, __, sprintf, n__ } from '~/locale';` — never a
relative path. Wrap every user-facing string.

**Snapshot 2026-04-23.** ~2,783 monolith Vue files under
`app/assets/javascripts/` + `ee/app/assets/javascripts/` import from
`~/locale`.

## §10.2 Inline vs `$options.i18n` copy — pick one per component

**Rule.** Don't mix `{{ $options.i18n.title }}` with `{{ s__('...') }}`
in the same template. Inline is the reviewer's slight preference; `$options` is
acceptable when sprintf+HTML escapes require a function.

**Verbatim.** !219578 notes 3031081115, 3031081132.
