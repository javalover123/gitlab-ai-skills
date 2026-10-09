# §12. Detection heuristics (auto-fix grep commands)

Run these before requesting review. Counts below are a snapshot from
2026-04-23 against a local `gitlab-org/gitlab` checkout on `master`. Re-run
before trusting — the monolith drifts fast.

| # | Purpose | Monolith hits (snapshot) | Notes |
|---|---|---|---|
| 1 | `<style scoped>` | 31 | Each hit high-signal |
| 2 | Raw absolute CSS | ~9 | Review each |
| 3 | Imperative Apollo queries | ~77 | Don't flag `.mutate` |
| 4 | Mocking `vue-apollo` wholesale | ~3 | All anti-patterns |
| 5 | `mockClear` in beforeEach | — | Only flag inside `beforeEach` |
| 6 | Brittle snapshots | ~176 | Brittle form; replace |
| 7 | `wrapper.vm` in integration | 13 | All `wrapper.vm.$toast` in AI catalog |
| 8 | Router asserts in integration | 37 | AI catalog suite |
| 9 | `check*` mutator | ~34 raw, ~5 real | Verify body mutates `this.*` |
| 10 | `!== undefined` (smell with FPs) | ~172 | Exclude `dataset.*` |
| 11 | forEach building arrays | — | Review by hand |
| 12 | Tab index compare | — | Replace with string enum |
| 13 | Same query two apollo entries | — | Manual per file |
| 14 | Hand-rolled `is*Loading` | — | ast-grep preferred |
| 15 | `newVal !== oldVal` inside watcher | — | Watchers only fire on change |
| 16 | Spy on `$apollo.mutate` | — | Use handler mock instead |
| 17 | Nested finders inside describe | — | Hoist to top of file |
| 18 | Inline `...helper(this.x)` in return | — | Extract to named computed |
| 19 | `<gl-button variant="link">` with no action | — | See §1.10 |
| 20 | `!== null` where `undefined` is reachable | — | Audit each; often `!= null` or `typeof`/`.length`/`Number.isFinite` is correct — see §7.3 |
| 21 | Listener arg guard `if (!arg) return` | — | Push guard to the emit site and document via `emits: { 'name': validator }` — see §1.11 |
| 22 | Inline hex color literal | — | Move to a named palette constant (§5.14) |
| 23 | Bare tick/timeout literal | — | Name the duration (`IDLE_TIMEOUT_MS`, `DEBOUNCE_RESIZE_MS`) — see §5.14 |

## Commands

Append the changed file paths to each command to scope it to your MR. Numbers match the table above.

```sh
# 1
rg '^<style scoped' -g '*.vue'
# 2
rg 'position:\s*absolute' -g '*.vue' -g '!vendor/**'
# 3
rg 'this\.\$apollo\.query\(' -g '*.vue'
# 4
rg "jest\.mock\(['\"]vue-apollo['\"]" -g '*.js'
# 5
rg -U 'beforeEach\([^)]*\)\s*=>\s*\{[^}]*mockClear' -g '*.js' --multiline
# 6
rg 'wrapper\.(element|html\(\))\).*toMatchSnapshot' -g '*.js'
# 7
rg 'wrapper\.vm\.' -g '**/msw_integration/**/*.js' -g '**/integration/**/*.js'
# 8
rg 'router\.currentRoute' -g '**/integration/**/*.js' -g '**/msw_integration/**/*.js'
# 9
rg 'check[A-Z]\w*\s*\(\)\s*\{' -g '*.vue'
# 10
rg '!==\s*undefined' -g '*.js' -g '*.vue' -g '*.ts' | rg -v 'dataset\.'
# 11
rg 'forEach\(' -g 'app/assets/javascripts/**/*.js' -g 'ee/app/assets/javascripts/**/*.js'
# 12
rg 'activeTab\s*===\s*\d' -g '*.vue'
# 13 (manual, per file)
# grep for duplicate `query:\s+<ident>` under `apollo:`
# 14 (manual; ast-grep preferred)
# find `is.*Loading` in `data()` assigned inside `result()`
# 15
rg -U 'watch:\s*\{[^}]*\(\w+,\s*\w+\)[^}]*!==' -g '*.vue'
# 16
rg -n 'spyOn\([^\n]*\$apollo|wrapper\.vm\.\$apollo\.mutate' -g '*_spec.js'
# 17
rg -n '^\s{4,}const find[A-Z]\w*\s*=\s*\(\)\s*=>' spec ee/spec -g '*_spec.js'
# 18
rg -n '\.\.\.[A-Za-z_][A-Za-z0-9_]*\(this\.[A-Za-z_][A-Za-z0-9_]*\)' -g '*.vue'
# 19
rg -n '<gl-button[^>]*variant="link"' -g '*.vue'
# then audit each hit for a missing @click / href / :to
# 20
rg '!==\s*null' -g '*.vue' -g '*.js' -g '*.ts'
# 21
rg -n 'handle[A-Z]\w*\(\w+\)\s*\{[\s\n]*if\s*\(!' -g '*.vue'
# 22
rg -n '0x[0-9a-fA-F]{6}' -g '*.js' -g '*.vue'
# 23
rg -n 'setTimeout\(|setInterval\(' -g '*.js' -g '*.vue' -A 1
```
