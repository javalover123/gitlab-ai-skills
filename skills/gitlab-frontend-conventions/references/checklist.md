# §13. Auto-fix checklist (in order of impact)

Before requesting review on a frontend MR:

1. **Scoped styles:** migrate to Tailwind utilities or page-bundle SCSS (§2.1, §2.3).
2. **`computed` with no `this.*`:** move to `$options` (§1.1).
3. **Imperative `$apollo.query`:** rewrite as smart query (§3.1).
4. **Snapshots:** replace with explicit VTU assertions (§6.9).
5. **Hard-set Apollo data in specs:** switch to mock handlers + `writeQuery` (§6.1, §6.5).
6. **`wrapper.vm.*` in integration tests:** switch to native DOM (§6.10).
7. **`router.currentRoute.*` assertions:** assert destination DOM instead (§6.11).
8. **`check*` that mutates:** rename to `set*`, drop caller guards (§4.8).
9. **Early return + length-zero check:** default + `.map`/`.filter`/`.reduce` (§5.1).
10. **`.forEach` building arrays:** switch to `.map` / `.reduce` (§5.2).
11. **Duplicated template markup:** extract to `$options` array + `v-for` (§1.6).
12. **`<style scoped>` empty block:** delete (§2.1).
13. **`mockClear()` in `beforeEach`:** delete or justify (§6.3).
14. **`@:event`:** normalize to kebab-case (§1.2).
15. **Numeric tab indices:** switch to string enum (§2.4).
16. **Empty `.catch(() => {})`:** either handle or document (§4.9).
17. **`absolute` positioning without justification:** reconsider flex/grid (§1.3).
18. **`computed` returning only `s__(...)` or `sprintf(...)`:** move to `$options` (§1.1).
19. **Two `apollo:` entries same query import:** collapse (§3.3).
20. **`(newVal, oldVal)` watcher guarding `newVal !== oldVal`:** drop the guard (§4.2).
21. **Nested ternaries inside template literals:** switch to `[parts].filter(Boolean).join(' ')` (§5.10).
22. **`checkFoo()` that mutates `this.*`:** rename to `setFoo()`, drop caller guards (§4.8).
23. **`?.` on a guaranteed-non-null parent:** move `?.` to the actually-nullable field (§7.2).
25. **`findXWidget()` for direct object access:** use `workItem?.features?.X` (§5.12).
26. **Presentational component reading `isGroup`/`isProject`:** split into domain wrappers (§5.13).
27. **`toMatchSnapshot` on `wrapper.element`/`wrapper.html()`:** replace with VTU assertions (§6.9).
28. **`router.push()` inside integration `beforeEach`/`it`:** click the link the user would click (§6.16).
29. **`toHaveBeenCalled` without preceding `not.toHaveBeenCalled`:** add the baseline (§6.17).
30. **FF-gated `describe('when FF is enabled')`:** include the flag name verbatim (§6.18).
31. **`toEqual` on string/number/boolean literals:** swap for `toBe` (§6.19).
32. **`glFeatures.X && currentUser.canY` client-side gate:** use backend widget/permission nullable (§8.1).
33. **EE-only component imported via relative path from CE:** use `ee_component` webpack alias (§8.2).
34. **3+ `else if` chain returning constants:** switch to object lookup or `switch` (§8.3).
35. **Two adjacent `push()` / `return` with one differing field:** spread conditional (§5.9).
36. **Parser spec missing the no-match row:** add a test input that does not contain the token (§6.26).
37. **Assertion helper with hidden defaults / arrays of "visible" vs "disabled":** take a full state hash keyed by element (§6.21).
38. **Test helper verb names like `toDisappear`:** rename to `waitForElementToBeNull` (§6.22).
39. **`jest.mock('vue-apollo')` or `jest.mock('*apollo_utils*')`:** use `createMockApollo` + handler mocks (§6.2).
40. **`wrapper.setData({ apolloField })`:** drive via mock handlers or `cache.writeQuery` (§6.1, §6.5).
41. **`nextTick()` chains in integration tests:** switch to `waitFor(() => expect(...))` when moving to MSW (§6.14).
42. **Trigger event with a modifier (`trigger('submit.prevent')`):** use plain `trigger('submit')` (§6.13).
43. **`<gl-button variant="link">` with no `@click`/`href`/`:to`:** wire a real action (§1.10).
44. **Inline `...helper(this.x)` spread inside a return object:** extract to named computed (§5.13).
45. **Nested `const findX = ...` inside a `describe`:** hoist to top of spec file (§6.27).
46. **`jest.spyOn(wrapper.vm.$apollo, 'mutate')`:** assert on the handler mock you own (§6.28).
47. **Assertion helper with no input validation:** add a `throw` at the top for invalid states (§6.29).
48. **`if (!event) return` at the top of every listener:** move the guard to the emit site (§1.11).
49. **`x !== null` where `undefined` is reachable:** use `x != null` or narrow by shape (§7.3).
50. **Bare numeric literals in thresholds, tick counts, opacities, colors, or camera math:** extract to module-scope `UPPER_SNAKE_CASE` constants named by role (§5.14).
