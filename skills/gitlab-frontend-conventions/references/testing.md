# §6. Tests (Jest + VTU + Apollo + MSW)

## Contents

- §6.1 Never hard-set Apollo-owned data in tests
- §6.2 Mock GraphQL handlers, not `vue-apollo` or wrapper utilities
- §6.3 Don't `mockClear` in `beforeEach` — Jest auto-clears
- §6.4 Don't repeat describe-block context in `it` names
- §6.5 Describe-nesting: `describe('when X')` + terse `it`
- §6.6 Setup in `beforeEach`, not in `it`
- §6.7 Default handler at describe level, override in nested
- §6.8 Mount helper assigns internally; no destructuring in callers
- §6.9 No snapshots (except data viz)
- §6.10 Integration tests assert native DOM, never `wrapper.vm`
- §6.11 Don't assert router internals in integration tests
- §6.12 Mount the SPA root, not a leaf page, for integration tests
- §6.13 Trigger native DOM events, not `.vm.$emit`
- §6.14 `waitFor` over `nextTick` (MSW direction)
- §6.15 Golden-path integration vs passive-feedback unit split
- §6.16 Integration tests: use the real app router via `assignRouter` + `fullMount`
- §6.17 Assert mock was NOT called before the action
- §6.18 Include the FF name verbatim in FF-gated describe strings
- §6.19 `toBe` for primitives, `toEqual` for objects/arrays
- §6.20 Don't pass `null` explicitly for optional args
- §6.21 Assertion helpers take a full state hash, no hidden defaults
- §6.22 Name test helpers for literal assertion, not metaphor
- §6.23 ESLint overrides for specs scope to `*_spec.js` only
- §6.24 Spread shared metadata objects, don't replace
- §6.25 Test via user-visible behavior, not `wrapper.vm` internals (even in unit specs)
- §6.26 Test the negative/no-match branch of parsers explicitly
- §6.27 Define reusable finder helpers at the top of the spec file
- §6.28 Assert on handler mocks, not `$apollo.mutate` spies
- §6.29 Assertion helpers validate their inputs eagerly

## §6.1 Never hard-set Apollo-owned data in tests

**Rule.** If a field comes from Apollo, drive it via mocked handlers. Do
NOT `createComponent({ data: () => ({ field: value }) })`. You're bypassing
the consumption layer (`apollo:` block, `result()`, `update()`) and your
test no longer proves the component consumes Apollo correctly.

**Verbatim.** !223639 note 3101411257, 3139069806:
> **Issue** […] we should avoid hard setting data in the createComponent
> call and use whatever defaults we get, and then we mock/use actions on
> the UI to get to the desired state, which result in much more solid
> tests in general. So in this case, we want to mock the API response to
> give us true or false or an error, and go from there and not hard pass
> the hasCredit to the data, which bypass testing the consumption layer
> of our component.
> […] we should _rarely_ ever set the data explicitly here, because you
> are overwritting Apollo's default behaviour and therefore the whole unit
> test suite value drops significantly.

**Bad.**
```js
wrapper = shallowMount(Component, { data() { return { hasCredits: true }; } });
```

**Good.**
```js
const creditsAvailableQueryMock = jest.fn().mockResolvedValue({ data: { gitlabCreditsAvailable: true } });
const apolloProvider = createMockApollo([[getGitlabCreditsAvailableQuery, creditsAvailableQueryMock]]);

// override per-describe:
creditsAvailableQueryMock.mockResolvedValue({ data: { gitlabCreditsAvailable: false } });
```

**Adoption:** PARTIAL in !223639 (data overrides not fully removed); the reviewer
softened this for a specific case. Treat as a firm rule for new code.

## §6.2 Mock GraphQL handlers, not `vue-apollo` or wrapper utilities

**Rule.** Do not `jest.mock('vue-apollo')` or `jest.mock('.../apollo_utils')`.
Use `createMockApollo([[document, handler]])` from
`helpers/mock_apollo_helper` (`spec/frontend/__helpers__/mock_apollo_helper.js`).

**Verbatim.** !223639 note 3139069819:
> This test file is mocking the Apollo utils and not the graphql query
> through Apollo's client. […] We shouldn't mock the utils, but we should
> instead mock the Graphql handlers directly to return the right data.
> Otherwise Apollo never gets to write to the data property because all
> you mock is the util call, and Apollo is never part of the equation.

**Detection heuristic (verified).**
- `rg "jest\.mock\(['\"]vue-apollo['\"]" -g '*.js'` — 3 hits in monolith,
  all anti-patterns.

## §6.3 Don't `mockClear` in `beforeEach` — Jest auto-clears

**Rule.** `jest.config` already runs `clearMocks: true`. `mockClear()` in
`beforeEach` is redundant. If a test genuinely leaks state, fix the
`describe` structure.

**Verbatim.** !223639 note 3101411280:
> **Thought** We shouldn't need to mockClear here. We have this by default
> with jest between tests, so either our tests are _leaking_ and we a
> larger problem worth checking, or we can safely remove the clear and
> all should be well.

**Detection heuristic (refined).**
```
rg -U 'beforeEach\([^)]*\)\s*=>\s*\{[^}]*mockClear\(\)' -g '*.js' --multiline
```

## §6.4 Don't repeat describe-block context in `it` names

**Rule.** If you're inside `describe('when credits are exhausted')`, the
`it` name should not start with "when exhausted…".

**Verbatim.** !223639 note 3101411267:
> **Nitpick** We already are in a block for credit exhaustion, so the
> assertion text can be leaner to avoid repetition.

**Bad.**
```js
describe('when credits are exhausted', () => {
  it('when exhausted disables chat and shows an explanation text', () => { /* ... */ });
});
```

**Good.**
```js
describe('when credits are exhausted', () => {
  it('disables chat and shows an explanation text', () => { /* ... */ });
});
```

## §6.5 Describe-nesting: `describe('when X')` + terse `it`

**Rule.** Put context (`when X`, `with Y`) in `describe`, behavior in `it`.
Nest `describe` when there are orthogonal axes (tool type × version).

**Verbatim.** !229296 note 3217340814: "I think we're better off with
`describe('when submitting the form') => it('creates the agent and
redirects to the show page')` and then we can put the setup in the
`beforeEach`"

## §6.6 Setup in `beforeEach`, not in `it`

**Rule.** Mount, fill, submit, and await inside `beforeEach`. Keep `it`
bodies to the assertions only.

**Verbatim.** !229296 note 3217340862:
> beforeEach is _really_ where we should be doing the mounting anyway.

## §6.7 Default handler at describe level, override in nested

**Rule.** Global `let handler = jest.fn()` in the parent `describe`; reset
to default in parent `beforeEach`; override with `.mockResolvedValue(error)`
in the nested error-case `beforeEach`.

**Verbatim.** !229296 note 3217340845: (the reviewer's full code block shown
earlier)

## §6.8 Mount helper assigns internally; no destructuring in callers

**Rule.** Declare `let wrapper` in the `describe`; the mount helper
assigns to it. Callers never destructure.

**Verbatim.** !229296 note 3217340862: "**Thought** […] I'd go for option
3 as it requires little to no change and it make it usable in beforeEach…
`wrapper = mountEditPage().wrapper`"

## §6.9 No snapshots (except data viz)

**Rule.** Snapshots are banned per
`doc/development/testing_guide/frontend_testing.md:1736-1862`. Replace with
explicit VTU finders + `exists()` / `text()` / `length` assertions.

**Verbatim.** !219578 note 3031081145:
> **Issue** We have pretty strong guidelines against snapshots. The true
> value of a snapshot is a guardrail against unwanted diff, which is much
> more useful for things like data visualization graphs […]. This doesn't
> seem to match here as we are just checking the element is what we
> expect, which really doesn't help us more than not having it or having
> more thorough assertions. So we should remove this entirely and instead
> assert a few key UI elements are rendering with VTU.

**Detection heuristic (verified — 343 hits in monolith; most brittle).**
- `rg 'wrapper\.(element|html\(\))\).*toMatchSnapshot' -g '*.js'` — the
  brittle form.
- `toMatchInlineSnapshot` on small scalars is usually fine.

**Adoption:** ADOPTED in !219578 (all snapshots removed).

## §6.10 Integration tests assert native DOM, never `wrapper.vm`

**Rule.** At the integration layer: `document.querySelector('.gl-toast')`
text, `findByTestId('destination-page-heading').exists()`. NOT
`wrapper.vm.$toast.show`, NOT `wrapper.findComponent(X).vm.$emit(...)`.

**Verbatim.** !229296 note 3217340834:
> **Issue** We are in an integration test layer, yet we also check
> internals in a few place (wrapper vm, that certain functions were
> called, etc). This breaks the paradigm so I'd suggest instead trying to
> find the Toast element is in the DOM, and that it contains the right
> text. Or for example not to assert the router properties and just
> assert the text has changed has we expect with the new route.
> If you look at the MSW tests now, you can see that we moved away
> entirely from wrapper.find even and are focusing on native DOM checks
> to be as far away from Vue as possible.

**Toast-container pattern.**
```js
let toastContainer;
beforeEach(() => {
  toastContainer = document.createElement('div');
  toastContainer.setAttribute('id', 'toast-container');
  document.body.appendChild(toastContainer);
});
afterEach(() => { toastContainer.remove(); });

it('shows the success toast', () => {
  const toast = document.querySelector('.gl-toast');
  expect(toast).not.toBeNull();
  expect(toast.textContent).toContain('Agent created.');
});
```

**Detection heuristic (snapshot 2026-04-23: 13 hits, all in
`ee/spec/frontend/ai/catalog/integration/`).**
- `rg 'wrapper\.vm\.' -g '**/msw_integration/**/*.js' -g '**/integration/**/*.js'`

**Adoption:** PARTIAL in !229296; the reviewer explicitly accepted
`wrapper.vm.$toast.show` as a scaffold while jsdom limitations block DOM-
based toast assertions. Move when feasible.

## §6.11 Don't assert router internals in integration tests

**Rule.** Never `expect(router.currentRoute.name).toBe(...)`. Assert that
the destination page's DOM elements are now visible.

**Verbatim.** !229296 note 3217340884:
> **Issue** I've raised this before in a larger comment, but we shouldn't
> assert anything router based, only the UI!

**Pattern.**
```js
// before
expect(wrapper.findByTestId('agent-form-input-name').exists()).toBe(true);
await submitAgentForm(wrapper);
await waitForPromises();
// after
expect(wrapper.findByTestId('agent-form-input-name').exists()).toBe(false);
expect(wrapper.findByTestId('more-actions-dropdown').exists()).toBe(true);
```

**Detection heuristic (snapshot 2026-04-23: 37 hits, all in
`ee/spec/frontend/ai/catalog/integration/`).**
- `rg 'router\.currentRoute' -g '**/integration/**/*.js' -g '**/msw_integration/**/*.js'`

## §6.12 Mount the SPA root, not a leaf page, for integration tests

**Rule.** True integration = mount the SPA's top-level component so
`<router-view>` actually renders the destination on navigation. Canonical
pattern: `ee/spec/frontend/msw_integration/work_items/` suite.

**Verbatim.** !229296 note 3231710456:
> Integration tests are not supposed to be done per component: you use
> the root of your SPA, mount it, and then you test all your features
> that way.

## §6.13 Trigger native DOM events, not `.vm.$emit`

**Rule.** `.trigger('click')`, `.trigger('submit')`, `.trigger('input')`.
Modals: open the full modal and click the primary button — don't emit
`ok`/`primary`.

**Verbatim.**
- !229296 note 3217340872: "At the integration layer, we should use
  `trigger` for as many events as possible (actually, all of them!)."
- !225094 note 3128213754 (`self_hosted_model_form_spec.js:610`):
  > **Issue** I don't think that we should manually trigger the prevent
  > event here. I am not sure it would give us what we expect because
  > Vue _does not_ emit the prevent in the chain this way as part of the
  > event name. Rather, Vue emits the event name and the modifier is
  > passed as part of the details of the event for Vue to affect its
  > outcome. So we should instead do something more like this:
  > `wrapper.find('form').trigger('submit');`

## §6.14 `waitFor` over `nextTick` (MSW direction)

**Rule.** Plan helper APIs so the await target is an observable UI
condition, not a tick count. `await waitFor(() => expect(x).toBeVisible())`
beats chained `await nextTick(); await waitForPromises()`.

**Verbatim.** !229296 note 3217340936: "**Thought for later** as this
could easily move to MSW in the future, we'll want to avoid next ticks
altogether as they are internal event timers and we'll use `waitFor`
instead."

## §6.15 Golden-path integration vs passive-feedback unit split

**Rule.** Does the error change which page/region the user ends up on?
- Yes → integration test.
- No (just a toast/alert on the same screen) → unit test.

**Verbatim.** !229296 note 3217266934:
> **integration layer cares about preserving the integrity of the golden
> path _despite_ errors.
> * **Errors that divert the golden path** (redirect to recovery UI,
>   degraded state with options) → integration test
> * **Errors that are passive feedback on the golden path** (toast, alert,
>   form validation staying on the same page) → unit test

## §6.16 Integration tests: use the real app router via `assignRouter` + `fullMount`

**Rule.** In MSW integration suites, hand the production `createRouter`
factory to `assignRouter` (picks up base path and runs the router setup)
and use `fullMount` to handle DOM attachment. Navigate by clicking the
link the user would click — don't `router.push(...)` manually.

**Verbatim.** !230984 note 3267873274 (spirit; the canonical helper name in
current master is `assignRouter`, not `declareRouter`):
> you shouldn't use `createRouter` [directly] and instead use a new helper
> […] which will handle all of the base routing for you. That way you
> can avoid manually pushing at all. If you need to navigate within the
> app, then you would click on the item in the list and get to where you
> want. […] We also have a new mount util `fullMount` which will remove
> the need to attach to the dom manually.

**In-tree references.**
- `spec/frontend/msw_integration/test_helpers.js` exports `assignRouter` and
  `fullMount`.
- `ee/spec/frontend/msw_integration/work_items/` suites use
  `assignRouter(createRouter, ...)` to wire the app router.

**Detection heuristic.**
- In `spec/frontend/**/msw_integration/**` and `ee/spec/frontend/**/msw_integration/**`,
  grep for `new VueRouter(` / `createRouter(` called directly, or
  `router.push(` inside an `it` / `beforeEach`.

## §6.17 Assert mock was NOT called before the action

**Rule.** For any `expect(mock).toHaveBeenCalledWith(...)`, precede it
with `expect(mock).not.toHaveBeenCalled()` before the triggering action.
Guards against false positives from a leaky mock.

**Verbatim.** !230071 note 3237283911 (`work_item_actions_spec.js:388`):
> **Suggestion** we should probably make sure that it wasnt called before
> emitting the action too.

## §6.18 Include the FF name verbatim in FF-gated describe strings

**Rule.** `describe('when workItemConfigurableTypes FF is enabled', ...)`,
not `describe('when FF is enabled', ...)`. Grep-by-flag-name then
finds all guarded tests for cleanup on rollout.

**Verbatim.** !230071 note 3237283900.

## §6.19 `toBe` for primitives, `toEqual` for objects/arrays

**Rule.** Jest matcher hygiene: string/number/boolean → `toBe`. Reserve
`toEqual`/`toStrictEqual` for structural (deep) equality.

**Verbatim.** !225106 note 3139120083: "**Suggestion** We should use `toBe`
on string assertions since they are primitives."

## §6.20 Don't pass `null` explicitly for optional args

**Rule.** Either the parameter is optional (make it so) or it's required
(then don't omit it). `null` as a placeholder for "no value" is a smell.

**Verbatim.** !223639 note 3101411228:
> **question** Do we need to pass `null` explicitly here? I would imagine
> then the second argument of `fetchWorkflowEvents` should be optional,
> and we can just ignore it instead.

## §6.21 Assertion helpers take a full state hash, no hidden defaults

**Rule.** Test helpers that assert UI state should take a single object
keyed by element with an explicit state value. No arrays with implicit
defaults. Separate setup helpers from assertion helpers.

**Verbatim.** !227738 notes 3187510691, 3187510696:
> This utility function is suppose to be a helper to assert the UI state,
> but currently it is _also_ doing UI actions for the setup. I would
> recommend making this a separate util…
> If we are going to be using this utility to its full extent, I would
> recommend making **0 assumptions** about what to assert. […] So instead
> of getting two arrays, one disabled and one visible, I would say we
> define each button as a hash and we pass one of three value: 'visible',
> 'hidden', 'disabled'.

**Bad.**
```js
expectActions(wrapper, { disabled: ['save'], visible: ['cancel'] });
// what about 'delete'? hidden? assumed-visible?
```

**Good.**
```js
expectActions(wrapper, { save: 'disabled', cancel: 'visible', delete: 'hidden' });
```

## §6.22 Name test helpers for literal assertion, not metaphor

**Rule.** Helpers should name the jest matcher they back. `toBeNull` not
`toDisappear`.

**Verbatim.** !231612 note 3257966580:
> **Suggestion - non-blocking** I find that `toDisappear` is a a bit
> dramatic. Maybe we keep it tied in to the actual expectations to be null?
> `export function waitForElementToBeNull(finder) {`

## §6.23 ESLint overrides for specs scope to `*_spec.js` only

**Rule.** Test-specific lint rules should target `*_spec.js`. Helpers,
constants, utils under the same directory are regular JS and use the
generic ruleset.

**Verbatim.** !231612 note 3267225189:
> We want to apply the rules _only_ to spec files because utils/constants
> files are just regular js file and the rules we define here don't apply,
> like for example using router.push.
> ```
> files: ['{,ee/}spec/frontend/msw_integration/**/*_spec.js'],
> ```

## §6.24 Spread shared metadata objects, don't replace

**Rule.** `app.metadata = { ...app.metadata, router }`, not
`app.metadata = { router }`. Preserves future fields.

**Verbatim.** !230984 note 3271372280:
> I still updated this line differently because right now you are
> overwriting the whole metadata object with _just_ the router, so if we
> add more fields there in time, it will break the config.

## §6.25 Test via user-visible behavior, not `wrapper.vm` internals (even in unit specs)

**Rule.** Spy on collaborators (`JSON.stringify`, router, API modules);
don't poke `wrapper.vm.someInternal()`. LLM-generated specs love this
anti-pattern.

**Verbatim.** !227814 note 3203845800:
> I don't want to block this given the urgency, but _usually_ I would
> make sure we get the wrapper.vm assertions all out before merge. This
> isn't just you, LLM do output tests formatted this way a lot but it's
> really not great for coverage and I'd love for these base specs to
> serve as self-feeding for other Orbit features and avoid adding more
> and more internal assertions.

## §6.26 Test the negative/no-match branch of parsers explicitly

**Rule.** Any parser/matcher returning `null | undefined | ''` for "no
match" needs a spec row where the input does not contain the token.

**Verbatim.** !231769 note 3262020618 (`agents_utils_spec.js:166`):
> **Question** What about when camelCase does not contain the event
> type? Are we omitting that test path on purpose?

## §6.27 Define reusable finder helpers at the top of the spec file

**Confidence:** hard.

**Rule.** `const findX = () => wrapper.findByTestId('x')` helpers belong at
the top of the spec file so every `describe` can reuse them. Don't bury
shared finders inside nested `describe` blocks.

**Verbatim.** !225106 note 3139120098 (`note_actions_spec.js:526`):
> Finders should be defined at the top of the file so we can reuse them
> throughout.

**Bad.**
```js
describe('when editing', () => {
  const findSaveButton = () => wrapper.findByTestId('save-button');

  it('shows save', () => {
    expect(findSaveButton().exists()).toBe(true);
  });
});
```

**Good.**
```js
const findSaveButton = () => wrapper.findByTestId('save-button');

describe('when editing', () => {
  it('shows save', () => {
    expect(findSaveButton().exists()).toBe(true);
  });
});
```

**Do.**
- Hoist every `findX = () => ...` to module scope (below imports, above
  the first `describe`).
- Group related finders together.

**Don't.**
- Re-declare the same `findSaveButton` in multiple `describe` blocks.

**Detection heuristic.**
- `rg -n '^\s{4,}const find[A-Z]\w*\s*=\s*\(\)\s*=>' spec ee/spec -g '*_spec.js'`

**Edge cases.**
- A one-off local finder used once is tolerable; repeated selectors move up.

## §6.28 Assert on handler mocks, not `$apollo.mutate` spies

**Confidence:** hard.

**Rule.** When you've already wired a Jest-mocked GraphQL handler into
`createMockApollo`, assert on that handler directly. Don't also
`jest.spyOn(wrapper.vm.$apollo, 'mutate')` — the handler already proves
the mutation fired with the right variables.

**Verbatim.** !226933 note 3155602174 (`work_item_note_spec.js:424`):
> we don't have to spy on Apollo here ... we already have a jest mocked
> function

**Bad.**
```js
const mutateSpy = jest.spyOn(wrapper.vm.$apollo, 'mutate');
findNoteActions().vm.$emit('assign-user');
await waitForPromises();
expect(mutateSpy).toHaveBeenCalled();
```

**Good.**
```js
const updateWorkItemMutationHandler = jest.fn().mockResolvedValue(mutationResponse);
createComponent({ updateWorkItemMutationHandler });

findNoteActions().vm.$emit('assign-user');
await waitForPromises();

expect(updateWorkItemMutationHandler).toHaveBeenCalledWith({
  input: expect.objectContaining({ id: mockWorkItemId }),
  useWorkItemFeatures: true,
});
```

**Do.**
- Assert on the mocked handler you own (`updateWorkItemMutationHandler`,
  `createAgentMutationHandler`, etc.).
- Use `expect.objectContaining(...)` for the input payload so field
  additions don't thrash the test.

**Don't.**
- `jest.spyOn(wrapper.vm.$apollo, 'mutate')` when a handler mock is
  already wired — you're double-asserting and coupling to Apollo
  internals.
- Spy on `provider.defaultClient.mutate` for the same reason.

**Detection heuristic.**
- `rg -n 'spyOn\([^\n]*\$apollo|wrapper\.vm\.\$apollo\.mutate|provider\.defaultClient\.mutate' -g '*_spec.js'`

**Edge cases.**
- Tests for Apollo helper code itself may legitimately spy on `$apollo`.

## §6.29 Assertion helpers validate their inputs eagerly

**Confidence:** hard.

**Rule.** Test helpers that accept state-string arguments (`'visible'`,
`'hidden'`, `'disabled'`) should throw on invalid values before asserting.
A typo like `'vissible'` should fail loudly, not silently skip the
assertion.

**Verbatim.** !227738 note 3187510696 (`helpers.js:171`):
> I am also adding a throw at the top for good measure.

**Bad.**
```js
export const expectActions = (wrapper, { visible = [], disabled = [] } = {}) => {
  // hidden defaults, no validation of the keys
  visible.forEach((id) => expect(findAction(id).exists()).toBe(true));
  disabled.forEach((id) => expect(findAction(id).props('disabled')).toBe(true));
};
```

**Good.**
```js
export const ACTION_STATE = Object.freeze({
  VISIBLE: 'visible',
  HIDDEN: 'hidden',
  DISABLED: 'disabled',
});

export const expectActions = (wrapper, actions) => {
  for (const [id, expectedState] of Object.entries(actions)) {
    if (!Object.values(ACTION_STATE).includes(expectedState)) {
      throw new Error(`Invalid state "${expectedState}" for "${id}"`);
    }
    // ...assert per state...
  }
};

// usage — full state hash, no hidden defaults
expectActions(wrapper, { save: 'disabled', cancel: 'visible', delete: 'hidden' });
```

**Do.**
- Freeze an enum for the valid states (`ACTION_STATE`).
- Throw at the top of the helper with the bad value and the bad key in
  the message.
- Accept a full state hash per call so every button is explicitly
  accounted for (see §6.21).

**Don't.**
- Silently ignore unknown states.
- Default to an implicit "visible" / "disabled" partition.

**Detection heuristic.**
- Review every `export const expect*` / `export const assert*` helper for
  a leading validation block.

**Edge cases.**
- Boolean-only helpers still validate, but the check can collapse to a
  simple `typeof` guard.
