# Nix Code Quality Rules

## Critical Anti-Patterns

Nix's laziness and purity give you reproducibility for free -- but only if you don't undermine it with these common mistakes.

- Never use `with` at expression scope:
  ```nix
  # BAD: with pkgs; [ curl jq ]
  # GOOD: [ pkgs.curl pkgs.jq ]
  # ALSO GOOD: inherit (pkgs) curl jq;
  ```
  `with` hides where names come from, making code harder to read and debug.
- Avoid `rec {}` blocks -- use `let` bindings instead. `rec` makes it too easy to create accidental self-references.
- Never use `<nixpkgs>` lookup paths (depends on `$NIX_PATH`, breaks reproducibility)
  ```nix
  # BAD: import <nixpkgs> {}
  # GOOD: pin nixpkgs in flake.lock
  ```
- Always pin inputs in flakes (the lock file is your friend)
- Avoid Import-From-Derivation (IFD) -- it forces Nix to build during evaluation, which kills caching and parallelism

## Derivation Patterns

Getting dependency categories right matters. The wrong choice means broken cross-compilation or bloated closures.

- `nativeBuildInputs`: tools that run at build time (cmake, pkg-config, makeWrapper)
- `buildInputs`: libraries linked at runtime
- `propagatedBuildInputs`: transitive deps that downstream consumers also need
- `checkInputs` / `nativeCheckInputs`: test-only dependencies
- Use `lib.makeBinPath` for wrapping, not hardcoded paths
- Prefer `installPhase` over `postInstall` for clarity

## Module System

NixOS modules have their own idioms. Fighting them makes your config brittle.

- Always use `lib.mkIf` not raw `if/else` in module definitions
- Use `lib.mkMerge` for combining config blocks from multiple places
- Use `lib.mkDefault` for overridable defaults (priority 1000)
- Use `lib.mkOption` with proper types -- `types.str`, `types.bool`, `types.listOf`, etc.
- Use `lib.mkEnableOption` for boolean enable/disable patterns
- Document options with `description` and `example` attributes

## Flake Structure

Here's a minimal flake that pins nixpkgs and sets up a formatter:

```nix
{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-24.11";
  };

  outputs = { self, nixpkgs, ... }:
    let
      supportedSystems = [ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ];
      forAllSystems = nixpkgs.lib.genAttrs supportedSystems;
    in {
      formatter = forAllSystems (system:
        nixpkgs.legacyPackages.${system}.nixfmt
      );

      devShells = forAllSystems (system:
        let pkgs = nixpkgs.legacyPackages.${system}; in {
          default = pkgs.mkShell {
            nativeBuildInputs = [ pkgs.nixfmt pkgs.statix pkgs.deadnix ];
          };
        }
      );
    };
}
```

Keep flakes focused. If your `flake.nix` is getting long, break outputs into separate files and import them.

## Detection Commands

```bash
# Scope-level with (import or lib)
rg '^\s*with\s+(import|lib)\b' --glob '*.nix'

# rec blocks
rg '\brec\s*\{' --glob '*.nix'

# Deprecated stdenv.lib (use lib directly)
rg 'stdenv\.lib\b' --glob '*.nix'

# Impure lookup paths
rg '<nixpkgs>' --glob '*.nix'

# Linting
statix check . && deadnix -f .

# Formatting
nixfmt --check .
```

## Testing

- `nixosTest` for integration tests that spin up VMs
- `runCommand` for simple build-time checks
- `nix flake check` to validate all outputs
- `nix build --dry-run` to verify evaluation without building
- Test your dev shells: `nix develop --command bash -c "echo works"`
- Pin CI to the same nixpkgs as your flake.lock
