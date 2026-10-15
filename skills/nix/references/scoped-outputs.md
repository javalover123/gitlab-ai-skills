# Scoped outputs & flake output conventions

## The standard output set

| Output | Shape | Purpose |
|---|---|---|
| `packages.<system>.<name>` | flat attrset of derivations | your real build artifacts; enumerated by `nix flake show` and validated |
| `devShells.<system>.<name>` | mkShell derivations | `nix develop` environments |
| `checks.<system>.<name>` | derivations that must build | run by `nix flake check` (tests, VM tests, lint) |
| `apps.<system>.<name>` | `{ type = "app"; program = "…"; }` | `nix run` entry points |
| `overlays.default` | `final: prev: { … }` | let other flakes/NixOS consume your packages |
| `nixosModules.<name>` | module function | reusable NixOS config |
| `nixosConfigurations.<host>` | `nixpkgs.lib.nixosSystem { … }` | full machine configs |
| `formatter.<system>` | a formatter derivation | `nix fmt` (point at treefmt) |
| `templates.<name>` | `{ path; description; }` | `nix flake init -t` scaffolds |

## Per-system handling

Map outputs over systems with `lib/eachSystem.nix` (a `genAttrs` one-liner),
`flake-utils.lib.eachDefaultSystem`, or flake-parts' `perSystem` (which also
type-checks). Default systems to support:
`x86_64-linux`, `aarch64-linux`, `aarch64-darwin`. Nixpkgs 26.05 is the last
release that supports `x86_64-darwin`; from 26.11 it no longer builds packages
for it (release notes), so don't add it for new work unless a consumer pins an
older nixpkgs.

## `packages` vs `legacyPackages`

- **`packages.<system>`** must be a *flat* attrset of derivations. `nix flake
  show` enumerates it and the flake schema validates it. **Use this for your
  real outputs.**
- **`legacyPackages.<system>`** may be *arbitrarily nested* (it exists for
  nixpkgs-like trees). It is not enumerated/validated the same way. Use it only
  for large nested collections (e.g. the per-tool tree of a build-system
  replacement, if you genuinely need nesting).

For the build-system-replacement track, prefer flat
`packages.<system>.<tool>` names (e.g. `packages.x86_64-linux.gcc`,
`.ruby`, `.postgresql`) so `nix flake show` lists every tool. Reach for
`legacyPackages` only when nesting is unavoidable.

## Namespacing & variants

Expose variants as distinct scoped attrs rather than nesting:

```
packages.<system>.myapp           # the binary
packages.<system>.myapp-image     # nix2container image
packages.<system>.myapp-static    # static/musl variant
```

This keeps `nix build .#myapp-image` discoverable and avoids the validation
quirks of nested `packages`.

## `checks` should mirror what CI runs

Put every gate in `checks.<system>` so `nix flake check` is the single CI
command: build all packages, run unit tests, run lint (clippy/rubocop/…), run VM
tests. A common pattern is `checks = self.packages.<system> // { <vm-tests> };`
so building the packages is itself a check.
