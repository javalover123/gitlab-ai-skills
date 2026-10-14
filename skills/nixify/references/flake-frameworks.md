# Flake frameworks — when to use which

**Default: plain `flake.nix` + a tiny `eachSystem` helper.** Adopt a framework
only when it earns its learning-curve cost. Whatever you pick, the per-package
code still lives in `pkgs/` and is called by `flake.nix`
(`references/flake-layout.md`).

## Comparison

| Approach | Problem it solves | DRY-ness | Learning curve | Use when |
|---|---|---|---|---|
| **Plain `flake.nix`** | none added; full control | low (until you add helpers) | lowest | Small/leaf projects; you value zero deps. **Default.** |
| **flake-utils** (numtide) | `eachSystem` over systems | medium | tiny | You only need a system map — but a 1-line `genAttrs` does this with no input; flake-utils is criticised for not checking outputs make sense. Prefer inlining. |
| **flake-parts** (hercules-ci) | a **NixOS-module system for flake outputs**; typed, composable; ecosystem modules (treefmt-nix, git-hooks, pre-commit, devshell) | high | moderate (the module system) | **Preferred framework** when composing several modules / many outputs / multiple consumers. A minimal mirror of the flake schema. |
| **blueprint** (numtide) | convention-over-config; flat `nix/` autoloading; `formatter.nix` → `nix fmt` | high (by convention) | low (no module system) | You want opinionated structure with minimal plumbing. Some features still in flux. |
| **flake-utils-plus** | channels/overlays mgmt atop flake-utils | high | moderate | Mostly as snowfall's substrate; standalone use waning. |
| **snowfall-lib** | auto-imports a structured tree (`systems/`, `modules/`, `packages/`) | high | moderate–high | Personal machine/system configs wanting full autoload. Overkill for app repos. |
| **digga / devos** | batteries-included NixOS fleet template | high | high | Large multi-host NixOS estates. Too heavy for app/build-system repos. |

## Decision guide for nixify

- **Application project, one or few outputs** → plain flake +
  `lib/eachSystem.nix` + `packagesFromDirectoryRecursive`. Lowest cost, fully
  owned, easy review. This is the default the templates implement.
- **You need treefmt-nix + git-hooks + per-system checks + several consumers, and
  the wiring is getting repetitive** → **flake-parts**. Its `perSystem` removes
  the boilerplate and its module ecosystem (treefmt-nix, git-hooks.nix) composes
  cleanly. Use the `drupol/pkgs-by-name-for-flake-parts` module so `pkgs/` still
  autoloads (`pkgsDirectory = ./pkgs/by-name;`). See
  `assets/templates/flake-parts.nix`.
- **Personal/system config repo, not a project** → snowfall or plain; out of
  scope for most nixify targets.

## Why not just always use flake-parts?

flake-parts is excellent but introduces the NixOS module system as a concept the
maintainers must understand to extend the flake. For a single-package
application that just needs a dev shell and a build, that's more machinery than
the problem warrants — and it violates principle #4 (default to plain). Escalate
deliberately, not reflexively.

## flake-parts sketch

```nix
{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-parts.url = "github:hercules-ci/flake-parts";
    treefmt-nix.url = "github:numtide/treefmt-nix";
    git-hooks.url = "github:cachix/git-hooks.nix";
    pkgs-by-name.url = "github:drupol/pkgs-by-name-for-flake-parts";
  };
  outputs = inputs@{ flake-parts, ... }:
    flake-parts.lib.mkFlake { inherit inputs; } {
      systems = [ "x86_64-linux" "aarch64-linux" "aarch64-darwin" ];
      imports = [
        inputs.treefmt-nix.flakeModule
        inputs.git-hooks.flakeModule
        inputs.pkgs-by-name.flakeModule
      ];
      perSystem = { config, pkgs, ... }: {
        pkgsDirectory = ./pkgs/by-name;     # autoloads pkgs/
        treefmt = { /* … */ };
        devShells.default = pkgs.mkShell { /* … */ };
        checks = config.packages;           # build all packages as checks
      };
    };
}
```
