# Rust

Load this when you package a Rust crate, set up a Rust dev shell, or contribute a Rust program to nixpkgs.
The two halves use different tools: crane plus a community toolchain in your own flake, `rustPlatform.buildRustPackage`
with the toolchain nixpkgs ships when you contribute.

**Contents:** [Choosing the approach](#choosing-the-approach) · [In your own flake or project](#in-your-own-flake-or-project) · [In nixpkgs](#in-nixpkgs) · [Checkable rules](#checkable-rules) · [Evidence](#evidence) · [Dated advice to ignore](#dated-advice-to-ignore)

## Choosing the approach

| You're doing | Use | Builder / entry point |
|---|---|---|
| Your own app in a flake, with CI caching | crane + oxalica `rust-overlay` | `craneLib.buildDepsOnly` then `craneLib.buildPackage` |
| Your own small app, no toolchain pinning | nixpkgs builder in your flake | `rustPlatform.buildRustPackage` with `cargoLock.lockFile = ./Cargo.lock` |
| A Rust program for nixpkgs | `pkgs/by-name/<xx>/<name>/package.nix` | `rustPlatform.buildRustPackage (finalAttrs: { ... })` with `cargoHash` |
| A non-Rust package that embeds Rust code | `rustPlatform.fetchCargoVendor` + hooks | `cargoDeps`, `cargoSetupHook`, `cargoBuildHook`; Python wheels use `maturinBuildHook` |
| A dev shell | `mkShell` with a toolchain, rust-analyzer, cargo tools | `rustToolchain` from `rust-overlay` (flake) or `rustc` / `cargo` (nixpkgs) |
| Nightly or a pinned compiler version | rust-overlay or fenix, flake-side only | `makeRustPlatform { cargo; rustc; }` for derivations |

## In your own flake or project

**Default builder:** `crane`.
**Toolchain:** oxalica `rust-overlay`, reading `rust-toolchain.toml`.
**Lockfile transform:** crane reads `Cargo.lock` at eval time and splits a cached dependencies-only derivation
from the source build ([transforms and IFD](transforms-and-ifd.md) covers the eval-cost trade-off).
**Why:** incremental, cached CI builds; clippy, test and coverage become composable derivations; no codegen file
to maintain. This is the converged 2025-26 stack (rust-overlay + crane + flake-parts + nix-direnv).

### Toolchain (oxalica rust-overlay)

```nix
{
  # in flake.nix inputs
  inputs.rust-overlay.url = "github:oxalica/rust-overlay";

  # when instantiating pkgs (inside outputs):
  #   pkgs = import nixpkgs { inherit system; overlays = [ rust-overlay.overlays.default ]; };
  #   rustToolchain = pkgs.rust-bin.fromRustupToolchainFile ./rust-toolchain.toml;
}
```

`rust-overlay` has every published toolchain version in-tree (pin stable, nightly, or a specific date; it respects
`rust-toolchain.toml` components and targets). **fenix** is the alternative (smaller repo, ships nightly
rust-analyzer and a nix-community cachix), but pinning older versions needs workarounds or IFD. The nixpkgs
manual says either project is preferable to Mozilla's nixpkgs-mozilla overlay. devenv migrated from fenix to
rust-overlay citing maintenance. nixpkgs-native `rustc` / `cargo` carry a single compiler version (see the
nixpkgs half below): fine for simple apps, but no pinning and no nightly.

### Builder (crane)

```nix
{ craneLib, lib, pkgs, rustToolchain }:
let
  crane = craneLib.overrideToolchain rustToolchain;
  src = crane.cleanCargoSource ../..;
  commonArgs = {
    inherit src;
    strictDeps = true;
    buildInputs = [ /* e.g. pkgs.openssl */ ];
    nativeBuildInputs = [ pkgs.pkg-config ];
  };
  cargoArtifacts = crane.buildDepsOnly commonArgs; # cached dependency layer
in
crane.buildPackage (commonArgs // { inherit cargoArtifacts; })
```

`buildDepsOnly` compiles only the dependencies into a separate derivation. Push it to the binary cache once, and
every later CI run and dev machine skips recompiling dependencies. Build clippy, test and audit as sibling
derivations sharing `cargoArtifacts`:

```nix
{
  checks = {
    clippy = crane.cargoClippy (commonArgs // { inherit cargoArtifacts; cargoClippyExtraArgs = "--all-targets -- --deny warnings"; });
    test   = crane.cargoTest   (commonArgs // { inherit cargoArtifacts; });
    fmt    = crane.cargoFmt { inherit src; };
  };
}
```

### Workspaces

crane is workspace-aware. Build a single member with `cargoExtraArgs = "-p <crate>"`, or build the whole workspace
and select binaries. For a workspace that embeds generated assets (for example a frontend `dist/`), produce the
asset derivation first and feed it via `preBuild` or an extra source; see
[worked example: gkg-orbit](worked-example-gkg-orbit.md).

### Alternatives (when not crane)

| Tool | Granularity | Codegen | Use when |
|---|---|---|---|
| `buildRustPackage` (`rustPlatform`) | one dep derivation | `cargoHash` FOD, or `importCargoLock` (per-crate FODs, no hash for registry crates) | trivial apps, or contributing to nixpkgs (use `cargoHash` there) |
| `naersk` | deps-once + project | none | simple projects wanting minimal config |
| `cargo2nix` | per-crate | `Cargo.nix` (committed) | need per-crate cache granularity |
| `crate2nix` | per-crate | committed | devenv's default backend |

Per-crate codegen (cargo2nix, crate2nix) gives the finest cache but adds a generated file to keep in sync; prefer
crane unless you specifically need per-crate parallelism. `importCargoLock` reads the lockfile at eval time, which
becomes IFD if `lockFile` points into a fetched source instead of a path in your own repository.

### Dev shell

```nix
{ mkShell, pkgs, rustToolchain }:
mkShell {
  packages = [ rustToolchain pkgs.rust-analyzer pkgs.cargo-nextest pkgs.cargo-watch ];
  RUST_SRC_PATH = "${rustToolchain}/lib/rustlib/src/rust/library"; # for rust-analyzer
}
```

`cargo build`, `cargo test`, `cargo clippy`, `cargo nextest run` all work unchanged. crane reads `Cargo.lock`
directly, so updating dependencies is just `cargo update`; there's no Nix file to regenerate (the trade-off is
eval cost, see [transforms and IFD](transforms-and-ifd.md)). `RUST_SRC_PATH` as written needs the `rust-src`
component in `rust-toolchain.toml`.

## In nixpkgs

Verified against `doc/languages-frameworks/rust.section.md`, `pkgs/build-support/rust/` (including the hooks), and
the by-name tree.

### Template (`pkgs/by-name/ex/example/package.nix`)

```nix
{
  lib,
  rustPlatform,
  fetchFromGitHub,
  pkg-config,
  protobuf,
  openssl,
  versionCheckHook,
}:

rustPlatform.buildRustPackage (finalAttrs: {
  pname = "example";
  version = "1.2.3";

  src = fetchFromGitHub {
    owner = "example";
    repo = "example";
    tag = "v${finalAttrs.version}";
    hash = lib.fakeHash;
  };

  cargoHash = lib.fakeHash;

  nativeBuildInputs = [
    pkg-config
    protobuf
  ];

  buildInputs = [ openssl ];

  # build the CLI crate from a workspace
  cargoBuildFlags = [
    "--package"
    "example-cli"
  ];

  buildNoDefaultFeatures = true;
  buildFeatures = [ "tls" ];

  env.OPENSSL_NO_VENDOR = 1;

  checkFlags = [
    # needs network access
    "--skip=net::tests::connects"
  ];

  nativeInstallCheckInputs = [ versionCheckHook ];
  doInstallCheck = true;

  meta = {
    description = "Short, concrete description of what it does";
    homepage = "https://github.com/example/example";
    changelog = "https://github.com/example/example/releases/tag/v${finalAttrs.version}";
    license = lib.licenses.mit;
    mainProgram = "example";
    maintainers = with lib.maintainers; [ ];
  };
})
```

Replace both `lib.fakeHash` values after the builds report the real ones (`src` first, then `cargoHash`;
`cargoHash = "";` also triggers the hash report).

### Dependencies: `cargoHash`, `cargoLock`, `fetchCargoVendor`

| Situation | Do |
|---|---|
| Upstream commits `Cargo.lock` (the usual case) | `cargoHash = "sha256-...";`. Since 25.05 this runs `rustPlatform.fetchCargoVendor` under the hood. |
| `Cargo.lock` has git dependencies | Still `cargoHash`: `fetchCargoVendor` fetches `git+` sources itself, so no per-crate `outputHashes` are needed. |
| Upstream has no `Cargo.lock` or it's stale | Patch one into the source with `cargoPatches = [ ./add-Cargo.lock.patch ];`. Patches run before vendoring, so `cargoHash` still works. Ask upstream to commit it. |
| Hash changes with every `version` bump but dependencies don't | `cargoDepsName = finalAttrs.pname;` makes the hash independent of `version`. |
| Lock file lives in a subdirectory | `cargoRoot` / `sourceRoot` (for `buildRustPackage`), or `sourceRoot` in `fetchCargoVendor`. |
| You must copy the lock file into nixpkgs | `cargoLock = { lockFile = ./Cargo.lock; };` (plus `outputHashes` for git deps). Rare: 43 by-name files, against about 2,800 using `cargoHash`. `cargoLock` can't see patches to `Cargo.lock` made in `postPatch`; use `cargoLock.lockFileContents` for that. |
| A non-Rust package that embeds Rust | `cargoDeps = rustPlatform.fetchCargoVendor { inherit (finalAttrs) src; hash = "..."; };` plus `rustPlatform.cargoSetupHook` (and `cargoBuildHook`, `cargoInstallHook` as needed). `importCargoLock` is the hash-free alternative when a lock file is available. |
| The project already vendors crates | `cargoVendorDir`. |

`cargoSha256` is gone: since 25.05 `buildRustPackage` ignores it and then fails with "cargoHash, cargoVendorDir,
cargoDeps, or cargoLock must be set". `useFetchCargoVendor` is no longer optional; leaving it in warns, and setting
it to `false` throws. Remove it. `fetchCargoTarball` isn't in the tree anymore.

### Build, features, tests

| Attribute | Notes |
|---|---|
| `cargoBuildFlags` | Extra `cargo build` args, for example `[ "--package" "foo" ]` or `[ "--bin" "foo" ]`. |
| `buildAndTestSubdir` | Build a crate that isn't the root workspace, such as one inside a larger tarball. Output still lands in the top-level `target/`. |
| `buildNoDefaultFeatures`, `buildFeatures` | Feature selection for build (and check, unless `checkNoDefaultFeatures` / `checkFeatures` differ). |
| `buildType` | `"release"` by default; `"debug"` is possible and also changes the check mode. |
| `cargoTestFlags` | Arguments to `cargo test` itself (`--package foo`). |
| `checkFlags` | Arguments to the test binary, after `--`: `--skip=path::to::test`, `--exact`. Comment every skip. |
| `checkType = "debug"` | Compiles twice (release for build, debug for tests); use only when release-mode tests fail. |
| `useNextest = true` | Runs `cargo nextest`; flags may need adjusting. |
| `dontUseCargoParallelTests` | Serial tests. |
| `doCheck = false` | Valid when no tests exist or tests are highly impure, with a comment. A partial skip list is preferred. |
| `cargoPatches` | Patches that also apply before vendoring. Use `patches` for source-only patches. |
| `auditable` | On by default (`cargo-auditable`), so binaries embed their dependency list. Leave it unless it breaks the build. |

Tests that assume the `target/release` layout fail because the hooks build with `--target`, so artifacts are in
`target/<triple>/release/`; patch the tests. For packages with a Makefile or Meson, override `buildPhase`,
`installPhase` and `checkPhase` (the manual's recommendation). Meson projects (many GNOME apps) use
`fetchCargoVendor` plus `cargoSetupHook` and leave the build to Meson.

### System libraries, build scripts, and flags

- `pkg-config`, `protobuf`, `cmake`, `installShellFiles` go in `nativeBuildInputs`; libraries to link (`openssl`,
  `zlib`, `sqlite`) go in `buildInputs`. `strictDeps` is on by default for `buildRustPackage`.
- `env.OPENSSL_NO_VENDOR = 1;` stops `openssl-sys` from compiling its bundled copy; it's one of the most common
  `env` lines in the tree. Equivalent switches exist for other `-sys` crates (check their build scripts).
- Build scripts that look for `protoc` by variable need `env.PROTOC = lib.getExe buildPackages.protobuf;` so cross
  builds pick the build-platform binary; most packages just put `protobuf` in `nativeBuildInputs`.
- Crates using `bindgen` need `rustPlatform.bindgenHook` in `nativeBuildInputs`; it points `bindgen` at `libclang` and
  the libraries in `buildInputs`.
- `RUSTFLAGS`: set it as `env.RUSTFLAGS = "--cfg tokio_unstable";` (a top-level `RUSTFLAGS` is also accepted and
  moved into `env`). A set `RUSTFLAGS` replaces the `rustflags` from the project's `.cargo/config.toml`
  (MEASURED with cargo 1.95: with a config `[build] rustflags = ["--cfg", "from_config"]`, a build with
  `RUSTFLAGS="--cfg from_env"` saw only `from_env`). If upstream relies on config-file flags, repeat them in
  `RUSTFLAGS`.
- `fetchCrate` fetches from crates.io and reviewers sometimes ask for it when the crate is published there (support
  9 in the corpus); the repository tag is the alternative when you need files the published crate omits (tests,
  for example).
- Nightly-only features: the manual calls `RUSTC_BOOTSTRAP = true;` (in `env`) a hack that sometimes works. Don't
  reach for rust-overlay or fenix; their IFD is disallowed in nixpkgs.

### Toolchain selection

nixpkgs ships one Rust compiler at a time (`rust` points at a single `rust_1_xx`; check `all-packages.nix`), and
`rustPlatform.buildRustPackage` uses its `rustc` and `cargo`. If a crate needs a newer compiler than nixpkgs has,
wait for the compiler bump; nixpkgs has no per-package compiler pin. `rust-overlay`, `fenix` and `crane` are flake-side tools: `makeRustPlatform { cargo = ...; rustc = ...; }`
builds with a custom toolchain in your own expressions, and the manual shows it for rust-overlay nightlies. Those
tools need IFD or extra inputs, so none are allowed in nixpkgs.

## Checkable rules

- A Rust program uses `rustPlatform.buildRustPackage` (or `buildRustCrate`/hooks for non-Rust packages), with the `finalAttrs` form for new code.
- `cargoHash`, `cargoLock`, `cargoDeps`, or `cargoVendorDir` is set; `cargoSha256` and `useFetchCargoVendor` are absent.
- A `cargoHash` is used for git dependencies instead of `cargoLock.outputHashes`, unless the package has a reason to ship a lock file.
- `cargoHash` isn't `lib.fakeHash` or an empty string in a committed change.
- `cargoBuildFlags`, `cargoTestFlags`, `buildFeatures`, `buildNoDefaultFeatures` are lists of strings.
- Every `--skip=` entry in `checkFlags` has a comment; `doCheck = false;` has a comment.
- `pkg-config`, `protobuf`, `cmake` are in `nativeBuildInputs`; linked libraries are in `buildInputs`.
- `RUSTFLAGS` appears in `env` (or as the accepted top-level form) and doesn't silently drop required `.cargo/config.toml` flags.
- `rustPlatform.bindgenHook` is present when a dependency uses `bindgen`.
- Nixpkgs code doesn't import rust-overlay, fenix, or crane, and doesn't read the lockfile with IFD.
- `src` uses a tag and `hash =`; `meta.mainProgram` is set for programs.
- The commit title is `example: 1.0.0 -> 1.1.0` ([upstreaming and PRs](upstreaming-and-prs.md)).

## Evidence

Counts from `find-rules.py --category language-ecosystems`:

| Rule | support / cr |
|---|---|
| `cargoHash` instead of `cargoSha256` | 41 / 15 |
| Keep the hash in sync with `Cargo.lock` and regenerate it when dependencies change | 25 / 6 |
| `nix-update-script` for updating `cargoHash` | 8 / 5 |
| `fetchCargoVendor` instead of manual vendoring | 15 / 4 |
| `buildRustPackage` with standard patterns instead of manual setup | 10 / 5 |
| `cargoPatches` for patching Rust packages | 20 / 3 (category `patches-and-overrides`) |

## Dated advice to ignore

- `cargoSha256`: removed in 25.05; use `cargoHash`.
- `useFetchCargoVendor = true;` and the old `fetchCargoTarball`: the vendor fetcher is the only path now.
- "For git dependencies, use `cargoLock.outputHashes` instead of `cargoHash`" (a high-support review rule): `fetchCargoVendor` handles git sources, and `cargoHash` is the norm.
- "Commit the `Cargo.lock` into nixpkgs and reference it via `cargoLock.lockFile`": the manual treats that as the fallback when `cargoHash` doesn't work; start with `cargoHash` and `cargoPatches`.
- "Prefer `fetchCrate` for any crate on crates.io": a reviewer preference, not a documented rule; the manual's own examples use both.
- Reaching for rust-overlay, fenix or crane in nixpkgs: not allowed there (IFD); they belong in flakes.
