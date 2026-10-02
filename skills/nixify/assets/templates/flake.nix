{
  description = "REPLACE_ME — reproducible builds and dev shell via Nix";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

    # Pick only what the project needs; delete the rest. Always `follows`
    # nixpkgs to dedupe.
    rust-overlay = {
      url = "github:oxalica/rust-overlay";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    crane.url = "github:ipetkov/crane";
    nix2container = {
      url = "github:nlewo/nix2container";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    treefmt-nix = {
      url = "github:numtide/treefmt-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    git-hooks = {
      url = "github:cachix/git-hooks.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs =
    inputs@{ self, nixpkgs, ... }:
    let
      inherit (nixpkgs) lib;

      systems = [
        "x86_64-linux"
        "aarch64-linux"
        "aarch64-darwin"
      ];

      # lib/eachSystem.nix — zero-dependency replacement for flake-utils.
      eachSystem = import ./lib/eachSystem.nix { inherit lib systems; };

      # Instantiate nixpkgs per system, applying overlays the project needs.
      pkgsFor =
        system:
        import nixpkgs {
          inherit system;
          overlays = [
            inputs.rust-overlay.overlays.default
            # nix2container ships no overlay of its own; expose its package
            # at the top level so pkgs/app-image/package.nix's callPackage
            # can resolve the `nix2container` argument from pkgs.
            (_final: _prev: {
              nix2container = inputs.nix2container.packages.${system}.nix2container;
            })
            self.overlays.default
          ];
        };
    in
    {
      # Packages are autoloaded from pkgs/ — never hand-listed.
      # A pkgs/<name>/package.nix becomes packages.<system>.<name>.
      packages = eachSystem (
        system:
        let
          pkgs = pkgsFor system;
          scope = lib.makeScope pkgs.newScope (
            self_:
            lib.packagesFromDirectoryRecursive {
              inherit (self_) callPackage newScope;
              directory = ./pkgs;
            }
          );
        in
        scope
      );

      # Consumers apply this overlay to get the project's packages.
      overlays.default =
        final: _prev:
        lib.packagesFromDirectoryRecursive {
          inherit (final) callPackage newScope;
          directory = ./pkgs;
        };

      devShells = eachSystem (
        system:
        let
          pkgs = pkgsFor system;
        in
        {
          default = pkgs.callPackage ./pkgs/_shell/shell.nix { };
        }
      );

      # checks/ holds VM tests and testers checks; building packages is also a check.
      checks = eachSystem (
        system:
        let
          pkgs = pkgsFor system;
        in
        (self.packages.${system} or { })
        // {
          # integration = pkgs.callPackage ./checks/integration.nix {
          #   inherit (self.packages.${system}) myapp;
          #   inherit (pkgs.testers) runNixOSTest; # not a top-level pkgs attribute
          # };
        }
      );

      formatter = eachSystem (
        system:
        let
          pkgs = pkgsFor system;
        in
        (inputs.treefmt-nix.lib.evalModule pkgs ./treefmt.nix).config.build.wrapper
      );
    };
}
