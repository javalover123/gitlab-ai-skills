# Build closure and platforms

Load this when a package behaves differently per platform, needs cross-compilation to work, ships a bigger closure than it should, loads libraries at run time, needs a wrapper, builds on Darwin, or touches something near `stdenv`. For the flake-level question of native versus cross-built artifacts, read [native-vs-cross](native-vs-cross.md) first; this file covers the package-level mechanics under it.

Checked against nixpkgs master (Oct 2026): `doc/stdenv/` (stdenv, cross-compilation, platform-notes, meta, multiple-output), `doc/hooks/`, `pkgs/stdenv/generic/`, `pkgs/top-level/aliases.nix`, and `CONTRIBUTING.md`.

**Contents:** [Platform conditionals](#platform-conditionals) · [`meta` platform fields](#meta-platform-fields) · [Cross-compilation correctness](#cross-compilation-correctness) · [Closure size](#closure-size) · [Prebuilt binaries, `autoPatchelfHook`, and `dlopen`](#prebuilt-binaries-autopatchelfhook-and-dlopen) · [Wrappers](#wrappers) · [Darwin](#darwin) · [Bootstrap and `stdenv`-adjacent changes](#bootstrap-and-stdenv-adjacent-changes) · [Checkable rules](#checkable-rules) · [Evidence](#evidence) · [Dated advice to ignore](#dated-advice-to-ignore)

## Platform conditionals

Use the platform attributes on `stdenv.hostPlatform`. `stdenv.isDarwin`, `stdenv.isLinux`, `stdenv.isx86_64`, `stdenv.isAarch64`, and the other `stdenv.is*` shortcuts are deprecated (the stdenv now warns "`stdenv.<name>` is deprecated, use `stdenv.hostPlatform.<name>` instead", added 2026-05-09). The manual says the `hostPlatform.is*` predicates are better because they make you say which platform you're inspecting.

| You mean | Write |
|---|---|
| The package will run on Darwin / Linux | `stdenv.hostPlatform.isDarwin`, `stdenv.hostPlatform.isLinux` |
| The build machine is Darwin (something executed during the build) | `stdenv.buildPlatform.isDarwin` |
| A CPU architecture | `stdenv.hostPlatform.isx86_64`, `isAarch64`, `is64bit` |
| An exact system string (platform-specific source hashes, prebuilt binaries) | `stdenv.hostPlatform.system` |
| The C library | `stdenv.hostPlatform.libc == "glibc"`, `isMusl` |
| Static linking | `stdenv.hostPlatform.isStatic` |
| The compiler | `stdenv.cc.isClang`, `stdenv.cc.isGNU` |
| A shared library's filename extension | `stdenv.hostPlatform.extensions.sharedLibrary` (`.so`, `.dylib`) |

Never use `builtins.currentSystem` or `builtins.system` inside a package; they're the evaluator's platform, not the package's, and they break cross builds. In a flake's `perSystem` plumbing, `system` is fine, but don't pass it into the package function.

When correctness depends on a specific distinction, compare to the concrete value (`libc == "glibc"`) rather than an abstract predicate, and dispatch on the full triple (`stdenv.hostPlatform.config`) when the ABI matters, since `system` hides the libc.

Gate with the list and string helpers; don't use `if ... then [ ... ] else null`:

```nix
{
  buildInputs = [
    zlib
  ]
  ++ lib.optionals stdenv.hostPlatform.isLinux [ libfoo ]
  ++ lib.optional stdenv.hostPlatform.isDarwin libiconv;

  env = lib.optionalAttrs stdenv.hostPlatform.isDarwin {
    NIX_CFLAGS_COMPILE = "-Wno-error=unguarded-availability";
  };

  postInstall = lib.optionalString stdenv.hostPlatform.isLinux ''
    install -Dm644 contrib/foo.service $out/lib/systemd/system/foo.service
  '';
}
```

Gate only what's actually platform-specific: the Darwin notes say to write the derivation as if nothing special is needed, build it, and add handling only if it fails. Under `__structuredAttrs = true`, environment variables go in `env`.

Source or hash that differs per system, keyed on `system` with an explicit failure:

```nix
{
  src =
    let
      sources = {
        x86_64-linux = {
          url = "https://example.org/foo-x86_64.tar.gz";
          hash = "sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=";
        };
        aarch64-linux = {
          url = "https://example.org/foo-aarch64.tar.gz";
          hash = "sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=";
        };
      };
    in
    fetchurl (
      sources.${stdenv.hostPlatform.system}
        or (throw "foo: unsupported system ${stdenv.hostPlatform.system}")
    );
}
```

## `meta` platform fields

`meta` goes last in the derivation (after `passthru`).

| Field | Meaning | Use when |
|---|---|---|
| `meta.platforms` | Platforms the package supports; Hydra builds for these. With none set, no prebuilt binaries | Always set; use `lib.platforms.linux`, `.unix`, `.darwin`, `.all` |
| `meta.badPlatforms` | Platforms known not to work, excluded from Hydra even if in `platforms`; participates in `lib.meta.availableOn` | The platform is structurally unsupported (static linking, a missing OS feature) |
| `meta.broken` | The package fails, though it might work with a fix; hides it from search and blocks install | A known build or test failure on a platform; can be conditional |
| `meta.hydraPlatforms` | Subset Hydra builds; defaults to `platforms` | You want a supported package that Hydra doesn't build (`[ ]`) |

Guidelines:

- Declare support as widely as you've verified or as upstream documents it, and no wider. Don't claim a platform you haven't tried and can't reason about.
- The manual prefers `meta.platforms = lib.platforms.all` plus `badPlatforms` for exclusions, when most platforms work.
- `meta.broken` is the more flexible tool: it can depend on arguments (`!(stdenv.buildPlatform.canExecute stdenv.hostPlatform)` marks a package as not cross-compiling). It does not affect `lib.meta.availableOn`, which looks only at `platforms` and `badPlatforms`.
- Mark a platform broken instead of leaving it failing. CONTRIBUTING suggests it when ofborg reports a failure on a platform you can't reach. Add a comment with the failure and, where there is one, the issue link, so the next person can test removal.
- Broken for a whole release cycle with no fix is the usual trigger for removal, not a permanent state (see [versioning-and-updates](versioning-and-updates.md)).
- The corpus has "prefer `badPlatforms` over `broken`" (13 PRs) and "mark `broken` rather than leave it" (157 PRs). Use the table: structural, never-will-work exclusions go in `badPlatforms`; fixable failures go in a conditional `broken`.

```nix
{
  meta = {
    platforms = lib.platforms.unix;
    # Needs dynamic linking.
    badPlatforms = [ lib.systems.inspect.platformPatterns.isStatic ];
    # Link failure on Darwin; reported at https://example.org/foo/issues/1.
    broken = stdenv.hostPlatform.isDarwin;
  };
}
```

Use `lib.meta.availableOn` to turn an optional feature on only where its dependency exists:

```nix
{
  lib,
  stdenv,
  libfoo,
  withFoo ? lib.meta.availableOn stdenv.hostPlatform libfoo,
}:
stdenv.mkDerivation {
  buildInputs = lib.optional withFoo libfoo;
}
```

`pkgs/top-level/release-supported-systems.json` lists `x86_64-linux`, `aarch64-linux`, and `aarch64-darwin`. `x86_64-darwin` support was dropped for 26.11, so new `platforms` lists don't need it.

## Cross-compilation correctness

Nixpkgs wants every package written with cross-compilation in mind, and with as few cross-specific special cases as possible. Most of it comes down to putting inputs in the right list.

| List | Put there | Examples |
|---|---|---|
| `nativeBuildInputs` | Programs that run during the build, setup hooks | `cmake`, `pkg-config`, `makeWrapper`, `autoPatchelfHook`, a code generator |
| `buildInputs` | Libraries linked into the output, and interpreters for installed scripts | `zlib`, `libfoo`, `perl` for installed scripts |
| `depsBuildBuild` | Tools that run on the build machine and emit code for the build machine | `buildPackages.stdenv.cc` for a helper compiled and run during the build |
| `nativeCheckInputs` | Test tools on `PATH`, test hooks | `pytestCheckHook`, a test runner |
| `checkInputs` | Libraries linked into test executables | A test library |
| `propagatedBuildInputs` | Libraries consumers need at their build time (see below) | Libraries whose headers appear in your public headers |

The criteria are independent: something can be in both `nativeBuildInputs` and `buildInputs`, as a library that also ships a code generator needed at build time. The old corpus advice to "use `buildInputs` for build-time tools" is backwards. Build tools go in `nativeBuildInputs`.

Set `strictDeps = true` for new packages. Without it, native builds forgive misplaced inputs (a runtime library only in `nativeBuildInputs` still works, since both end up on one platform), which hides cross-build failures. The `buildGoModule`, `buildRustPackage`, `buildPythonPackage`, and similar builders enable it by default. New top-level packages also set `__structuredAttrs = true` (stdenv manual).

Splicing handles the build/host split for you. A plain `nativeBuildInputs = [ foo ]` already gets the build-platform `foo`; don't write `buildPackages.foo` there. Use `buildPackages` where an expression needs a build-platform tool outside the dependency lists, such as inside a script string, or `depsBuildBuild = [ buildPackages.stdenv.cc ]`. Prefer `buildPackages` over `targetPackages` whenever either would do; `targetPackages` is only for compilers and leads to cycles.

Common cross fixes from the cross-compilation chapter:

```nix
{
  # Build system needs to compile and run a helper on the build machine.
  depsBuildBuild = [ buildPackages.stdenv.cc ];

  # Tests execute host binaries; skip them when the build machine can't run them.
  doCheck = stdenv.buildPlatform.canExecute stdenv.hostPlatform;

  # Meson runs host binaries during the build.
  nativeBuildInputs = [
    meson
  ]
  ++ lib.optionals (!stdenv.buildPlatform.canExecute stdenv.hostPlatform) [ mesonEmulatorHook ];

  # Build scripts hardcode an unprefixed compiler.
  makeFlags = [ "CC=${stdenv.cc.targetPrefix}cc" ];
}
```

- To run a host binary under emulation, use `${stdenv.hostPlatform.emulator buildPackages} ./binary`, guarded by `stdenv.hostPlatform.emulatorAvailable buildPackages`. Don't invoke `qemu` by hand.
- Using `-static` outside a static platform may need `stdenv.cc.libc.static` in `buildInputs` for glibc; `pkgsStatic` is often the better route.
- Scripts installed into the output should refer to the host shell: `runtimeShell` (a path to non-interactive bash) rather than `stdenv.shell`, which is the build platform's.
- Test cross builds with `nix-build -A pkgsCross.aarch64-multiplatform.<name>` (nixpkgs checkout) or `pkgs.pkgsCross.aarch64-multiplatform.<name>` in an expression. See `lib.systems.examples` for the list.

## Closure size

The runtime closure is what users download and what containers ship. Reviewers commonly ask for it to be kept small; measure instead of guessing, and put the before and after in the commit message:

```sh
nix path-info -S -h ./result                  # closure size of one output
nix path-info -r -S ./result | sort -nk2      # every path in the closure with its closure size
nix why-depends ./result /nix/store/<hash>-bar   # why this path is in the closure
```

### Dependencies

- Put a dependency in a list that matches its role. A tool listed in `buildInputs` instead of `nativeBuildInputs` can still end up in the closure.
- Nix finds runtime dependencies by scanning outputs for store paths, so a path embedded in a script or binary (a `substituteInPlace` result, a `makeWrapper` PATH) is a runtime dependency without being in `buildInputs`.
- `propagatedBuildInputs` makes every consumer carry the dependency as a build input and runs its setup hooks. The manual says to use it with care because it hides real inputs and causes hard-to-resolve conflicts. Propagate only when a consumer must see the dependency at its own build time: headers in your public API, a `.pc` file that lists it in `Requires:`, the Python-style "all transitive deps in one environment" model. Don't propagate build tools or runtime-only helpers.
- Turn off optional dependencies by default when they add a lot to the closure or only matter for tests (the corpus rule has 115 PRs). Expose them as arguments:

```nix
{
  withDocs ? false,
  withTests ? false,
}:
stdenv.mkDerivation {
  cmakeFlags = [
    (lib.cmakeBool "BUILD_DOCS" withDocs)
    (lib.cmakeBool "BUILD_TESTING" withTests)
  ];
  nativeBuildInputs = lib.optionals withDocs [ doxygen ];
}
```

- Use `lib.cmakeBool`, `lib.mesonEnable`, `lib.mesonBool`, and `lib.withFeature` / `lib.enableFeature` instead of hand-written flag strings.
- `bashNonInteractive` is bash without readline; it's what `runtimeShell` points at. Use it in place of `bash` when a package needs bash only to run scripts.
- Keep test infrastructure out of the runtime output. Tests use `nativeCheckInputs`/`checkInputs`, which apply only when `doCheck = true`.
- Link dynamically unless there's a specific technical requirement for static linking (13 PRs back this in the corpus); `pkgsStatic` exists for the cases that need it.

### Outputs

Split outputs so users don't pull in headers, docs, or man pages they don't use. Each name in `outputs` becomes an attribute and an environment variable holding that output's path.

```nix
{
  outputs = [
    "out"
    "dev"
    "doc"
    "man"
  ];
}
```

How it works (from the multiple-output chapter):

- The setup hook moves files by type: development files (`include/`, `lib/pkgconfig/`, `lib/cmake/`) to `dev`; documentation to `doc`; man pages to `man`; libraries to `lib`; binaries to `bin`. Unset groups fall back to `out`.
- A multiple-output package used as a `buildInputs` entry contributes its `dev` output (or the first output if there's no `dev`), plus `propagatedBuildOutputs` (binaries and libraries by default).
- Executables go in the first output (the "binaries first" convention). `glibc` is the deliberate exception.
- Select an output explicitly with `lib.getBin foo`, `lib.getLib foo`, `lib.getDev foo`, or `foo.dev`.
- Splitting `lib` away from `out` often gains little because libraries reference data in `out`; the manual says keeping them together is easier in that case.
- Outputs of one derivation may reference each other, but not in a cycle.
- If `configure` rejects the `--docdir`-style flags the framework adds, set `setOutputFlags = false`.

Prevent accidental references to heavy build-time paths:

```nix
{
  postFixup = ''
    remove-references-to -t ${stdenv.cc.cc} $out/bin/foo
  '';
  disallowedReferences = [ stdenv.cc.cc ];
  nativeBuildInputs = [ removeReferencesTo ];
}
```

`remove-references-to` rewrites a store hash to a placeholder in the files you give it; `disallowedReferences` fails the build if any reference survives. If you set `separateDebugInfo` together with any `allowed*`/`disallowed*` attribute, also set `__structuredAttrs = true` (a hard requirement since the 25.11 release notes).

## Prebuilt binaries, `autoPatchelfHook`, and `dlopen`

For prebuilt Linux ELF binaries, add `autoPatchelfHook` to `nativeBuildInputs` and list the libraries in `buildInputs`. It rewrites each ELF file's interpreter and RPATH to point at those inputs; a library it can't find fails the build. Don't call `patchelf` by hand or set `LD_LIBRARY_PATH` to make a binary start. Also set `meta.sourceProvenance = [ lib.sourceTypes.binaryNativeCode ]` for packages that aren't built from source.

```nix
{
  nativeBuildInputs = [ autoPatchelfHook ];
  buildInputs = [
    stdenv.cc.cc.lib
    zlib
  ];
  # Loaded with dlopen at run time, so the linker never sees them.
  runtimeDependencies = [ (lib.getLib libfoo) ];
  # Provided by the host driver, not by Nix.
  autoPatchelfIgnoreMissingDeps = [ "libcuda.so.1" ];
}
```

- `runtimeDependencies` adds the named packages' `lib` directories to the RPATH of every executable unconditionally. This is what makes `dlopen("libfoo.so")` work. It takes packages; the hook appends `/lib` to each. Use `appendRunpaths` when you need a directory that isn't `<pkg>/lib`.
- `autoPatchelfIgnoreMissingDeps` takes a list of sonames, or `[ "*" ]` for all. The old boolean form (`= true`) is deprecated and warns.
- `dontAutoPatchelf = true` disables the automatic run so you can call `autoPatchelf` on chosen directories in `postFixup`; `--no-recurse` stops it descending.
- The hook is for ELF platforms. On Darwin, look at `fixDarwinDylibNames` and `install_name_tool` (below).
- It runs in `postFixup`, after the stock `patchelf` RPATH shrinking, so the runtime RPATHs it adds survive.
- A source build that `dlopen`s a library can usually patch the full store path in with `substituteInPlace` (for example the library name replaced by `${lib.getLib libfoo}/lib/libfoo${stdenv.hostPlatform.extensions.sharedLibrary}`), which is more explicit than an RPATH.

## Wrappers

Use a wrapper when a program finds helpers or data through the environment and you can't patch the path in. `makeWrapper` is a setup hook; add it to `nativeBuildInputs`.

```nix
{
  nativeBuildInputs = [ makeWrapper ];
  postInstall = ''
    wrapProgram $out/bin/foo \
      --prefix PATH : ${lib.makeBinPath [ jq ]} \
      --set-default FOO_HOME "$out/share/foo"
  '';
}
```

| Choice | Guidance |
|---|---|
| `--prefix PATH : ...` | Hardcodes the dependency; can't be overridden without a rebuild. Use when the program must run exactly this tool |
| `--suffix PATH : ...` | Fallback that lets the user's `PATH` win. Use when a user-provided tool is acceptable |
| `--set` / `--set-default` | `--set` always applies; `--set-default` only when unset |
| `makeBinaryWrapper` | Compiled wrapper; usable as a shebang interpreter, which Darwin needs. Usually preferred. Doesn't support shell features such as `--run` |
| `makeWrapper` | Shell wrapper; use when you need shell expansion at run time |
| `--chdir DIR` | Use instead of `--run "cd DIR"`; works with both wrappers |
| `LD_LIBRARY_PATH` via `--prefix` | Last resort. It affects every child process the program starts; prefer `autoPatchelfHook`/RPATH. On Darwin the variable is `DYLD_LIBRARY_PATH` |

Don't wrap an already-wrapped program again; double wrapping overwrites the wrapper file. To wrap without rebuilding the original, use `symlinkJoin` plus `wrapProgram` in `postBuild`:

```nix
{
  foo-wrapped = symlinkJoin {
    name = "foo-wrapped";
    paths = [ foo ];
    nativeBuildInputs = [ makeWrapper ];
    postBuild = ''
      wrapProgram $out/bin/foo --prefix PATH : ${lib.makeBinPath [ jq ]}
    '';
  };
}
```

Prefer patching an absolute store path into the source over a wrapper when the path is known at build time (fewer layers, nothing for the user to see in `PATH`). Reviewers commonly ask you to remove wrappers that only add a path the program could have had patched in.

## Darwin

The Darwin `stdenv` already has Clang, an SDK, `libc++` from the system, and `xcrun`. Most packages need nothing extra. If a build fails, then:

- Hardcoded `gcc`/`g++`: pass `CC=cc`/`CXX=c++` via `makeFlags`, or patch the build script.
- Missing frameworks or APIs: add the right SDK to `buildInputs` (`apple-sdk_14`, `apple-sdk_15`, `apple-sdk_26`, ...). The default SDK is already included; the highest version among several wins. `stdenv.hostPlatform.darwinSdkVersion` and `darwinMinVersion` give the current defaults, as lower bounds.
- C++ API unavailable at the default deployment target: raise it with `(darwinMinVersionHook "13.3")` in `buildInputs` instead of switching to LLVM's `libc++`, which causes mixed-library problems.
- Availability-check errors: patch the source to use `__builtin_available`, or raise the deployment target. Only if the program genuinely handles it another way, add `-Wno-error=unguarded-availability` to `env.NIX_CFLAGS_COMPILE`.
- `xcrun` can't find a tool: add that tool to `nativeBuildInputs` (or `nativeCheckInputs`).
- A build requires `xcodebuild`: add `xcbuildHook`, and pass `xcbuildFlags`; if a scheme has spaces, set `__structuredAttrs = true`.
- Absolute `/usr/bin/xcrun`, `/usr/bin/xcodebuild`, or PlistBuddy paths: `substituteInPlace ... --replace-fail` them to bare command names.
- Library install names are wrong: fix with linker flags, with `install_name_tool` in `postFixup`, or with the `fixDarwinDylibNames` hook as a last resort.
- `iconv` and `libresolv` are in the SDK already; add `libiconv` to `nativeBuildInputs` only if you need the `iconv` binary.
- A `configure` script that detects libiconv but never links it: `env.NIX_LDFLAGS = "-liconv"` under `lib.optionalAttrs stdenv.hostPlatform.isDarwin` (the pattern used by the GNU `hello` package in nixpkgs).
- Don't propagate an SDK from a package unless it's a compiler or language; propagated SDKs become public API.

Cross-compiling works between Darwin systems only. SDK and deployment-target variables are role-prefixed: `DEVELOPER_DIR`, `MACOSX_DEPLOYMENT_TARGET`, and their `_FOR_BUILD` and `_FOR_TARGET` variants.

Test Darwin-guarded changes on Darwin or in CI before claiming they work.

## Bootstrap and `stdenv`-adjacent changes

Changing anything that every package depends on rebuilds those packages. Before you open the PR, measure the rebuild count rather than estimating it:

- Locally: `maintainers/scripts/rebuild-amount.sh HEAD^` (compares a commit against its parent) in a git-controlled nixpkgs tree.
- Full evaluation diff: `nix-build ci -A eval.baseline --out-link baseline` on the base commit, then `nix-build ci -A eval.full --arg baseline ./baseline` on yours; the report lands in `$out/step-summary.md`.
- CI assigns `rebuild` labels from the count on the PR itself.
- Keep a change that rebuilds many packages separate from unrelated work, so it can target `staging` alone.

Thresholds (`CONTRIBUTING.md`): about 500 or more rebuilds, consider `staging`; 1000 or more is a mass rebuild and goes to `staging`. Linux kernel changes go to `staging-nixos`. Branch routing is in [upstreaming-and-prs](upstreaming-and-prs.md).

Things that commonly move the count: edits under `pkgs/stdenv/`, to setup hooks, to `cc-wrapper`/`bintools-wrapper`, to fetchers, to a widely used library, or to a default build flag or hardening option.

Rules for code near the bootstrap:

- Don't add a dependency to anything in the early stdenv stages that is built after stdenv exists; you'll create a cycle or "infinite recursion".
- Reference `buildPackages`, not `targetPackages`, in anything that might be part of the bootstrap. Cycles in `buildPackages`-only graphs stay within one stage and show up in native builds too.
- Don't introduce a large new dependency into a core package without upstream backing.
- A change that fixes a bug without rebuilding the world sometimes uses an explicit `if` with `null` instead of `lib.optional`, with a follow-up PR to tidy it. CONTRIBUTING allows this exception.

## Checkable rules

- No `stdenv.isDarwin`, `stdenv.isLinux`, or other `stdenv.is*` attributes; use `stdenv.hostPlatform.is*` (or `buildPlatform` for build-time behavior).
- No `builtins.currentSystem` or `builtins.system` in package expressions.
- `meta.platforms` is set; `meta.broken`/`badPlatforms` conditions have a comment with the reason.
- `strictDeps = true` is present for new packages; `__structuredAttrs = true` for new top-level packages.
- Build tools are in `nativeBuildInputs`; libraries in `buildInputs`; test tools in `nativeCheckInputs`.
- `nativeBuildInputs` entries aren't written as `buildPackages.<x>` unless a cross-specific reason is commented.
- `doCheck` that runs host binaries is guarded by `stdenv.buildPlatform.canExecute stdenv.hostPlatform` (or `emulatorAvailable`).
- Conditional list entries use `lib.optional`/`lib.optionals`; conditional strings use `lib.optionalString`; conditional attrs use `lib.optionalAttrs`.
- `propagatedBuildInputs` entries are libraries consumers need at build time, not tools.
- Prebuilt ELF binaries use `autoPatchelfHook`, with `runtimeDependencies` for `dlopen`ed libraries; no hand-written `patchelf` or `LD_LIBRARY_PATH` workaround.
- `makeWrapper` appears in `nativeBuildInputs`; a wrapper isn't applied twice to the same file.
- `outputs` lists `out` first (or `bin` first), and its `dev`, `doc`, `man` entries match files the build produces.
- No `darwin.apple_sdk*` references.

## Evidence

From `find-rules.py --category build-closure-and-platforms`:

| Rule | support | cr |
|---|---|---|
| Avoid propagating dependencies unless consumers need them at runtime or build time | 118 | 28 |
| `autoPatchelfHook` instead of manual `patchelf` | 55 | 23 |
| Disable optional dependencies by default when heavy or test-only | 115 | 22 |
| Guard host-execution with `stdenv.buildPlatform.canExecute stdenv.hostPlatform` | 85 | 21 |
| Use `stdenv.hostPlatform`, not hardcoded strings or deprecated attributes | 52 | 14 |
| Test builds across architectures before merging | 224 | 7 |
| Use `disallowedReferences` to keep unintended references out of outputs | 14 | 2 |

## Dated advice to ignore

- `stdenv.isDarwin`, `stdenv.isLinux`, and the other `stdenv.is*` shortcuts: deprecated, warn on use. The corpus rule that names `stdenv.isDarwin` (46 PRs) predates this. `common-mistakes.md` in this skill also still shows the old form.
- "Use `buildInputs` for build-time tools" (inside a rule on propagation): backwards. Tools run during the build are `nativeBuildInputs`.
- `darwin.apple_sdk.frameworks.*`, `darwin.apple_sdk_11_0`, and `overrideSDK`: removed. The default SDK suffices; use `apple-sdk_NN` and `darwinMinVersionHook` for exceptions.
- Testing on `x86_64-darwin`: dropped for 26.11. Test on `x86_64-linux`, `aarch64-linux`, and `aarch64-darwin`.
- `xorg.libX11`-style attributes: the `xorg` package set is deprecated (2026-01-29). Use the top-level names (`libx11`, `libxext`, and so on).
- `autoPatchelfIgnoreMissingDeps = true`: use a list.
- "Prefix build tools with `buildPackages`" for `nativeBuildInputs`: splicing already selects the build-platform package; use `buildPackages` for tools referenced outside the dependency lists.
- "Prefer `badPlatforms` over `broken`" as a blanket rule: they differ. See the `meta` table.
