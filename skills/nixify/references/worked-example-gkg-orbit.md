# Worked example — GKG / Orbit (Nixify an application project)

The **application-project** case: a Rust workspace plus a Node frontend compiled
into a single binary. Use it as the mental model for Stages 1–2 when a project
mixes a compiled backend with a built frontend.

> **Provenance caveat.** GKG/Orbit is partly internal and fast-moving (GKG is in
> maintenance mode; Orbit is under active development; EE-licensed). The build
> *shape* below is publicly documented, but **detect the actual shape from
> `Cargo.toml` / `package.json` at runtime** rather than hard-coding, and flag
> internal-only assumptions in the plan.

## What it is

**GitLab Knowledge Graph (gkg)** — "structured, queryable representations of
code repositories to power AI features." Original repo
`gitlab-org/rust/knowledge-graph` (now maintenance mode); successor
**`gitlab-org/orbit/knowledge-graph`** ("Orbit"), under active development.

Orbit is "a single Rust binary backed by ClickHouse (Remote) or DuckDB (Local),
driven by a YAML ontology," serving HTTP/gRPC with MCP + REST layers. Product
name "Orbit"; engineering name still "GKG" (binary `gkg-server`, `GKG_*`
config). Parses 11+ languages via `gitlab-code-parser`; clients connect over MCP
(the `gitlab.com/api/v4/orbit` surface). EE license.

## Build shape (public)

- A **Rust workspace** — crates such as `crates/http-server-desktop`,
  `crates/database`, `crates/indexer`, `crates/gkg-server`.
- A **Node frontend workspace** — `packages/frontend`, `packages/docs`.
- The `http-server-desktop` crate **embeds the frontend `dist/` into the final
  `gkg` binary** (unless built with `--features no-frontend`).
- TS bindings are generated from Rust via `ts-rs` and **committed** (no IFD
  needed for them).
- Tasks run through **`mise`** (`mise build`, `mise test:fast`, `mise lint:code`
  = clippy-as-errors). Local install via a `curl … install.sh | bash`; server
  listens on `localhost:27495`.

## How nixify handles it

This is a two-stage build: **frontend → `dist/`**, then **Rust build that embeds
`dist/`**.

1. **Frontend (`references/nodejs.md`).** Build `packages/frontend` with
   `buildNpmPackage` (or the pnpm hook, per its lockfile) to produce a `dist/`
   derivation.

   ```nix
   # pkgs/gkg-frontend/package.nix
   { buildNpmPackage }:
   buildNpmPackage {
     pname = "gkg-frontend"; version = "0.1.0";
     src = ../../packages/frontend;
     npmDepsHash = "sha256-…";
     installPhase = "cp -r dist $out";
   }
   ```

2. **Rust binary (`references/rust.md`).** Build with **crane** + oxalica
   **rust-overlay** (reading `rust-toolchain.toml`), feeding the frontend
   derivation in so the binary embeds it — mirroring the existing two-stage
   build:

   ```nix
   # pkgs/gkg/package.nix
   { craneLib, rustToolchain, gkg-frontend, pkg-config, openssl, lib }:
   let crane = craneLib.overrideToolchain rustToolchain;
       src = crane.cleanCargoSource ../..;
       commonArgs = {
         inherit src; strictDeps = true;
         nativeBuildInputs = [ pkg-config ];
         buildInputs = [ openssl ];
         # place built frontend where http-server-desktop expects it:
         preBuild = "cp -r ${gkg-frontend} crates/http-server-desktop/dist";
       };
       cargoArtifacts = crane.buildDepsOnly commonArgs;
   in crane.buildPackage (commonArgs // {
     inherit cargoArtifacts;
     cargoExtraArgs = "-p gkg-server";   # or the bin crate that embeds dist
   });
   ```

3. **Outputs.** `packages.<system>.gkg` (full binary with frontend) and
   `packages.<system>.gkg-server`; a container via **nix2container**
   (`references/containers.md`). `ts-rs` bindings are committed → no IFD there.

4. **Dev shell (`references/ergonomics.md`).** Keep `cargo`, `mise`, `node`/
   `pnpm`, `clippy`, `rust-analyzer`, `duckdb` available so developers keep
   running `mise build` / `cargo` / `pnpm` unchanged; nix-direnv auto-loads.

   ```nix
   devShells.default = pkgs.mkShell {
     packages = [ rustToolchain pkgs.rust-analyzer pkgs.mise pkgs.nodejs pkgs.pnpm pkgs.duckdb pkgs.pkg-config ];
     buildInputs = [ pkgs.openssl ];
   };
   ```

5. **Checks (`references/vm-tests.md`).** crane clippy + tests as derivations,
   plus a `runNixOSTest` that boots `gkg-server`, hits `:27495`, and asserts a
   healthy response. **DuckDB local mode needs no external service**, so the VM
   check is self-contained — ideal.

   ```nix
   testScript = ''
     server.wait_for_unit("gkg-server.service")
     server.wait_for_open_port(27495)
     server.succeed("curl -sf http://localhost:27495/health")
   '';
   ```

## Why this shape generalizes

"Compiled backend that embeds a built frontend into one artifact" is extremely
common (Go + embed.FS, Rust + include_dir, etc.). The reusable trick is:
**build the frontend as its own derivation, then inject it via `preBuild`/source
into the backend build** so the single-artifact output is reproduced exactly,
with each half cached independently.
