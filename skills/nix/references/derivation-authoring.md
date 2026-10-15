# Authoring derivations

Load this when you write, review, or shrink a `package.nix` (nixpkgs or out-of-tree) built with `stdenv.mkDerivation`. Language builders (`buildGoModule`, `buildRustPackage`, ...) have their own files: [Python](lang-python.md), [Go](lang-go.md), [Rust](lang-rust.md), [Node.js](lang-nodejs.md), [Ruby](lang-ruby.md), [C/C++](lang-c-cpp.md), [other ecosystems](lang-other-ecosystems.md). Sources are in [fetchers-and-sources](fetchers-and-sources.md), metadata in [meta-and-licensing](meta-and-licensing.md).

Verified against the nixpkgs manual and tree (Oct 2026): `doc/stdenv`, `doc/hooks`, `pkgs/README.md`, `pkgs/by-name/README.md`, `CONTRIBUTING.md`.

**Contents:** [Where the file goes](#where-the-file-goes) · [The modern skeleton](#the-modern-skeleton) · [Dependency attributes](#dependency-attributes) · [Phases and hooks](#phases-and-hooks) · [Installing files](#installing-files) · [Runtime dependencies without hardcoded paths](#runtime-dependencies-without-hardcoded-paths) · [Conditional inputs and features](#conditional-inputs-and-features) · [Multiple outputs](#multiple-outputs) · [passthru](#passthru) · [The minimal derivation ladder](#the-minimal-derivation-ladder) · [Packaging existing software](#packaging-existing-software) · [Binary releases (last resort)](#binary-releases-last-resort) · [Reuse: callPackage, override, overrideAttrs](#reuse-callpackage-override-overrideattrs) · [Checkable rules](#checkable-rules) · [Evidence](#evidence) · [Dated advice to ignore](#dated-advice-to-ignore)

## Where the file goes

- New top-level packages live in `pkgs/by-name/<xx>/<name>/package.nix`. `<xx>` is the first two characters of the attribute name, lowercased (`_0` for `_0ad`). The attribute exists automatically; there's no `all-packages.nix` entry.
- The attribute name equals `pname`, hyphens included (don't convert to camelCase). `pname` must not contain uppercase letters and should match upstream.
- A by-name package can't reference files outside its own directory, and only `pkgs.callPackage` packages qualify (not `python3Packages.callPackage`). CI runs `nixpkgs-vet`; reproduce it with `./ci/nixpkgs-vet.sh master`.
- File and directory names are kebab-case (`all-packages.nix`, not `allPackages.nix`).
- Function arguments list exactly what the expression uses: no `...`, no `with args;`. Use an `@args` pattern only for truly generic wrappers.
- Out of tree, keep the same `package.nix` shape and wire it with `pkgs.callPackage ./package.nix { }` (see [flake-layout](flake-layout.md)).

## The modern skeleton

```nix
{
  lib,
  stdenv,
  fetchFromGitHub,
  cmake,
  pkg-config,
  installShellFiles,
  versionCheckHook,
  nix-update-script,
  zlib,
}:

stdenv.mkDerivation (finalAttrs: {
  pname = "foo";
  version = "1.2.3";

  src = fetchFromGitHub {
    owner = "example";
    repo = "foo";
    tag = "v${finalAttrs.version}";
    hash = "sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=";
  };

  __structuredAttrs = true;
  strictDeps = true;

  nativeBuildInputs = [
    cmake
    pkg-config
    installShellFiles
  ];

  buildInputs = [ zlib ];

  doInstallCheck = true;
  nativeInstallCheckInputs = [ versionCheckHook ];

  passthru.updateScript = nix-update-script { };

  meta = {
    description = "Tool that does a thing";
    homepage = "https://example.org/foo";
    changelog = "https://example.org/foo/releases/tag/${finalAttrs.src.tag}";
    license = lib.licenses.mit;
    maintainers = with lib.maintainers; [ someone ];
    mainProgram = "foo";
    platforms = lib.platforms.unix;
  };
})
```

The hash is `lib.fakeHash`; replace it from the build error ([hash workflow](fetchers-and-sources.md#hash-workflow)). `someone` must be a registered maintainer ([registration](meta-and-licensing.md#maintainers)).

- **`finalAttrs` instead of `rec`.** `rec` self-references freeze at definition time; `finalAttrs` references follow `overrideAttrs`. `finalAttrs.finalPackage` is the result itself (used in tests). Don't build `name` yourself: set `pname` and `version`; the manual says RFC 35 makes this the nixpkgs form.
- **`__structuredAttrs = true`.** The stdenv manual states: "All new top level packages must enable `__structuredAttrs`." It's a complete replacement for the old attribute passing. Consequences: variables you want exported to the builder go in `env` (`env.NIX_CFLAGS_COMPILE = "..."`), not as bare attributes, and `passAsFile` is unavailable. Only a minority of existing packages set it today, so don't "fix" unrelated packages in a feature PR.
- **`strictDeps = true`.** Without it, `stdenv` only enforces the native/host split when it's cross-compiling (`strictDeps` defaults to `hostPlatform != buildPlatform`, unless `config.strictDepsByDefault`). Native builds therefore hide misplaced inputs. Setting it makes the mistake fail in your normal build.
- **Order and reference.** Put `passthru` before `meta`, and `meta` last (`pkgs/README.md`). `hello` (`pkgs/by-name/he/hello/package.nix`) is the maintained reference for this shape.

## Dependency attributes

| Put it in | When | Example |
|---|---|---|
| `nativeBuildInputs` | It *runs* during the build: build tools, code generators, setup hooks, interpreters used by `patchShebangs --build` | `cmake`, `pkg-config`, `makeBinaryWrapper`, `installShellFiles`, `bison` |
| `buildInputs` | It's linked, included, or otherwise used by the output at runtime | `zlib`, `openssl`, a library whose headers you include |
| both | The software uses a library *and* runs a tool from the same package | `wayland` (library) and its scanner tool |
| `nativeCheckInputs` / `checkInputs` | Only tests need it; native = runs on `$PATH`, plain = linked | `pytestCheckHook`, a test-only library |
| `propagatedBuildInputs` | Consumers can't compile or link against your output without it | A library whose public headers include another library's headers; interpreted-language environments |
| none of them | A script shells out to it at runtime | wrap it with `makeBinaryWrapper` or substitute its store path |

**Why the split exists.** Cross-compiling `foo` for aarch64 on x86_64 needs an x86_64 `cmake` (runs here) and an aarch64 `zlib` (runs there). `nativeBuildInputs` come from the build platform; `buildInputs` come from the host platform. The two criteria are independent, which is why one package can legitimately sit in both lists. Test a cross build from a nixpkgs checkout with `nix-build -A pkgsCross.aarch64-multiplatform.foo`. See [native-vs-cross](native-vs-cross.md) for flake-level concerns.

**Propagation is a last resort.** The manual warns that propagated inputs obscure the real build inputs and cause side effects through setup hooks. If a runtime executable is only called by absolute path, Nix already records it as a runtime reference through the store path in your output; don't add it to `buildInputs` just to keep it alive.

Review-derived guidance often says "`buildInputs` for runtime dependencies, `nativeBuildInputs` for build dependencies". That's a decent heuristic for libraries and tools, but it misses executables your program calls at runtime (wrap them) and tools that are both.

## Phases and hooks

Default order: unpack, patch, configure, build, check, install, fixup, installCheck. Extend it, don't replace it.

- Add behavior with hooks: `postPatch`, `preConfigure`, `preBuild`, `postInstall`, `preFixup`, `postFixup`. Hooks compose with the defaults; an overridden phase replaces the default wholesale.
- Override a whole phase only when its default does the wrong thing. Start with `runHook preX` and end with `runHook postX`, even if you don't use them; otherwise downstream `preInstall`/`postInstall` silently stop working.
- Don't set `phases`. The manual discourages it because `fixupPhase` hides important work (shebang patching, stripping). If you need an extra phase, use `preConfigurePhases`, `preBuildPhases`, `preInstallPhases`, and the like.
- Skip a phase with `dontConfigure`, `dontBuild`, `dontUnpack`, or `dontInstall` rather than overriding it with an empty script.

```nix
# BAD: no hooks, and hand-rolled mkdir/cp
{
  installPhase = ''
    mkdir -p $out/bin
    cp foo $out/bin/
  '';
}
```

```nix
# GOOD
{
  installPhase = ''
    runHook preInstall

    install -Dm755 foo -t $out/bin

    runHook postInstall
  '';
}
```

If the upstream Makefile already has an `install` target, don't override anything; set `makeFlags = [ "PREFIX=$(out)" ];` (flags are quoted for bash, but `make` variable syntax works).

Iterate on a failing phase without rebuilding everything: in `nix-shell -A foo`, run `export out=$(pwd)/out`, then `phases="buildPhase" genericBuild` (see the stdenv manual's "Building a `stdenv` package in `nix-shell`"). `breakpointHook` (Linux only, in `nativeBuildInputs`) pauses a failing build so you can attach to the sandbox, and `nix-build -K` keeps the failed build directory.

## Installing files

`installShellFiles` (in `nativeBuildInputs`) provides `installBin`, `installManPage`, and `installShellCompletion`; they pick the right output directory and fail if a completion file ends up empty.

```nix
{
  postInstall = ''
    installManPage doc/foo.1
  ''
  + lib.optionalString (stdenv.buildPlatform.canExecute stdenv.hostPlatform) ''
    installShellCompletion --cmd foo \
      --bash <($out/bin/foo completions bash) \
      --fish <($out/bin/foo completions fish) \
      --zsh <($out/bin/foo completions zsh)
  '';
}
```

Generating completions by running the binary breaks cross builds, so guard it with `canExecute` (the manual's own example). Shipped completion files install with `installShellCompletion --bash share/foo.bash`.

## Runtime dependencies without hardcoded paths

Prefer, in this order:

1. A build-system option (`makeFlags`, `cmakeFlags`, `configureFlags`) that takes the path.
2. `substituteInPlace file --replace-fail "/usr/bin/bar" "${lib.getExe bar}"` in `postPatch`. `--replace-fail` errors when nothing matched; bare `--replace` is deprecated.
3. `replaceVars ./fix-paths.patch { bar = lib.getExe bar; }` for a vendored patch with `@bar@` placeholders (the build fails on any unreplaced `@name@`).
4. A wrapper that sets `PATH` for tools the program finds by name:

```nix
{
  nativeBuildInputs = [ makeBinaryWrapper ];

  postInstall = ''
    wrapProgram $out/bin/foo \
      --prefix PATH : ${lib.makeBinPath [ git openssh ]}
  '';
}
```

- `lib.getExe pkg` resolves `${lib.getBin pkg}/bin/<meta.mainProgram>`. Use `lib.getExe' pkg "name"` when the package has several binaries (the name can't contain `/`).
- `--prefix PATH` pins the dependency; `--suffix PATH` leaves the user's own tools first.
- `makeBinaryWrapper` makes a small compiled wrapper (works as a shebang on Darwin); `makeWrapper` is a shell wrapper and is what you need when the wrapper must use shell features. `wrapProgram` works with both. Wrap each binary once; double wrapping stacks wrappers.
- Scripts' `#!` lines are rewritten to store paths in `fixupPhase` automatically. Call `patchShebangs --build` yourself for scripts the *build* runs.

## Conditional inputs and features

```nix
{
  buildInputs = [
    zlib
  ]
  ++ lib.optionals stdenv.hostPlatform.isLinux [ systemd ]
  ++ lib.optional withFoo libfoo;

  cmakeFlags = [
    (lib.cmakeBool "WITH_FOO" withFoo)
    (lib.cmakeFeature "FOO_BACKEND" "native")
  ];
}
```

- Use `lib.optional`, `lib.optionals`, and `lib.optionalString`, not `if c then [ x ] else null`. CONTRIBUTING allows the `null` form only for an urgent fix that avoids a mass rebuild.
- Check platforms with `stdenv.hostPlatform.isLinux`/`isDarwin`. The old `stdenv.isDarwin` form now warns as deprecated.
- Feature toggles are function arguments with defaults (`withFoo ? true`), so `.override { withFoo = false; }` works. Add a flag only when someone needs it.
- Helpers for build-system flags: `lib.cmakeBool`, `lib.cmakeFeature`, `lib.mesonBool`, `lib.mesonEnable`, `lib.mesonOption`, `lib.withFeature`, `lib.enableFeature`.

## Multiple outputs

Split when it shrinks a runtime closure: headers and `.pc` files to `dev`, manuals to `man`, large docs to `doc`.

```nix
{
  outputs = [
    "out"
    "dev"
    "man"
  ];
}
```

- A consumer that lists your package in `buildInputs` gets `dev` (if present) plus `propagatedBuildOutputs`; other outputs need explicit `lib.getBin`, `lib.getLib`, `lib.getDev`, or `foo.man`.
- Executables belong in the first output by convention (the "binaries first" rule). `outputs = [ "bin" "dev" "out" ]` is also common for libraries with CLI tools.
- The `multiple-outputs.sh` hook adds configure flags and moves files during fixup. If a configure script chokes on them, set `setOutputFlags = false;`.
- `separateDebugInfo = true;` creates a `debug` output by itself.
- Each output name becomes an environment variable in the builder, so phases write to `$out`, `$dev`, `$man`, and so on.
- Don't split libraries from `out` when they reference data in `out`; the manual notes there's often no gain.

## passthru

`passthru` isn't passed to the builder, so changing it never rebuilds the package.

```nix
{
  passthru = {
    tests.run = callPackage ./test.nix { foo = finalAttrs.finalPackage; };
    updateScript = nix-update-script { };
  };
}
```

- Tests use `finalAttrs.finalPackage` so `overrideAttrs` still tests the overridden package. See [testing](testing.md).
- `passthru.updateScript` lets bots update the package: `nix-update-script { }` for tags, `nix-update-script { extraArgs = [ "--version=branch" ]; }` for branch snapshots, `unstableGitUpdater { }` for untagged commits. See [versioning-and-updates](versioning-and-updates.md).

## The minimal derivation ladder

Write the least that could work, build, and climb one rung per failure. Every line you add should trace to a failing build, a documented upstream requirement, or a reviewer rule.

| Rung | You write | Add the next rung only when |
|---|---|---|
| 0 | `pname`, `version`, `src` (autotools and plain-Makefile projects often finish here) | the build fails |
| 1 | `nativeBuildInputs` / `buildInputs` entries | the log names a missing tool, header, or library |
| 2 | `configureFlags`, `cmakeFlags`, `makeFlags` | the build picks a wrong default (bundled dependency, network access, `/usr` prefix) |
| 3 | `patches`, or `postPatch` with `substituteInPlace --replace-fail` | a hardcoded path or compile error needs a source change |
| 4 | `postInstall`, `installShellFiles`, a wrapper | outputs lack man pages or completions, or a runtime tool isn't found |
| 5 | an overridden phase with `runHook` | no hook, helper, or flag expresses the change |
| 6 | checks (`doCheck`, `versionCheckHook`), `meta`, `passthru.updateScript` | always, before you open a PR |

Prefer a builder helper or hook over a custom phase: `cmake`, `meson` plus `ninja`, `pkg-config`, `autoreconfHook`, `installShellFiles`, `makeBinaryWrapper`, `copyDesktopItems` with `makeDesktopItem`, `autoPatchelfHook`, `versionCheckHook`, or the language builder.

Then delete. After the build passes, remove each input, patch, flag, and argument one at a time and rebuild; keep what the build needs. Lint for unused arguments ([nix-linting-tools](nix-linting-tools.md)). Reviewers also ask you to document, in a comment or the patch name: pinned versions, non-default build flags, partly disabled checks, and every `patches` entry (upstream URL or why it isn't upstreamed).

## Packaging existing software

1. **Decide it belongs.** Search nixpkgs first. The `pkgs/README.md` questions: is it ready for general use, does it have a clear license, would others use it, is it maintained upstream, will *you* maintain it for a release cycle. Anything that would need `meta.knownVulnerabilities` is unlikely to fit.
2. **Read upstream's build.** Check the README and CI workflow for the real build and test commands, the build-system file (`CMakeLists.txt`, `meson.build`, `configure.ac`, `Makefile`, `go.mod`, `Cargo.toml`, `pyproject.toml`, `package.json`), the lockfile, optional features, bundled third-party code, and how the binary prints its version.
3. **Pick the builder** from the table below. Use the language framework, not a hand-written `stdenv` build, whenever one exists.
4. **Pin the source** with the right fetcher and a verified hash ([fetchers-and-sources](fetchers-and-sources.md)).
5. **Climb the ladder** in a checkout: `nix-build -A foo` (add `-K` to keep the build directory). Sandboxing must be on; Linux enables it by default.
6. **Run upstream's tests** in `checkPhase` with `doCheck = true`, and add `versionCheckHook`. Heavier checks go in `passthru.tests` ([testing](testing.md)).
7. **Finish `meta`** and register yourself if needed ([meta-and-licensing](meta-and-licensing.md)).
8. **Run every installed binary**, build on each platform you can, check a cross build, and use `nixpkgs-review` when other packages depend on yours. Then see [upstreaming-and-prs](upstreaming-and-prs.md).

| Upstream uses | Use | Notes |
|---|---|---|
| `./configure && make` | plain `stdenv.mkDerivation` | add `autoreconfHook` only if the tarball lacks `configure` or you must patch it |
| CMake | `cmake` in `nativeBuildInputs` | the hook replaces the configure phase; pass options through `cmakeFlags`; `ninja` in the inputs switches the generator |
| Meson | `meson` and `ninja` | `mesonEmulatorHook` when the build runs host binaries while cross-compiling |
| Bare Makefile | `makeFlags`, maybe `installPhase` | see the install example above |
| Go, Rust, Python, Node.js, Ruby | the language builder | [Go](lang-go.md), [Rust](lang-rust.md), [Python](lang-python.md), [Node.js](lang-nodejs.md), [Ruby](lang-ruby.md) |
| Anything else | check `doc/languages-frameworks` | [other ecosystems](lang-other-ecosystems.md) |

## Binary releases (last resort)

Build from source whenever you can. The manual's security guidance says source-available software should be built from source where possible, since binary blobs risk supply-chain attacks and vendored outdated libraries, and reviewers occasionally ask whether a source build is possible (support 9, cr 4 in the corpus). Repackage a binary only for unfree or source-unavailable software, or when the source build isn't feasible.

```nix
{
  lib,
  stdenv,
  fetchurl,
  autoPatchelfHook,
  zlib,
}:

stdenv.mkDerivation (finalAttrs: {
  pname = "foo-bin";
  version = "1.2.3";

  src = fetchurl {
    url = "https://example.org/foo/releases/foo-${finalAttrs.version}-linux-x86_64.tar.gz";
    hash = "sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=";
  };

  __structuredAttrs = true;
  strictDeps = true;

  nativeBuildInputs = lib.optionals stdenv.hostPlatform.isLinux [ autoPatchelfHook ];
  buildInputs = [ (lib.getLib stdenv.cc.cc) zlib ];

  dontConfigure = true;
  dontBuild = true;

  installPhase = ''
    runHook preInstall

    install -Dm755 foo -t $out/bin

    runHook postInstall
  '';

  meta = {
    description = "Tool that does a thing";
    homepage = "https://example.org/foo";
    license = lib.licenses.unfree;
    sourceProvenance = [ lib.sourceTypes.binaryNativeCode ];
    maintainers = with lib.maintainers; [ someone ];
    mainProgram = "foo";
    platforms = [ "x86_64-linux" ];
  };
})
```

- `autoPatchelfHook` rewrites ELF interpreters and RPATHs from your `buildInputs`; it fails on unresolved libraries unless you set `autoPatchelfIgnoreMissingDeps`. Libraries loaded with `dlopen` go in `runtimeDependencies`. It's Linux-only, so guard it.
- Set `meta.sourceProvenance` (`binaryNativeCode` for native code, including repackaged `.deb`, `.rpm`, and `.whl`; `binaryBytecode` for jars). Set `meta.license` accurately, usually `lib.licenses.unfree` ([unfree handling](meta-and-licensing.md#licenses)).
- Restrict `meta.platforms` to the systems you ship an archive for.
- Don't mark the package `unfreeRedistributable` if you modify the binaries (`patchelf` counts); the manual says to use `unfree` then.

## Reuse: callPackage, override, overrideAttrs

- `callPackage` fills your function arguments from the package set, and gives the result `.override` for argument changes. Expose variation as arguments with defaults and callers use `foo.override { withBar = true; }`.
- If a package needs a specific variant of a dependency, name the argument for it (`libbar_2`) instead of overriding the default in `all-packages.nix`; the by-name README explains that this keeps the requirement visible and makes downstream breakage loud.
- `foo.overrideAttrs` changes the attributes passed to `mkDerivation`. It's the right tool *outside* nixpkgs:

```nix
foo.overrideAttrs (finalAttrs: previousAttrs: {
  patches = previousAttrs.patches or [ ] ++ [ ./fix-build.patch ];
})
```

- **Inside nixpkgs, don't add new `overrideAttrs` or `overridePythonAttrs` uses.** `pkgs/README.md` says to change the dependency's own package instead: add an argument and use `.override`, or factor a shared builder. See [patches-and-overrides](patches-and-overrides.md).
- Don't copy a package into your tree to tweak it. Override it, or send the change upstream to nixpkgs.
- `lib.extendMkDerivation` defines new build helpers that support `finalAttrs` (`doc/build-helpers/fixed-point-arguments.chapter.md`).

## Checkable rules

- The package is `pkgs/by-name/<xx>/<name>/package.nix`, `<xx>` matches the first two lowercase characters of the name.
- `pname` and `version` exist as separate attributes; `name` isn't hand-built; `pname` has no uppercase letters.
- The derivation uses `finalAttrs`, not `rec`.
- `version` starts with a digit.
- `strictDeps = true` and `__structuredAttrs = true` are set (new top-level packages).
- Build tools sit in `nativeBuildInputs`; the same tool isn't in `buildInputs` unless it's also linked.
- Every overridden `*Phase` begins with `runHook pre*` and ends with `runHook post*`; `phases` isn't set.
- No `/usr/...` or `/bin/...` path or bare `${pkg}/bin/x` string remains where `lib.getExe`/`lib.getExe'`/`replaceVars` fits.
- Conditionals on platform use `stdenv.hostPlatform.is*`, not `stdenv.is*`.
- Optional inputs use `lib.optional(s)`.
- `meta` is the last attribute and `passthru` precedes it.
- `substituteInPlace` uses `--replace-fail` (or `--replace-warn`/`--replace-quiet` with a reason).
- Each `patches` entry has a descriptive name or comment.
- No unused function arguments.
- Binary repackages set `sourceProvenance`.

## Evidence

From `find-rules.py` (support = backing PRs, cr = PRs with a changes-requested review):

| Rule | support | cr |
|---|---|---|
| Separate `pname` and `version` | 549 | 186 |
| Build-time tools in `nativeBuildInputs` | 565 | 130 |
| `finalAttrs` instead of `rec` | 178 | 76 |
| Remove unused dependencies | 477 | 70 |
| Use `lib.getExe`/`lib.getExe'` instead of hardcoded paths | 77 | 34 |
| `strictDeps = true` | 122 | 33 |
| New packages in `pkgs/by-name` | 138 | 68 |
| Use `runHook` in custom phases | 515 | 25 |
| `__structuredAttrs` for new by-name packages | 26 | 5 |

## Dated advice to ignore

- `stdenv.isDarwin`, `stdenv.isLinux`, `stdenv.isx86_64` and siblings: deprecated with a warning in the current tree; use `stdenv.hostPlatform.isDarwin` etc.
- `name = "${pname}-${version}"` and `rec { ... }` self-references: replaced by `finalAttrs`.
- `substituteInPlace --replace` (deprecated) and `pkgs.substituteAll` (removed, now `replaceVars`). The stdenv *shell* functions `substitute`/`substituteInPlace` are current.
- "Always `buildInputs` for runtime dependencies": too coarse; see the dependency table.
- Review-derived "package names use lowercase with hyphens (PEP 503)": that's the Python rule. The general rule is no uppercase letters in `pname`.
- Older nix.dev tutorials use `rev = "v0.5"`, `sha256 = ...`, and plain-attrset `mkDerivation`; the nixpkgs manual's `tag`, `hash`, and `finalAttrs` forms supersede them.
- This skill's own [code-patterns](code-patterns.md) package templates use `meta = with lib;`, `rev`, and `sha256`, and reference `licenses.MIT` and `licenses.proprietary`, which don't exist in `lib.licenses`. Follow the skeleton above instead.
- `discord-gamesdk`, which `pkgs/README.md` lists as an example binary package, uses `rec` and lacks `strictDeps`; treat it as an `autoPatchelfHook` illustration only.
- Merge-rate percentages in the review corpus are correlations, not rules.
