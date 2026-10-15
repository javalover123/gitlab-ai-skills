# A NixOS VM test wired into flake `checks` (see the commented entry in flake.nix).
# `testers.runNixOSTest` is the entry point outside nixpkgs; it isn't a
# top-level pkgs attribute, so take `testers` as the argument.
# Rename `myapp` to the package under test; it needs `meta.mainProgram`.
# Build and debug interactively:
#   nix build .#checks.<system>.integration.driverInteractive
{
  lib,
  testers,
  myapp,
}:
testers.runNixOSTest {
  name = "myapp-integration";

  nodes.server =
    { ... }:
    {
      systemd.services.myapp = {
        wantedBy = [ "multi-user.target" ];
        serviceConfig.ExecStart = "${lib.getExe myapp} --port 8080";
      };
      networking.firewall.allowedTCPPorts = [ 8080 ];
    };

  testScript = ''
    server.wait_for_unit("myapp.service")
    server.wait_for_open_port(8080)
    server.succeed("curl --fail http://localhost:8080/health")
  '';
}
