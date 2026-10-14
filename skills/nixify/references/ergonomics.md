# Developer ergonomics — keeping Nix out of the way

These patterns are what make Nix *invisible* in daily work. Stage 1 should add
all of them.

## nix-direnv — auto-load the dev shell

`.envrc`:

```bash
use flake
# reload when generated dep files change:
watch_file gemset.nix
watch_file gomod2nix.toml
```

`cd` into the repo → the dev shell loads automatically; `cd` out → it unloads.
The first `direnv allow` is an explicit, safe opt-in. nix-direnv caches the
built shell so re-entry is instant. The developer never types `nix develop`.

## Caching — never recompile dependencies twice

- **Cachix** (hosted): add `cachix/cachix-action` to CI; its daemon pushes
  every built path. Free tier covers open source: a 5 GB limit for open-source
  projects (plus 20 Cachix Deploy agents); entries are compressed (saving up to
  ~90% of storage) and LRU-evicted once full.
- **attic** (self-hosted, multi-tenant): for private/internal caches.
- Declare substituters in the flake so contributors get cache hits without
  config:

  ```nix
  nixConfig = {
    extra-substituters = [ "https://myproject.cachix.org" ];
    extra-trusted-public-keys = [ "myproject.cachix.org-1:…" ];
  };
  ```

With crane, push the `buildDepsOnly` derivation once → every CI run and dev
machine skips dependency compilation. FOD/dependency derivations cache
especially well because their hash is stable until deps change.

## treefmt-nix — one formatter for everything

```nix
# treefmt.nix
{ projectRootFile = "flake.nix";
  programs = { nixfmt.enable = true; rustfmt.enable = true; gofmt.enable = true;
               rufo.enable = true; prettier.enable = true; }; }
```

Expose it as `formatter.<system>` (so `nix fmt` works) and as a `checks` entry
(so CI fails on unformatted code). It wraps every per-language formatter behind
one `treefmt` command.

## git-hooks.nix — pre-commit hooks declared in Nix

`cachix/git-hooks.nix` (formerly pre-commit-hooks.nix) declares hooks in Nix and
installs the git hook on shell entry via `shellHook`. The same hooks run in `nix
flake check` (sandboxed), so local and CI enforcement match:

```nix
checks.pre-commit = git-hooks.lib.${system}.run {
  src = ./.;
  hooks = {
    treefmt.enable = true;     # reuse the treefmt config
    clippy.enable = true;      # or rubocop, golangci-lint, etc.
    nil.enable = true;         # nix LSP/lint
  };
};
# then in the dev shell:
devShells.default = pkgs.mkShell {
  inherit (checks.pre-commit) shellHook;
  buildInputs = checks.pre-commit.enabledPackages ++ [ /* toolchain */ ];
};
```

## Editor / LSP

The dev shell ships the language server (`rust-analyzer`, `gopls`, `clangd`,
`ruby-lsp`/`rubocop`, `pyright`) so editors using direnv pick them up
automatically. For Rust + rust-overlay, set
`RUST_SRC_PATH = "${rustToolchain}/lib/rustlib/src/rust/library";`. For C/C++,
export `compile_commands.json` from CMake/Meson for clangd.

## CI integration

The whole gate is two commands:

```bash
nix flake check     # builds packages + checks + VM tests + formatting + hooks
nix build .#<name>  # produce the artifact / image
```

Cache via Cachix/attic; pin via `flake.lock`. This is the entire CI surface —
no hand-rolled build scripts.

## The promise

Inside the shell, `cargo` / `go` / `bundle` / `uv` / `npm` / `pnpm` / `mise`
behave exactly as before. Nix governs toolchain *versions* and the *reproducible
build/CI path*. The developer's inner loop is untouched.
