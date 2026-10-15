# Upstreamable checklist

Load this last, right before you report a change as done or open a PR. It's the single walk-through you run against your own diff; each box points to the file that explains the rule and, where a grep-level rule exists, to its `scripts/antipatterns.py` id (`python3 scripts/antipatterns.py --list-rules`). Verified against nixpkgs master (26.11 development, Oct 2026).

**Contents:** [How to use it](#how-to-use-it) · [Universal](#universal) · [Package (nixpkgs by-name or your own flake)](#package-nixpkgs-by-name-or-your-own-flake) · [Language builders](#language-builders) · [NixOS module](#nixos-module) · [NixOS system configuration](#nixos-system-configuration) · [Flake / dev shell / nixify result](#flake--dev-shell--nixify-result) · [Commit and PR (nixpkgs)](#commit-and-pr-nixpkgs) · [Severity guide](#severity-guide) · [Report template](#report-template) · [Dated advice to ignore](#dated-advice-to-ignore)

## How to use it

Run `scripts/gates.sh` first, so the mechanical boxes (parse, format, anti-pattern scan, eval, build) are already settled and you spend your attention on judgment. Then walk `Universal` plus the sections that match your change type: a nixpkgs package goes through `Package`, the matching row of `Language builders`, and `Commit and PR`; a module adds `NixOS module`; a flake adds `Flake`. Every box you can't tick needs either a fix or a one-line reason in your report. Don't tick a box from memory: if you didn't look at the diff for that rule, it's unchecked. Finish with the [report template](#report-template).

## Universal

Applies to every Nix change, in nixpkgs or your own repo.

- [ ] Every changed line traces to the request. No drive-by reformatting, renames or refactors; mechanical churn goes in its own commit. [upstreaming-and-prs](upstreaming-and-prs.md)
- [ ] You reused what exists: a nixpkgs package, a `lib` function, a builder or a setup hook instead of hand-rolled shell. [derivation-authoring](derivation-authoring.md), [nix-language-style](nix-language-style.md)
- [ ] No dead code: unused arguments, `let` bindings, `inherit` entries, commented-out blocks. nixpkgs CI ignores unused-binding diagnostics, so run `deadnix -L` on your diff yourself. [gates-and-tooling](gates-and-tooling.md)
- [ ] `nixfmt` reports nothing to change (`nix fmt`), and every changed file passes `nix-instantiate --parse` with empty stderr. [gates-and-tooling](gates-and-tooling.md)
- [ ] Every function, attribute and flag you used resolves in this tree (grep or evaluate it), and none is a removed or deprecated name: `stdenv.isX`, `stdenv.lib`, `mdDoc`, `--replace`, `substituteAll`, `pkgs.system`, `darwin.apple_sdk*`. `NL06` `NL07` `NL08` `NL11` `NL12` `DV07` `BP01` [nix-language-style](nix-language-style.md)
- [ ] No impurity: no `<nixpkgs>` or `NIX_PATH`, no `builtins.currentSystem`/`getEnv`, no import from derivation, no `builtins.fetch*` in nixpkgs-bound code. `NL04` `NL05` `NL17` `FS04` [transforms-and-ifd](transforms-and-ifd.md)
- [ ] No placeholder hash (`lib.fakeHash` and siblings) and no disabled TLS verification survives. `NL16` `SC01` [security](security.md)
- [ ] No secret reaches the store: not in a `.nix` file, `pkgs.writeText`, `environment.etc.*.text`, `Environment=` or an eval-time `builtins.readFile`. [security](security.md)
- [ ] Each pin, non-obvious patch, non-default flag and disabled test has a comment saying why. `TS01` [upstreaming-and-prs](upstreaming-and-prs.md)
- [ ] Your report names every gate as run (with result) or not run (with reason); a platform appears only if a build ran there. [gates-and-tooling](gates-and-tooling.md)

## Package (nixpkgs by-name or your own flake)

### Structure and derivation shape

- [ ] New top-level package lives at `pkgs/by-name/<xx>/<name>/package.nix`, `<xx>` the first two lowercase characters of the name, and `./ci/nixpkgs-vet.sh master` exits 0. [derivation-authoring](derivation-authoring.md)
- [ ] `pname` and `version` are separate attributes, `pname` has no uppercase letters, and `version` starts with a digit. `DV01` `DV05` [versioning-and-updates](versioning-and-updates.md)
- [ ] The derivation uses `finalAttrs: { ... }`, not `rec`, and references itself through `finalAttrs`. `NL01` [derivation-authoring](derivation-authoring.md)
- [ ] Package arguments are listed explicitly (no `...`) and there's no `with lib;` or `with pkgs;`. `with lib.maintainers;` is fine. `NL02` `NL03` `NL14` [nix-language-style](nix-language-style.md)
- [ ] `strictDeps = true;` and `__structuredAttrs = true;` are set; the manual requires the latter for new top-level packages, and with it on, environment-style variables live in `env`. [build-closure-and-platforms](build-closure-and-platforms.md)
- [ ] Build tools sit in `nativeBuildInputs`, linked libraries in `buildInputs`, test tools in `nativeCheckInputs`; runtime-only executables are wrapped or substituted, not dropped into `buildInputs`. [derivation-authoring](derivation-authoring.md)
- [ ] Overridden phases begin with `runHook pre<Phase>` and end with `runHook post<Phase>`; `phases` and `patchPhase` aren't set (use `prePatch`/`postPatch`). `NL21` `DV03` `DV04` [derivation-authoring](derivation-authoring.md)
- [ ] Binary paths come from `lib.getExe`/`lib.getExe'` or `replaceVars`, not hand-built `${pkg}/bin/x` strings; `meta` is the last attribute and `passthru` precedes it. `NL18` [nix-language-style](nix-language-style.md)

### Sources and hashes

- [ ] Fetchers take `hash = "sha256-..."` (SRI), pass exactly one of `tag` or a full 40-hex `rev`, and never `rev = version`. `FS01` `FS02` [fetchers-and-sources](fetchers-and-sources.md)
- [ ] URLs are `https://` and pinned: no `git://`, `http://`, `refs/heads/` or `latest`. `FS03` [fetchers-and-sources](fetchers-and-sources.md)
- [ ] The hash came from a real build or prefetch, and `version` changed together with `src.hash` and any dependency hash in the same commit. `NL16` [versioning-and-updates](versioning-and-updates.md)
- [ ] `fetchSubmodules`, `leaveDotGit`, `deepClone`, `fetchTags` and `fetchLFS` are set only when the build needs them, with a comment. [fetchers-and-sources](fetchers-and-sources.md)
- [ ] Network patches use `fetchpatch2` (or `fetchpatch` for short-hash patches) with a `name` and `hash`, from a commit URL rather than a PR. [fetchers-and-sources](fetchers-and-sources.md)
- [ ] `src = ./.;` is replaced by `lib.fileset.toSource` so unrelated files don't enter the store. `NL15` [nix-language-style](nix-language-style.md)

### Meta

- [ ] `meta` evaluates: `nix-instantiate --eval --strict --json -A <pkg>.meta` succeeds with no unknown keys. [meta-and-licensing](meta-and-licensing.md)
- [ ] `description` is capitalized, one sentence, has no trailing period, and doesn't start with `A `, `An `, `The ` or the package name. `MT03` [meta-and-licensing](meta-and-licensing.md)
- [ ] `license` is a `lib.licenses.*` value, a list, or a compound; no deprecated `gpl2`/`gpl3`/`lgpl*` attributes; non-free software uses `unfree` or `unfreeRedistributable`. `MT01` `MT02` [meta-and-licensing](meta-and-licensing.md)
- [ ] `maintainers` (or `teams`) is non-empty and every handle exists in `lib.maintainers`. [meta-and-licensing](meta-and-licensing.md)
- [ ] `mainProgram` is a string equal to a file in `bin/` for any package that installs a program. [meta-and-licensing](meta-and-licensing.md)
- [ ] `platforms` is set, and any `broken` or `badPlatforms` condition carries a comment with the reason. [build-closure-and-platforms](build-closure-and-platforms.md)
- [ ] `changelog` points at a versioned release, and binary repackages carry `sourceProvenance`. `MT05` [meta-and-licensing](meta-and-licensing.md)

### Patches and overrides

- [ ] Every `patches` entry has a descriptive name or an adjacent comment; a CVE fix is named `CVE-<id>.patch`. [patches-and-overrides](patches-and-overrides.md), [security](security.md)
- [ ] `substituteInPlace` uses `--replace-fail` (or `--replace-warn`/`--replace-quiet` with a reason); there's no `sed -i` and no `substituteAll`. `NL10` `NL11` `NL12` [patches-and-overrides](patches-and-overrides.md)
- [ ] Platform-specific patches and substitutions sit behind `lib.optionals`/`lib.optionalString` with `stdenv.hostPlatform`. `NL09` [patches-and-overrides](patches-and-overrides.md)
- [ ] You added no new `overrideAttrs` or `overridePythonAttrs` inside nixpkgs. In your own flake, overrides append to `previousAttrs` and overlays take `final: prev:`. [patches-and-overrides](patches-and-overrides.md)

### Platforms and cross

- [ ] Platform tests use `stdenv.hostPlatform.is*`; no `stdenv.isDarwin`, `darwin.apple_sdk*`, `xorg.*` attributes or `builtins.currentSystem`. `NL06` `DV07` [build-closure-and-platforms](build-closure-and-platforms.md)
- [ ] A `doCheck` or post-install step that runs host binaries is guarded by `stdenv.buildPlatform.canExecute stdenv.hostPlatform`. [build-closure-and-platforms](build-closure-and-platforms.md)
- [ ] Prebuilt ELF binaries use `autoPatchelfHook` with `runtimeDependencies` for `dlopen`ed libraries; no `LD_LIBRARY_PATH` workaround. [build-closure-and-platforms](build-closure-and-platforms.md)
- [ ] You built on each platform you claim, from `x86_64-linux`, `aarch64-linux` and `aarch64-darwin` (not `x86_64-darwin`), and stated the ones you couldn't. [gates-and-tooling](gates-and-tooling.md)

### Tests

- [ ] `doCheck` is on (explicitly or by builder default); any `doCheck = false;` has a comment, and disabled tests are named individually with a reason. `TS01` [testing](testing.md)
- [ ] A package with an installed program has `versionCheckHook` in `nativeInstallCheckInputs` with `doInstallCheck = true;`, plus `mainProgram`; test hooks never sit in `checkInputs` or `nativeBuildInputs`. `TS03` `TS04` `TS05` `TS09` [testing](testing.md)
- [ ] `passthru.tests` entries reference `finalAttrs.finalPackage`; module-backed packages link `nixosTests.<name>`. [testing](testing.md)
- [ ] You ran `nix-build -A <pkg>.tests` and any `nixosTests.<name>` yourself, because `nixpkgs-review` and Hydra don't build `passthru.tests` by default. [upstreaming-and-prs](upstreaming-and-prs.md)
- [ ] You ran the installed binary (`./result/bin/<prog> --version` plus one real invocation) and ran `nixpkgs-review wip` when the package has dependents. [gates-and-tooling](gates-and-tooling.md)
- [ ] No obsolete test spelling: `pytestFlagsArray`, `nixosTest {`, `skipLint`/`skipTypeCheck`, `platformDontCheck`. `TS06` `TS07` `TS08` `TS10` [testing](testing.md)

### Updates and versioning

- [ ] A release package sets `tag`; a snapshot version is `<base>-unstable-YYYY-MM-DD` (base is the last release or `0`) and pins a full `rev`. `DV05` [versioning-and-updates](versioning-and-updates.md)
- [ ] `passthru.updateScript` is set (`nix-update-script`, or `unstableGitUpdater` for snapshots) unless the language builder supplies one, as the Python builders do. [versioning-and-updates](versioning-and-updates.md)
- [ ] A pinned or special version has a comment giving the reason and the condition for unpinning. [versioning-and-updates](versioning-and-updates.md)
- [ ] A removed package leaves a `throw` alias in `pkgs/top-level/aliases.nix` with an `# Added YYYY-MM-DD` comment and a message saying why; a rename uses `warnAlias`. [versioning-and-updates](versioning-and-updates.md)
- [ ] Extra versions are named with a version suffix (`foo_1_2`) next to an unversioned default. [versioning-and-updates](versioning-and-updates.md)
- [ ] Cargo, Go, npm and pnpm hashes were regenerated for the new version, not carried over from the old one. [lang-rust](lang-rust.md), [lang-go](lang-go.md), [lang-nodejs](lang-nodejs.md)

## Language builders

Walk the row for your ecosystem on top of the Package boxes. For anything else, see [lang-other-ecosystems](lang-other-ecosystems.md).

| Ecosystem | The checks that matter most | Reference |
|---|---|---|
| Python | `pyproject = true;` with a `build-system` list and `dependencies` (not `format =` or `propagatedBuildInputs`) `PY01` `PY02`; `pythonImportsCheck` set and `pytestCheckHook` in `nativeCheckInputs` with each `disabledTests` entry commented `TS02` `TS03`; libraries under `pkgs/development/python-modules/<pname>/default.nix` and registered in `python-packages.nix`, applications in `pkgs/by-name`; no `disabled = pythonOlder "3.9"` or `isPy3k` | [lang-python](lang-python.md) |
| Go | `buildGoModule` with `vendorHash` (never `buildGoPackage` or `vendorSha256`) `GO01`; `vendorHash = null` only with a committed `vendor/`, `lib.fakeHash` to bootstrap; `ldflags` as a list using `finalAttrs.version`, `CGO_ENABLED` under `env`; each `-skip=` entry commented, `subPackages` set when there are several mains | [lang-go](lang-go.md) |
| Rust | `rustPlatform.buildRustPackage` with `cargoHash` (never `cargoSha256` or `useFetchCargoVendor`) `RS01`; git dependencies covered by `cargoHash`, not hand-written `outputHashes`; `pkg-config`, `protobuf` and `cmake` in `nativeBuildInputs`, `rustPlatform.bindgenHook` when bindgen is used; no rust-overlay, fenix or crane inside nixpkgs | [lang-rust](lang-rust.md) |
| Node | `buildNpmPackage` or the pnpm and Yarn hooks, never `nodePackages`, `node2nix`, `mkYarnPackage` or `pnpm.fetchDeps`; a real `npmDepsHash` or `pnpmDeps` hash; `fetchPnpmDeps` with `fetcherVersion = 4` and a pinned `pnpm_N`; `dontNpmBuild` when no build script exists, `nodejs_N` matching upstream | [lang-nodejs](lang-nodejs.md) |
| Ruby | `bundlerApp` with `Gemfile`, `Gemfile.lock` and `gemset.nix` all committed and never hand-edited; non-empty `exes`; `passthru.updateScript = bundlerUpdateScript "<attr>";`; native-extension gems get a `gem-config` or `gemConfig` entry for their libraries | [lang-ruby](lang-ruby.md) |
| C and C++ | build tools (`cmake`, `meson`, `ninja`, `pkg-config`, `autoreconfHook`) only in `nativeBuildInputs`; options through `lib.cmakeBool`, `lib.cmakeFeature`, `lib.mesonBool`, `lib.enableFeature` instead of typed `"-DX=ON"` strings; compiler flags via `env.NIX_CFLAGS_COMPILE`; each `hardeningDisable` entry names the flag and says what fails | [lang-c-cpp](lang-c-cpp.md) |

## NixOS module

- [ ] Every `mkOption` has a `type`; enable options use `mkEnableOption`, package options use `mkPackageOption`; computed defaults carry `defaultText = lib.literalExpression ...`. [nixos-modules](nixos-modules.md)
- [ ] Descriptions are plain Markdown: no `lib.mdDoc`, no DocBook tags. `MOD01` `NL08` [nixos-modules](nixos-modules.md)
- [ ] `config` is `lib.mkIf cfg.enable { ... }` (or a `mkMerge` of `mkIf`s); impossible combinations use `assertions`; removed or renamed options use `mkRemovedOptionModule` or `mkRenamedOptionModule`. [nixos-modules](nixos-modules.md)
- [ ] The module is listed in `nixos/modules/module-list.nix` and its test in `nixos/tests/all-tests.nix`; the backing package links `nixosTests.<name>`. [nixos-modules](nixos-modules.md), [testing](testing.md)
- [ ] The service sets `DynamicUser = true` or a documented `User`/`Group`; static ids go through `nixos/modules/misc/ids.nix` with a reason; state lives under `StateDirectory`, `RuntimeDirectory`, `CacheDirectory` or `LogsDirectory`, not `mkdir` in `preStart`. `MOD02` `MOD03` [nixos-modules](nixos-modules.md)
- [ ] `Exec*` arguments built from options go through `utils.escapeSystemdExecArg(s)`; shell text goes through `lib.escapeShellArg(s)`. [security](security.md)
- [ ] Secrets arrive through `*File` options (`types.externalPath`) and `LoadCredential`, `EnvironmentFile` or runtime substitution; nothing secret is interpolated into a unit or store path. [nixos-modules](nixos-modules.md), [security](security.md)
- [ ] A release note exists in `nixos/doc/manual/release-notes/rl-YYMM.section.md` for a new module or a backward-incompatible change, and a change that could corrupt state is gated on `system.stateVersion`. [upstreaming-and-prs](upstreaming-and-prs.md)

## NixOS system configuration

- [ ] The host sets `nixpkgs.hostPlatform` directly or through `hardware-configuration.nix`, not the legacy `nixpkgs.system`. [nixos-systems](nixos-systems.md)
- [ ] Nothing in `imports` reads `config` or `_module.args`; shared values travel through `specialArgs`. [nixos-systems](nixos-systems.md)
- [ ] `system.stateVersion` is set explicitly, and your diff doesn't change it without a migration note. [nixos-systems](nixos-systems.md)
- [ ] No secret sits in a `.nix` file, `pkgs.writeText`, `environment.etc.*.text` or a `builtins.readFile` of a secret path. [nixos-systems](nixos-systems.md), [security](security.md)
- [ ] Customization uses `package` options with `overrideAttrs` at the use site; overlays are reserved for changes every dependent needs; Nix settings live under `nix.settings`. [nixos-systems](nixos-systems.md)
- [ ] `nix flake check --no-build` and `nixos-rebuild build --flake .#<host>` pass; you didn't `switch` or `test` unless asked; deploy commands use `--elevate=sudo` (or `--sudo`) with `--target-host`, never `--use-remote-sudo`, and CI runs `--no-update-lock-file`. [nixos-systems](nixos-systems.md), [gates-and-tooling](gates-and-tooling.md)

## Flake / dev shell / nixify result

- [ ] `flake.nix` holds only inputs, system mapping and output wiring; no builder calls. Every file under `pkgs/` is a `callPackage`-style package file. [flake-layout](flake-layout.md), [nixify-workflow](nixify-workflow.md)
- [ ] `packages.<system>` contains only derivations with flat names; the dev shell lives outside the autoloaded `pkgs/` directory; `checks` values are derivations. `TS11` [scoped-outputs](scoped-outputs.md), [testing](testing.md)
- [ ] Checks include a version or smoke check per packaged tool, and a `testers.runNixOSTest` check for services (`testers` is the callPackage argument; `pkgs.runNixOSTest` doesn't exist). [nixify-workflow](nixify-workflow.md), [vm-tests](vm-tests.md)
- [ ] `formatter` is wired and `nix fmt` changes nothing; treefmt uses `ruff-format`/`ruff-check`, not a `ruff` program. [nixify-workflow](nixify-workflow.md)
- [ ] `flake.lock` is committed, every input that takes nixpkgs has `inputs.nixpkgs.follows = "nixpkgs";`, new files are `git add`ed before evaluation, and updates use `nix flake update [input]`, not `--update-input`. [gates-and-tooling](gates-and-tooling.md), [nixos-systems](nixos-systems.md)
- [ ] `nix flake check --option allow-import-from-derivation false` passes, or the change states why import from derivation is needed. [nixify-workflow](nixify-workflow.md)
- [ ] The native workflow is intact: no application source changed, `.envrc` has `use flake` with any `watch_file` lines before it, and the project's own build and test commands pass inside `nix develop` unchanged. [nixify-workflow](nixify-workflow.md), [dev-shells-and-ergonomics](dev-shells-and-ergonomics.md)
- [ ] No Nix file hand-lists dependency names or versions a lockfile already records, and one documented command (`scripts/update-deps.sh` or equivalent) refreshes everything. [nixify-workflow](nixify-workflow.md)

## Commit and PR (nixpkgs)

### Commits

- [ ] Subjects follow the area format: `foo: init at 1.2.3`, `foo: 1.2.2 -> 1.2.3`, `foo: fix build with gcc 15`, `foo: remove`, `nixos/foo: add bar option`, `doc/stdenv: ...`, `lib.fileset: ...`. Each contains `: `, has no trailing period, no `fixup!`/`squash!`/`amend!` prefix and no Conventional Commits prefix (`feat:`, `fix:`, `chore:`). [upstreaming-and-prs](upstreaming-and-prs.md)
- [ ] One logical change per commit, each buildable; formatting-only churn is separate. [upstreaming-and-prs](upstreaming-and-prs.md)
- [ ] `maintainers: add <handle>` is its own commit, comes first, and touches only `maintainers/maintainer-list.nix`. `MT04` [meta-and-licensing](meta-and-licensing.md)
- [ ] An update body links the changelog or release notes; a new package says why it belongs; a removal says why and links the evidence. [upstreaming-and-prs](upstreaming-and-prs.md)
- [ ] LLM-assisted commits carry an `Assisted-by:` trailer naming the tool and primary model and version; `Co-authored-by:` doesn't satisfy the policy. [upstreaming-and-prs](upstreaming-and-prs.md)
- [ ] A security fix is its own PR, with the CVE id or advisory URL in the message. [security](security.md)

### PR body and evidence

- [ ] The PR template is intact with only true boxes ticked, and the top says what changed and why plus a smoke test a reviewer can run. [upstreaming-and-prs](upstreaming-and-prs.md)
- [ ] The "built on" boxes match builds that ran; the `./result/bin/*` line says which binaries you ran and how; the `nixpkgs-review` line says which dependents fail and whether they also fail on the base. [upstreaming-and-prs](upstreaming-and-prs.md)
- [ ] `nix fmt` is clean and `./ci/nixpkgs-vet.sh master` passes (new top-level packages). [gates-and-tooling](gates-and-tooling.md)
- [ ] You searched open and closed PRs, issues and `pkgs/top-level/aliases.nix` for the same work and linked any competing PR. [upstreaming-and-prs](upstreaming-and-prs.md)
- [ ] Release notes exist where required: `nixos/doc/manual/release-notes/rl-YYMM.section.md` for new, removed or significantly changed modules, `doc/release-notes/rl-YYMM.section.md` for major or breaking package changes, none for plain package removals. [upstreaming-and-prs](upstreaming-and-prs.md)
- [ ] Special packaging choices (pins, opinionated patches, non-default flags, disabled checks) are explained in a comment or patch name, because reviewers check for exactly that. [upstreaming-and-prs](upstreaming-and-prs.md)

### Target branch

| Rebuild count or change type | Base branch |
|---|---|
| Under 500 rebuilds, or not for a release | `master` |
| 500 to 999 | `master` or `staging`; CI flags a possible mass rebuild and you judge |
| 1000 or more | `staging` (`staging-YY.MM` for a release branch) |
| Rebuilds all NixOS tests without being a mass rebuild, or a Linux kernel change | `staging-nixos` |
| Critical security fix, not a mass rebuild | `master` |
| Same change can't apply to both master and a release | two PRs: `master` and `release-YY.MM` |

Retarget as soon as CI posts its mass-rebuild review. The thresholds are 500 and 1000 (from `CONTRIBUTING.md` and `ci/github-script/check-target-branch-policy.ts`); "100+ goes to staging" is review folklore.

### Backports

- [ ] The change is merged on `master` first and is eligible: new packages or modules, security fixes, patch-level bumps, or minor updates without breaking changes. [upstreaming-and-prs](upstreaming-and-prs.md)
- [ ] The base is `release-YY.MM`, never `nixos-YY.MM` or a `nixpkgs-*` channel branch. [upstreaming-and-prs](upstreaming-and-prs.md)
- [ ] Commits come from `git cherry-pick -x <hash>` (`-xe` to add a reason), using the hash as it landed on `master`. [upstreaming-and-prs](upstreaming-and-prs.md)
- [ ] The title includes `[YY.MM]` and the description links the master PR. [upstreaming-and-prs](upstreaming-and-prs.md)
- [ ] A fix that needs different code on master and the release is two PRs; a `Not-cherry-picked-because:` footer is used only when cherry-picking is impossible. [upstreaming-and-prs](upstreaming-and-prs.md)
- [ ] A mass rebuild is backported to `staging-YY.MM`, not to the release branch directly. [upstreaming-and-prs](upstreaming-and-prs.md)

## Severity guide

Triage a failed box before you decide what to do with it. A Blocker means the change is wrong, insecure, doesn't build, or isn't reproducible: fix it, don't argue it, and don't report done. Required evidence means the change may be right but the reviewer can't tell without proof: produce the proof, or state plainly that you couldn't. Style means a tool or a reviewer's habit settles it: run the tool, and treat reviewer-custom items as suggestions (the contributing guide says unwritten style points aren't to be raised in review), though CI still fails on unformatted code, so run the formatter anyway.

| Class | Example items from the boxes above |
|---|---|
| Blocker | eval or build fails; a removed API (`substituteAll`, `vendorSha256`, `cargoSha256`, `darwin.apple_sdk*`) is used; a placeholder hash is left in; TLS verification is off; a secret reaches the store; a lookup path, impure builtin or import from derivation in nixpkgs-bound code; a test hook in `checkInputs` or `versionCheckHook` in `nativeBuildInputs`; wrong or missing license; `--replace` instead of `--replace-fail`; a commit subject CI rejects (`fixup!`, trailing period) |
| Required evidence | platforms ticked only where built; the installed binary was run; `nixpkgs-review` for packages with dependents; `passthru.tests` and `nixosTests` built; a version check or test exists; `meta` is complete (description, license, maintainers, mainProgram, platforms); a release note for a module change; a changelog link in an update commit; a comment on every pin, patch and disabled test; the target branch matches the rebuild count; the `Assisted-by:` trailer |
| Style | `nixfmt` layout; `with lib.maintainers;` rather than a wider `with`; alphabetical list order (required only in `maintainer-list.nix` and `aliases.nix`); `lib.getExe` over a hand-built path; `lib.optionals` over `if ... else [ ]`; `tag = version;` over `"${version}"`; quoting URL literals; unused arguments (reviewers catch them, CI doesn't); commit-body wording; anything a reviewer labels nitpick |

## Report template

End your work with this, filled in. Delete nothing; write `none` where a section is empty.

```
Change type:    <nixpkgs package | nixpkgs module | flake/dev shell | NixOS system | other>
Gates run:      <gate: result>, e.g. parse OK, nixfmt 0 changed, antipatterns 0 findings,
                nix-build x86_64-linux OK, passthru.tests OK
Not run:        <gate: reason>, e.g. aarch64-darwin build (no builder),
                nixpkgs-review (no GitHub token)
Unchecked boxes:
  - <section: box text> -> fixed in <file> | not applicable: <one line> | left open: <reason>
Unverified claims:
  - <anything you state but didn't measure, and the command that would confirm it>
Evidence for the PR body: <commands you ran and what they printed, one line each>
```

## Dated advice to ignore

- "Test on x86_64-darwin": it's not in `pkgs/top-level/release-supported-systems.json` or the PR template; use `aarch64-darwin`.
- "Rebuilds of 100+ packages go to staging": the docs and CI use 500 and 1000.
- "Format with `nixfmt-rfc-style`": it's a warning alias for `nixfmt`; `nixfmt-classic` throws.
- "Run `statix` and `deadnix` because nixpkgs CI does": it doesn't; they're advisory tools for your own repos and your own diff.
- "Ofborg must pass": the required status is `no PR failures`; ofborg builds are optional and can hang.
- "`meta.license` must be a list": a single `lib.licenses.*` value is valid.
