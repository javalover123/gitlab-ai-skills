# Choosing a Nix track

Load this first when a task says "use Nix" without saying how, when you're deciding between flakes and plain Nix, or when a repository already has Nix files and you need to know which style to follow. It picks a track, gives the first command, and points at the file that covers the rest.

Commands here were run against Nix 2.34.8 and a nixpkgs master checkout (26.11 development, Oct 2026). Where a result comes from running it, the text says "measured".

**Contents:** [The stance](#the-stance) · [Decision table](#decision-table) · [Ad-hoc tools](#ad-hoc-tools) · [Per-project dev environments](#per-project-dev-environments) · [Reproducible builds for your own app](#reproducible-builds-for-your-own-app) · [NixOS systems and nixpkgs](#nixos-systems-and-nixpkgs) · [Flakes or not](#flakes-or-not) · [Using Nix in CI](#using-nix-in-ci) · [Checkable rules](#checkable-rules) · [Dated advice to ignore](#dated-advice-to-ignore)

## The stance

- An existing convention wins. Look before you write: `ls flake.nix flake.lock shell.nix default.nix npins nix/sources.nix .envrc`. Follow whatever style is there, including its pinning tool.
- A new project with no Nix files gets a flake, laid out as in [flake layout](flake-layout.md).
- Never convert an existing workflow (`shell.nix` to flake, niv to npins, flake to non-flake) unless the user asked. A conversion is its own change; don't fold it into a feature.
- Logic goes in `callPackage`-style files that work with or without a flake. The flake is wiring.

## Decision table

| Situation | Track | First command | Load |
|---|---|---|---|
| Run a program once | ad-hoc | `nix run nixpkgs#hello -- --version` or `nix-shell -p hello --run 'hello --version'` | this file, [Ad-hoc tools](#ad-hoc-tools) |
| A script that needs tools | shebang | `chmod +x script.sh && ./script.sh` | this file |
| Repo has `flake.nix` | existing flake | `nix develop`, then `nix flake check` | [dev shells and ergonomics](dev-shells-and-ergonomics.md) |
| Repo has `shell.nix`, `default.nix`, `npins/` or `nix/sources.nix` | existing non-flake | `nix-shell`, `nix-build -A <attr>` | this file, [Non-flake shells](#non-flake-shells) |
| New project, wants a pinned toolchain | flake `devShells` | copy `assets/templates/flake.nix`, then `nix develop` | [flake layout](flake-layout.md) |
| Existing project, user asked to "Nixify" it | nixify | `bash scripts/detect.sh .` | [nixify workflow](nixify-workflow.md) |
| Reproducible build of your own app | flake `packages` + `checks` | `nix build -L .#<name>` | `lang-*.md` for the language, [scoped outputs](scoped-outputs.md) |
| Container image of your app | flake `packages.<name>-image` | `nix build .#<name>-image` | [containers](containers.md) |
| Integration test that boots the app | flake `checks` | `nix build -L .#checks.<system>.<name>` | [VM tests](vm-tests.md) |
| NixOS machine or fleet | NixOS system | `nixos-rebuild build --flake .#<host>` | [NixOS systems](nixos-systems.md) |
| Package or module for nixpkgs | nixpkgs (non-flake) | `nix-build -A <pkg>` in the checkout | [upstreaming and PRs](upstreaming-and-prs.md), [derivation authoring](derivation-authoring.md) |
| Library used by flake and non-flake consumers | thin flake over `default.nix` | `nix-build` and `nix flake check` both pass | this file, [Flakes or not](#flakes-or-not) |
| CI for any of the above | CI | `nix flake check` | [Using Nix in CI](#using-nix-in-ci) |

## Ad-hoc tools

Use these for one-off needs. If a project needs the tool repeatedly, put it in the dev shell instead of asking everyone to type the command.

| Command | Where nixpkgs comes from | Notes |
|---|---|---|
| `nix-shell -p git jq` | `<nixpkgs>` via `NIX_PATH` (channels) | Classic CLI, no experimental features. Add `--run 'cmd'` to run once and exit, `--pure` to drop most of your environment. |
| `nix shell nixpkgs#git nixpkgs#jq` | the flake registry entry `nixpkgs` | Needs `nix-command flakes`. `--command cmd args` runs once. |
| `nix run nixpkgs#hello -- --version` | the registry entry `nixpkgs` | Runs one program. Arguments after `--`. |
| `nix run . -- args` | the flake in the current directory | The first positional argument is the installable, so write `.` explicitly before `--`. |

How `nix run` picks what to execute (from `nix run --help`): with no attribute it tries `apps.<system>.default`, then `packages.<system>.default`; with a name it tries `apps`, `packages`, then `legacyPackages`. For a plain derivation it runs `bin/<x>` where `<x>` is the first that exists of `meta.mainProgram`, `pname`, then the name part of `name`.

Both `nix-shell -p` and `nix shell nixpkgs#...` float with the machine. A `nix registry list` on the test machine showed a `system` entry for `nixpkgs` pointing at one store path and a `global` registry loaded from a URL. Two developers can get different versions from the same command. When the version matters, name a commit:

```bash
# classic, from nix.dev: -I names the package source, --pure drops ambient programs
nix-shell -p git --run "git --version" --pure \
  -I nixpkgs=https://github.com/NixOS/nixpkgs/tarball/<commit>

# flake CLI
nix run github:NixOS/nixpkgs/<commit>#git -- --version
```

[status.nixos.org](https://status.nixos.org/) lists the latest tested commit per release; nix.dev points to it for pinning.

### Shebang scripts

Two forms exist. The classic one (the same shape ran here with `-I` pointing at a local nixpkgs):

```bash
#!/usr/bin/env nix-shell
#! nix-shell -i bash --pure
#! nix-shell -p bash cacert curl jq
#! nix-shell -I nixpkgs=https://github.com/NixOS/nixpkgs/archive/<commit>.tar.gz

curl https://example.org/data.json | jq .
```

The flake CLI form, from `nix shell --help`:

```bash
#! /usr/bin/env nix
#! nix shell nixpkgs/<commit>#bash nixpkgs/<commit>#curl nixpkgs/<commit>#jq --command bash

curl https://example.org/data.json | jq .
```

`-i` names the real interpreter. You can't write `#! /usr/bin/env nix shell ...` on one line because most systems pass only one argument to the interpreter. `cacert` has to be in `-p` for TLS to work under `--pure`.

Don't install tools into the user's profile (`nix-env -i`, `nix profile install`) to finish a task. That changes their machine; an ephemeral shell doesn't.

## Per-project dev environments

Two layouts, one shell function. A flake's `devShells.default` and a non-flake `shell.nix` both call `mkShell` or `mkShellNoCC`. Built from the same nixpkgs source with the same arguments, they gave the identical `.drv` path in a test here, so the choice is about workflow, not about what the shell contains.

### mkShell or mkShellNoCC

`mkShell` is a specialised `stdenv.mkDerivation`; `mkShellNoCC` is the same on `stdenvNoCC`. In a `--pure` shell on the test machine, `mkShell` had `cc`, `gcc` and `ld` from a gcc wrapper and `NIX_CC` set; `mkShellNoCC` had none of them. Without `--pure`, a `cc` already on your `PATH` leaks in (measured: a `nix develop` shell from `mkShellNoCC` resolved `cc` to a clang wrapper from the surrounding environment), so a missing `mkShell` can pass on your machine and fail in CI.

| You need | Use |
|---|---|
| Interpreters and CLI tools only (Python, Node without native addons, shellcheck, jq) | `mkShellNoCC` |
| A C compiler or linker: C/C++, Rust (links through `cc`), cgo, node-gyp addons, Python wheels that build | `mkShell` |
| A shell that reuses a package's build dependencies | either, with `inputsFrom = [ pkg ];` |

Attributes (from the nixpkgs manual and `pkgs/build-support/mkshell/default.nix`): `packages` is added to `nativeBuildInputs`; `inputsFrom` merges the listed derivations' build inputs and their `shellHook`s but not the derivations themselves (measured: `hello` was not on `PATH` after `inputsFrom = [ hello ]`); `shellHook` is bash run on entry; any other attribute that coerces to a string becomes an environment variable, except protected ones like `PS1`.

### Flake dev shell

```nix
{
  description = "Dev shell for example";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs =
    { nixpkgs, ... }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
        "aarch64-darwin"
      ];
      forAllSystems = f: nixpkgs.lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});
    in
    {
      devShells = forAllSystems (pkgs: {
        default = pkgs.mkShellNoCC {
          packages = [
            pkgs.jq
            pkgs.npins
          ];
        };
      });
    };
}
```

Enter it with `nix develop`; `nix develop` looks for `devShells.<system>.default`, then `packages.<system>.default`. Commit `flake.lock` and `git add` every new file first (see [Flakes or not](#flakes-or-not)).

### Non-flake shells

The nix.dev route is a pinned `default.nix` with a `shell` attribute, plus a one-line `shell.nix`. Pin nixpkgs with npins (`npins init --bare`, `npins add github nixos nixpkgs --branch nixos-unstable`, `npins update`; `npins import-niv` migrates a niv setup, and the nix.dev guide warns it updates every imported entry):

```nix
# default.nix
{
  sources ? import ./npins,
  system ? builtins.currentSystem,
  pkgs ? import sources.nixpkgs {
    inherit system;
    config = { };
    overlays = [ ];
  },
}:
rec {
  package = pkgs.callPackage ./package.nix { };
  shell = pkgs.mkShellNoCC {
    inputsFrom = [ package ];
    packages = [ pkgs.npins ];
  };
}
```

```nix
# shell.nix
(import ./. { }).shell
```

Without a pin tool, `builtins.fetchTarball` works if you name a commit and a hash:

```nix
# shell.nix
let
  nixpkgs = builtins.fetchTarball {
    url = "https://github.com/NixOS/nixpkgs/archive/<commit>.tar.gz";
    sha256 = "0000000000000000000000000000000000000000000000000000";
  };
  pkgs = import nixpkgs {
    config = { };
    overlays = [ ];
  };
in
pkgs.mkShellNoCC {
  packages = [ pkgs.jq ];
}
```

Measured: with a wrong `sha256` Nix prints `specified:` and `got:` and the `got:` value is the one to paste; in pure evaluation mode, `fetchTarball` without `sha256` fails with "requires a 'sha256' argument". The nix.dev tutorials write `fetchTarball "https://github.com/NixOS/nixpkgs/tarball/nixos-24.05"` for brevity. That URL names a branch, not a commit. Nix re-checks a downloaded tarball after `tarball-ttl` (3600 s by default, measured), so the branch moves under you. Don't copy it into a repo.

Two more rules from nix.dev's best-practices guide: always pass `config = { }; overlays = [ ];` when importing nixpkgs (it otherwise reads `~/.config/nixpkgs` and system overlays), and don't use `<nixpkgs>` lookup paths outside throwaway examples. `NIX_PATH= nix-instantiate ...` is the gate for that; see [gates and tooling](gates-and-tooling.md).

### direnv

`.envrc` is `use flake` for a flake and `use nix` for `shell.nix`. [nix-direnv](https://github.com/nix-community/nix-direnv) replaces direnv's built-in `use_nix` and `use_flake` with a faster, persistent version: it caches the evaluated shell and roots it so garbage collection doesn't remove your build dependencies. direnv asks for `direnv allow` once per directory. On NixOS, `programs.direnv.enable` turns on direnv with nix-direnv by default. nix-direnv already watches `flake.nix`, `flake.lock` and `.envrc`; add `watch_file` lines for other generated inputs, and put them before `use flake` or `use nix`, because its README says they only take effect when invoked first. See [dev shells and ergonomics](dev-shells-and-ergonomics.md) for the rest.

## Reproducible builds for your own app

Flake `packages` for the artifacts, `checks` for everything CI must prove, built with the builder from the matching `lang-*.md` file. The wiring and the `pkgs/` autoload are in [flake layout](flake-layout.md); output names are in [scoped outputs](scoped-outputs.md). Minimum bar for a result you'd hand to someone: `nix build -L .#<name>` succeeds, the binary runs, and `nix flake check` is green. The ladder is in [gates and tooling](gates-and-tooling.md).

For a repo you didn't create, don't start here. Run the [nixify workflow](nixify-workflow.md) so the dev shell lands first.

## NixOS systems and nixpkgs

For machines and fleets, load [NixOS systems](nixos-systems.md). A flake with `nixosConfigurations` is the common shape; since NixOS 26.05 a `system.nix` file is a channel-free non-flake entry point (`nixos-rebuild --file`/`--attr`, from the 26.05 release notes and the `nixos-rebuild` man page). If the machine already uses `configuration.nix` plus channels, keep that unless asked.

For contributions to nixpkgs, load [upstreaming and PRs](upstreaming-and-prs.md). nixpkgs is a non-flake workflow on purpose: its own `shell.nix` says it avoids flakes because each `nix develop` would copy the roughly 500 MB tree into the store again. Use `nix-build -A <pkg>`, `nix-shell`, and `nix-shell -p nixpkgs-review --run "nixpkgs-review wip"` there.

## Flakes or not

### What the docs say

The nix.dev concepts page states flakes are an experimental feature needing Nix 2.4 or later, "with outstanding issues", and that their functionality "can generally be achieved without them". The same page says that if you need to run existing flake software, or want to contribute to it, you should feel free to use them. Every `nix flake` subcommand on 2.34.8 still prints "This program is experimental and its interface is subject to change" (measured). `nix config show` listed `experimental-features = fetch-tree flakes nix-command` on the test machine, so the features are switched on per machine, not by default. The nixpkgs flake file is headed "Experimental flake interface to Nixpkgs." Determinate Nix and Lix treat the feature differently (nix.dev's History section), so check `nix --version` before assuming behaviour.

Enable them for one command with `--experimental-features 'nix-command flakes'`, or permanently with `experimental-features = nix-command flakes` in `nix.conf` (`nix.settings.experimental-features` on NixOS).

### Tradeoffs

| Aspect | Flakes | Non-flake |
|---|---|---|
| Status | Experimental, interface can change | Stable commands (`nix-build`, `nix-shell`) |
| Pinning | `flake.lock`, written on first use; `nix flake update [input]` | npins, niv, or `fetchTarball` with `sha256`; you wire it |
| Purity | Pure evaluation by default; `<nixpkgs>` and `builtins.currentSystem` unavailable | Impure by default; purity is discipline (`config = { }`, empty `NIX_PATH`) |
| Structure | Fixed `outputs` schema, checked by `nix flake check`; no parameters, so you spell out each `system` | Any function shape; `system ? builtins.currentSystem` and `--arg` overrides |
| Inputs | `inputs` and `follows`; all inputs fetched eagerly; default is each dependency's own lock | `sources` argument you can override |
| Source handling | The whole flake directory is copied to the store; only git-tracked files are visible | Only what a derivation references is copied; `lib.fileset` narrows it |
| Ad-hoc use | `nix run github:owner/repo`, registry aliases | `nix-shell -p`, `-I` |
| Ecosystem | Most community tools document flake use first | Many (treefmt-nix, git-hooks.nix) also document non-flake use |

Two points deserve numbers or a command:

- Source copying. Measured: `nix flake metadata path:<nixpkgs checkout>` on a 573 MB tree took 16 to 18 seconds on each of two runs. A non-flake `import` of the same directory listing its attribute names took 0.4 seconds. One machine, one tree; it shows the shape of the cost, not a benchmark. For a normal app repo the copy is small. For a monorepo or a vendored tree it adds up on every evaluation.
- Staging. Measured: an untracked `flake.nix` fails with "Path 'flake.nix' in the repository is not tracked by Git" and a suggested `git add`. `git add -N <path>` (intent to add) was enough to make a new directory visible.

Also remember `nixConfig` in a flake (extra substituters, keys) is ignored unless trusted. Measured: without `--accept-flake-config`, a non-interactive run printed "ignoring untrusted flake configuration setting 'extra-substituters'", and `nix config show accept-flake-config` was `false`.

### Default for new projects

Choose a flake. The lock file, pure evaluation, the typed outputs schema and a single `nix flake check` entry point are what make an agent's result checkable, and the tools this skill points at (treefmt-nix, git-hooks.nix, crane, uv2nix, flake-parts) are flake-first. Accept the experimental label knowingly and limit its reach:

- Keep real logic in `pkgs/<name>/package.nix` files that `callPackage` can load, so the flake stays a thin wrapper, as nix.dev suggests ("use flakes as thin wrappers over existing Nix code").
- Commit `flake.lock`, and give every input that depends on nixpkgs `inputs.<x>.inputs.nixpkgs.follows = "nixpkgs"` so you don't get two copies. If your flake is a library, nix.dev says to add `follows` for all its recursive inputs, or downstream consumers can't add their own `follows` on your indirect inputs.
- Put the experimental-features line in CI and in the README's setup step.
- Add `flake-compat` only when a non-flake consumer exists; it exposes a flake's default package or shell to them.

### When to honour a non-flake setup

- The repo already has `shell.nix`/`default.nix` and a pin (npins, niv, `fetchTarball` with a hash). Work inside it. Add packages as `callPackage` files, extend `shell`, keep `.envrc` as `use nix`.
- The repo has a flake that wraps a `default.nix` through `flake-compat`. Edit the real source of truth the flake points to, not the shim.
- The tree is large and evaluated often (nixpkgs itself), or the target machines can't enable the experimental features.
- The repo's CI uses `nix-build`. Keep CI and local commands identical.

If the existing pin is a bare `<nixpkgs>`, say so in your summary and offer npins. Don't change it silently.

## Using Nix in CI

The same two commands work everywhere. For flakes:

```bash
nix --extra-experimental-features 'nix-command flakes' flake check
nix --extra-experimental-features 'nix-command flakes' build -L .#<name>
```

What `nix flake check` does (from `nix flake check --help` and a measured run): evaluates `checks`, `packages`, `devShells`, `apps`, `overlays`, `nixosModules`, `templates` and each `nixosConfigurations.<host>.config.system.build.toplevel`, and builds only `checks.<system>.*`. It never builds `packages`. It covers the current system and prints "omitted these incompatible systems" for the rest; `--all-systems` includes them. `--no-build` makes it an evaluation-only gate, which is useful with `--all-systems` when you lack builders. `--keep-going` collects more than one failure.

To have CI build packages too, put them in `checks` (`checks = self.packages.${system} // { ... };`, the pattern in [scoped outputs](scoped-outputs.md)) or add a `nix build` step. Put the formatting gate in `checks` as well; [gates and tooling](gates-and-tooling.md) lists the gate order and [dev shells and ergonomics](dev-shells-and-ergonomics.md) shows treefmt-nix and git-hooks.nix wiring. git-hooks.nix's README warns that hooks which rewrite files or need the network fit badly in the sandboxed `nix flake check`; run them through `nix fmt` or `nix develop -c pre-commit run -a`.

Non-flake projects use `nix-build -A <attr>`, `nix-shell --run '<cmd>'`, and `NIX_PATH= nix-instantiate -A <attr>` as the purity check.

### Caching

Binary caches are what keep CI from rebuilding dependencies every run.

| Option | Use it for | Source |
|---|---|---|
| Cachix | Hosted cache; `cachix/cachix-action` substitutes before the job and pushes built paths after it | nix.dev GitHub Actions recipe |
| attic | Self-hosted, multi-tenant cache for private work | named in [dev shells and ergonomics](dev-shells-and-ergonomics.md) |
| Your own HTTP or S3 cache | Full control; push with a `post-build-hook` or `nix copy` | nix.dev recipes: post-build hook, binary cache setup |
| `cache.nixos.org` | Already the default substituter for nixpkgs paths | built in |

Wiring a cache into Nix takes `substituters` or `extra-substituters` plus `trusted-public-keys` or `extra-trusted-public-keys`. nix.dev warns that Nix accepts anything signed by a configured key, so add only keys you trust. In a flake you can declare them under `nixConfig`, but as measured above they need `--accept-flake-config` (or the user answering the prompt), so CI should pass the flag or write the lines into `nix.conf`.

A GitHub Actions skeleton, from the nix.dev recipe with the action versions left for you to choose (the recipe pins old tags; look up the current ones and pin to your organisation's policy):

```yaml
name: "Test"
on:
  pull_request:
  push:
jobs:
  tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@<tag>
      - uses: cachix/install-nix-action@<tag>
      - uses: cachix/cachix-action@<tag>
        with:
          name: mycache
          authToken: "${{ secrets.CACHIX_AUTH_TOKEN }}"
      - run: nix --extra-experimental-features 'nix-command flakes' flake check
```

`nix-fast-build` and `nix-eval-jobs` exist in nixpkgs (descriptions: run evaluation and builds in parallel; Hydra's evaluator as a standalone tool) for large check sets. They weren't exercised for this file.

VM tests need `kvm` in the builder's `system-features`; `/dev/kvm` was present on the test machine and a `testers.runNixOSTest` check built and passed in 17 seconds of test time. A runner without `/dev/kvm` can't run them; report the check as not run rather than deleting it.

## Checkable rules

- A flake project has a committed `flake.lock`, and each input that itself takes nixpkgs has `inputs.<x>.inputs.nixpkgs.follows = "nixpkgs"`.
- `git ls-files flake.nix flake.lock` lists both before you run `nix flake check`; untracked files are invisible to flakes.
- No committed `.nix` file contains `<nixpkgs>` outside a comment, except throwaway examples.
- Every `import nixpkgs` or `import sources.nixpkgs` passes `config = { }` and `overlays = [ ]` (or an explicit overlay list).
- Every `builtins.fetchTarball` in committed code names a commit, not a branch, and passes `sha256`.
- `.envrc` contains `use flake` when `flake.nix` is the entry point and `use nix` when `shell.nix` is.
- A change that doesn't ask for it adds no `flake.nix` to a `shell.nix`-only repo and no `shell.nix` to a flake-only repo.
- Shells that compile anything use `mkShell`; `mkShellNoCC` shells list no compiler-dependent tools.
- CI runs `nix flake check` (or `nix-build`/`nix-instantiate` for non-flake) and fails on any non-zero exit.
- A flake's `nixConfig` substituters have a matching `trusted-public-keys` entry, and CI passes `--accept-flake-config` or sets them in `nix.conf`.

## Dated advice to ignore

- "Use `fetchTarball "https://github.com/NixOS/nixpkgs/tarball/nixos-NN.MM"` to pin nixpkgs" (nix.dev tutorials): that tracks a moving branch. Name a commit with `sha256`, or use npins.
- "Use niv": nix.dev's current guide recommends npins and documents `npins import-niv`.
- "`pkgs.system`" (still in the treefmt-nix README example): evaluating it on current nixpkgs printed "'system' has been renamed to/replaced by 'stdenv.hostPlatform.system'". Use `pkgs.stdenv.hostPlatform.system`, or the `system` you already have from `genAttrs`.
- "Install with `nix-env -iA nixpkgs.foo`": channel-based and mutates the user profile. Use ephemeral shells or declared environments.
- "Flakes are the only modern way" or "flakes are deprecated": neither is in the docs. nix.dev calls them experimental with open issues; they're widely used and nixpkgs ships an experimental flake interface.
- "Use `mkShell` everywhere": nix.dev's tutorials use `mkShellNoCC` for tool-only shells; reach for `mkShell` when you need the compiler.
- The `cachix/install-nix-action@v25` and `cachix/cachix-action@v14` tags in the nix.dev recipe are old; look up the current tags.
- `.envrc` examples that put `watch_file` after `use flake` (including the one in [dev shells and ergonomics](dev-shells-and-ergonomics.md)) get the order wrong; see the direnv note above.
