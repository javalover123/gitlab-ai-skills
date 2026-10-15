# NixOS modules for nixpkgs

Load this when you add, change, rename, or test a module under `nixos/modules/` in nixpkgs. For the RFC 42 design theory and option-count judgement, read [module design](module-design.md) and the [RFC summary](rfc-summary.md); the tickbox version is `../assets/module-design-checklist.md`. For configuring a machine rather than writing a module, see [NixOS systems](nixos-systems.md). Secrets and supply-chain rules live in [security](security.md).

Everything below was checked against nixpkgs master (the 26.11 development cycle) and its NixOS manual. Where an older reference file disagrees, this file wins and the conflict is listed at the end.

**Contents:** [Where the pieces go](#where-the-pieces-go) · [A module that follows current conventions](#a-module-that-follows-current-conventions) · [Declaring options](#declaring-options) · [The `settings` pattern (RFC 42)](#the-settings-pattern-rfc-42) · [`mkIf`, `mkMerge`, and priorities](#mkif-mkmerge-and-priorities) · [Service definition](#service-definition) · [Hardening](#hardening) · [Secrets](#secrets) · [Assertions and warnings](#assertions-and-warnings) · [Deprecating and removing options](#deprecating-and-removing-options) · [Tests](#tests) · [Modular services](#modular-services) · [Checkable rules](#checkable-rules) · [Evidence](#evidence) · [Dated advice to ignore](#dated-advice-to-ignore)

## Where the pieces go

| Piece | Location | Notes |
|---|---|---|
| Module | `nixos/modules/<category>/<name>.nix` | Categories in use: `services/<area>/`, `programs/`, `hardware/`, `security/`, `virtualisation/`, `system/`, `misc/`. File names are kebab-case. |
| Registration | `nixos/modules/module-list.nix` | Entries sit between `# keep-sorted start` and `# keep-sorted end`; insert yours in sorted order. A module that isn't listed isn't imported by default. |
| Option path | `services.<name>`, `programs.<name>` | camelCase, except when the segment names a package: then it matches the package attribute (`services.nix-serve`). |
| Prose docs | `meta.doc = ./<name>.md;` | Optional Nixpkgs-flavored CommonMark added to the manual. Check it with `nix-build nixos/release.nix -A manual.x86_64-linux`. |
| Test | `nixos/tests/<name>.nix` plus an entry in `nixos/tests/all-tests.nix` | See "Tests" below. |
| Release note | `nixos/doc/manual/release-notes/rl-<YYMM>.section.md` | Use the file for the release in development. |
| Commit title | `nixos/<module>: <what changed>` | From `nixos/README.md`, for example `nixos/example: init module` or `nixos/example: add setting`. |

CONTRIBUTING asks for a release note when you add or remove a module or make another breaking or significant NixOS change. The release-notes file has four sections: `## Highlights`, `## New Modules`, `## Backward Incompatibilities`, `## Other Notable Changes`. The files tell you to add your entry anywhere in the list, not at the end, to avoid merge conflicts. A new-module entry has this shape:

```markdown
- [Example](https://example.com/), a demonstration daemon. Available as [services.example](#opt-services.example.enable).
```

## A module that follows current conventions

This skeleton evaluates on current nixpkgs with a stub package (it was checked with `nix eval` on a NixOS system, not run as a VM). It shows the usual order: `options`, then `config = mkIf cfg.enable`, then `meta`.

```nix
{
  config,
  lib,
  pkgs,
  utils,
  ...
}:
let
  cfg = config.services.example;
  settingsFormat = pkgs.formats.toml { };
  configFile = settingsFormat.generate "example.toml" cfg.settings;
in
{
  options.services.example = {
    enable = lib.mkEnableOption "example, a demonstration daemon";

    package = lib.mkPackageOption pkgs "example" { };

    settings = lib.mkOption {
      type = lib.types.submodule {
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

  config = lib.mkIf cfg.enable {
    services.example.settings.log_level = lib.mkDefault "info";

    networking.firewall.allowedTCPPorts = lib.mkIf cfg.openFirewall [ cfg.settings.listen_port ];

    systemd.services.example = {
      description = "Example daemon";
      wantedBy = [ "multi-user.target" ];
      after = [ "network.target" ];
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
        DynamicUser = true;
        StateDirectory = "example";
        RuntimeDirectory = "example";
        LoadCredential = lib.optional (cfg.tokenFile != null) "token:${cfg.tokenFile}";

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

  meta.maintainers = [ ];
}
```

Put your handle in `meta.maintainers` (`with lib.maintainers; [ yourhandle ]`). The module meta attributes are `maintainers`, `doc`, and `buildDocsInSandbox`, each defined at most once per file. Leave `buildDocsInSandbox` at its default of `true` unless option docs need `config` or the full `pkgs`; a sandboxed doc build only lets descriptions reach `options`, `lib`, and `pkgs.formats`.

## Declaring options

The manual calls `type` mandatory for nixpkgs modules, and the fallback type has unspecified behaviour. An option without `default` must be set by the user or evaluation fails: right for a public URL, wrong for anything optional.

`lib.mkEnableOption "name"` takes one string and yields a `bool` option defaulting to `false`, described as "Whether to enable name." Pass the noun phrase only: `"the example daemon"`, or `"example, a demonstration daemon"`. Markdown links work in it.

`lib.mkPackageOption pkgs name { ... }` yields a `package` option with `defaultText` already set. The third argument is mandatory, even when empty.

| Argument | Meaning |
|---|---|
| `default` | Attribute path as a string or list of strings (`[ "python3Packages" "foo" ]`); omit it when `name` is the attribute. `null` means no default. |
| `nullable` | `true` makes the type `nullOr package`, so users can switch the package off. |
| `example` | String or attribute path, rendered as a `literalExpression`. |
| `extraDescription` | Appended to "The X package to use." |
| `pkgsText` | How to display a non-`pkgs` package set in docs. |

Reviewers commonly ask for `package` options because overlays slow evaluation and are harder to debug (the manual says so directly). `mkPackageOption` also covers the case of several implementations: document how to switch and make sure the generated config works with each.

Pick the type for how definitions should merge:

| Need | Type | Behaviour (measured where noted) |
|---|---|---|
| Free text appended into a config file | `types.lines` | Definitions concatenate, so two modules can both contribute. |
| One string | `types.str` | Two definitions fail with "conflicting definition values". |
| Port, non-empty string | `types.port`, `types.nonEmptyStr` | |
| Secret or credential path | `types.externalPath`, usually `nullOr` | Rejects a path already in the store ("not in the Nix store"), accepts `/run/secrets/x`. It only checks the current value, so don't interpolate it into a store path. |
| Any absolute path | `types.path` | A path literal like `./secret` is accepted and then copied into the store when interpolated. |
| Fixed choices; optional value that defers to upstream | `types.enum [ ... ]`; `types.nullOr T` with `default = null` | |
| Structured program config | `format.type` through `settings` | See the next section. |
| Argument list | `types.listOf types.str` | Escape on use. |

`types.loaOf` still exists but carries a deprecation message; use `types.attrsOf`.

### Documentation attributes

- `description` is Nixpkgs-flavored CommonMark. Write it as a plain `''...''` string. The inline roles are `` {option}`a.b` ``, `` {file}`/etc/x` ``, `` {command}`x` ``, `` {env}`X` ``, `` {var}`x` ``, and `` {manpage}`x(5)` ``. Headings aren't supported in option descriptions, and raw HTML is forbidden.
- `example` and `defaultText` are for values the manual can't compute (anything depending on `config`, `pkgs`, or another option). Wrap them: `lib.literalExpression "..."` for Nix code, `lib.literalMD "..."` for prose.
- A bare string in `defaultText` or `example` doesn't render as code. `lib.options.renderOptionValue` pretty-prints it as a quoted Nix string, so `defaultText = "cfg.x != null"` appears as `"cfg.x != null"` in the manual (measured). Use `lib.literalExpression "cfg.x != null"`.
- Don't put absolute store paths in docs; `literalExpression` with a `pkgs.` reference or `defaultText` avoids that.

## The `settings` pattern (RFC 42)

For programs configured with a Nix-representable file (JSON, YAML, TOML, INI, and so on), expose one `settings` option typed by a `pkgs.formats.*` generator, as in the skeleton. Every format returns `{ type; generate; lib?; }`, where `generate name value` returns a store file. The manual lists `json`, `yaml`, `toml`, `ini`, `iniWithGlobalSection`, `javaProperties`, `hocon`, `hcl1`, `libconfig`, `xml`, `plist`, `configobj`, `pythonVars`, `cdn`, `elixirConf`, `lua`, and `php`. Several of them carry `lib` helpers for values Nix can't express (`mkRaw`, `mkAtom`, `mkInclude`, and similar).

- `type = settingsFormat.type` alone gives correct merging. To type-check or document selected keys, use `types.submodule { freeformType = settingsFormat.type; options.<key> = ...; }`.
- Set required or helpful values in `config` with `mkDefault` (changeable) or plainly (required, for example a path that matches `StateDirectory`). A `default = { ... }` on the option is dropped wholesale as soon as a user sets any key, so it can't carry per-key defaults.
- Freeform keys can't depend on sibling keys: `settings.logLevel = mkIf (config.settings.port == 80) ...` is an infinite recursion. Declare an option for any key that needs to read another.
- `generate` writes into the Nix store, which is world-readable. Keep secrets out of `settings`; see "Secrets".
- For formats that aren't Nix-representable, the manual says there's no fixed convention: a `configFile` option plus an optional `extraConfig` of type `lines` is typical.
- Don't expose every upstream key as an option. Typed options are for the main ones, the mandatory ones, and secrets; the rest is `settings`. [Module design](module-design.md) has the full criteria and migration recipes.

## `mkIf`, `mkMerge`, and priorities

- Wrap `config` in `lib.mkIf cfg.enable`. Combine independent chunks with `lib.mkMerge [ ... ]` and a `mkIf` per chunk.
- Never choose attribute names with `if` or `lib.optionalAttrs` on a value read from `config`. Evaluating `config` needs the attribute names of every module's `config`, so this recurses. Measured: `config = { feature.enable = true; } // lib.optionalAttrs config.feature.enable { ... }` fails with "infinite recursion encountered"; the same body under `mkIf` evaluates. Conditional entries in `imports` that read `config` fail the same way; import unconditionally and gate with `mkIf`.

```nix
{ config, lib, ... }:
let
  cfg = config.services.example;
in
{
  config = lib.mkMerge [
    (lib.mkIf cfg.enable { systemd.services.example.wantedBy = [ "multi-user.target" ]; })
    (lib.mkIf (cfg.enable && cfg.openFirewall) {
      networking.firewall.allowedTCPPorts = [ cfg.settings.listen_port ];
    })
  ];
}
```

Priorities (lower wins): `mkForce` = 50, a normal definition = 100, `mkDefault` = 1000, an option's own `default` = 1500 (`mkOptionDefault`). `mkBefore` and `mkAfter` order list and `lines` definitions (500 and 1500), which is how modules contribute to the same file. Modules set `mkDefault` for what users may reasonably change; they don't use `mkForce` on user-facing options.

## Service definition

- Directories: `StateDirectory`, `RuntimeDirectory`, `CacheDirectory`, `LogsDirectory` instead of `mkdir`/`chown` in `preStart` or `systemd.tmpfiles.rules`. The activation-script chapter says the same: the script runs on every boot and switch, so use systemd mechanisms or `preStart` only if nothing else works. Use tmpfiles for paths outside a service's own directories.
- Upstream units: when a package ships its units in `lib/systemd/system`, put the package in `systemd.packages` rather than copying the unit into the module. Installing the package in `environment.systemPackages` doesn't register units. Anything you set under `systemd.services.<name>` becomes a drop-in (`overrideStrategy` defaults to `asDropinIfExists`), and `wantedBy` still has to be set there.
- Ordering: `after = [ "network.target" ]` doesn't mean the network is up. If the service needs connectivity at start, use both `wants` and `after` on `network-online.target`; since 25.05 `multi-user.target` no longer pulls it in. Don't add it by default.
- Arguments: `Exec*` lines undergo `%` specifier expansion, `$VAR` expansion, and whitespace and `;` splitting. Build them with `utils.escapeSystemdExecArgs` (list) or `utils.escapeSystemdExecArg` (one value), and don't disable environment substitution to compensate. Inside `script`, `lib.escapeShellArg` and `lib.escapeShellArgs` are the right tools.
- Reload on change: `restartTriggers = [ configFile ]` (or `reloadTriggers`) so a changed generated file restarts the unit.
- Don't use import-from-derivation in a module; `pkgs/README.md` disallows it in nixpkgs for evaluation performance and CI evaluates with `allow-import-from-derivation false`.

### Users and groups

Order of preference, from RFC 52 and the header of `nixos/modules/misc/ids.nix`:

1. `DynamicUser = true` with `StateDirectory`, as in the skeleton. systemd then also implies `PrivateTmp`, `RemoveIPC`, `NoNewPrivileges`, `RestrictSUIDSGID`, `ProtectSystem=strict`, and `ProtectHome=read-only` (per `systemd.exec(5)`). State lives under `/var/lib/private/<name>` with a symlink at `/var/lib/<name>`. It doesn't fit services that share files with others, need a fixed user name, or claim a D-Bus name.
2. A system user with no fixed IDs: `users.users.example = { isSystemUser = true; group = "example"; };` plus `users.groups.example = { };`. `group` must be set or evaluation asserts. NixOS allocates a persistent UID from 400 to 999 downward and remembers it in `/var/lib/nixos/uid-map`.
3. A static `uid`/`gid` only when IDs must match across hosts or the application hardcodes them. That means an entry in `nixos/modules/misc/ids.nix`, which says static IDs are deprecated and need a stated reason.
4. `root`, only with a comment saying why and a tight `CapabilityBoundingSet`.

If users may choose the account, expose `user` and `group` options and wrap `users.users.${cfg.user}` in `mkIf (cfg.user == "example")`.

### `system.stateVersion`

The manual discourages new direct uses of `config.system.stateVersion` in a module. When you must change state-affecting behaviour for existing installs, declare `stateRevision = utils.mkStateRevisionOption { descriptionName = "..."; migrations = { ... }; }`, branch on `cfg.stateRevision`, and register it in `system.moduleStateRevisions."services.example.stateRevision"` inside the `mkIf cfg.enable`. Plenty of existing modules still compare `lib.versionOlder config.system.stateVersion "..."`, and `nixos/README.md` still shows `lib.versionAtLeast` in its review checklist. Those two documents disagree; follow the manual's section.

## Hardening

DynamicUser covers part of the list. The skeleton's directives are a reasonable starting point for a network daemon, and reviewers commonly ask for them when a module ships none. Check each against what the daemon does: run the VM test, then `systemd-analyze security example.service` for the exposure score, and comment any directive you leave out. [Security hardening](security-hardening.md) has longer templates, with the corrections listed at the end of this file.

## Secrets

Never interpolate a secret into `settings`, `environment.etc.*.text`, `pkgs.writeText`, `Environment=`, or an `ExecStart` string: all of those land in the world-readable Nix store. Options for runtime delivery:

- `LoadCredential = "name:${cfg.fooFile}"` plus `$CREDENTIALS_DIRECTORY/name` (the skeleton). Per `systemd.exec(5)` the data is readable only by the unit's user (and root), is exposed as a read-only file, and is backed by non-swappable memory where possible.
- `EnvironmentFile = cfg.environmentFile` for programs that only read the environment. Document the variable names and the file format.
- `utils.genJqSecretsReplacementSnippet` (with a `_secret` marker in an attrset) or `pkgs.replace-secret` to patch a placeholder in a generated file at start time, written to a `RuntimeDirectory`. `utils.genJqSecretsReplacement` can also produce `LoadCredential` entries.
- `LoadCredentialEncrypted` takes credentials encrypted with `systemd-creds` (bound to the TPM2 or a host key) and decrypts them only when the unit starts.

Name the option `<thing>File` and type it `nullOr types.externalPath`. Option descriptions should say how the file is read and who needs access. Hashed passwords for users go through `users.users.<name>.hashedPasswordFile`.

## Assertions and warnings

- Use `assertions = [ { assertion = ...; message = "..."; } ]` for impossible configurations (mutually exclusive options, a secret option unset while another requires it). Don't `throw` or `abort` from a module.
- Use `warnings = [ "..." ]` or `lib.optional cond "..."` for configurations that work but are risky or deprecated.
- Prefix messages with the option path so users can find the cause.
- Put both inside the `mkIf cfg.enable` block, so a disabled module can't fail evaluation.

```nix
{ config, lib, ... }:
let
  cfg = config.services.example;
in
{
  config = lib.mkIf cfg.enable {
    assertions = [
      {
        assertion = (cfg.settings ? user) == (cfg.settings ? password_file);
        message = "services.example: settings.user and settings.password_file must be set together.";
      }
    ];
    warnings = lib.optional (cfg.settings ? password) "services.example.settings.password ends up in the Nix store; use services.example.tokenFile.";
  };
}
```

## Deprecating and removing options

Don't break existing configurations silently. All of these ship in `lib` and were checked by evaluation:

| Situation | Function | Behaviour |
|---|---|---|
| Option moved | `mkRenamedOptionModule [ old ] [ new ]` | Forwards the value (and its priority) and warns whenever the old name is used. |
| Option moved, warn later | `mkRenamedOptionModuleWith { sinceRelease; from; to; }` | `sinceRelease` is an integer such as `2611`. It warns only once the oldest supported release is at least that, so users on stable don't see it early. The `nixos/README.md` review checklist names this one. |
| Type or semantics changed | `mkChangedOptionModule [ old ] [ new ] (config: value)` | Warns and computes the new value from the old. `mkMergedOptionModule` merges several old options. |
| Option gone | `mkRemovedOptionModule [ path ] "instructions"` | Fails evaluation with your instructions if it's still defined. Always give instructions. |
| Alias, no warning | `mkAliasOptionModule [ old ] [ new ]` | Keeps the old name visible in docs. |

```nix
{ lib, ... }:
{
  imports = [
    (lib.mkRenamedOptionModuleWith {
      sinceRelease = 2611;
      from = [ "services" "example" "logLevel" ];
      to = [ "services" "example" "settings" "log_level" ];
    })
    (lib.mkRemovedOptionModule [ "services" "example" "setupNginx" ]
      "Configure your own reverse proxy and point it at services.example.settings.listen_port."
    )
  ];
}
```

Put these in the module's own `imports`. `nixos/modules/rename.nix` is only for cases where the owning module no longer exists. The renamed "to" option must already exist and the "from" option must not be declared. Every removal or incompatible rename also needs a "Backward Incompatibilities" release note. Don't guard option renames with `config.allowAliases`; that flag belongs to `pkgs/top-level/aliases.nix`, and nothing under `nixos/modules` uses it.

## Tests

Add a NixOS test with every new module. CONTRIBUTING asks you to run the existing tests that apply, and reviewers commonly ask for a new one when none exists. New tests are modules passed to `runTest`:

- Create `nixos/tests/example.nix` as shown below. Use `nodes.<name>` for QEMU VMs or `containers.<name>` for systemd-nspawn; VMs are needed for kernel features, setuid binaries, systemd sandboxing options such as `ProtectSystem=`, and specialisations.
- Register it in `nixos/tests/all-tests.nix` as `example = runTest ./example.nix;`, in alphabetical order inside the `keep-sorted` block. Use `handleTest` or `import ../make-test-python.nix` only when editing an existing test that already uses them (about a hundred entries remain); `handleTest` is documented as deprecated.
- Run it with `nix-build -A nixosTests.example` from the nixpkgs root. `nix-build -A nixosTests.example.driverInteractive` builds an interactive driver (`result/bin/nixos-test-driver`), documented in the manual's interactive-testing section.
- In-tree tests run with read-only `pkgs` and `nix.enable = false`. If a test sets any `nixpkgs.*` option it must also set `node.pkgsReadOnly = false;`; without that, evaluation fails with "defined multiple times" (measured).
- Tests have a `meta.maintainers` option and most in-tree tests set it. The test script is linted with Pyflakes and type-checked with Mypy at build time; `skipLint` and `skipTypeCheck` are for local iteration only.
- Link the test from the package with `passthru.tests = { inherit (nixosTests) example; };` so changes to the package run it. `nixosTests` is a package argument.

```nix
{ lib, ... }:
{
  name = "example";
  meta.maintainers = [ ];

  nodes.machine =
    { pkgs, ... }:
    {
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
```

Outside nixpkgs the entry point is `pkgs.testers.runNixOSTest ./test.nix`. [Testing](testing.md) covers the wider test strategy and [VM tests](vm-tests.md) covers flake `checks`.

Keep the test small: boot the service with a minimal config, wait for the unit and a port, make one real request, and supply a credential file if the module has a secret option. Add a second node for client/server or database integrations.

## Modular services

`system.services.<name>` is a newer, service-manager-agnostic mechanism; the manual marks it "in development" and says to expect significant changes. Don't convert existing modules. If you're asked to write one, follow `nixos/README-modular-services.md`: a service module declares `_class = "service"`, keeps systemd-specific settings behind `lib.optionalAttrs (options ? systemd)`, sets `meta.maintainers`, ships a VM test, and gets listed in `nixos/modules/misc/documentation/modular-services.nix`.

## Checkable rules

- Every option declared with `mkOption` has `type`; options with computed defaults have `defaultText = lib.literalExpression ...`; examples that aren't plain data use `literalExpression` or `literalMD`.
- No `lib.mdDoc` and no DocBook (`<link xlink:href=...>`, `<literal>`) in descriptions.
- The module appears in `module-list.nix`, and `all-tests.nix` has an entry for its test.
- `config` is `lib.mkIf cfg.enable { ... }` or a `mkMerge` of `mkIf`s; no `optionalAttrs` or `if` on `config` values at attribute-name level.
- Enable options come from `mkEnableOption` and package options from `mkPackageOption`.
- No secret value is interpolated into a store path, unit file, or `Environment`; secrets arrive through a `*File` option and `LoadCredential`, `EnvironmentFile`, or runtime replacement.
- Services set `DynamicUser = true` or a documented `User`/`Group`; no `uid`/`gid` without an `ids.nix` entry and a stated reason.
- Service directories use `StateDirectory`, `RuntimeDirectory`, `CacheDirectory`, or `LogsDirectory`, not `mkdir` in `preStart`.
- `Exec*` arguments built from options go through `utils.escapeSystemdExecArgs`; shell snippets go through `lib.escapeShellArg(s)`.
- Impossible combinations use `assertions`; removed or renamed options use `mkRemovedOptionModule` or `mkRenamedOptionModule(With)`.
- A test that touches `nixpkgs.*` sets `node.pkgsReadOnly = false`.
- A release note exists for new modules and for backward-incompatible changes.

## Evidence

Counts from `find-rules.py` (support = PRs backing the rule, cr = PRs with a formal changes-requested review). They show what reviewers raise, not what causes merges.

| Rule | support | cr |
|---|---|---|
| Use `RuntimeDirectory`/`StateDirectory` instead of manual tmpfiles | 58 | 23 |
| Use `systemd.packages` instead of duplicating units | 56 | 22 |
| RFC 42 `settings` instead of ad-hoc string templating | 42 | 20 |
| Default optional features to off | 80 | 17 |
| Don't add options for unjustified or unimplemented features | 57 | 17 |
| Merge with `mkMerge` rather than overriding | 63 | 15 |
| Typed options with `types.*` | 53 | 15 |
| Avoid manual uid/gid; use `DynamicUser` or `users.users` | 22 | 11 |

## Dated advice to ignore

- `lib.mdDoc` in option descriptions: deprecated in 24.05, removed in 24.11 (release notes). The manual and in-tree modules use plain strings, so the review-derived "must use `lib.mdDoc`" rule is obsolete. `mkAliasOptionModuleMD` is a deprecated alias of `mkAliasOptionModule`.
- DocBook markup such as `<link xlink:href="..."/>` in descriptions (still shown in `rfc-summary.md`). Use Markdown.
- `nixosTest { ... }`: `code-patterns.md` puts `passthru.tests.x = nixosTest ...` inside a module's `config`, and `common-mistakes.md` and the module checklist use `nixosTest` for package tests. `passthru` is a package attribute, so a module can't have one. The top-level `nixosTest` alias now throws (the function lives at `testers.nixosTest`); write `runTest` in nixpkgs and `testers.runNixOSTest` elsewhere, and link from packages with `nixosTests`.
- `preStart` with `mkdir`/`chown` plus `DynamicUser = false` (the `code-patterns.md` module template) contradicts the directory rule above.
- `security-hardening.md`: it lists `ProtectHome = true` as "automatic" with `DynamicUser` (systemd implies `ProtectHome=read-only`); it says DynamicUser gives "state cleanup on service removal" (state persists under `/var/lib/private`); and it shows a static UID declared directly in `users.users` (static IDs belong in `nixos/modules/misc/ids.nix`, and are deprecated).
- "Deprecate options with `lib.optionalAttrs config.allowAliases`": that pattern is for `pkgs` aliases. No NixOS module uses it.
- `types.loaOf`: deprecated; use `types.attrsOf`.
- `with lib;` at the top of a module (still present in older modules); use `lib.` prefixes or `inherit (lib)`.
- "Enum types must be exhaustive and duplicate-free" (review guide) names no mechanical check; don't treat it as a rule.
- `rfc-summary.md` lists six `pkgs.formats` generators; the manual lists seventeen.
