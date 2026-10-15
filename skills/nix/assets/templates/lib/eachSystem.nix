# lib/eachSystem.nix
#
# Zero-dependency replacement for flake-utils.lib.eachDefaultSystem.
# Usage in flake.nix:
#   eachSystem = import ./lib/eachSystem.nix { inherit lib systems; };
#   packages = eachSystem (system: { ... });
#
# Produces { <system> = f system; } for each system, e.g.
#   { x86_64-linux = ...; aarch64-darwin = ...; }
{ lib, systems }:
f: lib.genAttrs systems (system: f system)
