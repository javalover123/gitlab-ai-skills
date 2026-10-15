# Other language ecosystems in nixpkgs

Load this when you package something in an ecosystem that doesn't have its own reference file here. It's a router: for each ecosystem you get the builder name, the lock or hash mechanism, the traps, and where the package lives. Read the named manual file before you write the derivation; everything below was checked against `doc/languages-frameworks/` (and the other paths named) in the current nixpkgs tree, and each entry cites its source. Python, Go, Rust, Node.js, Ruby, and C/C++ have their own files: [lang-python.md](lang-python.md), [lang-go.md](lang-go.md), [lang-rust.md](lang-rust.md), [lang-nodejs.md](lang-nodejs.md), [lang-ruby.md](lang-ruby.md), [lang-c-cpp.md](lang-c-cpp.md).

**Contents:** [Two conventions that apply everywhere](#two-conventions-that-apply-everywhere) · [Router table](#router-table) · [Haskell](#haskell) · [Java, Maven, Gradle](#java-maven-gradle) · [.NET](#net) · [PHP](#php) · [Lua](#lua) · [Perl](#perl) · [OCaml](#ocaml) · [BEAM (Erlang, Elixir, LFE)](#beam-erlang-elixir-lfe) · [Dart and Flutter](#dart-and-flutter) · [Zig](#zig) · [Nim](#nim) · [Crystal](#crystal) · [Julia](#julia) · [R](#r) · [Qt, KDE, GNOME and GTK](#qt-kde-gnome-and-gtk) · [Emacs](#emacs) · [Vim and Neovim](#vim-and-neovim) · [Agda, Rocq and Coq, Lean 4](#agda-rocq-and-coq-lean-4) · [Android](#android) · [Other manual sections](#other-manual-sections) · [Checkable rules](#checkable-rules) · [Dated advice to ignore](#dated-advice-to-ignore)

## Two conventions that apply everywhere

- Applications are top-level packages and go in `pkgs/by-name/<xx>/<name>/package.nix`. Libraries that live in an ecosystem package set (`haskellPackages`, `perlPackages`, `luaPackages`, `ocamlPackages`, `agdaPackages`, and so on) don't: `pkgs/by-name/README.md` says it only covers packages made with the plain `pkgs.callPackage`, and "refer to the definition and documentation of the respective package set" for the rest. Most sets are defined in `pkgs/top-level/<name>-packages.nix`.
- Generated files (`hackage-packages.nix`, `generated-packages.nix`, `generated.nix`, `cran-packages.json`, `ruby-packages.nix`, the Emacs `*-generated.nix`) are overwritten by update scripts. Put fixes in the matching overrides file, not in the generated one.

## Router table

| Ecosystem | Builder | Lock or hash | Package set or location | Manual file |
|---|---|---|---|---|
| Haskell | `haskellPackages.mkDerivation`, `callCabal2nix` (outside nixpkgs) | generated from Hackage; no hash to maintain per package | `haskellPackages` | `haskell.section.md` |
| Java (Ant, plain JARs) | `stdenv.mkDerivation` + `jdk`, `stripJavaArchivesHook` | none | top-level | `java.section.md` |
| Maven | `maven.buildMavenPackage` | `mvnHash` | top-level | `maven.section.md` |
| Gradle | `stdenv.mkDerivation` + `gradle` hook | `mitmCache = gradle.fetchDeps { ... data = ./deps.json; }` | top-level | `gradle.section.md` |
| .NET | `buildDotnetModule`, `buildDotnetGlobalTool` | `nugetDeps = ./deps.json` | top-level; SDKs in `dotnetCorePackages` | `dotnet.section.md` |
| PHP | `php.buildComposerProject2` | `vendorHash` | top-level; libraries in `php.packages` | `php.section.md` |
| Lua | `buildLuarocksPackage`, `buildLuaApplication` | generated from the Luarocks list | `luaPackages` (`lua54Packages` etc.) | `lua.section.md` |
| Perl | `buildPerlPackage` | source hash only | `perlPackages` | `perl.section.md` |
| OCaml | `buildDunePackage` | source hash only | `ocamlPackages` | `ocaml.section.md` |
| BEAM | `beamPackages.mixRelease`, `buildRebar3`, `buildErlangMk`, `buildMix` | `mixFodDeps` hash or `mix2nix` file | `beamPackages` | `beam.section.md` |
| Dart, Flutter | `buildDartApplication`, `buildFlutterApplication` | `pubspecLock` JSON + `gitHashes` | top-level | `dart.section.md` |
| Zig | `zig` hook in `nativeBuildInputs` | `zig.fetchDeps` (tree only) | top-level | `doc/hooks/zig.section.md` |
| Nim | `buildNimPackage`, `buildNimSbom` | `lockFile` JSON from `nim_lk` | top-level | `nim.section.md` |
| Crystal | `crystal.buildCrystalPackage` | `shardsFile` from `crystal2nix` | top-level | `crystal.section.md` |
| Julia | `julia.withPackages` | pinned registry | n/a (environments, not packages) | `julia.section.md` |
| R | `rPackages`, `rWrapper` | generated `*-packages.json` | `rPackages` | `r.section.md` |
| Qt, KDE | `qt6.wrapQtAppsHook`, `kdePackages.mkKdeDerivation` | n/a | `qt6Packages`, `libsForQt5`, `kdePackages` | `qt.section.md` |
| GNOME and GTK apps | `wrapGAppsHook3` / `wrapGAppsHook4` | n/a | top-level | `gnome.section.md` |
| Emacs | `melpaBuild` (manual packages) | generated from MELPA, ELPA, NonGNU | `emacs.pkgs` | `doc/packages/emacs.section.md` |
| Vim, Neovim | `vimUtils.buildVimPlugin`, `neovimUtils.buildNeovimPlugin` | generated `generated.nix` | `vimPlugins` | `vim.section.md`, `neovim.section.md` |
| Agda | `agdaPackages.mkDerivation` | source hash only | `agdaPackages` | `agda.section.md` |
| Rocq, Coq | `rocqPackages.mkRocqDerivation`, `coqPackages.mkCoqDerivation` | `release` table with hashes | `rocqPackages`, `coqPackages` | `rocq.section.md` |
| Lean 4 | `leanPackages.buildLakePackage` | `lakeHash`, `lake-manifest.json` | `leanPackages` | `lean4.section.md` |
| Android | `androidenv.composeAndroidPackages`; apps via Gradle | generated `repo.json` | `androidenv` | `android.section.md` |

## Haskell

Sources: `haskell.section.md`, `pkgs/development/haskell-modules/HACKING.md`, `ci/README.md`.

- `haskellPackages` holds a version of every Hackage package, and attribute names match Hackage names. Where a Stackage LTS snapshot has a package, its version is the default; otherwise it's the newest Hackage release in the pinned snapshot.
- `hackage-packages.nix` is auto-generated ("DO NOT EDIT MANUALLY"); change behavior through `configuration-*.nix` overrides and the `configuration-hackage2nix/*.yaml` lists (`broken.yaml`, `main.yaml`, `stackage.yaml`).
- Override a package with `haskell.lib.compose` helpers such as `doJailbreak`, `dontCheck`, `overrideCabal`, `justStaticExecutables`, `markBroken`, and `appendPatches`. Applications exposed at top level usually wrap `justStaticExecutables` so the closure drops Haskell libraries.
- `callCabal2nix` and `cabal2nix` need import-from-derivation, so they're for your own projects, not nixpkgs.
- Only the default compiler's package set is tested broadly; `haskell.packages.ghcNNN` sets for other GHC versions have fewer working packages.
- Branch workflow: `haskell-updates` is a long-lived secondary branch that a rota of Haskell team members merges into `staging` (HACKING.md), and `ci/README.md` lists it with the `staging-` branches. The manual doesn't say contributors must target it for ordinary fixes; confirm with the CI bot's base-branch suggestion before retargeting a PR.

## Java, Maven, Gradle

Sources: `java.section.md`, `maven.section.md`, `gradle.section.md`.

**Plain Java and Ant.** Put `ant`, `jdk`, and `stripJavaArchivesHook` in `nativeBuildInputs` (the hook removes timestamps so JARs are deterministic, though not always fully). Install library JARs into `$out/share/java`, private JARs into `$out/share/<name>`, and wrap programs with `makeWrapper ${jre}/bin/java ... --add-flags "-jar ..."`.
**Maven.** `maven.buildMavenPackage` with `mvnHash`; `maven_4.buildMavenPackage` for Maven 4, whose hash differs from Maven 3's. By default tests run twice (once in the fixed-output derivation, once in the build), and a failing test refetches every dependency; `buildOffline = true` changes that, but test-only dependencies then need `manualMvnArtifacts`. There's no per-package lockfile; the single `mvnHash` covers everything.
**Gradle.** nixpkgs records dependencies through a MITM proxy. Set `mitmCache = gradle.fetchDeps { inherit (finalAttrs) pname; data = ./deps.json; };`, `__darwinAllowLocalNetworking = true;` for Darwin, and refresh the lockfile with `$(nix-build -A <pname>.mitmCache.updateScript)`. Name the lockfile `deps.json`. Add `binaryBytecode` to `meta.sourceProvenance` because the cache holds prebuilt JARs. `gradleBuildTask` defaults to `assemble`, `gradleCheckTask` to `test`.

## .NET

Source: `dotnet.section.md`.

- `buildDotnetModule` takes `projectFile` (prefer a `.csproj`, because building whole `.sln` files isn't fully supported), `nugetDeps` (a `deps.json`), `dotnet-sdk`, `dotnet-runtime`, `executables`, and `runtimeDeps` (wrapped into `LD_LIBRARY_PATH`).
- Create the lockfile with an empty `deps.json`, set `nugetDeps = ./deps.json`, then run the script from `nix-build -A <pkg>.fetch-deps`. `maintainers/scripts/update-dotnet-lockfiles.nix` exists for bulk refreshes.
- Pick `dotnetCorePackages.sdk_X_Y` (and the matching `runtime_X_Y` or `aspnetcore_X_Y`) rather than the old `dotnet-sdk` alias, since major and minor both matter. `dotnetCorePackages.combinePackages` merges several SDKs.
- `buildDotnetGlobalTool` packages a tool straight from NuGet with `nugetHash`; it wants an SDK as its runtime.

## PHP

Source: `php.section.md`.

- `php.buildComposerProject2` needs `composer.json` and `composer.lock`; set `vendorHash`, and `composerLock = ./composer.lock;` if the repository doesn't ship one. Extensions: `php.buildEnv { extensions = { enabled, all }: enabled ++ [ all.ast ]; }` passed as the `php` argument, or `php.withExtensions`. Binaries listed under `bin` in `composer.json` get linked automatically.
- The manual's low-level example (building inside another derivation) uses `php.mkComposerRepository` and `php.composerHooks`. In `pkgs/top-level/php-packages.nix` those names are the v1 builders; the v2 builder behind `buildComposerProject2` exposes `mkComposerVendor` and `composerHooks2` (sources in `pkgs/build-support/php/builders/v2`). Read those sources before using the low-level pieces. Library packages come from `php.packages`, defined in `php-packages.nix`.

## Lua

Source: `lua.section.md`; paths verified: `maintainers/scripts/luarocks-packages.csv`, `pkgs/development/lua-modules/overrides.nix`.

Packages on Luarocks come from the package list in `maintainers/scripts/luarocks-packages.csv`, regenerated by `luarocks-packages-updater` (`luarocks-packages-updater add <name>` adds one). Rockspec `external_dependencies` need a manual entry in `pkgs/development/lua-modules/overrides.nix`.
For a library that isn't on Luarocks use `buildLuaPackage` or wrap a `stdenv.mkDerivation` in `toLuaModule`. `buildLuaApplication` is the same as the package builder without the interpreter-version name prefix.
Don't depend on the `lua`, `lua5`, or `luaPackages` aliases; pick an explicit version (`lua5_4`, `lua54Packages`). Commit subjects name the set: `luaPackages.luafilesystem: 1.11 -> 1.12`.

## Perl

Source: `perl.section.md`.

`buildPerlPackage` handles `Makefile.PL` distributions; `makeMakerFlags` passes flags. Define CPAN modules in `pkgs/top-level/perl-packages.nix` (large ones in `pkgs/development/perl-modules/`), using `mirror://cpan/authors/id/...` URLs and a `pname` matching the distribution name. Applications reach top level through `perlPackages`.
For Perl modules the manual says build-only module dependencies go in `buildInputs` and anything needed at runtime in `propagatedBuildInputs`. That's specific to Perl; for compiled languages `buildInputs` is not the build-tools list.
`nix-generate-from-cpan Some::Module` prints a starting expression (`maintainers/scripts/nix-generate-from-cpan.pl`).

## OCaml

Source: `ocaml.section.md`.

- `buildDunePackage` with `minimalOCamlVersion`, and `duneVersion` only when you need a non-default value. Libraries other packages `require` go in `propagatedBuildInputs`; test-only dependencies go in `checkInputs`. Two different versions of one library in the closure fail the build unless `dontDetectOcamlConflicts = true;`. Libraries install under `$out/lib/ocaml/<version>/site-lib/`. The set is `ocamlPackages` (`pkgs/top-level/ocaml-packages.nix`).

## BEAM (Erlang, Elixir, LFE)

Source: `beam.section.md`.

- Work inside one set, `beamPackages` (default OTP) or a versioned one such as `beam28Packages`. Builders don't accept `erlang`, `elixir`, or `hex` arguments; they take them from the set. Change Elixir with `beamPackages.overrideScope`.
- `mixRelease` for Elixir apps (Phoenix included), `buildRebar3` and `buildErlangMk` for Erlang. Dependencies come either from a fixed-output hash (`mixFodDeps = beamPackages.fetchMixDeps { ... hash = ...; }`) or from `mix2nix > mix_deps.nix` passed as `mixNixDeps`. If a second build after fixing the hash reports another hash, mix isn't fetching reproducibly and you need `mix2nix`; `mix2nix` can't handle git dependencies, so those need manual entries. The frontend half uses `buildNpmPackage` or `fetchYarnDeps`. Move secrets to `runtime.exs` runtime variables.

## Dart and Flutter

Source: `dart.section.md`.

- `buildDartApplication` and `flutterNNN.buildFlutterApplication` take `pubspecLock = lib.importJSON ./pubspec.lock.json;` (convert with `yq . pubspec.lock`) and `gitHashes` for git dependencies. `autoPubspecLock` uses import-from-derivation and isn't permitted in nixpkgs.
- Pin Flutter to a versioned attribute (`flutter335`, `flutter338`, and so on) because `flutter` always follows the newest stable. Package-specific fixes belong in `customSourceBuilders` in `pkgs/development/compilers/dart/package-source-builders`, which the manual strongly prefers over per-app patches. Don't call `dart run` in a build, because Pub tries to download; use `packageRun` from `dartConfigHook`.

## Zig

Sources: `doc/hooks/zig.section.md`; the `zig.fetchDeps` usage in `pkgs/by-name/ri/river/package.nix` and `pkgs/development/compilers/zig/fetcher.nix`.

- Adding `zig` to `nativeBuildInputs` overrides the configure, build, check, and install phases; flags go in `zigBuildFlags`, `zigCheckFlags`, `zigInstallFlags`, and each phase has a `dontUseZig*` switch.
- The manual doesn't document dependency fetching. In the tree, packages use `zig.fetchDeps { inherit (finalAttrs) src pname version; hash = ...; }` (with `fetchAll = true;` when needed) and link it into `$ZIG_GLOBAL_CACHE_DIR/p` in `postConfigure`. Zig versions are `zig_0_NN` attributes; pin one.

## Nim

Source: `nim.section.md`.

- `buildNimPackage` takes `lockFile` (JSON from `nim_lk`; the manual shows `nix run -f . nim_lk ./result | jq --sort-keys > lock.json`), `nimFlags`, `nimDefines`, and `nimRelease`. Native library dependencies come from the `nimOverrides` set (`pkgs/top-level/nim-overrides.nix`).
- `overrideAttrs` can't change `lockFile` because flags derive from it earlier; use `overrideNimAttrs`.

## Crystal

Source: `crystal.section.md`.

- `crystal.buildCrystalPackage` with `shardsFile = ./shards.nix;` (from `crystal2nix`, which needs a `shard.lock`; create one with `shards lock` if upstream doesn't commit it) and `crystalBinaries.<name>.src = "src/<name>.cr";`. Default build options are `--release --progress --no-debug --verbose`; override in `crystalBinaries.<name>.options`.

## Julia

Source: `julia.section.md`.

- There's no per-package builder. `julia.withPackages [ "Plots" ]` builds an environment from a pinned registry. Packages that precompile badly in the sandbox (for example ones that touch a display) need `precompile = false;` through `.override`. Use `juliaCpuTarget = "generic"` for depots meant for a binary cache.

## R

Source: `r.section.md`; `pkgs/development/r-modules/`.

- Use `rWrapper.override { packages = with rPackages; [ ... ]; }` or `rstudioWrapper`; RStudio ignores other R environments. `rPackages` derives from generated `cran-packages.json`, `bioc-packages.json`, and the annotation and experiment lists. Never edit those; fix breakage with overrides in `pkgs/development/r-modules/default.nix`.

## Qt, KDE, GNOME and GTK

Sources: `qt.section.md`, `gnome.section.md`; `pkgs/kde/` and `pkgs/top-level/all-packages.nix` for KDE (no manual page).

**Qt.** Put `qt6.wrapQtAppsHook` in `nativeBuildInputs` (the `libsForQt5` one for Qt 5), or set `dontWrapQtApps = true;`. Add runtime paths through `qtWrapperArgs`. The hook skips non-ELF scripts, so wrap Python scripts yourself with `wrapQtApp`. A library that supports several Qt versions takes Qt modules as separate arguments and is called from `qt5-packages.nix` or `qt6-packages.nix`. Applications should use upstream's preferred Qt version.
**KDE.** `kdePackages` is `callPackage ../kde { }`. Packages in `pkgs/kde/gear`, `frameworks`, `plasma`, `third-party`, and `misc` use `mkKdeDerivation` (for example `extraBuildInputs`, `meta.mainProgram`).
**GNOME and GTK.** Add `wrapGAppsHook3` (GTK 3), `wrapGAppsHook4` (GTK 4), or `wrapGAppsNoGuiHook` to `nativeBuildInputs`. The wrapper sets `XDG_DATA_DIRS`, GSettings, GdkPixbuf, GIO modules, and typelib paths from your dependencies. Add `dconf.lib` for anything reading GSettings and `glib-networking` for GIO network access. Extra arguments go in `gappsWrapperArgs` from `preFixup`; `dontWrapGApps = true;` disables automatic wrapping when another wrapper must own it.

## Emacs

Source: `doc/packages/emacs.section.md`; `pkgs/applications/editors/emacs/elisp-packages/`.

- The set is `emacs.pkgs`; `withPackages` builds an environment, and `overrideScope` replaces a package consistently across the set. Packages come from MELPA, ELPA, and NonGNU ELPA through generated files refreshed by the scripts next to them (`update-melpa`, `update-elpa`, `update-nongnu`, `update-from-overlay`). Hand-maintained packages live in `elisp-packages/manual-packages/<name>/package.nix` and use `melpaBuild` with `pname`, `version`, `src`, `packageRequires`, and optionally `files`. The 25.05 release notes record that the Emacs Lisp build helpers such as `melpaBuild` enable `__structuredAttrs` by default.
- After changing the MELPA list, the header of `melpa-packages.nix` says to evaluate `emacs.pkgs.melpaPackages` and `melpaStablePackages` with `NIXPKGS_ALLOW_BROKEN=1` to catch evaluation errors.

## Vim and Neovim

Sources: `vim.section.md`, `neovim.section.md`; `pkgs/applications/editors/vim/plugins/`.

- Most plugins come from `vim-plugin-names` through `generated.nix`: `nix-shell -p vimPluginsUpdater --run 'vim-plugins-updater add "owner/name"'`. The script commits to your git repository, so start from a fresh branch, and pass a GitHub token to avoid rate limits (`--github-token` or `GITHUB_TOKEN`). Plugin fixes go in `overrides.nix` (for example `dependencies = [ ... ]`); an override that must change with each update should specify everything needed so the updater doesn't alter it.
- For a Neovim Lua plugin, check Luarocks first; if a release exists add it to `luarocksPackageNames` in `luaPackagePlugins.nix` and let `buildNeovimPlugin { luaAttr = ...; }` convert it.
- Neovim runs `nvimRequireCheck` automatically: set `nvimRequireCheck = "module";` to test one module, `nvimSkipModules = [ ... ]` for modules that need user configuration, or `doCheck = false;` as a last resort.
- `vim-full.customize` and `neovim.override { configure = { ... }; }` build user setups. The manual still calls `vim_configurable` a deprecated alias for `vim-full`; `pkgs/top-level/aliases.nix` now throws for it.

## Agda, Rocq and Coq, Lean 4

Sources: `agda.section.md`, `rocq.section.md`, `lean4.section.md`.

**Agda.** `agdaPackages.mkDerivation` needs a single `*.agda-lib` file and sets `libraryName` (default `pname`) and `libraryFile`. In nixpkgs, put the expression in `pkgs/development/libraries/agda/<library>/default.nix` and register it in `pkgs/top-level/agda-packages.nix`. The default build runs `agda --build-library`.
**Rocq and Coq.** `rocqPackages.mkRocqDerivation` (and `coqPackages.mkCoqDerivation`) with a `release` table of hashes, `defaultVersion` to pick a release for the Rocq in use, and `propagatedBuildInputs` for library dependencies. Libraries install under `lib/coq/<version>/user-contrib/`.
**Lean 4.** `leanPackages.buildLakePackage` with `leanDeps` for Nix-managed libraries and `lakeHash` (`null` when everything is Nix-managed, `lib.fakeHash` to discover the hash for Lake-fetched dependencies). A `lake-manifest.json` must exist at the project root.

## Android

Source: `android.section.md`; `pkgs/development/mobile/androidenv/`.

- `androidenv.composeAndroidPackages { ... }` selects SDK, NDK, and image components, with `"latest"` as a wildcard. Set `config.android_sdk.accept_license = true;` (the source text names this option) to accept the SDK license. Export `ANDROID_HOME` as `${androidComposition.androidsdk}/libexec/android-sdk`; `ANDROID_SDK_ROOT` is deprecated. The Android Gradle plugin needs `GRADLE_OPTS` pointing `aapt2FromMavenOverride` at the Nix-store `aapt2`.
- Gradle-based apps follow the Gradle section above. `androidenv.buildApp` is an Ant builder kept for historical reasons. The `repo.json` behind the SDK is generated by `pkgs/development/mobile/androidenv/update.sh`; `aarch64-linux` support is partial.

## Other manual sections

`doc/languages-frameworks/` also has files for Chicken, COSMIC, CUDA, Cue, Dhall, D (`dlang`), Emscripten, Factor, Hare, Hy, Idris and Idris 2, iOS, Lisp, Octave, Scheme, Swift, Tcl, TeX Live, and Typst. This file doesn't cover them; read the manual file and the `pkgs/top-level/<name>-packages.nix` set (where one exists) before writing a derivation.

## Checkable rules

- A new application package is under `pkgs/by-name/`; a library for an ecosystem set is under that set's directory and registered in its `*-packages.nix`.
- No edits to generated files (`hackage-packages.nix`, `generated-packages.nix`, `generated.nix`, `cran-packages.json`, `ruby-packages.nix`, `*-generated.nix`) except through their update script.
- Lock or hash material is a real value: `mvnHash`, `vendorHash`, `nugetDeps`/`deps.json`, `pubspecLock`, `lockFile`, `shardsFile`, `mixFodDeps`, or `lakeHash` isn't `lib.fakeHash` or empty.
- Version-sensitive attributes are explicit: `dotnetCorePackages.sdk_X_Y`, `flutterNNN`, `lua5_4` or `lua54Packages`, a pinned `zig_0_NN`, and an explicit `beamPackages` set.
- Lua packages don't reference the `lua`, `lua5`, or `luaPackages` aliases.
- Qt packages include `wrapQtAppsHook` (or `dontWrapQtApps`); GTK packages include a `wrapGApps*` hook.
- Gradle packages set `mitmCache` and a `deps.json` next to `package.nix`.

## Dated advice to ignore

- "Haskell packages submitted to master instead of `haskell-updates` fail to merge" (review synthesis): the merge-rate framing is correlation, and the docs only show that `haskell-updates` is a team-run branch merged into `staging`. Check the CI bot's suggested base branch.
- "Use Qt's `mkDerivation` instead of `wrapQtAppsHook`": the current Qt manual page puts `wrapQtAppsHook` in `nativeBuildInputs` for every Qt package.
- `buildComposerProject` (v1) still exists in the tree, but the manual documents `buildComposerProject2` for new work.
- `vimUtils.buildVimPluginFrom2Nix` warns that it's deprecated for `buildVimPlugin`, and `vim_configurable` throws (use `vim-full`), even though the Vim manual page still describes the latter as a deprecated alias.
