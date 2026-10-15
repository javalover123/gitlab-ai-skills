# nixos/tests/example.nix, a test module for services.example.
# Register it in nixos/tests/all-tests.nix as `example = runTest ./example.nix;`
# and run it with `nix-build -A nixosTests.example` from the nixpkgs root.
# Outside nixpkgs, import your module in the node and call
# `pkgs.testers.runNixOSTest ./test.nix`; `runNixOSTest` lives under `testers`.
# Link it from the package: passthru.tests = { inherit (nixosTests) example; };
{ ... }:
{
  name = "example";
  # Your handle: meta.maintainers = with lib.maintainers; [ yourhandle ];
  meta.maintainers = [ ];

  nodes.machine = {
    services.example = {
      enable = true;
      settings.log_level = "debug";
    };
  };

  testScript = ''
    machine.wait_for_unit("example.service")
    machine.wait_for_open_port(8080)
    machine.succeed("curl --fail http://localhost:8080/")
  '';
}
