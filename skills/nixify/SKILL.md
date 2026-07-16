---
name: nixify
description: "Analyze an existing codebase or a hand-rolled build system and generate maintainable, modular, ergonomic Nix build infrastructure for it — a thin flake.nix wiring up a lib/ + pkgs/ layout via callPackage, with scoped outputs, dev shells, nix2container images, and NixOS VM test checks — in a single reviewable MR that keeps the developer's native workflow (cargo, go, bundle, poetry/uv, npm/pnpm) working unchanged. Use when the user wants to Nixify, add a flake.nix, add reproducible or hermetic builds, set up nix develop / direnv, build containers or VM tests with Nix, or replace a Make/shell/Omnibus/Docker build system with Nix — even without saying Nix, if they describe reproducible builds, pinned toolchains, or a single-command dev environment for a Ruby, Go, Rust, Python, Node, or C/C++ project."
version: 0.1.0
license: MIT
category: Development Workflow
compatibility: opencode
metadata:
  audience: developers
  workflow: nix
---

# nixify

Generate ergonomic, maintainable Nix build infrastructure for an existing
project — or replace a hand-rolled build system with Nix — while keeping the
developer's native inner loop intact.

## Core philosophy

Six principles drive every decision; when in doubt, return to them.

- **Transform lockfiles, never hand-maintain dependency lists.** The developer
  keeps editing `Cargo.toml` / `go.mod` / `Gemfile` / `pyproject.toml` /
  `package.json` and running their normal package manager; Nix consumes the
  resulting lockfile. Nobody hand-edits a Nix dependency list.
- **The native dev loop is sacred.** Inside `nix develop` (auto-loaded by
  direnv), `cargo build`, `go test`, `bundle exec`, `pytest`, `npm run` behave
  exactly as before. Nix governs toolchain versions and the reproducible
  build/CI path, not the developer's daily commands.
- **`flake.nix` stays thin; real logic lives in `lib/` + `pkgs/`.** The flake
  only declares inputs, instantiates `pkgs`, maps over systems, and assigns
  outputs; every package is a `callPackage` function in `pkgs/<name>/package.nix`.
- **Default to plain flakes.** Reach for a framework (flake-parts) only when
  module composition earns its cost. See `references/flake-frameworks.md`.
- **One self-contained, reviewable MR.** Add Nix files; don't restructure the
  app's source or change how developers work.
- **Pin the toolchain, cache the rest, update in one command.** Lock versions via
  `flake.lock`, wire a binary cache (Cachix/attic), and always ship a
  single-command update path so a dependency bump never means hand-editing
  hashes. See `references/ergonomics.md` and `scripts/update-deps.sh`.

## Workflow

Always run Stage 0, then pick a track: an ordinary language build
(cargo/go/bundler/…) goes through Stages 1–2; a repo whose product *is* the
software it builds (Make/shell/Omnibus orchestrating many tools) goes to Stage 3.

### Stage 0 — Detect & plan (always)

Inventory the repo with `bash scripts/detect.sh /path/to/repo` — it reports
languages, lockfiles, the existing build system, entry points, and a first-guess
track. Then read the project's own `README`, `CONTRIBUTING`, `docs/`, and CI to
confirm its *purpose*. Write a short plan before generating anything: what the
project is and how it builds today, the proposed track, the builder per language
(cite the relevant `references/<lang>.md`), the file layout the MR adds, and any
human decisions (IFD tolerance, container target, consumer contract).

### Stage 1 — Dev shell first (lowest risk)

Get a working `nix develop` before packaging anything — pinned toolchains and a
one-command environment, the safest first MR. Scaffold the thin `flake.nix` and
`lib/eachSystem.nix` from `assets/templates/` (see
`references/flake-layout.md`); add a `devShells.default` with the project's
pinned native toolchain (per-language choices in `references/<lang>.md`); add
`.envrc` (`use flake`) for nix-direnv; wire `treefmt-nix` and `git-hooks.nix` as
`formatter` + a `checks` entry (`references/ergonomics.md`). **Done when**
`nix develop` works and the project's own build/test commands pass inside it,
unchanged.

### Stage 2 — Reproducible package + checks + container

Add `pkgs/<name>/package.nix` using the recommended builder — **pick it from the
per-language reference, don't guess:**

| Language | Default builder | Lockfile transform | Reference |
|---|---|---|---|
| Ruby | `bundlerEnv` / `bundlerApp` | bundix → committed `gemset.nix` | `references/ruby.md` |
| Go | `buildGoModule` + `vendorHash` | FOD hash (no codegen) | `references/go.md` |
| Rust | `crane` + oxalica `rust-overlay` | parses `Cargo.lock` | `references/rust.md` |
| Python | `uv2nix` (uv) / `poetry2nix` (Poetry) | parses lockfile | `references/python.md` |
| Node | `buildNpmPackage` (pnpm/yarn-berry for workspaces) | FOD hash | `references/nodejs.md` |
| C/C++ | `stdenv.mkDerivation` + cmake/meson hooks | vendored FODs | `references/c-cpp.md` |

Autoload `pkgs/` via `lib.packagesFromDirectoryRecursive`; add `checks` (at least
a `testers.testVersion`/smoke check plus one `runNixOSTest` VM test that boots
the artifact); expose `overlays.default`; add a container image as a scoped
output, defaulting to **nix2container** (`references/containers.md`,
`references/vm-tests.md`, `references/scoped-outputs.md`). **Done when**
`nix build` and `nix flake check` are green in CI with a binary cache configured.

### Stage 3 — Replace a hand-rolled build system

For repos whose product is the software they build. The decisive win: **Nix's
dependency graph replaces hand-ordered build chains**, and every component is
independently cached and rebuildable. Map each artifact to its own
`pkgs/<component>/package.nix`; compose components through an **overlay** so
ordering becomes the derivation graph; express any custom toolchain/bootstrap as
a custom `stdenv` or `crossSystem`; expose per-tool scoped outputs and
`overlays.default`; **preserve the existing consumer contract** (if consumers
fetch `URL + SHA256` tarballs, add a thin adapter emitting reproducible tarballs
and hashes so they don't change); validate each tool with `checks` and VM tests.
Worked designs: `references/worked-example-gitlab-toolchain.md` (build-system
replacement) and `references/worked-example-gkg-orbit.md` (application track).

## Cross-cutting defaults

Prefer vendor-hash or committed-codegen lockfile transforms over IFD; when using
IFD-based tooling (crane, poetry2nix, uv2nix), confirm CI tolerates the eval cost
(`references/transforms-and-ifd.md`). Always ship a one-command update path
(`scripts/update-deps.sh`). Dedupe inputs with
`inputs.<x>.inputs.nixpkgs.follows = "nixpkgs"`. Make native (QEMU-emulated) the
reproducible default and cross-compilation opt-in
(`references/native-vs-cross.md`). Never alter the app's native dev workflow or
source layout.

## References

Per-language playbooks: `references/ruby.md`, `references/go.md`,
`references/rust.md`, `references/python.md`, `references/nodejs.md`,
`references/c-cpp.md`. Cross-cutting:
[flake-layout](references/flake-layout.md),
[flake-frameworks](references/flake-frameworks.md),
[scoped-outputs](references/scoped-outputs.md),
[native-vs-cross](references/native-vs-cross.md),
[containers](references/containers.md), [vm-tests](references/vm-tests.md),
[transforms-and-ifd](references/transforms-and-ifd.md),
[ergonomics](references/ergonomics.md). Copy-paste starting points live in
`assets/templates/`; deterministic helpers in `scripts/`.
