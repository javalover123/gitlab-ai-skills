# C / C++ — nixify playbook

**Default builder:** `stdenv.mkDerivation` with the build-system hook for the
project (CMake / Meson / Autotools) plus `pkg-config`.
**Why:** no transform tooling exists or is needed — C/C++ dependency management
*is* the system libraries, which come from nixpkgs. Each artifact is one small
derivation; multi-artifact systems are an overlay of many derivations (this is
also the build-system-replacement pattern — see
`references/worked-example-gitlab-toolchain.md`).

## Builder + build-system hooks

Adding a build tool to `nativeBuildInputs` injects its configure/build logic
automatically:

```nix
# CMake
{ stdenv, cmake, pkg-config, openssl, zlib }:
stdenv.mkDerivation {
  pname = "mytool"; version = "1.2.3"; src = ../..;
  nativeBuildInputs = [ cmake pkg-config ];
  buildInputs = [ openssl zlib ];
  # cmakeFlags = [ "-DBUILD_TESTING=ON" ];
}
```

```nix
# Meson
nativeBuildInputs = [ meson ninja pkg-config ];
# mesonFlags = [ "-Dfoo=enabled" ];
```

```nix
# Autotools (regenerate ./configure when needed)
nativeBuildInputs = [ autoreconfHook pkg-config ];
```

- `cmake` / `meson` / `qmake` hooks set sensible configure + build + install
  phases; `enableParallelBuilding` defaults on for them.
- `pkg-config` hook populates `PKG_CONFIG_PATH` so `find_package` / `pkg_check_modules` resolve nixpkgs libs.
- `autoreconfHook` runs `autoreconf` for Autotools projects.

## The two dependency axes

- `nativeBuildInputs` — build-time, available on `$PATH` (cmake, pkg-config,
  code generators, the compiler when cross-building).
- `buildInputs` — runtime/link dependencies (libssl, zlib, …).

Set `strictDeps = true;` to enforce the split (it's the default for the
go/rust/python builders). Getting this wrong is the most common C/C++ packaging
bug — a lib in the wrong list either won't be found at build time or will leak.

## Vendored / fetched C dependencies

- Pull a dependency source as an FOD and add it as an extra source or unpack it
  in `postUnpack`:

  ```nix
  src = fetchFromGitHub { owner = "…"; repo = "…"; rev = "…"; hash = "sha256-…"; };
  ```
- Prefer nixpkgs-provided libs over vendoring whenever the version is
  compatible.

## Cross-compilation & custom toolchains

- Cross-compile via `pkgsCross.<target>.callPackage ./package.nix {}`.
- Swap the compiler with `stdenv.override` / `overrideCC` / `wrapCCWith` (used
  when expressing a custom toolchain stage — e.g. a crosstool-ng-style glibc
  bootstrap reimagined as a custom `stdenv`).
- **Default to native (emulated) builds, not cross, for the shipped artifact.**
  Cross-compiled binaries are not guaranteed byte-identical to native ones, so
  if there's a reproducibility or parity requirement the *native* path
  (`localSystem = <target>`, QEMU-emulated on a foreign-arch builder) is the
  authoritative output; expose cross as an opt-in fast-iteration sibling. The
  full pattern (one ABI overlay → `nativePkgs` default + `crossPkgs` opt-in, how
  to wire outputs, and how to verify you didn't silently get cross) is in
  `references/native-vs-cross.md`.

## Multi-artifact build systems

When the repo builds *many* C/C++ artifacts in a dependency order (the
gitlab-toolchain shape), express each as `pkgs/<artifact>/package.nix` and
compose them in `overlays.default`. Nix's `stdenv` fixpoint resolves the order;
you delete the hand-written ordering file. Validate each with
`pkgs.testers.testVersion` and link-against-expected-lib assertions.

## Dev shell

```nix
mkShell {
  nativeBuildInputs = [ pkgs.cmake pkgs.ninja pkgs.pkg-config pkgs.clang-tools ];  # clangd, clang-format
  buildInputs = [ pkgs.openssl pkgs.zlib ];
}
```

`cmake -B build`, `ninja -C build`, `ctest` work unchanged. `clangd` finds
headers via the env that the shell sets up (export
`compile_commands.json` from CMake/Meson for full LSP).
