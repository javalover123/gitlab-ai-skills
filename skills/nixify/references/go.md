# Go — nixify playbook

**Default builder:** `buildGoModule` with `vendorHash`.
**Lockfile transform:** a fixed-output-derivation vendor hash (no codegen, no
IFD, nothing extra committed beyond the hash in the package file).
**Why:** zero extra flake inputs, pure eval, in-tree, and `go build` / `go test`
stay completely normal.

## Builder

```nix
{ buildGoModule, lib }:
buildGoModule {
  pname = "myservice";
  version = "0.1.0";
  src = ../..;                      # or lib.cleanSource ../..
  vendorHash = "sha256-AAAA…";      # FOD hash of the fetched module set
  # subPackages = [ "cmd/myservice" ];
  ldflags = [ "-s" "-w" "-X main.version=0.1.0" ];
  # tags = [ "netgo" ];
  meta.mainProgram = "myservice";
}
```

### Getting the `vendorHash`

`buildGoModule` fetches all modules into one FOD and checks its hash. Two ways:

1. Set `vendorHash = lib.fakeHash;`, run `nix build`, copy the correct hash from
   the error. (`scripts/update-deps.sh` automates this.)
2. If the repo vendors deps in-tree, set `vendorHash = null;` to use the
   committed `vendor/` directory instead.

The hash changes when `go.mod`/`go.sum` change — re-derive it via the update
script. This explicit bump is the cost of the no-codegen, pure-eval approach;
it's CI-friendly precisely because there's no IFD.

### Why a hash and not pure resolution

Go resolves modules over the network/VCS, which the Nix evaluator can't do
purely. So the choices are a vendor-hash FOD (`buildGoModule`) or codegen
(`gomod2nix`). For most projects the FOD is the right default.

## CGO, codegen, and edge cases

- **CGO:** add the C toolchain to `nativeBuildInputs` and any libs to
  `buildInputs`; set `CGO_ENABLED = 1`. If module fetching misbehaves with CGO
  or case-insensitive paths, set `proxyVendor = true;` (fetches via the module
  proxy rather than vendoring).
- **Code generators (e.g. `templ`, `mockgen`, `protoc-gen-go`):** run them in
  `preBuild` with the generator added to `nativeBuildInputs`, so generated
  sources exist before `go build`.
- **Build cache:** `numtide/build-go-cache` pre-compiles imported modules to
  speed repeated `buildGoModule` runs in CI.

## When to use gomod2nix instead

`gomod2nix` is codegen: `gomod2nix generate` writes `gomod2nix.toml`, consumed
by `pkgs.buildGoApplication { modules = ./gomod2nix.toml; }`. It uses
**symlink-based vendoring**, so identical dependency trees are shared across
packages — giving **better cache-hit rates and per-module granularity** than a
single vendor FOD. It disables CGO by default (static binaries).

```bash
nix flake init -t github:nix-community/gomod2nix#app
gomod2nix generate     # regenerate after go.mod changes (commit gomod2nix.toml)
```

**Choose gomod2nix when** you build many Go packages that share dependencies and
the coarse single-FOD cache of `buildGoModule` causes redundant recompiles.
Otherwise prefer `buildGoModule`.

`go2nix` / `vgo2nix` are deprecated (pre-modules era) — do not use.

## Dev shell

```nix
{ mkShell, go, gopls, gotools, go-tools, delve }: # delve = Go debugger (dlv) <!-- voice-ok -->
mkShell { packages = [ go gopls gotools go-tools delve ]; } # <!-- voice-ok -->
```

`go build`, `go test ./...`, `go run`, `go mod tidy` all work unchanged inside
the shell. The only Nix-facing step is re-deriving `vendorHash` (or
regenerating `gomod2nix.toml`) after a dependency change — automated by the
update script.
