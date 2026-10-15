# Nix Code Patterns

Complete templates for common Nix code types, based on official nixpkgs standards.

**Contents:** [Package Derivation](#package-derivation) · [NixOS Module](#nixos-module) · [Flake](#flake) · [Binary Package (with sourceProvenance)](#binary-package-with-sourceprovenance) · [References](#references)

## Package Derivation

Based on [nixpkgs packaging tutorial](https://nix.dev/tutorials/packaging-existing-software.html) and the [GNU Hello example](https://github.com/NixOS/nixpkgs/blob/master/pkgs/by-name/he/hello/package.nix).

### Complete Template

```nix
{
  lib,
  stdenv,
  fetchFromGitHub,
  # Build-time dependencies (nativeBuildInputs)
  pkg-config,
  cmake,
  # Runtime dependencies (buildInputs)
  openssl,
  zlib,
  versionCheckHook,
  nixosTests,
}:
stdenv.mkDerivation (finalAttrs: {
  pname = "package-name";
  version = "1.0.0";

  src = fetchFromGitHub {
    owner = "owner";
    repo = "repo";
    tag = "v${finalAttrs.version}";
    hash = "sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=";
  };

  # Build-time dependencies (compilers, build tools)
  nativeBuildInputs = [
    pkg-config
    cmake
  ];

  # Runtime dependencies (libraries)
  buildInputs = [
    openssl
    zlib
  ];

  # Fast unit tests (runs during build)
  doCheck = true;
  checkPhase = ''
    runHook preCheck
    make test
    runHook postCheck
  '';

  # Post-install smoke test: runs the main program with --version/--help
  # and checks that the package version appears in the output
  nativeInstallCheckInputs = [ versionCheckHook ];
  doInstallCheck = true;

  # Integration tests (expensive, run separately). The NixOS test itself lives
  # in nixos/tests/package-name.nix and is registered in
  # nixos/tests/all-tests.nix; the package links to it via `nixosTests`.
  passthru.tests = {
    integration = nixosTests.package-name;
  };

  meta = {
    description = "One-line description (no period)";
    longDescription = ''
      Optional longer description explaining what the package does,
      its main features, and use cases.
    '';
    homepage = "https://example.com";
    changelog = "https://example.com/releases/tag/v${finalAttrs.version}";
    license = lib.licenses.mit;
    maintainers = with lib.maintainers; [ username ];
    platforms = lib.platforms.unix;
    mainProgram = "package-name";
  };
})
```

`nixosTests` is a package argument, so `passthru.tests` goes in the package, never in a NixOS module. A package outside nixpkgs has no `nixosTests.package-name` entry; use `pkgs.testers.runNixOSTest { name = "..."; nodes = ...; testScript = ...; }` there (see [testing](testing.md)). Prefer `tag` over `rev` for release tags and `hash` over `sha256`, as the fetchers chapter of the manual does.

### Key Patterns

**finalAttrs pattern:**
Allows self-reference in derivation (e.g., version in src.rev).

**nativeBuildInputs vs buildInputs:**
- `nativeBuildInputs`: Build-time tools (compilers, build systems)
- `buildInputs`: Libraries and other dependencies for the host platform

**Testing hierarchy:**
- `checkPhase`: Fast tests during build
- `installCheckPhase` (or `versionCheckHook`): Quick post-install verification
- `passthru.tests`: Expensive integration tests

## NixOS Module

Based on [NixOS module system documentation](https://nix.dev/tutorials/module-system/) and [official NixOS modules](https://wiki.nixos.org/wiki/NixOS_modules).

### Complete Template

```nix
{
  config,
  lib,
  pkgs,
  ...
}:
let
  cfg = config.services.myservice;

  # Use lib.types for configuration schema
  settingsFormat = pkgs.formats.toml { };
in
{
  options.services.myservice = {
    enable = lib.mkEnableOption "my service";

    package = lib.mkPackageOption pkgs "myservice" { };

    user = lib.mkOption {
      type = lib.types.str;
      default = "myservice";
      description = "User account under which myservice runs";
    };

    group = lib.mkOption {
      type = lib.types.str;
      default = "myservice";
      description = "Group under which myservice runs";
    };

    settings = lib.mkOption {
      type = settingsFormat.type;
      default = { };
      description = ''
        Configuration for myservice.
        See <https://example.com/config> for available options.
      '';
      example = lib.literalExpression ''
        {
          server = {
            port = 8080;
            host = "0.0.0.0";
          };
        }
      '';
    };

  };

  config = lib.mkIf cfg.enable {
    # Create user and group
    users.users.myservice = lib.mkIf (cfg.user == "myservice") {
      isSystemUser = true;
      group = cfg.group;
      home = "/var/lib/myservice";
      description = "My Service user";
    };

    users.groups.myservice = lib.mkIf (cfg.group == "myservice") { };

    # Generate configuration file
    environment.etc."myservice/config.toml" = {
      source = settingsFormat.generate "config.toml" cfg.settings;
    };

    # Systemd service with security hardening
    systemd.services.myservice = {
      description = "My Service";
      after = [ "network.target" ];
      wantedBy = [ "multi-user.target" ];

      serviceConfig = {
        Type = "simple";
        User = cfg.user;
        Group = cfg.group;
        ExecStart = "${cfg.package}/bin/myservice --config /etc/myservice/config.toml";
        Restart = "on-failure";
        RestartSec = "5s";

        # Security hardening
        DynamicUser = false; # We manage the user ourselves
        StateDirectory = "myservice"; # Creates /var/lib/myservice owned by User/Group
        NoNewPrivileges = true;
        PrivateTmp = true;
        ProtectSystem = "strict"; # StateDirectory stays writable
        ProtectHome = true;
        ProtectKernelTunables = true;
        ProtectKernelModules = true;
        ProtectControlGroups = true;
      };
    };
  };

  meta.maintainers = with lib.maintainers; [ username ];
}
```

### Key Patterns

**lib.mkEnableOption:**
Standard way to create boolean enable options.

**lib.mkPackageOption:**
Standardized package options (see [NixOS manual](https://nixos.org/manual/nixos/stable/)).

**settingsFormat:**
Use `pkgs.formats.*` for configuration files (TOML, JSON, YAML, etc).

**Security hardening:**
Always include systemd security features (DynamicUser, ProtectSystem, etc).

**State directories:**
Use `StateDirectory` (and `RuntimeDirectory`, `CacheDirectory`) so systemd creates and owns the directory. Don't `mkdir`/`chown` in `preStart`.

**Tests:**
A module's test is a separate file, `nixos/tests/myservice.nix`, registered in `nixos/tests/all-tests.nix` as `myservice = runTest ./myservice.nix;`. The file is a test module:

```nix
{
  name = "myservice";
  nodes.machine = {
    services.myservice = {
      enable = true;
      settings.server.port = 8080;
    };
  };
  testScript = ''
    machine.wait_for_unit("myservice.service")
    machine.wait_for_open_port(8080)
    machine.succeed("curl http://localhost:8080/health")
  '';
}
```

**Conditional config:**
Wrap entire config in `lib.mkIf cfg.enable`.

## Flake

Based on [Nix flakes documentation](https://nixos.org/manual/nix/stable/command-ref/new-cli/nix3-flake.html).

### Complete Template

```nix
{
  description = "Description of what this flake provides";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    # Pin other inputs
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs =
    {
      self,
      nixpkgs,
      flake-utils,
    }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
      in
      {
        # Packages provided by this flake
        packages = {
          default = self.packages.${system}.mypackage;
          mypackage = pkgs.callPackage ./package.nix { };
        };

        # Development shell
        devShells.default = pkgs.mkShell {
          packages = with pkgs; [
            nixfmt
            nixpkgs-review
          ];
          shellHook = ''
            echo "Development environment ready"
          '';
        };

        # Apps (executable flake outputs)
        apps.default = {
          type = "app";
          program = "${self.packages.${system}.mypackage}/bin/mypackage";
        };

        # Formatter for this flake
        formatter = pkgs.nixfmt;

        # Checks (run with `nix flake check`); each value must be a derivation
        checks = {
          inherit (self.packages.${system}) mypackage;
          # A package test from passthru.tests, if the package defines one
          # mypackage-integration = self.packages.${system}.mypackage.tests.integration;
        };
      }
    )
    // {
      # System-independent outputs
      nixosModules.default = import ./module.nix;

      overlays.default = final: prev: {
        mypackage = final.callPackage ./package.nix { };
      };
    };
}
```

### Key Patterns

**flake-utils:**
Use `flake-utils.lib.eachDefaultSystem` to support multiple systems.

**Per-system outputs:**
Use `legacyPackages.${system}` for accessing nixpkgs.

**Formatter:**
Always specify a formatter (use `pkgs.nixfmt`; `nixfmt-rfc-style` is now a deprecated alias for it).

**System-independent outputs:**
Modules and overlays go outside the per-system section.

## Binary Package (with sourceProvenance)

When packaging pre-built binaries, set `meta.sourceProvenance` per [RFC 0089](https://github.com/NixOS/rfcs/blob/master/rfcs/0089-collect-non-source-package-meta.md). `pkgs/README.md` says it must be set when the package isn't built from source (repackaged `.deb`, `.rpm`, `.whl` and similar usually get `binaryNativeCode`), and the meta chapter describes the `lib.sourceTypes` values.

```nix
{
  lib,
  stdenv,
  fetchurl,
  autoPatchelfHook,
  # Binary dependencies
  glibc,
  gcc-unwrapped,
}:
stdenv.mkDerivation (finalAttrs: {
  pname = "binary-package";
  version = "1.0.0";

  src = fetchurl {
    url = "https://example.com/releases/v${finalAttrs.version}/binary-linux-x64.tar.gz";
    hash = "sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=";
  };

  nativeBuildInputs = [
    autoPatchelfHook
  ];

  buildInputs = [
    glibc
    gcc-unwrapped
  ];

  installPhase = ''
    runHook preInstall
    mkdir -p $out/bin
    cp -r bin/* $out/bin/
    runHook postInstall
  '';

  meta = {
    description = "Pre-built binary package";
    homepage = "https://example.com";
    license = lib.licenses.unfree; # or the upstream's actual license
    maintainers = with lib.maintainers; [ username ];
    platforms = [ "x86_64-linux" ];

    # Mark prebuilt binaries
    sourceProvenance = with lib.sourceTypes; [
      binaryNativeCode
    ];
  };
})
```

### sourceProvenance Values

From [RFC 0089](https://github.com/NixOS/rfcs/blob/master/rfcs/0089-collect-non-source-package-meta.md):

- `fromSource`: Built from source
- `binaryNativeCode`: Native compiled binaries
- `binaryBytecode`: Third-party bytecode for a VM or JIT, such as prebuilt `.jar` files
- `binaryFirmware`: Firmware blobs

`lib.sourceTypes.obfuscatedCode` also exists, for code deliberately distributed in obfuscated form.

Use multiple values if package contains mixed content:
```nix
{
  meta.sourceProvenance = with lib.sourceTypes; [
    fromSource
    binaryFirmware # Contains firmware blobs
  ];
}
```

## References

- [Nixpkgs Manual](https://nixos.org/manual/nixpkgs/stable/)
- [NixOS Manual](https://nixos.org/manual/nixos/stable/)
- [nix.dev Packaging Tutorial](https://nix.dev/tutorials/packaging-existing-software.html)
- [NixOS Module System](https://nix.dev/tutorials/module-system/)
- [Nix Flakes Reference](https://nixos.org/manual/nix/stable/command-ref/new-cli/nix3-flake.html)
- [RFC 0089: Package Metadata](https://github.com/NixOS/rfcs/blob/master/rfcs/0089-collect-non-source-package-meta.md)
