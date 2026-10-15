# nixos/modules/services/misc/example.nix
# Register it in nixos/modules/module-list.nix (sorted, inside the keep-sorted
# block), add nixos/tests/example.nix, and add a release-notes entry.
{
  config,
  lib,
  pkgs,
  utils,
  ...
}:
let
  cfg = config.services.example;

  # RFC 42: one `settings` option typed by a format, instead of one option per
  # upstream key. Swap `toml` for json, yaml, ini and so on to match upstream.
  settingsFormat = pkgs.formats.toml { };
  configFile = settingsFormat.generate "example.toml" cfg.settings;
in
{
  options.services.example = {
    enable = lib.mkEnableOption "example, a demonstration daemon";

    package = lib.mkPackageOption pkgs "example" { };

    settings = lib.mkOption {
      type = lib.types.submodule {
        # Unlisted keys pass through to the file; list only what you type-check.
        freeformType = settingsFormat.type;
        options.listen_port = lib.mkOption {
          type = lib.types.port;
          default = 8080;
          description = "TCP port to listen on.";
        };
      };
      default = { };
      example = lib.literalExpression ''
        {
          log_level = "debug";
        }
      '';
      description = ''
        Configuration for example, see <https://example.com/docs/config>
        for supported values. Values end up in the world-readable Nix store,
        so don't put secrets here; use {option}`tokenFile` instead.
      '';
    };

    # Secrets arrive as a runtime path, never as a value, and never through
    # `settings`: everything evaluated from Nix is copied into the store.
    tokenFile = lib.mkOption {
      type = lib.types.nullOr lib.types.externalPath;
      default = null;
      example = "/run/secrets/example-token";
      description = ''
        File containing the API token. It's passed to the service with
        systemd's `LoadCredential`, so the service user doesn't need read
        access to the original file.
      '';
    };

    extraArgs = lib.mkOption {
      type = lib.types.listOf lib.types.str;
      default = [ ];
      description = "Extra command-line arguments for the example daemon.";
    };

    openFirewall = lib.mkEnableOption "opening {option}`settings.listen_port` in the firewall";
  };

  # Everything under mkIf, so a disabled module can't fail evaluation. Don't
  # pick attribute names with `if` or optionalAttrs on a `config` value:
  # that recurses infinitely.
  config = lib.mkIf cfg.enable {
    assertions = [
      {
        assertion = (cfg.settings ? user) == (cfg.settings ? password_file);
        message = "services.example: settings.user and settings.password_file must be set together.";
      }
    ];

    warnings = lib.optional (
      cfg.settings ? password
    ) "services.example.settings.password ends up in the Nix store; use services.example.tokenFile.";

    # mkDefault leaves users free to change it.
    services.example.settings.log_level = lib.mkDefault "info";

    networking.firewall.allowedTCPPorts = lib.mkIf cfg.openFirewall [ cfg.settings.listen_port ];

    systemd.services.example = {
      description = "Example daemon";
      wantedBy = [ "multi-user.target" ];
      after = [ "network.target" ];
      # A changed generated file restarts the unit.
      restartTriggers = [ configFile ];

      script = ''
        ${lib.optionalString (cfg.tokenFile != null) ''
          export EXAMPLE_TOKEN="$(< "$CREDENTIALS_DIRECTORY/token")"
        ''}
        exec ${
          utils.escapeSystemdExecArgs (
            [
              (lib.getExe cfg.package)
              "--config"
              configFile
            ]
            ++ cfg.extraArgs
          )
        }
      '';

      serviceConfig = {
        # Preferred over a static user: no uid to allocate, and systemd adds
        # PrivateTmp, RemoveIPC, NoNewPrivileges and ProtectSystem=strict.
        DynamicUser = true;
        StateDirectory = "example";
        RuntimeDirectory = "example";
        LoadCredential = lib.optional (cfg.tokenFile != null) "token:${cfg.tokenFile}";

        # Check each directive against what the daemon does, then compare with
        # `systemd-analyze security example.service`. Comment any you drop.
        CapabilityBoundingSet = "";
        LockPersonality = true;
        NoNewPrivileges = true;
        PrivateDevices = true;
        ProtectClock = true;
        ProtectControlGroups = true;
        ProtectHome = true;
        ProtectKernelLogs = true;
        ProtectKernelModules = true;
        ProtectKernelTunables = true;
        ProtectProc = "invisible";
        RestrictAddressFamilies = [
          "AF_INET"
          "AF_INET6"
          "AF_UNIX"
        ];
        RestrictNamespaces = true;
        RestrictRealtime = true;
        SystemCallArchitectures = "native";
        SystemCallFilter = [
          "@system-service"
          "~@privileged"
        ];
        UMask = "0077";
      };
    };
  };

  # Your handle: maintainers = with lib.maintainers; [ yourhandle ];
  meta.maintainers = [ ];
}
