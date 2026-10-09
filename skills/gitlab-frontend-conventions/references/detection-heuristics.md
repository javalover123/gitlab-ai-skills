# §12. Detection heuristics (auto-fix grep commands)

Run these before requesting review. Counts below are a snapshot from
2026-04-23 against `a local `gitlab-org/gitlab` checkout` on `master`. Re-run
before trusting — the monolith drifts fast.

| # | Purpose | Command | Monolith hits (snapshot) | Notes |
|---|---------|---------|--------------------------|-------|
| 1 | `<style scoped>` | `rg '^<style scoped' -g '*.vue'` | 31 | Each hit high-signal |
| 2 | Raw absolute CSS | `rg 'position:\s*absolute' -g '*.vue' -g '!vendor/**'` | ~9 | Review each |
| 3 | Imperative Apollo queries | `rg 'this\.\$apollo\.query\(' -g '*.vue'` | ~77 | Don't flag `.mutate` |
| 4 | Mocking `vue-apollo` wholesale | `rg "jest\.mock\(['\"]vue-apollo['\"]" -g '*.js'` | ~3 | All anti-patterns |
| 5 | `mockClear` in beforeEach | `rg -U 'beforeEach\([^)]*\)\s*=>\s*\{[^}]*mockClear' -g '*.js' --multiline` | — | Only flag inside `beforeEach` |
| 6 | Brittle snapshots | `rg 'wrapper\.(element\|html\(\))\).*toMatchSnapshot' -g '*.js'` | ~176 | Brittle form; replace |
| 7 | `wrapper.vm` in integration | `rg 'wrapper\.vm\.' -g '**/msw_integration/**/*.js' -g '**/integration/**/*.js'` | 13 | All `wrapper.vm.$toast` in AI catalog |
| 8 | Router asserts in integration | `rg 'router\.currentRoute' -g '**/integration/**/*.js' -g '**/msw_integration/**/*.js'` | 37 | AI catalog suite |
| 9 | `check*` mutator | `rg 'check[A-Z]\w*\s*\(\)\s*\{' -g '*.vue'` | ~34 raw, ~5 real | Verify body mutates `this.*` |
| 10 | `!== undefined` (smell with FPs) | `rg '!==\s*undefined' -g '*.js' -g '*.vue' -g '*.ts' \| rg -v 'dataset\.'` | ~172 | Exclude `dataset.*` |
| 11 | forEach building arrays | `rg 'forEach\(' -g 'app/assets/javascripts/**/*.js' -g 'ee/app/assets/javascripts/**/*.js'` | — | Review by hand |
| 12 | Tab index compare | `rg 'activeTab\s*===\s*\d' -g '*.vue'` | — | Replace with string enum |
| 13 | Same query two apollo entries | Grep per file for duplicate `query:\s+<ident>` under `apollo:` | — | Manual per file |
| 14 | Hand-rolled `is*Loading` | Find `is.*Loading` in `data()` assigned inside `result()` | — | ast-grep preferred |
| 15 | `newVal !== oldVal` inside watcher | `rg -U 'watch:\s*\{[^}]*\(\w+,\s*\w+\)[^}]*!==' -g '*.vue'` | — | Watchers only fire on change |
| 16 | Spy on `$apollo.mutate` | `rg -n 'spyOn\([^\n]*\$apollo\|wrapper\.vm\.\$apollo\.mutate' -g '*_spec.js'` | — | Use handler mock instead |
| 17 | Nested finders inside describe | `rg -n '^\s{4,}const find[A-Z]\w*\s*=\s*\(\)\s*=>' spec ee/spec -g '*_spec.js'` | — | Hoist to top of file |
| 18 | Inline `...helper(this.x)` in return | `rg -n '\.\.\.[A-Za-z_][A-Za-z0-9_]*\(this\.[A-Za-z_][A-Za-z0-9_]*\)' -g '*.vue'` | — | Extract to named computed |
| 19 | `<gl-button variant="link">` with no action | `rg -n '<gl-button[^>]*variant="link"' -g '*.vue'` then audit for missing `@click`/`href`/`:to` | — | See §1.10 |
| 20 | `!== null` where `undefined` is reachable | `rg '!==\s*null' -g '*.vue' -g '*.js' -g '*.ts'` | — | Audit each; often `!= null` or `typeof`/`.length`/`Number.isFinite` is correct — see §7.3 |
| 21 | Listener arg guard `if (!arg) return` | `rg -n 'handle[A-Z]\w*\(\w+\)\s*\{[\s\n]*if\s*\(!' -g '*.vue'` | — | Push guard to the emit site and document via `emits: { 'name': validator }` — see §1.11 |
| 22 | Inline hex color literal | `rg -n '0x[0-9a-fA-F]{6}' -g '*.js' -g '*.vue'` | — | Move to a named palette constant (§5.14) |
| 23 | Bare tick/timeout literal | `rg -n 'setTimeout\(\|setInterval\(' -g '*.js' -g '*.vue' -A 1` | — | Name the duration (`IDLE_TIMEOUT_MS`, `DEBOUNCE_RESIZE_MS`) — see §5.14 |
