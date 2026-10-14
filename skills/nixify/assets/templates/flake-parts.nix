{
  # flake-parts variant — use ONLY when module composition earns its cost
  # (treefmt-nix + git-hooks + per-system checks + several consumers).
  # Otherwise prefer the plain flake.nix template.
  #
  # pkgs/ still autoloads via drupol/pkgs-by-name-for-flake-parts, satisfying
  # the "flake.nix calls pkgs/" rule.
  description = "REPLACE_ME";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-parts.url = "github:hercules-ci/flake-parts";
    pkgs-by-name-for-flake-parts.url = "github:drupol/pkgs-by-name-for-flake-parts";
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
    inputs@{ flake-parts, ... }:
    flake-parts.lib.mkFlake { inherit inputs; } {
      systems = [
        "x86_64-linux"
        "aarch64-linux"
        "aarch64-darwin"
      ];

      imports = [
        inputs.pkgs-by-name-for-flake-parts.flakeModule
        inputs.treefmt-nix.flakeModule
        inputs.git-hooks.flakeModule
      ];

      perSystem =
        { config, pkgs, ... }:
        {
          # Autoload pkgs/by-name/<name>/package.nix → packages.<name>,
          # and expose them as an overlay (pkgs.local).
          pkgsDirectory = ./pkgs/by-name;

          treefmt = {
            projectRootFile = "flake.nix";
            programs.nixfmt.enable = true;
            # programs.rustfmt.enable = true; programs.gofmt.enable = true; ...
          };

          pre-commit.settings.hooks = {
            treefmt.enable = true;
            # clippy.enable = true; rubocop.enable = true; ...
          };

          devShells.default = pkgs.mkShell {
            inputsFrom = [ config.pre-commit.devShell ];
            packages = [
              # project toolchain
            ];
          };

          # Building every package is itself a check.
          checks = config.packages;
        };
    };
}
