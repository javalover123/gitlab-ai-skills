# Nixify an existing project

Load this when the user wants Nix build infrastructure added to a project that already exists: a `flake.nix`, a dev shell, a reproducible build, a container image, VM tests, or a replacement for a Make, shell, Omnibus or Docker build system. It's the staged workflow that keeps the developer's native commands working. If the user hasn't asked for Nix specifically, read [choosing a track](choosing-a-track.md) first.

The workflow comes from the `nixify` skill. Its content is kept; the corrections in [Dated advice to ignore](#dated-advice-to-ignore) were checked against the current nixpkgs tree, upstream READMEs and Nix 2.34.8, and the snippets below were evaluated or built against nixpkgs master.

If `scripts/detect.sh` reports a `flake.nix`, `shell.nix` or `default.nix` that already exists, stop before writing anything. Ask the user (question tool) whether to extend it, replace it, or leave it alone. A request to "add Nix" doesn't mean "convert my existing Nix".

**Contents:** [Core principles](#core-principles) · [Workflow](#workflow) · [Cross-cutting defaults](#cross-cutting-defaults) · [Constraints from review](#constraints-from-review) · [Checkable rules](#checkable-rules) · [Evidence](#evidence) · [Dated advice to ignore](#dated-advice-to-ignore)

## Core principles

Six rules drive every decision below. When a choice is unclear, return to them.

1. **Transform lockfiles; never hand-maintain dependency lists.** The developer keeps editing `Cargo.toml`, `go.mod`, `Gemfile`, `pyproject.toml` or `package.json` and running the normal package manager. Nix consumes the resulting lockfile (`Cargo.lock`, `go.sum`, `Gemfile.lock`, `uv.lock` or `poetry.lock`, `package-lock.json`). Nobody edits a Nix list of dependencies by hand.
2. **The native dev loop is sacred.** Inside `nix develop` (loaded by direnv), `cargo build`, `go test`, `bundle exec`, `pytest`, `npm run` and `mise build` behave as before. Nix governs toolchain versions and the reproducible build and CI path, not daily commands.
3. **`flake.nix` stays thin.** It declares inputs, instantiates `pkgs`, maps over systems and assigns outputs from `pkgs/` and `lib/`. Every package is a `callPackage` function in `pkgs/<name>/package.nix`. See [flake layout](flake-layout.md).
4. **Default to a plain flake.** Reach for flake-parts or another framework only when module composition earns its learning cost. See [flake frameworks](flake-frameworks.md).
5. **One self-contained, reviewable change.** Add Nix files. Don't restructure the app's source or change how developers work. A reviewer should be able to read the whole change and understand it.
6. **Pin the toolchain, cache the rest, update in one command.** `flake.lock` pins versions, a binary cache stops dependency compilation from repeating, and `scripts/update-deps.sh` is the single update path. See [dev shells and ergonomics](dev-shells-and-ergonomics.md).

## Workflow

```
Stage 0: detect and plan          (always)
   |
   +-- project has a normal language build (cargo, go, bundler, ...)
   |       -> Stage 1 -> Stage 2   ("application project" track)
   |
   +-- project IS a hand-rolled build system (Make, shell, Omnibus, multi-tool)
           -> Stage 3             ("replace a build system" track)
```

### Stage 0: detect and plan

Run the detector from the skill directory, then read the project's own README, CONTRIBUTING, `docs/`, CI config and build scripts. File types tell you the language; the docs tell you what the project is for.

```bash
bash scripts/detect.sh /path/to/repo
```

It lists the languages and lockfiles it finds, the existing build system (Make, shell, Omnibus, Docker, mise, Bazel, existing Nix files), entry points, and a first-guess track. Its report names the matching `references/lang-<lang>.md` files. Treat the output as a start, not a verdict.

State a short plan, then generate the files in the same turn. Stop and ask only when the plan holds a decision you can't default (the last item below). The plan covers:

- what the project is and how it builds today,
- the track (application or build-system replacement) and why,
- the builder for each language, with the reference you used,
- the files the change will add,
- any Nix files already in the repo and what you'll do with them,
- decisions you need from a human: whether CI tolerates import-from-derivation, which container target, whether a downstream consumer contract must stay as it is.

**Which track?** If the repo's product is software it builds (Makefiles or shell that orchestrate many tools, Omnibus software definitions, a staged Docker pipeline that compiles a toolchain), it's a build-system replacement: Stage 3. Otherwise it's an application project: Stages 1 and 2.

### Stage 1: dev shell first

Get `nix develop` working before you package anything. It pins the toolchain and gives a one-command environment, and it's the lowest-risk first change.

1. Scaffold the thin `flake.nix`, `lib/eachSystem.nix`, and `shells/default.nix` from `assets/templates/`.
2. Add `devShells.default` with the project's native toolchain, pinned. Per-language toolchain notes are in the `lang-*.md` files (for Rust, oxalica `rust-overlay` reading `rust-toolchain.toml`). Use `mkShell` when anything compiles C, links through `cc` or builds native extensions; `mkShellNoCC` otherwise. See [choosing a track](choosing-a-track.md#mkshell-or-mkshellnocc).
3. Add `.envrc` with `use flake` so nix-direnv loads the shell. Put any `watch_file` lines before `use flake`; nix-direnv's README says they only take effect when invoked first, and it already tracks `flake.nix`, `flake.lock` and `.envrc`.
4. Add treefmt-nix for formatting and git-hooks.nix for hooks, wired as `formatter` plus a `checks` entry. See [dev shells and ergonomics](dev-shells-and-ergonomics.md) and [gates and tooling](gates-and-tooling.md).

A minimal `shells/default.nix` for the `devShells.default` wiring shown in Stage 2 (the real one lists the project's toolchain and language server):

```nix
# shells/default.nix
{ mkShellNoCC, jq }:
mkShellNoCC {
  packages = [ jq ];
}
```

Done when `nix develop` works and the project's own build and test commands pass inside it, unchanged.

### Stage 2: reproducible package, checks, container

Add the reproducible build, validation, and optionally an image, each as a scoped output.

**Pick the builder from the language reference. Don't guess.**

| Language | Default builder | Lockfile transform | Reference |
|---|---|---|---|
| Ruby | `bundlerEnv` or `bundlerApp` | bundix writes a committed `gemset.nix` | [lang-ruby.md](lang-ruby.md) |
| Go | `buildGoModule` with `vendorHash` | fixed-output hash, no codegen | [lang-go.md](lang-go.md) |
| Rust | crane with oxalica `rust-overlay` | reads `Cargo.lock` at eval time | [lang-rust.md](lang-rust.md) |
| Python | uv2nix for uv projects; Poetry projects need a decision (poetry2nix is unmaintained) | reads `uv.lock` or `poetry.lock` at eval time | [lang-python.md](lang-python.md) |
| Node | `buildNpmPackage`; `fetchPnpmDeps` with `pnpmConfigHook` for pnpm; yarn has its own hooks | fixed-output hash | [lang-nodejs.md](lang-nodejs.md) |
| C and C++ | `stdenv.mkDerivation` with cmake, meson or pkg-config hooks | vendored sources as fixed-output fetches | [lang-c-cpp.md](lang-c-cpp.md) |

Other ecosystems are routed in [lang-other-ecosystems.md](lang-other-ecosystems.md).

The wiring below is a single-file form of the `assets/templates/flake.nix` wiring. It was evaluated with `nix flake check` and the packages built, including a dependency between two packages resolved through the overlay.

```nix
{
  description = "Example project";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs =
    { self, nixpkgs, ... }:
    let
      inherit (nixpkgs) lib;

      systems = [
        "x86_64-linux"
        "aarch64-linux"
        "aarch64-darwin"
      ];

      # One pkgs per system with this flake's overlay applied, so packages in
      # pkgs/ can name each other as arguments.
      eachSystem =
        f:
        lib.genAttrs systems (
          system:
          f (
            import nixpkgs {
              inherit system;
              config = { };
              overlays = [ self.overlays.default ];
            }
          )
        );
    in
    {
      overlays.default =
        final: _prev:
        lib.packagesFromDirectoryRecursive {
          inherit (final) callPackage;
          directory = ./pkgs;
        };

      packages = eachSystem (
        pkgs:
        lib.packagesFromDirectoryRecursive {
          inherit (pkgs) callPackage;
          directory = ./pkgs;
        }
      );

      devShells = eachSystem (pkgs: {
        default = pkgs.callPackage ./shells { };
      });

      checks = eachSystem (
        pkgs:
        self.packages.${pkgs.stdenv.hostPlatform.system}
        // lib.optionalAttrs pkgs.stdenv.hostPlatform.isLinux {
          integration = pkgs.callPackage ./checks/integration.nix { };
        }
      );
    };
}
```

Why the wiring looks like this:

- `lib.packagesFromDirectoryRecursive` called with `newScope` returns a scope: it wraps the directory in `makeScope` and `recurseIntoAttrs`, so the result also holds `callPackage`, `newScope`, `overrideScope`, `packages` and `recurseForDerivations`. Measured: `nix flake check` failed with "packages.x86_64-linux.recurseForDerivations is not a derivation", and with `newScope` in the overlay, evaluating any package hit "stack overflow; max-call-depth exceeded". Dropping `newScope` from the overlay alone fixed the overflow. Pass only `callPackage`. Siblings still resolve, because `final.callPackage` sees the overlay's own packages.
- Every `.nix` file under `pkgs/` is called as a package, and a directory without `package.nix` becomes a nested attribute set. Measured: a `pkgs/_shell/shell.nix` produced `packages.<system>._shell`, and `nix flake check` failed with "is not a derivation". Keep non-package files (shells, checks, publish helpers) outside `pkgs/`; this layout uses `shells/`, `checks/` and `publish/`.
- `packages` must be a flat attribute set of derivations ([scoped outputs](scoped-outputs.md)). If `pkgs/` ever needs a namespace directory, filter or flatten before assigning it.
- `checks` includes every package, so `nix flake check` builds them (it never builds `packages` by itself).

Then, in order:

1. Add `pkgs/<name>/package.nix` for each artifact with the builder from the table.
2. Add checks. Use `pkgs.testers.testVersion { package = ...; }` (or a `runCommand` smoke test) for every packaged tool, and at least one `pkgs.testers.runNixOSTest` that boots the built artifact. `runNixOSTest` lives under `testers`; it isn't a top-level `pkgs` attribute. See [VM tests](vm-tests.md). A minimal check that built and passed here, with `/dev/kvm` present:

   ```nix
   # checks/integration.nix
   { testers, example-app }:
   testers.runNixOSTest {
     name = "example-app-integration";

     nodes.machine = {
       environment.systemPackages = [ example-app ];
     };

     testScript = ''
       machine.succeed("example-app")
     '';
   }
   ```

3. Expose `overlays.default` (already in the snippet) so other flakes and NixOS configurations can consume the packages. See [scoped outputs](scoped-outputs.md).
4. Add a container as a scoped output such as `packages.<system>.<name>-image`. nix2container is the default when you push often (it skips layers already pushed); `dockerTools.streamLayeredImage` needs no extra input. See [containers](containers.md). nix2container isn't in nixpkgs: take its builder from the flake input, `inputs.nix2container.packages.${system}.nix2container`, and pass it to your image file.

Done when `nix build` and `nix flake check` are green in CI and a binary cache is configured so dependencies aren't compiled twice ([Using Nix in CI](choosing-a-track.md#using-nix-in-ci)).

### Stage 3: replace a hand-rolled build system

For repos whose product is the software they build ([worked example: GitLab toolchain](worked-example-gitlab-toolchain.md)). The payoff is that Nix's dependency graph replaces a hand-ordered build chain, and each component can be cached and rebuilt on its own.

1. Map each built artifact to its own `pkgs/<component>/package.nix` (`stdenv.mkDerivation` or a language builder).
2. Compose components through the overlay so they depend on each other through the stdenv fixpoint instead of an ordering file. The order that was buried in script sequence becomes the derivation graph. Measured: with the overlay above, a package that took `example-lib` as an argument built against the sibling package with no explicit ordering.
3. Express a custom toolchain or bootstrap stage (a crosstool-ng glibc, say) as a custom stdenv or a `crossSystem`. See [native vs cross](native-vs-cross.md) before choosing.
4. Expose per-tool outputs as flat `packages.<system>.<tool>` and keep `overlays.default`.
5. **Preserve the existing consumer contract.** If downstream consumers fetch `URL + SHA256` tarballs, add a thin publish adapter that emits reproducible tarballs and their hashes from the Nix outputs. Consumers don't change. The adapter is below.
6. Validate each tool with `checks` (`testVersion`, link-against-expected-library assertions) and VM tests.

A tested publish adapter:

```nix
# publish/tarball.nix
{
  runCommand,
  gnutar,
  gzip,
}:
{ name, drv }:
runCommand "${name}-tarball"
  {
    nativeBuildInputs = [
      gnutar
      gzip
    ];
  }
  ''
    mkdir -p $out
    tar --sort=name --mtime='@1' --owner=0 --group=0 --numeric-owner \
      -cf - -C ${drv} . | gzip -n > $out/${name}.tar.gz
    (cd $out && sha256sum ${name}.tar.gz > ${name}.tar.gz.sha256)
  ''
```

Call it as `pkgs.callPackage ./publish/tarball.nix { } { name = "example-app-1.0"; drv = pkgs.example-app; }`. Measured: `nix-build --check` (rebuild and compare) passed, so a second build produced the same tarball and hash on this machine. Store paths inside the tree (rpaths, shebangs) still point at `/nix/store`. If consumers unpack on machines without those paths, the artifact needs a relocatable build or a bundled closure; put that to the user as a human decision.

Read [worked example: GitLab toolchain](worked-example-gitlab-toolchain.md) for the full design and [worked example: GKG Orbit](worked-example-gkg-orbit.md) for an application-track example (a Rust workspace with an embedded Node frontend, built as a single binary).

## Cross-cutting defaults

- **Eval cost.** Prefer a vendor hash or a committed generated file over import-from-derivation. Crane, uv2nix and poetry2nix read the lockfile at evaluation time; whether that becomes IFD depends on where the lockfile lives (a path in your repo is fine, a fetched source isn't). Test instead of assuming: `nix flake check --option allow-import-from-derivation false`. Measured: that run fails with "cannot build ... during evaluation because the option 'allow-import-from-derivation' is disabled" when IFD is present, and `--no-build` can't be combined with IFD at all. Document the setting in the change if the tooling needs it. See [transforms and IFD](transforms-and-ifd.md).
- **One-command updates.** Ship an update path (`scripts/update-deps.sh`, `just update`, or a CI job) so a hash bump or a regenerated `gemset.nix` is one command.
- **Dedupe inputs.** `inputs.<x>.inputs.nixpkgs.follows = "nixpkgs"` for every input that takes nixpkgs.
- **Multi-arch.** The native build (possibly emulated on a foreign-arch builder) is the reproducible artifact; cross builds are an opt-in fast path and never the default `packages`. Cross-compiled output isn't guaranteed byte-identical to native. Don't set `crossSystem` with `localSystem = system` and assume you got cross; compare derivation paths. See [native vs cross](native-vs-cross.md).
- **Never alter the app's native workflow or source layout.**
- **Writing.** Apply the `natural-writing-style` skill to the change description, to comments in generated Nix, and to any docs. Say why a choice was made, in plain language.

## Constraints from review

The result is your own repository, not nixpkgs, but reviewers of Nix changes apply the same standards, and a package you write may be upstreamed later. [Upstreamable checklist](upstreamable-checklist.md) lists what a nixpkgs reviewer would ask for; [gates and tooling](gates-and-tooling.md) lists the commands and the completion rule. The ones that bite in a nixify change:

- **Minimal.** One logical change; the diff adds Nix files and touches nothing else the user didn't ask for. No framework without a reason.
- **No IFD where you can avoid it.** Choose the FOD or committed-codegen transforms first, as above.
- **Tests included.** At least a `testVersion` or smoke check per package and one VM test where the artifact is a service. nixpkgs itself prefers `versionCheckHook` in the build for packages it carries.
- **Formatting gate.** `nixfmt` through treefmt-nix, exposed as `formatter` and as a check, and `nix-instantiate --parse` clean on every file.
- **Verification stated.** End your message with the gates you ran and the ones you couldn't, as [gates and tooling](gates-and-tooling.md) requires.
- **Reproducible inputs.** Everything pinned by `flake.lock`; no `<nixpkgs>` lookups; `config = { }` when importing nixpkgs.

## Checkable rules

- `flake.nix` contains no builder calls (`mkDerivation`, `buildGoModule`, and so on); only inputs, system mapping and output wiring.
- Every file under `pkgs/` is a `callPackage`-style package file; shells, checks and publish helpers live elsewhere.
- `nix flake check` passes and `packages.<system>` holds only derivations, with flat names.
- No Nix file lists dependency names or versions that a lockfile already records.
- The diff touches only new Nix files, `.envrc`, `.gitignore`, `flake.lock`, `treefmt.nix`, and CI config when requested; no application source changes.
- `.envrc` has `use flake`, and any `watch_file` line comes before it.
- Every input that takes nixpkgs has `inputs.nixpkgs.follows = "nixpkgs"`.
- `nix flake check --option allow-import-from-derivation false` passes, or the change states why IFD is needed.
- Checks include a version or smoke check per packaged tool and a `testers.runNixOSTest` check for services.
- A build-system replacement keeps the published URL and SHA256 contract and says so in the plan.
- `nix fmt` reports nothing to change.

## Evidence

Counts are from `scripts/find-rules.py` and describe nixpkgs review comments, not this workflow. They show what reviewers commonly request.

| Rule | support | changes requested |
|---|---|---|
| Format Nix with `nixfmt` before review | 590 | 165 |
| Keep a PR focused on one logical change | 109 | 22 |
| Avoid import-from-derivation (nix-language-style rule) | 34 | 10 |
| Use `passthru.tests` to attach tests to packages | 91 | 10 |
| Use `versionCheckHook` with `doInstallCheck` | 51 | 16 |

## Dated advice to ignore

- **`runNixOSTest` as a `callPackage` argument.** Older examples take `{ runNixOSTest, ... }:`. `pkgs.runNixOSTest` doesn't exist (measured: `Function called without required argument "runNixOSTest"`). Take `testers` and call `testers.runNixOSTest`. `testers.testVersion` is current.
- **`watch_file` after `use flake`.** Many guides put it second. nix-direnv's README says `watch_file` must be invoked before `use flake` or `use nix` to take effect.
- **`programs.ruff.enable` in treefmt-nix configs.** treefmt-nix no longer has a `ruff` program (the file 404s upstream); use `ruff-format` and `ruff-check`. `nixfmt`, `rustfmt`, `gofmt`, `rufo`, `prettier` and `clang-format` still exist.
- **`nixfmt-rfc-style`.** Now a `warnAlias` for `nixfmt` in `pkgs/top-level/aliases.nix`; use `nixfmt`. `nixfmt-classic` is a `throw`.
- **`poetry2nix` for Poetry projects.** Its README marks it unmaintained and recommends uv2nix for new projects. Treat Poetry as a decision for the user: migrate to uv, or accept an unmaintained tool.
- **"Crane, poetry2nix and uv2nix are IFD."** Older guides say so flatly. [lang-rust.md](lang-rust.md) notes the read happens at eval time and is IFD only when the lockfile sits in a fetched source. Check with the `allow-import-from-derivation` run above.
- **`dockerTools.buildImage` with `contents`.** Deprecated there in favour of `copyToRoot`; the evaluator warns. `streamLayeredImage` and `buildLayeredImage` still take `contents`.
- **nix2container as a plain input.** Its README uses `nix2container.packages.${system}.nix2container.buildImage`, and `tag` defaults to the image's output hash, so you don't need `tag = "latest"`.
- **`pkgs.system`.** Deprecated (the evaluator prints "renamed to/replaced by 'stdenv.hostPlatform.system'"). Use `pkgs.stdenv.hostPlatform.system`.
- **"Declare `nixConfig` substituters so contributors get cache hits without config."** Untrusted flake settings are ignored unless the user accepts them (`accept-flake-config` defaults to false; measured). Say in the README how to accept them, and pass `--accept-flake-config` in CI.
- **Cachix free-tier figures** in the ergonomics reference weren't checked against Cachix's current pricing. Look them up before quoting them.
