# Rust — nixify playbook

**Default builder:** `crane`.
**Toolchain:** oxalica `rust-overlay`, reading `rust-toolchain.toml`.
**Lockfile transform:** crane parses `Cargo.lock` (IFD-ish) and splits a cached
dependencies-only derivation from the source build.
**Why:** incremental, cached CI builds; clippy/test/coverage become composable
derivations; no codegen file to maintain. This is the converged 2025–26 stack
(rust-overlay + crane + flake-parts + nix-direnv).

## Toolchain (oxalica rust-overlay)

```nix
# in flake.nix inputs
inputs.rust-overlay.url = "github:oxalica/rust-overlay";

# when instantiating pkgs
pkgs = import nixpkgs { inherit system; overlays = [ rust-overlay.overlays.default ]; };
rustToolchain = pkgs.rust-bin.fromRustupToolchainFile ./rust-toolchain.toml;
```

`rust-overlay` has every published toolchain version in-tree (pin stable,
nightly, or a specific date; respects `rust-toolchain.toml` components and
targets). **fenix** is the alternative (smaller repo, ships nightly
rust-analyzer + a nix-community cachix), but pinning older versions needs
workarounds/IFD; devenv migrated fenix→rust-overlay (PR #1500) citing
maintenance. nixpkgs-native `rustc`/`cargo` track only latest stable — fine for
trivial apps, no pinning/nightly.

## Builder (crane)

```nix
{ craneLib, lib, pkgs, rustToolchain }:
let
  crane = craneLib.overrideToolchain rustToolchain;
  src = crane.cleanCargoSource ../..;
  commonArgs = { inherit src; strictDeps = true; buildInputs = [ /* e.g. pkgs.openssl */ ]; nativeBuildInputs = [ pkgs.pkg-config ]; };
  cargoArtifacts = crane.buildDepsOnly commonArgs;   # cached dependency layer
in
crane.buildPackage (commonArgs // { inherit cargoArtifacts; })
```

`buildDepsOnly` compiles only the dependencies into a separate derivation. Push
it to the binary cache once, and every later CI run and dev machine skips
recompiling dependencies. Build clippy/test/audit as sibling derivations sharing
`cargoArtifacts`:

```nix
checks = {
  clippy = crane.cargoClippy (commonArgs // { inherit cargoArtifacts; cargoClippyExtraArgs = "--all-targets -- --deny warnings"; });
  test   = crane.cargoTest   (commonArgs // { inherit cargoArtifacts; });
  fmt    = crane.cargoFmt { inherit src; };
};
```

## Workspaces

crane is workspace-aware. Build a single member with `cargoExtraArgs = "-p
<crate>"`, or build the whole workspace and select binaries. For a workspace
that embeds generated assets (e.g. a frontend `dist/`), produce the asset
derivation first and feed it via `preBuild`/an extra source — see
`references/worked-example-gkg-orbit.md`.

## Alternatives (when not crane)

| Tool | Granularity | Codegen | Use when |
|---|---|---|---|
| `buildRustPackage` (`rustPlatform`) | one dep derivation | `cargoHash` FOD, or `importCargoLock` (IFD) | trivial apps, or contributing to nixpkgs (IFD disallowed there — use `cargoHash`) |
| `naersk` | deps-once + project | none | simple projects wanting minimal config |
| `cargo2nix` | per-crate | `Cargo.nix` (committed) | need per-crate cache granularity |
| `crate2nix` | per-crate | committed | devenv's default backend |

Per-crate codegen (cargo2nix/crate2nix) gives the finest cache but adds a
generated file to keep in sync; prefer crane unless you specifically need
per-crate parallelism.

## Dev shell

```nix
{ mkShell, pkgs, rustToolchain }:
mkShell {
  packages = [ rustToolchain pkgs.rust-analyzer pkgs.cargo-nextest pkgs.cargo-watch ];
  RUST_SRC_PATH = "${rustToolchain}/lib/rustlib/src/rust/library";  # for rust-analyzer
}
```

`cargo build`, `cargo test`, `cargo clippy`, `cargo nextest run` all work
unchanged. crane reads `Cargo.lock` directly, so updating dependencies is just
`cargo update` — no Nix file to regenerate (the tradeoff is IFD eval cost; see
`references/transforms-and-ifd.md`).
