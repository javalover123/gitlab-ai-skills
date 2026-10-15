# C / C++

Load this when you package a C or C++ project with `stdenv.mkDerivation`, in your own flake or in nixpkgs. C and C++ have no language-specific builder: the build-system hook in `nativeBuildInputs` (CMake, Meson, Autotools) does the work, and dependencies are system libraries from nixpkgs. Each artifact is one small derivation, and a multi-artifact system is an overlay of many derivations (the same shape as the build-system-replacement pattern in [worked-example-gitlab-toolchain.md](worked-example-gitlab-toolchain.md)).

**Contents:** [Choosing the approach](#choosing-the-approach) · [In your own flake or project](#in-your-own-flake-or-project) · [In nixpkgs](#in-nixpkgs) · [Dated advice to ignore](#dated-advice-to-ignore)

## Choosing the approach

| Project uses | Hooks in `nativeBuildInputs` | Flags | Notes |
|---|---|---|---|
| CMake | `cmake`, `pkg-config`, optionally `ninja` | `cmakeFlags` with `lib.cmakeBool` / `lib.cmakeFeature` | With `ninja` present the CMake hook picks the Ninja generator. `ctestCheckHook` for finer test control. |
| Meson | `meson`, `ninja`, `pkg-config` | `mesonFlags` with `lib.mesonBool` / `lib.mesonEnable` / `lib.mesonOption` | `mesonAutoFeatures` defaults to `enabled`, so "auto" features turn on unless you disable them. |
| Autotools with a shipped `configure` | `pkg-config` | `configureFlags` with `lib.enableFeature` / `lib.withFeature` | Default configure and make phases are enough. |
| Autotools without `configure`, or you patch `configure.ac` | `autoreconfHook`, `pkg-config` | same | The hook adds `autoreconfPhase`. |
| Plain Makefile | none | `makeFlags`, `installFlags`; `dontConfigure = true;` | Set `PREFIX=$(out)` or similar through `makeFlags`. |
| Qt | `qt6.wrapQtAppsHook` plus the build system's hook | as above | See wrappers below. |

## In your own flake or project

### Builder and build-system hooks

Adding a build tool to `nativeBuildInputs` injects its configure, build, and install logic:

```nix
# CMake
{ stdenv, cmake, pkg-config, openssl, zlib }:
stdenv.mkDerivation {
  pname = "mytool";
  version = "1.2.3";
  src = ../..;
  nativeBuildInputs = [ cmake pkg-config ];
  buildInputs = [ openssl zlib ];
  # cmakeFlags = [ "-DBUILD_TESTING=ON" ];
}
```

```nix
# Meson
{ stdenv, meson, ninja, pkg-config }:
stdenv.mkDerivation {
  pname = "mytool";
  version = "1.2.3";
  src = ../..;
  nativeBuildInputs = [ meson ninja pkg-config ];
  # mesonFlags = [ "-Dfoo=enabled" ];
}
```

```nix
# Autotools (regenerate ./configure when needed)
{ stdenv, autoreconfHook, pkg-config }:
stdenv.mkDerivation {
  pname = "mytool";
  version = "1.2.3";
  src = ../..;
  nativeBuildInputs = [ autoreconfHook pkg-config ];
}
```

- The `cmake`, `meson`, and `qmake` hooks set sensible configure, build, and install phases, and the manual says build systems with good parallel support (cmake, meson, qmake) set `enableParallelBuilding` to `true` unless you set it to `false`.
- The `pkg-config` hook adds `lib/pkgconfig` and `share/pkgconfig` of each build input to `PKG_CONFIG_PATH`, so `pkg_check_modules` resolves nixpkgs libraries. The `cmake` hook adds dependencies to `CMAKE_PREFIX_PATH`, which is what `find_package` uses.
- `autoreconfHook` runs `autoreconf`, `libtoolize`, and `automake`.
- The `ninja` hook swaps the build, install, and check phases to Ninja (`dontUseNinjaBuild` and friends turn that off); when the Meson hook is also present, Meson's install and check phases win.

### The two dependency axes

- `nativeBuildInputs`: build-time tools available on `$PATH` (cmake, pkg-config, code generators).
- `buildInputs`: libraries you link against at runtime (libssl, zlib, ...).

Set `strictDeps = true;` to enforce the split. The manual lists dlang, emacs, go, nim, ocaml, python, rust, and tcl builders as enabling it by default; `stdenv.mkDerivation` doesn't unless `config.strictDepsByDefault` is on or you're cross-compiling. A wrong placement is the most common C and C++ packaging bug: a tool in `buildInputs` fails under cross-compilation, and a library in `nativeBuildInputs` is the wrong architecture there.

### Vendored or fetched C dependencies

Pull a dependency source as a fixed-output derivation and add it as an extra source or unpack it in `postUnpack`:

```nix
{ fetchFromGitHub }:
{
  src = fetchFromGitHub {
    owner = "example";
    repo = "example";
    rev = "0000000000000000000000000000000000000000";
    hash = "sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=";
  };
}
```

Prefer nixpkgs-provided libraries over vendoring whenever the version is compatible.

### Cross-compilation and custom toolchains

- Cross-compile with `pkgsCross.<target>.callPackage ./package.nix {}`, and swap the compiler with `stdenv.override`, `overrideCC`, or `wrapCCWith` (a crosstool-ng-style glibc bootstrap becomes a custom `stdenv`).
- Default to native (emulated) builds for the shipped artifact. Cross-compiled binaries aren't guaranteed byte-identical to native ones, so when reproducibility or parity matters, the native path (`localSystem = <target>`, QEMU-emulated on a foreign-architecture builder) is the authoritative output and cross is an opt-in sibling for fast iteration. The pattern (one ABI overlay, `nativePkgs` as default, `crossPkgs` opt-in, and how to verify you didn't silently get cross) is in [native-vs-cross.md](native-vs-cross.md).

### Multi-artifact build systems

When the repo builds many artifacts in dependency order (the gitlab-toolchain shape), express each as `pkgs/<artifact>/package.nix` and compose them in `overlays.default`. The `stdenv` fixpoint resolves the order, so you delete the hand-written ordering file. Validate each with `pkgs.testers.testVersion` and link-against-expected-library assertions.

### Dev shell

```nix
{ mkShell, cmake, ninja, pkg-config, clang-tools, openssl, zlib }:
mkShell {
  nativeBuildInputs = [ cmake ninja pkg-config clang-tools ]; # clangd, clang-format
  buildInputs = [ openssl zlib ];
}
```

`cmake -B build`, `ninja -C build`, and `ctest` work unchanged. `clangd` finds headers through the environment the shell sets up; export `compile_commands.json` from CMake or Meson for full LSP support.

## In nixpkgs

New top-level packages go in `pkgs/by-name/<xx>/<name>/package.nix`. Reviewers commonly ask for `pkg-config` in `nativeBuildInputs` (support 34, 12 with formal changes-requested) and `autoreconfHook` over hand-listed autotools packages (support 29, 6), and for `strictDeps = true` (support 122, 33).

### Package shapes

```nix
{
  lib,
  stdenv,
  fetchFromGitHub,
  cmake,
  pkg-config,
  zlib,
  openssl,
  versionCheckHook,
}:

stdenv.mkDerivation (finalAttrs: {
  pname = "example";
  version = "1.2.3";

  src = fetchFromGitHub {
    owner = "example";
    repo = "example";
    tag = "v${finalAttrs.version}";
    hash = "sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=";
  };

  strictDeps = true;
  __structuredAttrs = true;

  nativeBuildInputs = [
    cmake
    pkg-config
  ];

  buildInputs = [
    openssl
    zlib
  ];

  cmakeFlags = [
    (lib.cmakeBool "BUILD_SHARED_LIBS" (!stdenv.hostPlatform.isStatic))
    (lib.cmakeBool "BUILD_TESTING" finalAttrs.doCheck)
    (lib.cmakeFeature "CMAKE_CXX_STANDARD" "17")
  ];

  doCheck = true;

  nativeInstallCheckInputs = [ versionCheckHook ];
  doInstallCheck = true;

  meta = {
    description = "Short description without the package name";
    homepage = "https://example.org";
    license = lib.licenses.mit;
    maintainers = with lib.maintainers; [ ];
    mainProgram = "example";
    platforms = lib.platforms.unix;
  };
})
```

The manual says all new top-level packages must enable `__structuredAttrs`. With it on, attributes meant as environment variables must live in `env`, so write `env.NIX_CFLAGS_COMPILE = "...";`, not a bare attribute. Meson and Autotools swap only the hook and flags:

```nix
{ lib, stdenv, meson, ninja, pkg-config, withGtk ? true }:
stdenv.mkDerivation (finalAttrs: {
  pname = "example";
  version = "1.2.3";
  src = ./.;
  nativeBuildInputs = [ meson ninja pkg-config ];
  mesonFlags = [
    (lib.mesonBool "tests" finalAttrs.doCheck)
    (lib.mesonEnable "gtk" withGtk)
    (lib.mesonOption "backend" "gl")
  ];
})
```

```nix
{ lib, stdenv, autoreconfHook, pkg-config, withSsl ? true }:
stdenv.mkDerivation {
  pname = "example";
  version = "1.2.3";
  src = ./.;
  nativeBuildInputs = [ autoreconfHook pkg-config ];
  configureFlags = [
    (lib.enableFeature true "shared")
    (lib.withFeature withSsl "ssl")
  ];
}
```

### Flag helpers (verified in `lib/strings.nix`, re-exported on `lib`)

| Helper | Result |
|---|---|
| `lib.cmakeBool "BUILD_TESTING" true` | `-DBUILD_TESTING:BOOL=TRUE` |
| `lib.cmakeFeature "CMAKE_CXX_STANDARD" "17"` | `-DCMAKE_CXX_STANDARD:STRING=17` |
| `lib.cmakeOptionType "path" "FOO_DIR" "/x"` | `-DFOO_DIR:PATH=/x` (types: bool, filepath, path, string, internal, list) |
| `lib.mesonBool "docs" false` | `-Ddocs=false` |
| `lib.mesonEnable "gtk" true` | `-Dgtk=enabled` (`disabled` for false) |
| `lib.mesonOption "backend" "gl"` | `-Dbackend=gl` |
| `lib.enableFeature true "shared"` | `--enable-shared` |
| `lib.withFeature false "ssl"` | `--without-ssl` |
| `lib.withFeatureAs true "ssl" "x"` | `--with-ssl=x` |

Use them in place of hand-typed `"-DFOO=ON"` strings: they check types, avoid `ON`/`TRUE` drift, and make boolean options visible to `override`. The helper arguments must be strings, so pass `"openssl"`, not the package. Reviewers commonly request them (support 16, 3 with formal changes-requested). Typical idioms in the tree: `lib.cmakeBool "BUILD_SHARED_LIBS" (!stdenv.hostPlatform.isStatic)`, and `lib.cmakeFeature "CMAKE_POLICY_VERSION_MINIMUM" "3.5"` when a project's `cmake_minimum_required` is too old for CMake 4.

### Rules and arguments that trip people up

- `strictDeps = true;` on every new package. If it exposes a missing tool, fix the dependency lists rather than turning it off. Under `strictDeps`, `pkg-config`, `cmake`, `meson`, `ninja`, and code generators go in `nativeBuildInputs`; the libraries you link go in `buildInputs`. Build-time tools in `buildInputs` is the usual mistake (the opposite of "use `buildInputs` for build tools", which you may read in old guidance).
- `enableParallelBuilding` is already on for cmake, meson, and qmake. For plain Makefile projects set `enableParallelBuilding = true;` yourself once the build survives `-j`; override per phase with `enableParallelChecking` and `enableParallelInstalling`.
- `dontUseCmakeConfigure = true;` when a project needs CMake as a tool but drives its own configure (support 13, 2). `dontUseMesonConfigure` and `dontUseNinjaBuild` do the same for their hooks. `cmakeBuildType` defaults to `Release`, `mesonBuildType` to `plain`, and `mesonWrapMode` to `nodownload`, so Meson subprojects must come from nixpkgs or be pre-populated.
- Compiler flags: `env.NIX_CFLAGS_COMPILE = "-Wno-error=incompatible-pointer-types";` (or `toString [ ... ]` for several), never an exported shell variable in a phase. The cc wrapper already puts every dependency's `include` directory into `NIX_CFLAGS_COMPILE` and `lib` directories into `NIX_LDFLAGS`, so you rarely add `-I` or `-L` by hand. If hardening breaks the build, name the flag you disable: `hardeningDisable = [ "format" ];`. Keep `"all"` for a last resort.
- Avoid `LD_LIBRARY_PATH`. The linker wrapper adds an `RPATH` entry for each library you actually link, so ordinary dependencies need nothing. For libraries loaded with `dlopen`, either patch the path in with `substituteInPlace` and `${lib.getLib foo}/lib/...`, or for prebuilt ELF binaries use `autoPatchelfHook` with `runtimeDependencies` (reviewers prefer `patchelf` and `autoPatchelfHook` over environment variables, support 22, 5). When a program really needs the variable at runtime, put it in a wrapper, not the environment.
- Multiple outputs: libraries usually split into `out` and `dev` through `outputs = [ "out" "dev" ];`, and the framework moves headers and `.pc` files by itself. Downstream packages get the `dev` output as a build input automatically. Reference other outputs with `lib.getDev`, `lib.getLib`, and `lib.getBin` instead of `${foo}/include`. Add `validatePkgConfig` to `nativeBuildInputs` to catch `.pc` files with undefined variables (library packages in the tree do this).
- Static versus shared: nixpkgs builds shared libraries unless there's a specific technical reason (reviewers commonly say so, support 19). The `pkgsStatic` set and `stdenv.hostPlatform.isStatic` cover static targets; `dontDisableStatic` is set automatically there. Reviewers also ask that static linking go through standardized mechanisms such as `Requires.private` in the `.pc` file.
- Wrappers: `makeBinaryWrapper` makes a small compiled wrapper that can act as a shebang interpreter (needed on Darwin) and is the manual's usual choice; `makeWrapper` writes a shell script and is for shell expansion. Both provide `wrapProgram`. GTK apps use `wrapGAppsHook3` or `wrapGAppsHook4` in `nativeBuildInputs`. Qt apps put `qt6.wrapQtAppsHook` (or the matching `libsForQt5` one) in `nativeBuildInputs`, set `qtWrapperArgs` for extra paths, and wrap non-ELF scripts by hand with `wrapQtApp`. Wrappers run during `fixupPhase`; to customize, set `dontWrapGApps = true;` or `dontWrapQtApps = true;` and call `wrapProgram` (or `wrapQtApp`) yourself in `preFixup`, or append to `gappsWrapperArgs` and `qtWrapperArgs`.
- Tests: `doCheck = true;` runs `make check`, `ninja test`, or `meson test` by default. Add `ctestCheckHook` to `nativeCheckInputs` to pass `ctestFlags` or `disabledTests` to `ctest`. `checkInputs` are libraries linked into tests; `nativeCheckInputs` are tools on `$PATH`. Install-time checks use `doInstallCheck = true;` with `nativeInstallCheckInputs = [ versionCheckHook ];` (support 51, 16); cross-compiled builds never run them.
- `separateDebugInfo = true;` produces a `debug` output on Linux when you need symbols.

### Checkable rules

- `strictDeps = true` and `__structuredAttrs = true` are set on new top-level C and C++ packages.
- Build tools (`cmake`, `meson`, `ninja`, `pkg-config`, `autoreconfHook`, `makeWrapper`) appear only in `nativeBuildInputs`.
- No hand-written `"-D...=ON"` for options that have a `lib.cmakeBool`, `lib.cmakeFeature`, or `lib.mesonBool` form, and no string-typed booleans in `mesonFlags`.
- No `LD_LIBRARY_PATH` assignment in `postInstall` or `preFixup`.
- Compiler flags go through `env.NIX_CFLAGS_COMPILE`, not a bare attribute or `export`.
- `enableParallelBuilding` isn't set to `false` without a comment explaining the race.
- Environment-style variables are in `env` when `__structuredAttrs` is on.
- `doInstallCheck` or `doCheck` is enabled, or a comment says why tests can't run in the sandbox.

### Evidence

| Rule | support | cr |
|---|---|---|
| `strictDeps = true` to separate build-time and runtime dependencies | 122 | 33 |
| `pkg-config` in `nativeBuildInputs` | 34 | 12 |
| `autoreconfHook` in `nativeBuildInputs` | 29 | 6 |
| Prefer `patchelf` or `autoPatchelfHook` over `LD_LIBRARY_PATH` | 22 | 5 |
| Use `lib.cmakeBool` and friends for build-system options | 16 | 3 |
| `dontUseCmakeConfigure = true` to let another hook configure | 13 | 2 |

## Dated advice to ignore

- "Use `buildInputs` for build tools" (seen in the build-closure synthesis): backwards. Build-time tools go in `nativeBuildInputs`.
- `stdenv.isDarwin` and `stdenv.isLinux`: deprecated aliases that warn (`stdenv.<name> is deprecated, use stdenv.hostPlatform.<name>`); write `stdenv.hostPlatform.isDarwin`.
- "Use Qt's `mkDerivation` from the package set instead of adding `wrapQtAppsHook` yourself": the current manual tells every Qt package to put `wrapQtAppsHook` in `nativeBuildInputs` (or set `dontWrapQtApps`).
- `-DFOO=ON` flag strings, `"-Dfoo=enabled"` literals: still valid CMake and Meson, but nixpkgs reviewers expect the `lib.*` helpers above.
