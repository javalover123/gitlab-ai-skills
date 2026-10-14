# Flake layout — thin `flake.nix` calling `lib/` + `pkgs/`

The non-negotiable structural rule: **`flake.nix` is thin and wires up `lib/`
(helpers) and `pkgs/` (one function per package). All real build logic lives in
`pkgs/<name>/package.nix`, called via `callPackage`.** This holds regardless of
whether you use a framework (`references/flake-frameworks.md`).

## Directory convention

```
repo/
  flake.nix            # inputs, pkgs instantiation, eachSystem, output wiring
  flake.lock           # pinned inputs (use inputs.*.follows to dedupe nixpkgs)
  lib/
    eachSystem.nix     # tiny multi-system helper (avoid flake-utils if you can)
    default.nix        # any project-specific helpers
  pkgs/
    <name>/package.nix # callPackage-style function — the actual build
    <other>/package.nix
  checks/              # VM tests / testers checks (or co-locate under pkgs)
  modules/             # nixosModules / home-manager modules (if any)
  nixos/               # nixosConfigurations (if any)
  .envrc               # `use flake` for nix-direnv
  treefmt.nix          # formatting config (referenced by flake)
```

## `callPackage` — the pattern

A package file is a function whose arguments are dependency names.
`callPackage` auto-fills them from `pkgs`:

```nix
# pkgs/myservice/package.nix
{ buildGoModule, lib, openssl }:
buildGoModule {
  pname = "myservice";
  version = "0.1.0";
  src = ../..;                # repo root relative to this file
  vendorHash = "sha256-…";
  buildInputs = [ openssl ];
}
```

```nix
# called from flake.nix
myservice = pkgs.callPackage ./pkgs/myservice/package.nix { };
```

`.override { openssl = pkgs.libressl; }` swaps a single input without editing
the package file — this is why every package is a `callPackage` function rather
than an inline derivation.

## Autoloading `pkgs/` — `packagesFromDirectoryRecursive`

Don't hand-list packages. `lib.packagesFromDirectoryRecursive` turns a
`pkgs/by-name`-style tree into a (possibly nested) attrset of derivations
automatically — nixpkgs itself uses this:

```nix
packages = lib.packagesFromDirectoryRecursive {
  inherit (pkgs) callPackage;
  directory = ./pkgs;
};
```

A directory containing `package.nix` becomes that attribute. To let packages
depend on *sibling* packages, thread `newScope` so siblings are in scope:

```nix
localPackages = lib.makeScope pkgs.newScope (self:
  lib.packagesFromDirectoryRecursive {
    inherit (self) callPackage newScope;
    directory = ./pkgs;
  });
```

(See the flake.nix template in `assets/templates/flake.nix` for the complete
wiring, and `assets/templates/flake-parts.nix` for the framework variant using
`drupol/pkgs-by-name-for-flake-parts`, which exposes `pkgsDirectory =
./pkgs/by-name;`.)

## Keeping `flake.nix` thin

`flake.nix` should only:

1. declare `inputs`,
2. instantiate `pkgs` per system (with your overlays),
3. map over systems (via `lib/eachSystem.nix`),
4. assign `packages` from `packagesFromDirectoryRecursive`, plus `devShells`,
   `checks`, `apps`,
5. expose `overlays.default` built from `pkgs/`.

Everything substantive is in `lib/` and `pkgs/`. A reviewer reading `flake.nix`
should see wiring, not logic.

## The `overlays.default` from `pkgs/`

```nix
overlays.default = final: prev:
  lib.packagesFromDirectoryRecursive {
    callPackage = final.callPackage;
    directory = ./pkgs;
  };
```

This lets other flakes and NixOS configs consume your packages by adding one
overlay — the clean composition story for the build-system-replacement track.

## Avoiding `flake-utils` for the system map

`flake-utils`'s `eachDefaultSystem` is convenient but criticised for not
validating that outputs make sense, and it's an extra input. A one-liner does
the job with zero dependencies — see `assets/templates/lib/eachSystem.nix`:

```nix
# lib/eachSystem.nix — import with { inherit lib systems; }, then call with f
{ lib, systems }:
f: lib.genAttrs systems (system: f system)
```
