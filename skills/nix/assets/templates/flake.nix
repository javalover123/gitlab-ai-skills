{
  description = "REPLACE_ME, reproducible builds and a dev shell via Nix";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

    # Add inputs only when the project needs them (rust-overlay, crane,
    # nix2container, git-hooks). Each one that takes nixpkgs gets
    # `inputs.nixpkgs.follows = "nixpkgs"` so there's a single copy.
    treefmt-nix = {
      url = "github:numtide/treefmt-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs =
    {
      self,
      nixpkgs,
      treefmt-nix,
    }:
    let
      inherit (nixpkgs) lib;

      systems = [
        "x86_64-linux"
        "aarch64-linux"
        "aarch64-darwin"
      ];

      # lib/eachSystem.nix: { <system> = f system; ... } without flake-utils.
      eachSystem = import ./lib/eachSystem.nix { inherit lib systems; };

      # config = { } keeps ~/.config/nixpkgs out of the evaluation. The overlay
      # lets packages in pkgs/ take each other as plain arguments.
      pkgsFor =
        system:
        import nixpkgs {
          inherit system;
          config = { };
          overlays = [
            # A flake input that ships packages but no overlay has to be put on
            # `pkgs` before callPackage can resolve it by name. nix2container is
            # one: add it to `inputs` and to the `outputs` arguments, then enable
            #   (_final: _prev: {
            #     inherit (nix2container.packages.${system}) nix2container;
            #   })
            # pkgs/app-image/package.nix takes it as an argument.
            self.overlays.default
          ];
        };

      # Pass `callPackage` only. Passing `newScope` as well makes the function
      # return a scope (callPackage, newScope, overrideScope, ...) instead of
      # packages, and inside an overlay it recurses until the stack overflows.
      autoload =
        pkgs:
        lib.packagesFromDirectoryRecursive {
          inherit (pkgs) callPackage;
          directory = ./pkgs;
        };
    in
    {
      # pkgs/<name>/package.nix becomes packages.<system>.<name>. Only package
      # files live under pkgs/; shells, checks and helpers sit beside it.
      overlays.default = final: _prev: autoload final;

      packages = eachSystem (system: autoload (pkgsFor system));

      devShells = eachSystem (system: {
        default = (pkgsFor system).callPackage ./shells { };
      });

      # `nix flake check` builds every entry, so packages are checks too.
      checks = eachSystem (
        system:
        let
          pkgs = pkgsFor system;
        in
        self.packages.${system}
        // lib.optionalAttrs pkgs.stdenv.hostPlatform.isLinux {
          # Rename `myapp` in checks/integration.nix to the package under test.
          # integration = pkgs.callPackage ./checks/integration.nix { };
        }
      );

      formatter = eachSystem (
        system: (treefmt-nix.lib.evalModule (pkgsFor system) ./treefmt.nix).config.build.wrapper
      );
    };
}
