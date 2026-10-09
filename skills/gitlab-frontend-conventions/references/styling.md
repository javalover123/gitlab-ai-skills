# §2. Pajamas, Tailwind, and styling

## §2.1 Prefer Tailwind utilities; scoped styles are (almost) banned

**Confidence:** hard.

**Rule — positive framing.** Default to Pajamas Tailwind utilities (`gl-*`).
If a CSS property has a Tailwind equivalent, use it. Reach for the named
design-token utility first (`gl-max-w-26`, `gl-min-h-12`), fall back to
arbitrary syntax (`gl-min-h-[5rem]`) only when no token matches, and only
write custom CSS when neither exists.

**Rule — negative framing.** Scoped styles are rarely, if ever, the GitLab
Vue way. Don't add a `<style scoped>` block to hold values Tailwind can
already express.

**Verbatim — canonical "use the utility" nudge.**
- !227814 note 3171915417 (`explorer_graph_toolbar.vue:81`):
  > **Suggestion** Why not use the [max width utility](https://design.gitlab.com/tailwind-documentation/max-width)
  > and that way we don't need to override this? **gl-max-w-26** roughly
  > gives us 208px and it would align with our design system.

**Verbatim — "should come from tailwind" drumbeat across the MR.**
- !227814 summary (3171916100, item 1):
  > Scoped styles is rarely, if ever, the way we built Vue components. […]
  > Scoped styled was only ever used to override underlying libraries
  > stylings that we have no control over.
- !227814 note 3171915508 (`explorer_node_sidebar.vue:94`):
  > **Issue** We try to avoid scoped style as much as possible. There's a
  > few properties in there like top, max-height, border and background
  > that should all comes from tailwind utils.
- !227814 note 3171915649 (`explorer_table_panel.vue:142`):
  > **Suggestion** These values exist in our tailwind utils, so we can drop
  > the scoped style and add it directly!
- !227814 note 3171915771 (`graph_canvas.vue:129`):
  > **Issue** we can remove this for tailwind too
- !227814 note 3171915918 (`graph_explorer.vue:325`):
  > The min height can move to a tailwind css class here
- !227814 note 3171915987 (`graph_explorer.vue:380`):
  > Everything in this scoped block should technically all be possible in
  > tailwind too.
- !227814 note 3171916006 (`node_detail_overlay.vue:33`):
  > **Issue** the display none can be done with the tailwind utils an the
  > harcoded pixel values should be possible too.

**Counts in monolith (snapshot 2026-04-23).** 31 `<style scoped>` blocks
across ~4,500 Vue files under `app/assets/javascripts/` and
`ee/app/assets/javascripts/` — under 1%. Do not add to this count.

**Swap table (verified against GitLab design tokens).**

| CSS                          | Tailwind utility       | Note                              |
|------------------------------|------------------------|-----------------------------------|
| `max-width: 208px`           | `gl-max-w-26`          | named token `spacing-scale-26 = 13rem`  |
| `min-height: 5rem`           | `gl-min-h-12`          | named token `spacing-scale-12 = 5rem`   |
| `min-height: 13rem`          | `gl-min-h-26`          | arbitrary `gl-min-h-[5rem]` also valid  |
| `margin-bottom: 0.75rem`     | `gl-mb-3`              | high-traffic utility                    |
| `margin-top: 0`              | `gl-mt-0`              | high-traffic utility                    |
| `padding: 0.25rem 0`         | `gl-py-1`              |                                         |
| `font-size: 0.75rem`         | `gl-text-sm`           | `gl-text-sm` is canonical; `gl-text-xs` is effectively unused |
| `font-weight: bold`          | `gl-font-bold`         |                                         |
| `color: var(--subtle)`       | `gl-text-subtle`       | semantic token; auto-adapts to dark     |
| `display: flex`              | `gl-flex`              | dominant flex utility                   |
| `align-items: center`        | `gl-items-center`      |                                         |
| `display: none`              | `gl-hidden`            |                                         |
| `flex: 1`                    | `gl-flex-1`            |                                         |

Cite: spacing tokens live in `node_modules/@gitlab/ui/src/tokens/build/css/tokens.css`
(`--gl-spacing-scale-12 = 5rem`, `--gl-spacing-scale-26 = 13rem`,
`--gl-spacing-scale-75 = 37.5rem`). Prefer named tokens to arbitrary values
when a match exists.

**Do.**
- Use Tailwind utilities. Reach for `gl-max-w-26` over a custom
  `max-width: 200px`.
- Use **semantic tokens** (`gl-text-subtle`, `gl-bg-subtle`) — they auto-adapt
  to dark mode (per `doc/development/fe_guide/dark_mode.md`).
- If overriding library styles (Monaco, Three.js canvas), use a page-scoped
  SCSS file under `app/assets/stylesheets/page_bundles/` (see §2.3).

**Don't.**
- Introduce a scoped class only to hold `max-width`, `top`, `background`,
  `border`, or `display` — all expressible in utilities.
- The prefix form is `dark:gl-*` (Tailwind dark variant composed with a
  Pajamas utility). ~55 uses. Never `gl-dark:*` — that prefix does not
  exist. Prefer semantic tokens (`gl-text-subtle`, `gl-bg-subtle`) over
  `dark:gl-*` when a token can express it.
- Duplicate dark-mode selectors in scoped blocks. Use semantic tokens.

**Detection heuristic (verified).**
- `rg '^<style scoped' -g '*.vue'` — 31 hits total; every match is
  high-signal.
- Empty `<style scoped></style>` blocks are pure noise — delete on sight.

## §2.2 Library overrides live in `page_bundles/` or `framework/`, not scoped

**Rule.** Monaco / Source Editor / third-party widget overrides go in:
- `app/assets/stylesheets/framework/source_editor.scss` for global Monaco
  overrides.
- `app/assets/stylesheets/page_bundles/<page>.scss` for page-scoped overrides.
Never inside `<style scoped>`.

**Verbatim.** !227814 note 3171915552 (`explorer_query_panel.vue:115`):
> **Issue** […] If we need to override the styles of monaco editor, then
> I'd expect a new SCSS file mapped to the Orbit page instead of scoped
> style. […] 1. Historically in GitLab Monolith, we've avoided scoped styles.
> […] 2. It becomes a bit too easy to override GitLab Pajamas design
> system. In SCSS, you can more easily consume SCSS variables […]
> I would want to understand first why Source editor needs all of this and
> why we aren't updating it in the source if it's a widespread issue.

**Do.**
- First ask if the override belongs upstream (in `SourceEditor`).
- If truly page-specific, add a `page_bundles/<page>.scss` and consume SCSS
  variables (`$gl-padding`, design tokens) to stay Pajamas-aligned.

**Don't.**
- Use `:deep()` + `!important` inside `<style scoped>` to defeat a library.
- Create a new top-level SCSS file unless it's mapped to a real page bundle
  or framework entry.

## §2.3 Enum strings for tabs/modes, never numeric indices

**Rule.** Tab identifiers, view modes, step keys — all use string constants.
Reorder-safe, grep-safe, and readable.

**Verbatim.** !227814 note 3171915607 (`explorer_tab_bar.vue:43`):
> **Suggestion** Index base nearly always end up breaking something. Can we
> use an ENUM here for the tab value?

**Bad.**
```vue
<gl-button :selected="activeTab === 0" @click="$emit('update-active-tab', 0)">
<gl-button :selected="activeTab === 1" @click="$emit('update-active-tab', 1)">
```

**Good.**
```js
// constants.js
export const TAB_GRAPH = 'graph';
export const TAB_TABLE = 'table';
```
```vue
<gl-button
  :selected="activeTab === $options.TAB_GRAPH"
  @click="$emit('update-active-tab', $options.TAB_GRAPH)"
>
```

**In-tree reference.** `app/assets/javascripts/groups/your_work/constants.js:51-72`
uses `{ ...baseTab, value: 'member' }` objects, templates bind to `value`.

**Adoption:** ADOPTED in !227814 final state.
