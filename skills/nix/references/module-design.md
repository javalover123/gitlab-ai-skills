# Module Design Patterns (RFC 0042)

Complete examples and migration patterns for settings-based NixOS modules.

**Contents:** [Basic Settings Module Template](#basic-settings-module-template) · [Format-Specific Examples](#format-specific-examples) · [Valuable Options Examples](#valuable-options-examples) · [Migration Patterns](#migration-patterns) · [Advanced Patterns](#advanced-patterns) · [Common Mistakes](#common-mistakes) · [Decision Flowchart](#decision-flowchart) · [References](#references)

## Basic Settings Module Template

**Minimal settings-based module.** Option descriptions are plain Nixpkgs-flavored Markdown strings; don't wrap them in `lib.mdDoc` (removed in 24.11, after a deprecation warning in 24.05):

```nix
{ config, lib, pkgs, ... }:

let
  cfg = config.services.myservice;
  # Choose format based on config file type
  settingsFormat = pkgs.formats.json {};  # or .yaml, .toml, .ini
in {
  options.services.myservice = {
    enable = lib.mkEnableOption "My Service";

    settings = lib.mkOption {
      type = lib.types.submodule {
        freeformType = settingsFormat.type;

        # Only expose critical options:
        options.port = lib.mkOption {
          type = lib.types.port;
          default = 8080;
          description = "Port to listen on.";
        };
      };
      default = {};
      description = ''
        Configuration for My Service.
        See <https://example.com/docs/config> for all available options.
      '';
    };
  };

  config = lib.mkIf cfg.enable {
    # Set sensible defaults
    services.myservice.settings = {
      log_level = lib.mkDefault "INFO";
      data_dir = "/var/lib/myservice";  # Required, no mkDefault
    };

    environment.etc."myservice/config.json".source =
      settingsFormat.generate "myservice-config.json" cfg.settings;

    systemd.services.myservice = {
      description = "My Service";
      wantedBy = [ "multi-user.target" ];

      serviceConfig = {
        DynamicUser = true;
        StateDirectory = "myservice";
        ExecStart = "${pkgs.myservice}/bin/myservice --config /etc/myservice/config.json";
      };
    };
  };
}
```

## Format-Specific Examples

### JSON Configuration

```nix
let
  settingsFormat = pkgs.formats.json {};
in {
  options.services.myservice.settings = lib.mkOption {
    type = lib.types.submodule {
      freeformType = settingsFormat.type;

      options.database = lib.mkOption {
        type = lib.types.submodule {
          freeformType = settingsFormat.type;
          options = {
            host = lib.mkOption {
              type = lib.types.str;
              default = "localhost";
              description = "Database host";
            };
            port = lib.mkOption {
              type = lib.types.port;
              default = 5432;
              description = "Database port";
            };
          };
        };
        default = {};
        description = "Database configuration";
      };
    };
  };

  # Usage:
  services.myservice.settings = {
    database = {
      host = "db.example.com";
      port = 5432;
      # Any other upstream database options work too:
      pool_size = 20;
      timeout = 30;
    };
  };
}
```

### YAML Configuration

```nix
let
  settingsFormat = pkgs.formats.yaml {};
in {
  options.services.myservice.settings = lib.mkOption {
    type = lib.types.submodule {
      freeformType = settingsFormat.type;
    };
  };

  config = {
    environment.etc."myservice/config.yaml".source =
      settingsFormat.generate "myservice-config.yaml" cfg.settings;
  };
}
```

### TOML Configuration

```nix
let
  settingsFormat = pkgs.formats.toml {};
in {
  options.services.myservice.settings = lib.mkOption {
    type = lib.types.submodule {
      freeformType = settingsFormat.type;
    };
  };

  config = {
    environment.etc."myservice/config.toml".source =
      settingsFormat.generate "myservice-config.toml" cfg.settings;
  };
}
```

### INI Configuration

```nix
let
  # INI has special generator for sections
  settingsFormat = pkgs.formats.ini {};
in {
  options.services.myservice.settings = lib.mkOption {
    type = lib.types.submodule {
      freeformType = settingsFormat.type;
    };
  };

  # Usage:
  services.myservice.settings = {
    general = {
      log_level = "INFO";
      data_dir = "/var/lib/myservice";
    };
    database = {
      host = "localhost";
      port = 5432;
    };
  };
}
```

## Valuable Options Examples

### Main/Popular Options

**Options most users need for basic functionality:**

```nix
options.services.nginx = {
  enable = lib.mkEnableOption "nginx";

  # Main options - needed by most users
  virtualHosts = lib.mkOption {
    type = lib.types.attrsOf (lib.types.submodule { /* ... */ });
    default = {};
    description = "Virtual hosts configuration";
  };

  # Everything else in settings
  settings = lib.mkOption {
    type = lib.types.submodule {
      freeformType = settingsFormat.type;
    };
  };
};
```

### Mandatory Options

**Options that must be set for service to work:**

```nix
options.services.hydra = {
  enable = lib.mkEnableOption "Hydra continuous integration";

  # Mandatory - no default, must be set
  hydraURL = lib.mkOption {
    type = lib.types.str;
    description = "URL Hydra is reachable at (for links in emails, etc.)";
    example = "https://hydra.example.org";
  };

  settings = lib.mkOption {
    type = lib.types.submodule {
      freeformType = settingsFormat.type;
    };
  };
};

config = lib.mkIf cfg.enable {
  assertions = [{
    assertion = cfg.hydraURL != "";
    message = "services.hydra.hydraURL must be set";
  }];
};
```

### Sensitive Data Options

**Passwords, API keys, certificates:**

```nix
options.services.myservice = {
  enable = lib.mkEnableOption "My Service";

  # Sensitive - use *File pattern
  apiKeyFile = lib.mkOption {
    type = lib.types.externalPath;
    description = ''
      Path to a file containing the API key.

      The file is passed to the service with systemd's `LoadCredential`, so
      the service user doesn't need read access to it.
    '';
    example = "/run/secrets/myservice-api-key";
  };

  # Never do this:
  # apiKey = lib.mkOption { ... };  # Ends up in the world-readable Nix store

  settings = lib.mkOption {
    type = lib.types.submodule {
      freeformType = settingsFormat.type;
    };
  };
};

config = lib.mkIf cfg.enable {
  systemd.services.myservice.serviceConfig = {
    # Read the secret at runtime from $CREDENTIALS_DIRECTORY/api-key
    LoadCredential = "api-key:${cfg.apiKeyFile}";
  };
};
```

`types.externalPath` rejects a path that is already in the Nix store. See "Settings with Runtime Substitution" below for putting the secret into a generated config file.

## Migration Patterns

### From extraConfig to settings

**Before (old pattern):**
```nix
options.services.myservice = {
  enable = lib.mkEnableOption "My Service";

  port = lib.mkOption {
    type = lib.types.port;
    default = 8080;
  };

  logLevel = lib.mkOption {
    type = lib.types.str;
    default = "INFO";
  };

  extraConfig = lib.mkOption {
    type = lib.types.lines;
    default = "";
    description = "Extra configuration";
  };
};

config = lib.mkIf cfg.enable {
  environment.etc."myservice/config".text = ''
    port = ${toString cfg.port}
    log_level = ${cfg.logLevel}
    ${cfg.extraConfig}
  '';
};
```

**After (settings pattern):**
```nix
let
  settingsFormat = pkgs.formats.ini {};  # or appropriate format
in {
  options.services.myservice = {
    enable = lib.mkEnableOption "My Service";

    settings = lib.mkOption {
      type = lib.types.submodule {
        freeformType = settingsFormat.type;

        options.port = lib.mkOption {
          type = lib.types.port;
          default = 8080;
          description = "Port to listen on";
        };
      };
      default = {};
    };

    # Deprecated for backwards compatibility
    extraConfig = lib.mkOption {
      type = lib.types.lines;
      default = "";
      description = ''
        **Deprecated:** Use `services.myservice.settings` instead.

        This option will be removed in a future release.
      '';
    };
  };

  config = lib.mkIf cfg.enable {
    warnings = lib.optional (cfg.extraConfig != "") ''
      services.myservice.extraConfig is deprecated.
      Use services.myservice.settings instead:

      services.myservice.settings = {
        # your config here
      };
    '';

    services.myservice.settings.log_level = lib.mkDefault "INFO";

    environment.etc."myservice/config.ini".source =
      settingsFormat.generate "myservice-config" cfg.settings;
  };
}
```

### From Many Options to settings

**Before (option explosion):**
```nix
options.services.myservice = {
  enable = lib.mkEnableOption "My Service";
  port = lib.mkOption { /* ... */ };
  address = lib.mkOption { /* ... */ };
  logLevel = lib.mkOption { /* ... */ };
  logFile = lib.mkOption { /* ... */ };
  maxConnections = lib.mkOption { /* ... */ };
  timeout = lib.mkOption { /* ... */ };
  bufferSize = lib.mkOption { /* ... */ };
  enableFeatureA = lib.mkOption { /* ... */ };
  enableFeatureB = lib.mkOption { /* ... */ };
  featureAOption1 = lib.mkOption { /* ... */ };
  featureAOption2 = lib.mkOption { /* ... */ };
  featureBSetting = lib.mkOption { /* ... */ };
  # ... 20 more options ...
};
```

**After (settings pattern):**
```nix
let
  settingsFormat = pkgs.formats.json {};
in {
  options.services.myservice = {
    enable = lib.mkEnableOption "My Service";

    # Keep only valuable options
    port = lib.mkOption {
      type = lib.types.port;
      default = 8080;
      description = "Port to listen on";
    };

    settings = lib.mkOption {
      type = lib.types.submodule {
        freeformType = settingsFormat.type;
      };
      default = {};
      description = ''
        Configuration for My Service.
        See <https://example.com/docs> for all options.
      '';
    };

    # Deprecated old options (for backwards compatibility)
    logLevel = lib.mkOption {
      type = lib.types.nullOr lib.types.str;
      default = null;
      description = "**Deprecated:** Use settings.log_level instead";
    };
    # ... deprecate other old options similarly
  };

  config = lib.mkIf cfg.enable {
    # Map old options to settings for backwards compat
    services.myservice.settings = {
      port = cfg.port;
    } // lib.optionalAttrs (cfg.logLevel != null) {
      log_level = cfg.logLevel;
    };

    warnings = lib.optional (cfg.logLevel != null) ''
      services.myservice.logLevel is deprecated.
      Use services.myservice.settings.log_level instead.
    '';
  };
}
```

## Advanced Patterns

### Nested Settings with Type Safety

```nix
let
  settingsFormat = pkgs.formats.json {};
in {
  options.services.myservice.settings = lib.mkOption {
    type = lib.types.submodule {
      freeformType = settingsFormat.type;

      options = {
        server = lib.mkOption {
          type = lib.types.submodule {
            freeformType = settingsFormat.type;

            options.port = lib.mkOption {
              type = lib.types.port;
              default = 8080;
              description = "Server port";
            };
          };
          default = {};
          description = "Server configuration";
        };

        database = lib.mkOption {
          type = lib.types.submodule {
            freeformType = settingsFormat.type;

            options.host = lib.mkOption {
              type = lib.types.str;
              default = "localhost";
              description = "Database host";
            };
          };
          default = {};
          description = "Database configuration";
        };
      };
    };
  };

  # Usage:
  services.myservice.settings = {
    server = {
      port = 9000;
      workers = 4;  # Any upstream option works
    };
    database = {
      host = "db.example.com";
      pool_size = 20;  # Any upstream option works
    };
  };
}
```

### Settings with Runtime Substitution

```nix
config = lib.mkIf cfg.enable {
  # Placeholder in settings; the real value is substituted at start
  services.myservice.settings.password = "@password@";

  systemd.services.myservice.serviceConfig =
    let
      baseConfig = settingsFormat.generate "myservice-base-config" cfg.settings;
    in
    {
      DynamicUser = true;
      LoadCredential = "password:${cfg.passwordFile}";
      RuntimeDirectory = "myservice";
      RuntimeDirectoryMode = "0700";

      # install copies the store file with a writable mode; replace-secret
      # then edits the copy in place
      ExecStartPre = [
        "${lib.getExe' pkgs.coreutils "install"} -m 600 ${baseConfig} \"\${RUNTIME_DIRECTORY}/config.json\""
        "${lib.getExe pkgs.replace-secret} '@password@' \"\${CREDENTIALS_DIRECTORY}/password\" \"\${RUNTIME_DIRECTORY}/config.json\""
      ];

      ExecStart = "${lib.getExe pkgs.myservice} --config \${RUNTIME_DIRECTORY}/config.json";
    };
};
```

The substituted file lives in a `0700` runtime directory owned by the service user, and the secret never enters the Nix store. `utils.genJqSecretsReplacementSnippet` is an alternative when the secret sits at a nested path in the settings attrset.

### Settings with Validation

```nix
options.services.myservice.settings = lib.mkOption {
  type = lib.types.submodule {
    freeformType = settingsFormat.type;

    options.port = lib.mkOption {
      type = lib.types.port;
      default = 8080;
    };
  };
  default = {};
};

config = lib.mkIf cfg.enable {
  assertions = [
    {
      assertion = cfg.settings.port > 1024 || cfg.settings ? bind_to_privileged;
      message = ''
        services.myservice.settings.port < 1024 requires
        services.myservice.settings.bind_to_privileged = true
      '';
    }
  ];
};
```

## Common Mistakes

### Don't: Mix individual options with settings

```nix
# Bad: Duplicates port setting in two places
options.services.myservice = {
  port = lib.mkOption { /* ... */ };
  settings = lib.mkOption { /* has port field too */ };
};
```

```nix
# Good: Port is only in settings
options.services.myservice = {
  settings = lib.mkOption {
    type = lib.types.submodule {
      freeformType = settingsFormat.type;
      options.port = lib.mkOption { /* ... */ };
    };
  };
};
```

### Don't: Set defaults inside option definition

```nix
# Bad: the default is dropped as soon as a user sets any key in settings
options.services.myservice.settings = lib.mkOption {
  default = {
    log_level = "INFO";  # Can't use mkDefault here
  };
};
```

```nix
# Good: Set defaults in config section
options.services.myservice.settings = lib.mkOption {
  default = {};
};

config = lib.mkIf cfg.enable {
  services.myservice.settings.log_level = lib.mkDefault "INFO";
};
```

### Don't: Create option for every upstream setting

```nix
# Bad: 50+ individual options
options.services.myservice = {
  upstreamOption1 = lib.mkOption { /* ... */ };
  upstreamOption2 = lib.mkOption { /* ... */ };
  upstreamOption3 = lib.mkOption { /* ... */ };
  # ... 47 more ...
};
```

```nix
# Good: Settings pattern with selective options
options.services.myservice = {
  # Only valuable options
  port = lib.mkOption { /* ... */ };

  # Everything else
  settings = lib.mkOption {
    type = lib.types.submodule {
      freeformType = settingsFormat.type;
    };
  };
};
```

## Decision Flowchart

```
Does service use a config file?
├─ No → Use individual options or command-line args
└─ Yes → Can format be mapped to Nix (JSON/YAML/TOML/INI)?
    ├─ No → Use templating or string-based config
    └─ Yes → Will module have >10-15 total options?
        ├─ No → Individual options OK
        └─ Yes → Use settings pattern
            └─ Which options to expose explicitly?
                ├─ Main/popular (>50% users need)
                ├─ Mandatory (no sensible default)
                └─ Sensitive (passwords, keys)
```

The NixOS manual's convention is broader than this flowchart: for any Nix-representable format (JSON, YAML, TOML, INI and similar) it says to expose a generic `settings` option. The ">10-15 options" cut-off isn't in the manual, so treat it as a heuristic for when individual options are still tolerable.

## References

- [RFC 0042](https://github.com/NixOS/rfcs/blob/master/rfcs/0042-config-option.md) - Full specification
- [NixOS Manual: Options for Program Settings](https://nixos.org/manual/nixos/stable/index.html#sec-settings-options)
- [NixOS Manual: Freeform Modules](https://nixos.org/manual/nixos/stable/index.html#sec-freeform-modules)
- [`pkgs.formats` source](https://github.com/NixOS/nixpkgs/blob/master/pkgs/pkgs-lib/formats.nix) - the manual's settings chapter lists the generators (`json`, `yaml`, `toml`, `ini`, `keyValue`, `hocon`, `libconfig`, `lua`, `php`, `xml`, and more)
