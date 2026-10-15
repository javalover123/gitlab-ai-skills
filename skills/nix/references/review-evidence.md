# Using the review corpus without being misled

Load this before you cite `find-rules.py` output as a reason for a change, or when a reviewer-derived rule conflicts with what you see in the docs. The corpus is a model-written distillation of about 500,000 nixpkgs PRs spanning 14 years (3,397 counted rules in `assets/rules.tsv`). It tells you what reviewers have asked for. It doesn't tell you what's currently required, and some of it is wrong. Verified against nixpkgs master (26.11 development, Oct 2026).

Companion files: [upstreaming-and-prs](upstreaming-and-prs.md) for PR mechanics, [upstreamable-checklist](upstreamable-checklist.md) for the code-level checklist, and the per-topic references named in the category table below.

**Contents:** [Provenance](#provenance) · [What the numbers mean](#what-the-numbers-mean) · [Running find-rules.py](#running-find-rulespy) · [The 15 categories](#the-15-categories) · [Curated rules by category](#curated-rules-by-category) · [Rules the corpus gets wrong or states misleadingly](#rules-the-corpus-gets-wrong-or-states-misleadingly) · [Dated advice to ignore](#dated-advice-to-ignore)

## Provenance

`assets/rules.tsv` is a snapshot, generated once in October 2026 from the merged and closed pull requests of `NixOS/nixpkgs` (review comments, review verdicts, and each PR's outcome). A language model distilled one generic rule per PR, near-duplicates were merged, and the counts below were computed by code, not by the model. Rules backed by fewer than 5 PRs were dropped. The snapshot isn't refreshed automatically and the generator isn't part of this repository, so anything newer than the snapshot is absent. Treat `find-rules.py` as a way to find out what reviewers have historically asked for, and the tree and manual as the authority on what's required now.

## What the numbers mean

Each line of `find-rules.py` output looks like:

```
[fetchers-and-sources] support 159, 83% merged, 55 cr, 124 maint
    Prefer `fetchFromGitHub` for GitHub-hosted sources, using `tag` instead of `rev` ...
```

| Field | Meaning | Limits |
|-------|---------|--------|
| `support` | PRs the rule was distilled from | Counts PRs, not independent confirmations. One PR can back many rules, and near-identical rules each get their own count. Don't add counts across paraphrases. |
| `merged%` | Share of those PRs that merged | A correlation. See selection effects below. |
| `cr` | PRs where a reviewer filed a formal "Request changes" | The best signal for active enforcement. It undercounts: `CONTRIBUTING.md` says comments are non-blocking by default, so many enforced conventions are raised as plain comments. |
| `maint` | PRs a package maintainer reviewed | Reflects how many PRs touch maintained packages, not how correct the rule is. |

Limits to keep in mind:

- Correlation, not cause. A 95% merge rate on a rule means PRs mentioning it usually merged. It doesn't mean following it makes a PR merge, and a 2% rate doesn't mean the rule is wrong.
- Selection effects dominate the extremes. "Search for existing PRs first" shows 1% merged on 1,708 PRs because those are most likely the duplicates reviewers closed. "Limit to 1-10 rebuilds" shows 99% merged on 593 PRs, probably because small leaf updates merge fast whatever you do. The many `nixpkgs-review` rules at 3,512 support and 100% merged probably come from the PR template's own checkbox text, so they'd measure how often the template was filled in. All three readings are inferences, not measurements; the point is that you can't read these numbers as effects.
- Age. Advice spans 14 years of tool names and conventions. `lib.mdDoc`, `stdenv.isDarwin`, `substituteAll`, `format = "pyproject"` and `nixfmt-rfc-style` all appear as live advice and are gone or superseded (see the end of this file).
- Distillation errors. A model wrote each rule from review comments. It sometimes invented a function (`platformDontCheck`), inverted a rule, merged two contexts, or emitted a placeholder (`SKIP`, support 1,563). Check anything you plan to cite against the tree.
- Contradictions. The corpus holds opposing rules side by side (lowercase versus capitalized descriptions, `postPatch` substitution versus consolidated patch files, tags versus commit hashes). When two rules disagree, the docs decide.
- Merge-rate priors differ by PR type. Bot updates and leaf bumps merge near 100%; breaking changes and new governance proposals merge far less. Compare a rule's `merged%` only with rules from the same PR type.

How to weigh a rule:

| Signal | Reading |
|--------|---------|
| High `cr`, docs agree | Treat as a requirement. |
| High `cr`, docs silent | Reviewer convention. Follow it in nixpkgs PRs; don't call it policy. |
| High support, low `cr`, ~100% merged | Background or template text. No information about the rule. |
| Low `merged%` on a duplicate- or conflict-related rule | Closed-PR artifact. |
| Docs disagree | Docs win. Say so in the PR if a reviewer pushes the old rule. |
| Two corpus rules contradict each other | Neither one. Look up the doc, or ask the reviewer which they mean. |

## Running find-rules.py

```
python3 scripts/find-rules.py [--category C] [--min-support N] [--sort support|merged|enforced] [--limit N] [KEYWORD...]
python3 scripts/find-rules.py --list-categories
```

Run it from the skill directory. Every keyword must appear in the rule text (case-insensitive substring), so `passthru.tests` and `fetchFromGitHub` work as written. Output is capped at 15 rules unless you set `--limit`. Exit status 1 means no match. `--sort enforced` ranks by `cr`, then support.

| Question | Command |
|----------|---------|
| What do reviewers say about `tag` versus `rev`? | `scripts/find-rules.py fetchFromGitHub tag` |
| Which module rules touch systemd? | `scripts/find-rules.py --category nixos-modules --min-support 10 systemd` |
| What's most enforced in package structure? | `scripts/find-rules.py --sort enforced --min-support 20 --category derivation-structure` |
| How are tests wired up? | `scripts/find-rules.py --sort enforced passthru.tests` |
| What does the corpus say about backports? | `scripts/find-rules.py --category rebuilds-staging-and-branching --limit 30 backport` |
| Which rules mention a function I'm about to use? | `scripts/find-rules.py --limit 20 substituteInPlace` |
| Is a piece of advice obsolete? Search the name, then check the tree. | `scripts/find-rules.py mdDoc` |
| Which rules look like template boilerplate? | `scripts/find-rules.py --sort merged --min-support 100 nixpkgs-review` |

Workflow: search for the function or attribute you're about to write, read the top `--sort enforced` hits, then grep `doc/`, `pkgs/README.md`, `CONTRIBUTING.md` or `lib/` in a nixpkgs checkout. Cite the doc, and cite the counts only as supporting context.

## The 15 categories

| Slug | Rules | Covers | Reference |
|------|-------|--------|-----------|
| `pr-process-and-commits` | 608 | Commit format and granularity, duplicates, review etiquette, force-push, maintainers | [upstreaming-and-prs](upstreaming-and-prs.md) |
| `testing-and-validation` | 472 | `checkPhase`, `passthru.tests`, `nixpkgs-review`, platform builds, disabled tests | [testing](testing.md) |
| `derivation-structure` | 449 | `pname`/`version`, dependency lists, `finalAttrs`, `by-name`, `meta` presence | [derivation-authoring](derivation-authoring.md) |
| `nix-language-style` | 278 | Formatting, `lib.optional*`, `rec`, `with`, ordering, unused code | [nix-language-style](nix-language-style.md) |
| `versioning-and-updates` | 252 | Version strings, update scripts, deprecation, removal, pins | [versioning-and-updates](versioning-and-updates.md) |
| `build-closure-and-platforms` | 195 | Dependency types, propagation, cross-compilation, platform conditionals | [build-closure-and-platforms](build-closure-and-platforms.md) |
| `rebuilds-staging-and-branching` | 194 | Staging routing, rebuild counts, backports | [upstreaming-and-prs](upstreaming-and-prs.md) |
| `patches-and-overrides` | 165 | Patches, `substituteInPlace`, `fetchpatch`, overrides | [patches-and-overrides](patches-and-overrides.md) |
| `language-ecosystems` | 153 | Python, Rust, Go, Node, Qt and other builders | [lang-python](lang-python.md), [lang-rust](lang-rust.md), [lang-other-ecosystems](lang-other-ecosystems.md) |
| `nixos-modules` | 153 | Options, `settings`, systemd, users, deprecation | [nixos-modules](nixos-modules.md) |
| `fetchers-and-sources` | 145 | Fetchers, hashes, tags, patches as sources | [fetchers-and-sources](fetchers-and-sources.md) |
| `documentation-and-release-notes` | 142 | Release notes, descriptions, explanatory comments | [upstreaming-and-prs](upstreaming-and-prs.md) |
| `security-and-hardening` | 103 | CVE handling, hardening, runtime libraries, systemd isolation | [security](security.md) |
| `meta-and-licensing` | 82 | `meta.*`, licenses, platforms, `mainProgram` | [meta-and-licensing](meta-and-licensing.md) |
| `other` | 6 | Inclusion bar, upstream-first, hardware repositories (mostly a placeholder) | [upstreaming-and-prs](upstreaming-and-prs.md) |

## Curated rules by category

Each table is the most strongly enforced rules (`--sort enforced --min-support 20`), rewritten as the rule that holds in the current tree, with paths that back it. "Counts" are `support / cr / merged%`. Where two or more corpus rules say the same thing, the counts are from the strongest one. Dubious rules aren't in these tables; they're in the next section.

### pr-process-and-commits

| Rule | Counts | Docs agree? |
|------|--------|-------------|
| One commit per logical unit; squash fixups. Don't over-fragment. | 1161 / 243 / 72 | Yes: `CONTRIBUTING.md` (Commit conventions, "over-fragmentation causes friction") |
| `maintainers: add <handle>` is its own commit and comes before the package commits. | 245 / 108 / 79 | Yes: `CONTRIBUTING.md`, `maintainers/README.md`, `doc/stdenv/meta.chapter.md` |
| Subject is `attr: action`, no trailing period, with a body that says why and links the changelog. | 632 / 92 / 72 | Yes: `pkgs/README.md`; `ci/github-script/lint-commits.ts` enforces the colon, the period and fixup rules |
| Use the area prefix: `nixos/<module>:`, `doc/<component>:`, `lib.<section>:`. | 254 / 71 / 81 | Yes, with a fix: the docs say `doc/component:` (`doc/README.md`), not `doc:` |
| Respond to every comment and suggestion before merge, applying or declining each. | 255 / 71 / 75 | Yes: `CONTRIBUTING.md` (Review and Merge conventions) |
| Fix failing CI and merge conflicts; a red PR isn't merged. | 393 / 37 / 30 | Yes: `CONTRIBUTING.md` ("Your PR will not be merged while CI is still failing") |
| Search for existing PRs before opening one. | 1708 / 46 / 2 | Docs silent. Sound practice; the 2% is the duplicates that got closed |
| Backport commits with `git cherry-pick -x`. | 225 / 12 / 80 | Yes: `CONTRIBUTING.md` (How to backport); CI checks the trailer on stable PRs |

### rebuilds-staging-and-branching

| Rule | Counts | Docs agree? |
|------|--------|-------------|
| 500+ rebuilds: consider `staging`; 1000+: it's a mass rebuild, use `staging`. | 1135 / 67 / 64 | Yes, with sharper numbers: `CONTRIBUTING.md` (Changes causing mass rebuilds), `ci/github-script/check-target-branch-policy.ts` |
| Backport fixes and security fixes after they merge to `master`. | 449 / 8 / 95 | Yes: `CONTRIBUTING.md` (Changes acceptable for releases), which also allows new packages and non-breaking minor bumps |
| Open a separate PR per release branch, cherry-picked with `-x`. | 45 / 9 / 76 | Yes: `CONTRIBUTING.md`, automatic backport via label in `.github/workflows/backport.yml` |
| Defer breaking changes to the next release; release branches take backwards-compatible changes. | 98 / 9 / 82 | Yes: `CONTRIBUTING.md`, with exceptions for client-dependent services and security-critical applications |
| Don't backport to an end-of-life branch. | 67 / 5 / 1 | Yes: `nix-instantiate --eval -A lib.trivial.oldestSupportedRelease` gives the oldest supported release |
| Add the `backport release-YY.MM` label, which needs maintainer status. | 114 / 2 / 96 | Yes: `CONTRIBUTING.md` (Automatically backporting changes) |
| Check dependent packages before merging large dependency updates. | 198 / 12 / 67 | Yes: `.github/PULL_REQUEST_TEMPLATE.md` (`nixpkgs-review`), `CONTRIBUTING.md` |
| Check a backport builds on the target branch. | 211 / 8 / 80 | Partly: CI runs the same required checks on release PRs, no explicit doc rule |

### documentation-and-release-notes

| Rule | Counts | Docs agree? |
|------|--------|-------------|
| Write release notes for breaking changes and for new, removed or significantly changed NixOS modules. | 1177 / 138 / 88 | Yes: `CONTRIBUTING.md` (Release notes); files under `nixos/doc/manual/release-notes/` and `doc/release-notes/` |
| `meta.description` is one sentence, capitalized, with no leading article, no package name and no trailing period. | 146 / 59 / 90 | Yes: `doc/stdenv/meta.chapter.md`, `pkgs/README.md` |
| Comment why a test or check is disabled. | 355 / 58 / 93 | Yes: `pkgs/README.md` (Reviewing contributions) |
| Comment the reason for workarounds, pins, patches and non-default flags. | 423 / 37 / 90 | Yes: `pkgs/README.md` (Reviewing contributions) |
| Link the upstream changelog or release notes in an update's commit body. | 116 / 14 / 89 | Yes: `CONTRIBUTING.md` (Writing good commit messages) |
| Explain why a dependency was added, removed or pinned. | 451 / 23 / 93 | Partly: `pkgs/README.md` asks for pinned versions and non-default flags, not every dependency change |
| Include docs with the change instead of a follow-up. | 137 / 22 / 95 | Yes: `CONTRIBUTING.md` step 3 and the template's release-notes checkboxes |
| Keep existing documentation anchors when moving content. | 47 / 8 / 89 | Yes: `doc/README.md` (Anchors), `doc/redirects.json` |

### other

This category is nearly empty; the real signal lives in `pkgs/README.md`.

| Rule | Counts | Docs agree? |
|------|--------|-------------|
| Keep immature or niche software out of nixpkgs (filed under `derivation-structure`, which names NUR). | 13 / 2 / 8 | Yes for the principle: `pkgs/README.md` (adding a package). The tree never mentions NUR |
| Report upstream version constraints upstream instead of carrying nixpkgs-only workarounds. | 56 / 6 / 29 | Docs silent; consistent with `pkgs/README.md` (patches, overrides) |
| Hardware firmware and kernel variants go to `nixos-hardware`. | 5 / 1 / 20 | Yes for kernels: `doc/packages/linux.section.md` |
| Weigh maintenance burden before packaging software with heavy or unfree build requirements. | 8 / 0 / 25 | Yes: `pkgs/README.md` (adding a package) |

### build-closure-and-platforms

| Rule | Counts | Docs agree? |
|------|--------|-------------|
| Use `autoPatchelfHook` for prebuilt ELF binaries, and list `dlopen`ed libraries in `runtimeDependencies`. | 55 / 23 / 82 | Yes: `doc/hooks/autopatchelf.section.md` |
| Guard build-time execution with `stdenv.buildPlatform.canExecute stdenv.hostPlatform`. | 85 / 21 / 92 | Yes: `doc/stdenv/cross-compilation.chapter.md` |
| Build paths with `lib.makeBinPath`, `lib.makeLibraryPath` and `stdenv.hostPlatform.extensions.sharedLibrary`. | 87 / 17 / 92 | Partly: functions exist (`lib/strings.nix`, `lib/systems/default.nix`), no doc mandate |
| Test platforms through `stdenv.hostPlatform.isDarwin` and friends, not hardcoded strings. | 52 / 14 / 85 | Yes: `doc/stdenv/platform-notes.chapter.md`; no `stdenv.isDarwin` is left in `pkgs/` |
| Make heavy or test-only optional dependencies opt-in. | 115 / 22 / 85 | Docs silent; reviewer convention (`pkgs/README.md` only shows a `spellCheck` flag) |
| Scope platform failures with `meta.platforms`, `meta.badPlatforms` or `meta.broken`. | 87 / 15 / 87 | Yes: `CONTRIBUTING.md` (CI failed), `doc/stdenv/meta.chapter.md` |
| Use `propagatedBuildInputs` only when consumers need the dependency to build. | 118 / 28 / 61 | Partly: `doc/stdenv/stdenv.chapter.md` explains propagation, no "avoid" rule |

### derivation-structure

| Rule | Counts | Docs agree? |
|------|--------|-------------|
| Set `pname` and `version`; let `mkDerivation` build `name`. | 549 / 186 / 92 | Yes: `doc/stdenv/stdenv.chapter.md` |
| Declare dependencies as function arguments. No `with args;`, no trailing `...` unless truly generic. | 587 / 156 / 79 | Yes: `CONTRIBUTING.md` (Syntax) |
| Put build-time tools in `nativeBuildInputs` and host libraries in `buildInputs`. | 565 / 130 / 89 | Yes: `doc/stdenv/stdenv.chapter.md`, review checklist in `pkgs/README.md` |
| New packages set `meta.maintainers`. | 528 / 141 / 75 | Yes: `pkgs/README.md` (Meta attributes) |
| Set `meta.platforms`; prefer `lib.platforms.all` minus `badPlatforms`. | 344 / 87 / 84 | Yes: `doc/stdenv/meta.chapter.md` (no platform means no prebuilt binaries) |
| New top-level packages go in `pkgs/by-name/<xx>/<name>/package.nix`. | 138 / 68 / 68 | Yes: `pkgs/by-name/README.md` ("whenever possible"); `nixpkgs-vet` in CI |
| Use `finalAttrs`, not `rec`, for self-references. | 106 / 64 / 95 | Yes: `doc/stdenv/stdenv.chapter.md` (Fixed-point arguments) |
| Enable `__structuredAttrs = true` in new top-level packages. | 26 / 5 / 85 | Yes: `doc/stdenv/stdenv.chapter.md` ("All new top level packages must enable") |

### fetchers-and-sources

| Rule | Counts | Docs agree? |
|------|--------|-------------|
| Check the hash by building or prefetching; recompute it whenever `url`, version or fetcher changes. | 623 / 132 / 84 | Yes: `doc/build-helpers/fetchers.chapter.md` (an unchanged hash "will produce the same output as before") |
| Write `hash = "sha256-..."` (SRI), not `sha256 = ...`. | 305 / 128 / 89 | Yes: the same file calls `hash` the recommended attribute |
| Fetch GitHub sources with `fetchFromGitHub`. | 208 / 103 / 86 | Yes: `pkgs/README.md` (Sources) |
| For a release tag write `tag = "v${version}"`, not `rev = "refs/tags/..."`. | 159 / 55 / 83 | Yes: `doc/build-helpers/fetchers.chapter.md` ("safer", less boilerplate) |
| Pin full commit hashes in `rev`; never abbreviations. | 61 / 25 / 89 | Yes: `pkgs/README.md` (Sources note) |
| Fetch merged upstream patches; use `fetchpatch2` unless the patch has short hashes. | 278 / 60 / 92 | Yes, with a fix: `pkgs/README.md` (Patches) names `fetchpatch2` first |
| Prefer tagged releases over arbitrary commits. | 122 / 27 / 72 | Yes: `pkgs/README.md` (Versioning) allows `-unstable-` only when no release fits |

### language-ecosystems

| Rule | Counts | Docs agree? |
|------|--------|-------------|
| Python tests: `pytestCheckHook` in `nativeCheckInputs`, not a hand-written `checkPhase`. | 214 / 53 / 91 | Yes: `doc/languages-frameworks/python.section.md` |
| Python libraries live in `pkgs/development/python-modules/<name>/default.nix` and are called from `python-packages.nix`. | 95 / 43 / 74 | Yes: `python.section.md` |
| List the build backend in `build-system`. | 76 / 31 / 76 | Yes: `python.section.md` |
| `buildPythonApplication` for programs, `buildPythonPackage` for libraries. | 74 / 30 / 74 | Yes: `python.section.md` |
| Set `pyproject = true` (the corpus's `format = "pyproject"` is the old spelling). | 107 / 27 / 94 | Yes, rewritten: `python.section.md` says other formats are deprecated |
| Use `cargoHash`, not `cargoSha256`. | 41 / 15 / 90 | Yes: `doc/languages-frameworks/rust.section.md` |
| Use `python3Packages`, not `python3.pkgs`. | 31 / 12 / 87 | Yes: `python.section.md` (the legacy API isn't spliced) |
| Compare versions with `pythonOlder` and `pythonAtLeast`. | 169 / 23 / 89 | Yes: `python.section.md`; defined in `pkgs/development/interpreters/python/passthrufun.nix` |

### meta-and-licensing

| Rule | Counts | Docs agree? |
|------|--------|-------------|
| Use the specific `lib.licenses` attribute (`gpl3Only`, `gpl3Plus`), not the deprecated `gpl3`. | 602 / 147 / 92 | Yes: `lib/licenses/licenses.nix` marks `gpl2`, `gpl3`, `lgpl2`, `lgpl21`, `lgpl3` deprecated |
| Set `meta.description` and follow its format. | 152 / 44 / 82 | Yes: `doc/stdenv/meta.chapter.md` |
| Set `meta.mainProgram` when a primary executable exists, as a literal string. | 87 / 32 / 94 | Yes: `pkgs/README.md` (Meta attributes) |
| Express platform limits in `meta.platforms`, `badPlatforms` or `broken`. | 355 / 29 / 94 | Yes: `doc/stdenv/meta.chapter.md` |
| Set `meta.platforms` explicitly. | 73 / 20 / 92 | Yes: `doc/stdenv/meta.chapter.md` |
| `meta.license` is a `lib.licenses` attribute, a list only when parts differ. | 41 / 17 / 76 | Yes, rewritten: `doc/stdenv/meta.chapter.md` |
| Set `meta.maintainers` so reviews have an owner. | 91 / 21 / 63 | Yes: `pkgs/README.md`, `maintainers/README.md` |

### nix-language-style

| Rule | Counts | Docs agree? |
|------|--------|-------------|
| Format with `nixfmt`. | 590 / 165 / 89 | Yes: `CONTRIBUTING.md` (Formatting); `ci/treefmt.nix` runs it |
| `finalAttrs` instead of `rec` in `mkDerivation`. | 154 / 78 / 90 | Yes: `doc/stdenv/stdenv.chapter.md` |
| Use `lib.optional` and `lib.optionals` for conditional lists. | 292 / 72 / 93 | Yes: `CONTRIBUTING.md` (Syntax; `if ... then [ ] else null` allowed only for a no-rebuild bug fix) |
| Use `lib.optionalString` for conditional strings. | 160 / 44 / 94 | Docs silent; the function is in `lib/strings.nix` and follows the same rule |
| Remove unused arguments and bindings. | 578 / 86 / 93 | Reviewer-enforced only: `ci/treefmt.nix` ignores the unused-binding diagnostics |
| Prefer `lib.` prefixes or `inherit` over a broad `with lib;`. | 191 / 101 / 87 | Partly: `nix.dev/source/guides/best-practices.md` advises against `with`; nixpkgs docs don't forbid it, yet only 27 `by-name` files still use `with lib;`, against 21,994 package directories |

### nixos-modules

| Rule | Counts | Docs agree? |
|------|--------|-------------|
| Create service directories with `StateDirectory` and `RuntimeDirectory`, not tmpfiles or activation scripts. | 58 / 23 / 95 | Yes: `nixos/doc/manual/development/activation-script.section.md` |
| Install upstream units with `systemd.packages` instead of copying them. | 56 / 22 / 75 | Partly: `nixos/doc/manual/administration/service-mgmt.chapter.md` documents it, no mandate |
| Use a freeform `settings` option typed by `pkgs.formats.*` for Nix-representable config. | 42 / 20 / 76 | Yes: `nixos/doc/manual/development/settings-options.section.md` (RFC 42) |
| Make features opt-in; enabling a module mustn't open firewall ports. | 80 / 17 / 78 | Yes: `nixos/README.md` (New modules) |
| Type options, and give each a description, default and example. | 53 / 15 / 72 | Yes: `nixos/README.md` (Module updates and New modules) |
| Deprecate with `mkRenamedOptionModule` or `mkRemovedOptionModule` and a release note. | 56 / 14 / 84 | Yes: `nixos/README.md` |
| Don't assign static uids and gids; use `DynamicUser` or a system user with no fixed id. | 22 / 11 / 68 | Yes: header of `nixos/modules/misc/ids.nix` (RFC 52) |
| Compose with `mkMerge` and `mkIf`. | 63 / 15 / 83 | Yes: `nixos/doc/manual/development/option-def.section.md` |

### patches-and-overrides

| Rule | Counts | Docs agree? |
|------|--------|-------------|
| Make small edits in `postPatch` with `substituteInPlace --replace-fail`. | 386 / 94 / 93 | Yes: `doc/stdenv/stdenv.chapter.md`; plain `--replace` is deprecated in `pkgs/stdenv/generic/setup.sh` |
| Name or comment every patch so its purpose and upstream status are clear. | 455 / 65 / 91 | Yes: `pkgs/README.md` (Patches) |
| Fetch merged upstream patches; vendor a `.patch` only when it's Nix-specific, hard to fetch or its URL is unstable. | 189 / 31 / 89 | Yes: `pkgs/README.md` (Fetching and vendoring patches) |
| Don't override `patchPhase`; use `patches` and `postPatch`. | 76 / 20 / 74 | Yes: review checklist in `pkgs/README.md` ("the list of `phases` is not overridden") |
| Keep each patch small, and drop it when upstream has the fix. | 197 / 26 / 75 | Partly: `pkgs/README.md` says clarity helps maintainers "determine when old patches are no longer required" |
| Substitute store paths into scripts with `substituteInPlace` or `replaceVars`. | 132 / 26 / 81 | Yes, rewritten: `pkgs/build-support/replace-vars/replace-vars.nix` |
| Prefer upstream fixes over local workarounds. | 236 / 24 / 81 | Yes: `pkgs/README.md` (`overrideAttrs` section argues for real support in the package) |

### security-and-hardening

| Rule | Counts | Docs agree? |
|------|--------|-------------|
| Keep security fixes out of unrelated PRs so they can be backported. | 128 / 26 / 80 | Partly: `pkgs/README.md` (Security) routes fixes through master, then release |
| List `dlopen`ed libraries in `runtimeDependencies` with `autoPatchelfHook`. | 66 / 13 / 82 | Yes: `doc/hooks/autopatchelf.section.md` |
| Use `lib.escapeShellArg` or `escapeShellArgs` when interpolating into shell. | 20 / 9 / 90 | Yes: both exist in `lib/strings.nix` |
| Name security patches by CVE and cite the advisory in the commit. | 406 / 6 / 97 | Yes: `pkgs/README.md` (Submitting security fixes) |
| When you disable a hardening option or check, comment why and link upstream. | 66 / 2 / 74 | Yes: `pkgs/README.md` ("If checks are partially or fully disabled, document why") |
| Critical security fixes may skip staging. | 190 / 2 / 92 | Yes: `pkgs/README.md`, branch table in `CONTRIBUTING.md` |
| Prefer systemd's own sandboxing options to running as root. | 41 / 10 / 66 | Partly: RFC 52 and `ids.nix` for users; no hardening checklist in the docs |

### testing-and-validation

| Rule | Counts | Docs agree? |
|------|--------|-------------|
| Run the upstream test suite; if you disable it, comment why. | 523 / 88 / 92 | Yes: `pkgs/README.md` (Package tests, Reviewing contributions) |
| Build the packages that depend on yours with `nixpkgs-review`. | 1384 / 57 / 90 | Yes: `.github/PULL_REQUEST_TEMPLATE.md`, `CONTRIBUTING.md` |
| Build on the platforms you can and list them. | 1980 / 56 / 95 | Partly: `CONTRIBUTING.md` (Pull request template) says testing every platform is "not required for a pull request to be merged" |
| Add `pythonImportsCheck` to Python packages. | 143 / 31 / 90 | Yes: `python.section.md` |
| Wire tests through `passthru.tests`. | 91 / 10 / 97 | Yes: `pkgs/README.md` (Package tests), `doc/stdenv/passthru.chapter.md` |
| Skip individual tests (`disabledTests`, `checkFlags`) instead of `doCheck = false`. | 66 / 13 / 86 | Yes: `python.section.md`, `rust.section.md` |
| Use a test hook or declarative attribute before a custom `checkPhase`. | 78 / 23 / 91 | Yes: `doc/hooks/` (`versionCheckHook`, `udevCheckHook`), `pytestCheckHook` |

### versioning-and-updates

| Rule | Counts | Docs agree? |
|------|--------|-------------|
| Untagged commit: `version = "<last-release>-unstable-YYYY-MM-DD"`, or `0-unstable-...` with no release. The version starts with a digit. | 127 / 46 / 87 | Yes: `pkgs/README.md` (Versioning) |
| Package tagged releases rather than commit hashes when releases exist. | 197 / 57 / 83 | Yes: `pkgs/README.md` (Versioning) |
| Remove packages by adding a `throw` alias that says why, with an `# Added YYYY-MM-DD` comment. | 81 / 18 / 95 | Yes: `pkgs/README.md` (Steps to remove a package), header of `pkgs/top-level/aliases.nix` |
| Use `passthru.updateScript` or `nix-update-script`, not a hand-written script. | 94 / 25 / 80 | Yes: `pkgs/README.md` (Automatic package updates) |
| Give users a migration path before a breaking change to widely used interfaces. | 642 / 69 / 18 | Partly: `nixos/README.md` for options; `merged%` reflects how contested these PRs are |
| Delete deprecated aliases eventually. | 136 / 21 / 75 | Partly: the `aliases.nix` header points to `maintainers/scripts/remove-old-aliases.py`; `pkgs/README.md` states "no policy" on timing |
| Comment why a package is pinned. | 55 / 18 / 85 | Yes: `pkgs/README.md` (Reviewing contributions) |

## Rules the corpus gets wrong or states misleadingly

| Corpus statement (counts) | Problem | Use instead |
|---------------------------|---------|-------------|
| "Avoid propagating dependencies ...; use `buildInputs` or PATH manipulation for build-time tools" (`build-closure-and-platforms`, 118 / 28 / 61) | The second half is backwards. Build-time tools belong in `nativeBuildInputs`. | `doc/stdenv/stdenv.chapter.md` |
| "Disable failing tests using `platformDontCheck`" (`testing-and-validation`, 339 / 43 / 80) | No such function or attribute exists in the tree. | `disabledTests`, `checkFlags`, or `doCheck = false` with a comment |
| "Use `format = "pyproject"`" (`language-ecosystems`, 107 / 27 / 94) | Superseded. The tree has 10,170 files with `pyproject = true` and 4 with the old form. | `pyproject = true` plus `build-system` |
| "Use lowercase first character in package descriptions" (`documentation-and-release-notes`, 100 / 25 / 86) | The docs require capitalization, and another corpus rule (26 / 12 / 88) says so too. | `doc/stdenv/meta.chapter.md` |
| "Ensure `meta.license` is always a list" (`meta-and-licensing`, 41 / 17 / 76) | A single `lib.licenses.x` is valid and preferred when there's one license. | List only when parts differ |
| "Use commit hashes instead of tags or branches" (`fetchers-and-sources`, 75 / 30 / 76) | Contradicts the tag rule, and tags are safer with `tag =`. Full hashes are right for untagged commits. | `tag = "v${version}"` for releases; full `rev` otherwise |
| "Use `fetchpatch` with `stripLen`, `extraPrefix` ..." (278 / 60 / 92) | The docs prefer `fetchpatch2` and keep `fetchpatch` for patches with short hashes. | `pkgs/README.md` (Fetching patches) |
| "Use Qt's `mkDerivation` rather than `wrapQtAppsHook`" (`language-ecosystems`, 34 / 13 / 82) | From the Qt5 `mkDerivation` era. The manual tells you to add `qt6.wrapQtAppsHook` to `nativeBuildInputs`. | `doc/languages-frameworks/qt.section.md` |
| "Use `__structuredAttrs = true` as standard for Python packages" (43 / 13 / 81) | Overstated. The mandate covers new top-level packages, which includes Python applications in `by-name`, but not every module in `python-modules`. | `doc/stdenv/stdenv.chapter.md` |
| "Route 100+ rebuilds to staging" (213 / 10 / 71) | The tree and CI use 500 (consider) and 1000 (mass rebuild). | `CONTRIBUTING.md` |
| "500+ rebuilds require explicit maintainer approval" (152 / 2 / 85) | Not in the docs. CI posts a review asking you to retarget instead. | `ci/github-script/check-target-branch.ts` |
| "Consolidate modifications into patch files rather than mixing with `substituteInPlace`" (102 / 18 / 63) | Contradicts "use `postPatch` with `substituteInPlace`" (386 / 94 / 93). Docs allow either. | Small path fixes inline; behavior changes as patches |
| "Maintain alphabetical ordering" (172 / 52 / 92) | No doc requires it. `CONTRIBUTING.md` says unwritten style choices shouldn't be raised in reviews, and `keep-sorted` only touches marked blocks. | Sort only where a `keep-sorted` marker says so, or where nearby code does |
| "Test across x86_64-linux, aarch64-linux, Darwin" (3042 / 43 / 98) | Box-ticking text from the template, not a requirement; Darwin means `aarch64-darwin` today. | Build on what you have, list it, leave the rest unticked |
| "Run `nixpkgs-review` across multiple architectures" (3512 / 19 / 100) | `nixpkgs-review` runs on your machine's system, and the 100% is template boilerplate. | Run it on one platform and name that platform |
| "Backports need an attestation of policy compliance" (81 / 2 / 90) | The current PR template has no such box. | The bot's backport PR text asks the reviewer to confirm |
| "Merge security fixes despite unrelated test failures" (82 / 1 / 96) | The required status `no PR failures` gates merges now. | Fix or explain the failing check |
| "Avoid packaging pre-release versions" (159 / 16 / 13) | Overbroad. `pkgs/README.md` accepts a pre-release next to the stable version. | Package pre-releases only with a reason |
| "Close PRs for outdated or superseded versions" (299 / 20 / 3) | Triage behavior, not a packaging rule. | Close yours when a newer one supersedes it |
| `SKIP` (`other`, 1563 / 34 / 88) | A placeholder from the distillation. | Ignore it |
| "Use a `libfoo` prefix for libraries" (`synthesis/other.md`, no counted rule) | The attribute name should equal `pname`, which should match upstream's name. | `pkgs/README.md` (Package naming) |
| "Merge rate of small rebuild footprints is 99%" (593 / 3 / 99) | Leaf updates merge fast whatever you do. It's not a rule. | Ignore |

## Dated advice to ignore

- `nixfmt-rfc-style`: now a warning alias for `nixfmt` in `pkgs/top-level/aliases.nix`.
- `lib.mdDoc` and "wrap documentation fields in `mdDoc`": gone from `lib/`; descriptions are Markdown by default. Three categories still carry this rule (27 / 11 / 85, 19 / 7 / 84, 14 / 3 / 100).
- `stdenv.isDarwin` and `stdenv.isLinux`: no uses remain under `pkgs/`; write `stdenv.hostPlatform.isDarwin`.
- `substituteAll`: `pkgs.substituteAll` is a `throw` alias since 2025-05-23; use `replaceVars`.
- `substituteInPlace --replace`: still accepted, but the docs and new code use `--replace-fail`.
- `cargoSha256`: deprecated; `cargoHash` replaces it.
- `unstable-YYYY-MM-DD` versions (also in changelog format rules, 75 / 17 / 83): the version must start with a digit.
- `x86_64-darwin` as a test target: absent from `pkgs/top-level/release-supported-systems.json`.
- Python `format = "setuptools"`, `"wheel"` and `"pyproject"`: use `pyproject = true` or `pyproject = false` with explicit hooks.
- The Python-based merge bot and "ofborg must pass": the bot is now part of `ci/github-script/`, and ofborg isn't a required check.
