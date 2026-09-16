# Build Environment Configuration Reference

Covers Linux kernel tuning, CI/CD setup, Docker builds with cargo-chef, and Nix-based reproducible builds.

---

## Linux Kernel Tuning

Large Rust builds can exhaust default kernel limits. If you see mysterious build failures or slowness:

```bash
# Default 65530 is too low for large Rust builds
sudo sysctl -w vm.max_map_count=262144
```

To make this permanent, add to `/etc/sysctl.d/rust-dev.conf`:
```
vm.max_map_count=262144
```

### tmpfs for target directories

On HDD or SATA systems, putting the target directory in RAM gives 10–30% faster builds:

```bash
sudo mount -t tmpfs -o size=8G tmpfs /path/to/project/target
```

**Risk**: target directories can grow 5–20 GB. Running out of RAM crashes the build. Set a conservative size limit and monitor usage.

---

## CI/CD

### GitHub Actions

GitHub Actions standard runners have 7 GB RAM and 2 vCPUs. Key setup:

```yaml
env:
  CARGO_INCREMENTAL: 0          # Disable incremental — faster clean builds in CI
  CARGO_PROFILE_TEST_DEBUG: 0   # No debug info for test builds

steps:
  - uses: actions/checkout@v4

  # Most impactful single optimization for CI
  - uses: Swatinem/rust-cache@v2

  - name: Build
    run: cargo build --locked

  - name: Test
    run: cargo nextest run --locked   # ~40% faster than cargo test
```

### GitLab CI

The same principles on GitLab CI — cache the registry and `target/` keyed on
`Cargo.lock`, disable incremental, and run tests with `--locked`:

```yaml
variables:
  CARGO_INCREMENTAL: "0"
  CARGO_HOME: "$CI_PROJECT_DIR/.cargo"

build-and-test:
  cache:
    key:
      files:
        - Cargo.lock
    paths:
      - .cargo/
      - target/
  script:
    - cargo build --locked
    - cargo nextest run --locked
```

**Caveat**: this cache key only changes when `Cargo.lock` changes, so the same
cache entry keeps accumulating artifacts across every commit in between —
and `target/` can grow 5–20 GB (see the tmpfs section above), so an
ever-growing cache eventually offsets or reverses the build-time win from
caching it at all. Clear the cache periodically, or use
[sccache](references/build-optimization.md#sccache-shared-compilation-cache)
or [cargo-chef](#docker-builds-with-cargo-chef) instead, neither of which has
this unbounded-growth problem.

### Memory-constrained runners

If you're hitting OOM on CI, add swap:

```yaml
- name: Add swap
  run: |
    sudo fallocate -l 8G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
```

### Minimizing cache invalidation

`Swatinem/rust-cache` keys the cache on `Cargo.lock`. To get maximum cache hits:

- Use `--locked` on cargo invocations (prevents Cargo.lock updates)
- Split slow jobs (e.g., build separately from test) so a test-only change doesn't rebuild everything
- Set `CARGO_INCREMENTAL=0` — incremental adds per-job overhead without benefit in clean CI environments

---

## Docker Builds with cargo-chef

Without caching, every Docker build recompiles all dependencies from scratch. `cargo-chef` enables Docker layer caching for Rust dependencies.

```dockerfile
FROM lukemathwalker/cargo-chef:latest-rust-1 AS chef
WORKDIR /app

# Phase 1: compute the recipe (dependency list only)
FROM chef AS planner
COPY . .
RUN cargo chef prepare --recipe-path recipe.json

# Phase 2: build just the dependencies (cached layer)
FROM chef AS builder
COPY --from=planner /app/recipe.json recipe.json
RUN cargo chef cook --release --recipe-path recipe.json

# Phase 3: build the application (only recompiles when src changes)
COPY . .
RUN cargo build --release --bin app

# Runtime image
FROM debian:trixie-slim AS runtime
COPY --from=builder /app/target/release/app /usr/local/bin
ENTRYPOINT ["/usr/local/bin/app"]
```

The key insight: the `cargo chef cook` layer is only invalidated when `Cargo.lock` or `Cargo.toml` files change, not when your source code changes. Real-world reports show ~5× faster Docker builds (~10 min → ~2 min for dependency-heavy projects).

---

## Nix-based Reproducible Builds

The `crane` library provides fully reproducible Rust builds with dependency caching:

```nix
{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    crane.url = "github:ipetkov/crane";
    rust-overlay.url = "github:oxalica/rust-overlay";
  };

  outputs = { self, nixpkgs, crane, rust-overlay, ... }:
    let
      pkgs = import nixpkgs { overlays = [ rust-overlay.overlays.default ]; };
      toolchain = pkgs.rust-bin.stable.latest.default;
      craneLib = (crane.mkLib pkgs).overrideToolchain toolchain;

      commonArgs = {
        src = craneLib.cleanCargoSource ./.;
        strictDeps = true;
      };

      # Build and cache dependencies separately
      cargoArtifacts = craneLib.buildDepsOnly commonArgs;

      # Build the actual application
      my-crate = craneLib.buildPackage (commonArgs // {
        inherit cargoArtifacts;
      });
    in {
      packages.default = my-crate;
    };
}
```

The `buildDepsOnly` step is cached by Nix's content-addressed store — it only rebuilds when `Cargo.lock` changes.

---

## Workspace Architecture

Workspaces sharing a single `target/` directory compile shared dependencies once. This gives 40–60% build time reduction for medium projects compared to separate crates with separate target dirs.

```toml
# Cargo.toml (workspace root)
[workspace]
resolver = "2"
members = [
    "crates/core",
    "crates/api-types",
    "crates/db",
    "crates/server",
    "crates/cli",
]
```

Prefer a diamond dependency shape (multiple crates depending on shared `core` and `api-types`) over a linear chain. Cargo can parallelize work on the "wide" parts of the diamond.

---

## rust-analyzer target dir

By default, rust-analyzer's on-save `cargo check` writes `.rmeta` files into the same `target/debug/` tree that your CLI `cargo build` populates with `.rlib` artifacts. Cargo tracks these as different unit kinds: they coexist but don't share. Every switch between editor and terminal kicks one side or the other into rebuilding.

**Fix: give rust-analyzer its own target dir.** The editor config is one line per editor; the underlying rust-analyzer setting is `cargo.targetDir`.

```elisp
;; .dir-locals.el (Emacs + eglot)
((nil . ((eglot-workspace-configuration
          . (:rust-analyzer (:cargo (:targetDir t)))))))
```

```json
// .vscode/settings.json (VS Code)
{
  "rust-analyzer.cargo.targetDir": true
}
```

`targetDir = true` resolves to `target/rust-analyzer/`, which gets picked up by `.gitignore`'s default `target/` rule. Disk cost is one extra dep lineage, same as you had before; the win is the editor no longer fights the terminal.

Verify it's working: `ls target/rust-analyzer/debug/deps/ | head` should show artifacts after the editor has run its first check. `target/debug/.fingerprint/` stops changing when you type in the editor.

---

## Toolchain pinning

`rustc`'s hash is part of every fingerprint in `target/`. If `rustup update` advances your `nightly` even by one day, every artifact invalidates and the next build is from scratch. Pin the channel at the project level so the whole team (and CI) compiles against the same rustc until someone deliberately bumps it.

```toml
# rust-toolchain.toml (project root)
[toolchain]
channel = "nightly-2026-01-19"
components = ["rust-src", "rustfmt", "clippy"]
profile = "minimal"
```

For Nix users, also pin inside the flake so the dev-shell toolchain matches:

```nix
rustToolchain = pkgs.rust-bin.nightly."2026-01-19".default.override {
  extensions = [ "rust-src" "rust-analyzer" "clippy" "rustfmt" ];
};
```

`pkgs.rust-bin.nightly.latest` drifts with the `nixpkgs` input; the dated form is immutable.

---

## Resources

- [Swatinem/rust-cache](https://github.com/Swatinem/rust-cache)
- [cargo-chef](https://github.com/LukeMathWalker/cargo-chef)
- [crane Nix library](https://crane.dev/)
- [rust-overlay](https://github.com/oxalica/rust-overlay)
- [GitHub Actions runner specs](https://docs.github.com/en/actions/using-github-hosted-runners/about-github-hosted-runners)
