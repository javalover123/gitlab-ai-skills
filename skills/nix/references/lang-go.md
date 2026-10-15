# Go

Load this when you package a Go module, set up a Go dev shell, or contribute a Go package to nixpkgs. Both halves
use the same builder, `buildGoModule`; what changes is the surrounding rules (toolchain pinning, test skipping,
comments, and where files go).

**Contents:** [Choosing the approach](#choosing-the-approach) · [In your own flake or project](#in-your-own-flake-or-project) · [In nixpkgs](#in-nixpkgs) · [Checkable rules](#checkable-rules) · [Evidence](#evidence) · [Dated advice to ignore](#dated-advice-to-ignore)

## Choosing the approach

| You're doing | Use | Builder / entry point |
|---|---|---|
| Your own app in a flake | `buildGoModule` with `vendorHash` | `pkgs.buildGoModule (finalAttrs: { ... })` |
| Your own flake with many Go packages sharing dependencies | gomod2nix | `buildGoApplication { modules = ./gomod2nix.toml; }` |
| A Go program for nixpkgs | `pkgs/by-name/<xx>/<name>/package.nix` | `buildGoModule (finalAttrs: { ... })` |
| A project that commits `vendor/` | same builder, `vendorHash = null;` | `buildGoModule` |
| A dev shell | `mkShell` with the toolchain and Go tools | `mkShell { packages = [ go gopls ... ]; }` |
| A package that breaks on newer toolchains (nixpkgs) | versioned builder plus a comment | `buildGo1xxModule` |

## In your own flake or project

**Default builder:** `buildGoModule` with `vendorHash`.
**Lockfile transform:** a fixed-output-derivation vendor hash (no codegen, no IFD, nothing extra committed beyond
the hash in the package file).
**Why:** zero extra flake inputs, pure eval, in-tree, and `go build` / `go test` stay completely normal.

### Builder

```nix
{ buildGoModule, lib }:
buildGoModule (finalAttrs: {
  pname = "myservice";
  version = "0.1.0";
  src = lib.cleanSource ../..;
  vendorHash = lib.fakeHash; # FOD hash of the fetched module set; replace after the first build
  # subPackages = [ "cmd/myservice" ];
  ldflags = [
    "-s"
    "-w"
    "-X main.version=${finalAttrs.version}"
  ];
  # tags = [ "netgo" ];
  meta.mainProgram = "myservice";
})
```

### Getting the `vendorHash`

`buildGoModule` fetches all modules into one FOD (`goModules`) and checks its hash. Two ways:

1. Set `vendorHash = lib.fakeHash;`, run `nix build`, copy the correct hash from the error.
   (`scripts/update-deps.sh` automates this.)
2. If the repo vendors deps in-tree, set `vendorHash = null;` to use the committed `vendor/` directory instead.
   That's for repositories that already have `vendor/`; `null` is not a way to make the build print a hash.

The hash changes when `go.mod` / `go.sum` change; re-derive it with the update script. This explicit bump is the
cost of the no-codegen, pure-eval approach, and it's CI-friendly precisely because there's no IFD. The builder also
applies `patches`, `postPatch`, `preBuild`, and `sourceRoot` when building `goModules`, so changing those can change
the hash. `goSum` (the contents of `go.sum`) forces a rebuild when the file changes.

### Why a hash and not pure resolution

Go resolves modules over the network or VCS, which the Nix evaluator can't do purely. So the choices are a
vendor-hash FOD (`buildGoModule`) or codegen (`gomod2nix`). For most projects the FOD is the right default.

### CGO, codegen, and edge cases

- **CGO:** `stdenv` already provides the C compiler. Add libraries to `buildInputs` and `pkg-config` to
  `nativeBuildInputs`. Control cgo with `env.CGO_ENABLED = 0;` or `= 1;`. Don't write `CGO_ENABLED = 1;` at the
  top level: `buildGoModule` sets it in `env` itself, and the overlap fails evaluation with "The `env` attribute set
  cannot contain any attributes passed to derivation" (checked against current nixpkgs). If module fetching misbehaves
  with CGO, or case-insensitive paths make the hash differ per platform, set `proxyVendor = true;`.
- **Code generators (for example `templ`, `mockgen`, `protoc-gen-go`):** run them in `preBuild` with the generator
  in `nativeBuildInputs`, so generated sources exist before `go build`.

`numtide/build-go-cache` pre-compiles imported modules to speed repeated `buildGoModule` runs in CI.

### When to use gomod2nix instead

`gomod2nix` is codegen: `gomod2nix generate` writes `gomod2nix.toml`, consumed by
`pkgs.buildGoApplication { modules = ./gomod2nix.toml; }`. It uses **symlink-based vendoring**, so identical
dependency trees are shared across packages, giving **better cache-hit rates and per-module granularity** than a
single vendor FOD. It disables CGO by default (static binaries).

```bash
nix flake init -t github:nix-community/gomod2nix#app
gomod2nix generate     # regenerate after go.mod changes (commit gomod2nix.toml)
```

**Choose gomod2nix when** you build many Go packages that share dependencies and the coarse single-FOD cache of
`buildGoModule` causes redundant recompiles. Otherwise prefer `buildGoModule`.

`go2nix` / `vgo2nix` are deprecated (pre-modules era); don't use them.

### Dev shell

```nix
{ mkShell, go, gopls, gotools, go-tools, delve }: # delve = Go debugger (dlv) <!-- voice-ok -->
mkShell { packages = [ go gopls gotools go-tools delve ]; } # <!-- voice-ok -->
```

`go build`, `go test ./...`, `go run`, `go mod tidy` all work unchanged inside the shell. The only Nix-facing step
is re-deriving `vendorHash` (or regenerating `gomod2nix.toml`) after a dependency change, automated by the update
script. To reuse a package's toolchain and inputs, add `inputsFrom = [ myservice ];`
([dev shells and ergonomics](dev-shells-and-ergonomics.md)).

## In nixpkgs

Verified against `doc/languages-frameworks/go.section.md`, `pkgs/build-support/go/module.nix` and its README.

### Template (`pkgs/by-name/ex/example/package.nix`)

```nix
{
  lib,
  buildGoModule,
  fetchFromGitHub,
  versionCheckHook,
}:

buildGoModule (finalAttrs: {
  pname = "example";
  version = "1.2.3";

  src = fetchFromGitHub {
    owner = "example";
    repo = "example";
    tag = "v${finalAttrs.version}";
    hash = lib.fakeHash;
  };

  vendorHash = lib.fakeHash;

  subPackages = [ "cmd/example" ];

  ldflags = [
    "-X main.version=${finalAttrs.version}"
  ];

  checkFlags =
    let
      skippedTests = [
        # needs network access
        "TestNetwork"
        # subtest (Go writes spaces in subtest names as "_")
        "TestDatabase/with_mysql"
      ];
    in
    [ "-skip=^${lib.concatStringsSep "$|^" skippedTests}$" ];

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

Replace both `lib.fakeHash` values after the builds report the real ones (`src` first, then `vendorHash`).
Unlike the Python builder, `buildGoModule` doesn't add an update script; use
`passthru.updateScript = nix-update-script { };` ([versioning and updates](versioning-and-updates.md)).

### Attribute rules

| Attribute | Rule |
|---|---|
| `vendorHash` | Required. `vendorSha256` throws ("Expect vendorHash"). Get it by setting `lib.fakeHash` (or `""`) and building. Use `null` only when the source tree commits `vendor/` or has no external dependencies. |
| `proxyVendor` | `true` when `go mod vendor` drops needed C sources, when dependencies have case-insensitive path conflicts (platform-dependent hashes), or when the module targets Go 1.16 or older. |
| `modRoot` | Directory with `go.mod` and `go.sum`, relative to `src` (default `"./"`). Use it when the module lives in a subdirectory of a larger repository. |
| `subPackages` | List of package paths to build (for example `[ "cmd/example" ]`). Without it, every child package builds, including test helpers and tools. Use `excludedPackages` to drop a few instead. |
| `ldflags` | A list of strings. Inject versions with `-X main.version=${finalAttrs.version}`. Don't reach for `buildFlagsArray` or `buildFlags` for Go flags. The builder already appends `-buildid=`, so don't set it. `-s -w` is a per-package choice. |
| `tags` | A list of build tags; `tags = [ "production" ] ++ lib.optionals withSqlite [ "sqlite" ];`. |
| `GOFLAGS` | A list argument (not `env`). The builder adds `-mod=vendor` (unless `proxyVendor`) and `-trimpath`; it warns if you set either yourself. Use `proxyVendor` for module-mode choices. |
| `env` | `env.CGO_ENABLED = 0;` for a static build; other Go variables such as `GOWORK` go here too, and the builder reads `env` when it builds `goModules`. Never set the same name at the top level. |
| `doCheck` / `checkFlags` | Tests run by default. Skip individual tests with `-skip=` regular expressions and comment each entry. `-run=` selects tests. `doCheck = false;` needs a comment saying why. |
| `checkInputs`, `preCheck` | Test dependencies and setup. Tool binaries needed only by tests go in `nativeCheckInputs`. |
| `modPostBuild`, `deleteVendor`, `overrideModAttrs` | Edit what `go mod vendor` produced, drop a broken committed `vendor/`, or override `goModules` hooks. Changing `modPostBuild` changes `vendorHash`. Overriding `goModules.overrideAttrs` directly is unsupported. |
| `allowGoReference` | Leave it `false`; `true` keeps references to the Go toolchain in the output. |
| `buildTestBinaries` | Builds `go test -c` binaries to run outside the sandbox. Mostly for downstream integration tests. |

Test-skipping details: `go test` accepts `-skip` and `-run` regexes. Join names with `$|^` inside `^...$` as in the
template so each name matches exactly. A subtest is `Parent/child_name`.

### Toolchain choice

- `buildGoModule` follows the default `go`. Use it unless you can show a toolchain problem.
- `buildGo1xxModule` (and `go_1_xx`) pins a version. nixpkgs policy: use it only for packages that depend on
  toolchain internals, and add a comment explaining why so the Go team can find it later. Pinned builders are
  removed when their Go version reaches end of life, and pinned packages move to the oldest remaining builder.
- `go_latest` / `buildGoLatestModule` is for tools that must be compiled with at least the Go version they
  analyze (language servers and linters). Use it only with a comment justifying it; its bumps go to `master`,
  and keeping the user count low avoids mass rebuilds.
- Use the builder directly as an argument. Don't override `buildGoModule` in `all-packages.nix`.
- Check names against `pkgs/top-level/all-packages.nix`; the available versions move with each Go release.
- On a stable release branch the default `go` and `go_latest` stay put, so version bumps there are backports.

### Cross-compilation and installs

`strictDeps = true` is the builder default, so `nativeBuildInputs` / `buildInputs` must be correct. Guard
post-install code that runs the built binary (shell completions are the usual case) with
`lib.optionalString (stdenv.buildPlatform.canExecute stdenv.hostPlatform) ''...''`. See
[native versus cross](native-vs-cross.md).

## Checkable rules

- A Go module uses `buildGoModule` (the `buildGoPackage` builder was removed in 25.05); new code uses `finalAttrs`, not `rec`.
- `vendorHash` is set (no `vendorSha256`); `null` appears only when the source has a committed `vendor/` directory or no dependencies.
- `ldflags` is a list; version strings use `${finalAttrs.version}`, not literals.
- `GOFLAGS` doesn't include `-mod=` or `-trimpath`; `-buildid=` isn't in `ldflags`.
- No attribute appears both in `env` and at the top level (`CGO_ENABLED` is the usual offender).
- Every entry in a `-skip=` list or `disabled` list has a comment explaining why; `doCheck = false;` has a comment.
- `subPackages` is set when the repository has more than one `main` package or helper tools.
- `buildGo1xxModule` and `buildGoLatestModule` carry a comment justifying the choice.
- `src` uses `tag = "v${finalAttrs.version}"` (or the upstream tag format) with `hash =`.
- Post-install steps that execute the binary are guarded for cross builds.
- `meta.mainProgram` is set for programs ([meta and licensing](meta-and-licensing.md)).

## Evidence

Counts from `find-rules.py --category language-ecosystems`:

| Rule | support / cr |
|---|---|
| `buildGoModule` with the `finalAttrs` pattern | 28 / 9 and 14 / 10 (two phrasings) |
| `buildGoModule` as the standard builder, with `vendorHash` | 9 / 6 |
| Prefer `buildGoModule` over `buildGoPackage` | 15 / 4 |
| Use `ldflags` to inject versions rather than hard-coding them (category `nix-language-style`) | 30 / 9 |
| `ldflags` as a list attribute, not `buildFlagsArray` | 7 / 3 |

## Dated advice to ignore

- `buildGoPackage`, `goPackagePath`, `goDeps`, `vendorSha256`: removed or throwing; use `buildGoModule` and `vendorHash`.
- "Set `vendorHash = null` first so the build reports the right hash": `null` means "use the committed `vendor/` directory". Use `lib.fakeHash`.
- `buildFlagsArray` / `buildFlags` for Go linker flags: use `ldflags` and `tags` lists.
- Top-level `CGO_ENABLED = 0;`: use `env.CGO_ENABLED`.
- `buildGoModule rec { ... ${version} ... }`: use the `finalAttrs` form so `overrideAttrs` can change the version.
- `-s -w` as a required rule: it's common but optional; stdenv already strips binaries.
