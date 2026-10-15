{
  description = "NixOS configuration for REPLACE_ME";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs =
    { self, nixpkgs }:
    let
      system = "x86_64-linux";

      mkHost =
        name: hostModule:
        nixpkgs.lib.nixosSystem {
          modules = [
            hostModule
            {
              networking.hostName = name;
              # nixosSystem sets no platform; without this, evaluation stops
              # with "Neither nixpkgs.hostPlatform nor ... has been set".
              # A generated hardware-configuration.nix usually sets it too.
              nixpkgs.hostPlatform = system;
              # Lets `nixos-version --configuration-revision` name the commit.
              system.configurationRevision = self.rev or self.dirtyRev or null;
            }
          ];
          # Values that `imports` needs go through specialArgs; `_module.args`
          # and `config` aren't available there (infinite recursion).
          specialArgs = { inherit self; };
        };

      # Grow this into hosts/<name>/default.nix importing configuration.nix and
      # hardware-configuration.nix. The two fileSystems and boot lines are
      # placeholders so the module evaluates; replace them with the real ones.
      exampleHost =
        { pkgs, ... }:
        {
          # Release you first installed on this machine. Set it once; don't
          # bump it on upgrade (it keeps old defaults for existing data).
          system.stateVersion = "26.05";

          boot.loader.grub.devices = [ "nodev" ];
          fileSystems."/" = {
            device = "/dev/disk/by-label/nixos";
            fsType = "ext4";
          };

          services.openssh.enable = true;
          environment.systemPackages = [ pkgs.git ];
        };
    in
    {
      nixosConfigurations.example = mkHost "example" exampleHost;

      # `nix flake check` only evaluates nixosConfigurations. A check that
      # names the toplevel makes CI build the system.
      checks.${system}.example = self.nixosConfigurations.example.config.system.build.toplevel;
    };
}
