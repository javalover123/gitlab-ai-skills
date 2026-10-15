# VM tests & lighter checks

Wire integration tests into `checks.<system>` so `nix flake check` runs them.
Two tiers: full NixOS VM tests (`runNixOSTest`) and lightweight `pkgs.testers`
checks.

**Contents:** [NixOS VM tests — `pkgs.testers.runNixOSTest`](#nixos-vm-tests--pkgstestersrunnixostest) · [Lightweight checks — `pkgs.testers`](#lightweight-checks--pkgstesters) · [Build-system validation](#build-system-validation)

## NixOS VM tests — `pkgs.testers.runNixOSTest`

The canonical integration-testing path. `runNixOSTest` is the modern wrapper
around `runTest`; it supersedes calling `nixosTest` / `make-test-python.nix`
directly. Tests run in QEMU/KVM with a Python test driver.

> The Python test driver replaced the Perl implementation; the Perl driver was
> deprecated in NixOS 20.03 and removed in 20.09 (per the 20.03 and 20.09 release
> notes).

```nix
# checks/myapp-integration.nix
{ testers, myapp }:
testers.runNixOSTest {
  name = "myapp-integration";
  nodes.server = { pkgs, ... }: {
    # a real NixOS config for the VM:
    systemd.services.myapp = {
      wantedBy = [ "multi-user.target" ];
      serviceConfig.ExecStart = "${myapp}/bin/myapp --port 8080";
    };
    networking.firewall.allowedTCPPorts = [ 8080 ];
  };
  testScript = ''
    server.wait_for_unit("myapp.service")
    server.wait_for_open_port(8080)
    server.succeed("curl -sf http://localhost:8080/health")
  '';
}
```

Wire it in:

```nix
checks.${system}.integration =
  pkgs.callPackage ./checks/myapp-integration.nix { inherit (self.packages.${system}) myapp; };
```

### Test-driver Python API (most-used)

- `machine.wait_for_unit("svc.service")`, `wait_for_open_port(port)`
- `machine.succeed("cmd")`, `machine.fail("cmd")`, `machine.execute("cmd")`
- multi-node: name each node under `nodes.<name>`; they resolve each other by
  hostname (e.g. `client.succeed("curl http://server/")`)
- screen/OCR: `get_screen_text()`, `wait_for_text("…")` for GUI/console
- debug interactively: `nix build .#checks.<system>.<name>.driverInteractive`
  then run `./result/bin/nixos-test-driver` for a REPL.

### Multi-node example shape

```nix
nodes = {
  db     = { … postgres … };
  server = { … app pointing at db … };
  client = { … curl tools … };
};
testScript = ''
  start_all()
  db.wait_for_unit("postgresql.service")
  server.wait_for_unit("myapp.service")
  client.succeed("curl -sf http://server:8080/")
'';
```

### Platform

VM tests need the `kvm` system feature, or `apple-virt` on macOS (autodetected
locally since Nix 2.19; features of remote builders must be configured by hand).
On macOS you also need a Linux builder. **CI runners must provide
virtualisation** — flag this in the plan if the target's CI doesn't.

## Lightweight checks — `pkgs.testers`

For fast smoke checks that don't need a VM:

- `testers.testVersion { package = pkg; version = "1.2.3"; }` — runs
  `pkg --version`, catching dynamic-linking and version-stamp errors. **Add this
  for every packaged tool** — cheap and catches the most common breakage. It's
  meant for `passthru.tests`; to make a version check fail the build itself, use
  `versionCheckHook` (see the stdenv hooks chapter).
- `testers.hasPkgConfigModules { … }` — assert pkg-config modules are present.
- `testers.testEqualContents` / `testers.testEqualDerivation` — equality checks.
- `runCommand "check" { } ''…assertions…; touch $out''` — arbitrary smoke test.
- `lib.runTests` (also `lib.debug.runTests`) — pure-eval unit tests for your Nix
  code: it takes an attribute set of cases named `test...`, each
  `{ expr = ...; expected = ...; }`, and returns a list of the failing ones. Pair it with `lib.evalModules` to test module option
  behavior. `nix-unit` is in nixpkgs and runs such tests from the command line;
  nixpkgs itself uses it in `lib/tests/nix-unit.nix`.

## Build-system validation

For the build-system-replacement track, VM tests are the way to assert that a
toolchain-built binary actually works: install the produced package/service in a
VM and assert it boots, links against the expected libraries, and serves
traffic. This replaces the hand-rolled health checks the old build system carried.
