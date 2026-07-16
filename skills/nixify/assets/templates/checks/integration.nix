# A NixOS VM integration test wired into flake `checks`.
# Build/debug interactively: nix build .#checks.<system>.integration.driverInteractive
{ runNixOSTest, myapp }:
runNixOSTest {
  name = "REPLACE_ME-integration";

  nodes.server =
    { ... }:
    {
      systemd.services.myapp = {
        wantedBy = [ "multi-user.target" ];
        serviceConfig.ExecStart = "${myapp}/bin/REPLACE_ME --port 8080";
      };
      networking.firewall.allowedTCPPorts = [ 8080 ];
    };

  testScript = ''
    server.wait_for_unit("myapp.service")
    server.wait_for_open_port(8080)
    server.succeed("curl -sf http://localhost:8080/health")
  '';
}
