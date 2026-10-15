# Working on NixOS systems

Load this when you're configuring, building, deploying, or debugging a NixOS machine (typically a flake exposing `nixosConfigurations`), as opposed to writing a module for nixpkgs. For module authoring see [NixOS modules](nixos-modules.md); for flake structure see [flake layout](flake-layout.md); for trust questions about inputs and secrets see [security](security.md).

Commands and options below were checked against the `nixos-rebuild` man page in nixpkgs master, `nix` 2.34 `--help` output, and by evaluating small flakes against nixpkgs master (the 26.11 cycle). Where something was evaluated rather than documented, it says "measured".

**Contents:** [A flake-based host](#a-flake-based-host) · [`nixos-rebuild`](#nixos-rebuild) · [Changing a machine safely](#changing-a-machine-safely) · [Evaluating without building](#evaluating-without-building) · [`system.stateVersion`](#systemstateversion) · [Generations, rollback, specialisations](#generations-rollback-specialisations) · [Packages in a configuration: `nixpkgs.*`, overlays, overrides](#packages-in-a-configuration-nixpkgs-overlays-overrides) · [Nix daemon settings, pinning, and cleanup](#nix-daemon-settings-pinning-and-cleanup) · [Secrets](#secrets) · [Home Manager](#home-manager) · [Checkable rules](#checkable-rules) · [Dated advice to ignore](#dated-advice-to-ignore)

## A flake-based host

```nix
{
  description = "Example fleet";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs =
    { self, nixpkgs }:
    let
      mkHost =
        name: system:
        nixpkgs.lib.nixosSystem {
          modules = [
            ./hosts/${name}
            { nixpkgs.hostPlatform = system; }
          ];
          specialArgs = { inherit self; };
        };
    in
    {
      nixosConfigurations.alpha = mkHost "alpha" "x86_64-linux";

      # nix flake check only evaluates nixosConfigurations; a check builds one.
      checks.x86_64-linux.alpha = self.nixosConfigurations.alpha.config.system.build.toplevel;
    };
}
```

- `nixpkgs.lib.nixosSystem` takes `modules`, `specialArgs`, and `modulesLocation`. It sets `system = null`, so something must set `nixpkgs.hostPlatform`; without it evaluation stops with "Neither nixpkgs.hostPlatform nor the legacy option nixpkgs.system has been set" (measured). The generated `hardware-configuration.nix` normally sets it. `system` and `pkgs` arguments are legacy. `nixosSystem` also sets `nixpkgs.flake.source`, which in turn sets `NIX_PATH` to `nixpkgs=flake:nixpkgs` and pins the registry entry `nixpkgs` to the input you built from (both measured; the options are `nixpkgs.flake.setNixPath` and `nixpkgs.flake.setFlakeRegistry`).
- New files in a git-tracked flake must be `git add`ed before Nix sees them: "Path 'x.nix' in the repository is not tracked by Git" (measured).
- Pass values that `imports` needs through `specialArgs`. Module arguments set through `_module.args` aren't available in `imports`; using one there fails with "infinite recursion encountered" (measured, as does reading `config` there). `lib.nixosSystem`'s old `extraArgs` and `check` arguments were removed in 26.11: use `config._module.args` and `_module.check = false`.
- Record the revision with `system.configurationRevision = self.rev or self.dirtyRev or null;` so `nixos-version --configuration-revision` and `nixos-rebuild list-generations` can show which commit built a generation.

Layout that scales: one directory per host (`hosts/<name>/default.nix` importing `configuration.nix` and `hardware-configuration.nix`), reusable pieces in `modules/` exposed as `nixosModules.<name>`, overlays in `overlays/`, and a `mkHost` helper like the one above. [Flake layout](flake-layout.md) and [flake frameworks](flake-frameworks.md) cover the rest.

The nixpkgs flake also exports two helper modules: `nixosModules.notDetected` (enables redistributable firmware on hardware `nixos-generate-config` didn't recognise) and `nixosModules.readOnlyPkgs`, covered below.

## `nixos-rebuild`

The current implementation is documented in `pkgs/by-name/ni/nixos-rebuild-ng/nixos-rebuild.8.scd`.

| Subcommand | What it does |
|---|---|
| `switch` | Build, activate, and make it the boot default. |
| `boot` | Build and make it the boot default; the running system is untouched until reboot. |
| `test` | Build and activate without a boot entry. A reboot reverts to the last `switch`/`boot` configuration. |
| `build` | Build and leave `./result`; needs no root. |
| `dry-build` | Show what would be built or fetched. |
| `dry-activate` | Build, then list what activation would do (restarted units, for instance). The list isn't guaranteed complete. |
| `build-vm` | Build a script that starts the configuration in QEMU: `./result/bin/run-<host>-vm`. |
| `build-vm-with-bootloader` | Same, but boots through the real boot loader. |
| `build-image` | Build a disk image variant; `--image-variant` picks it, and running with none lists the variants. |
| `repl` | Open the configuration in `nix repl` (`config` is bound; `:r` reloads). |
| `list-generations [--json]` | List generations with number, date, NixOS and kernel versions, and configuration revision. |

Flags you'll use (all in the man page):

| Flag | Notes |
|---|---|
| `--flake <uri>[#name]` | Defaults to the target of the `/etc/nixos/flake.nix` symlink, with `name` defaulting to the host name. `--no-flake` ignores that default. |
| `--target-host [user@]host` | Activate over SSH. `switch`, `boot`, and `test` need root there. |
| `--build-host [user@]host` | Build remotely. Without `--target-host` the result is copied back. `NIX_SSHOPTS` passes SSH options. |
| `--elevate {none,sudo,run0}` | How activation commands get privileges, which lets you deploy as a non-root user. `--sudo` is an alias for `--elevate=sudo`; `--ask-elevate-password` (`-S`) prompts for the password. `--use-remote-sudo` is deprecated. |
| `--diff` | Show the closure diff against `/run/current-system` (for `build`, `boot`, `test`, `switch`). |
| `--rollback` | Switch to the previous generation of the `/nix/var/nix/profiles/system` profile. |
| `--specialisation <name>` (`-c`) | Activate a specialisation. A bare `switch` or `test` goes back to the base system. |
| `--profile-name <name>` (`-p`) | Keep a separate profile, shown in its own boot submenu. |
| `--store-path <path>` | Activate a closure that was built elsewhere (CI, a build host). Works with `switch`, `boot`, `test`, `dry-activate`; excludes `--flake`, `--rollback`, `--file`, `--attr`. |
| `--use-substitutes` | Add `--use-substitutes` to `nix copy` when a remote host is involved. |
| `--no-reexec` | `nixos-rebuild` normally builds and re-executes the version belonging to the target configuration; this disables that. |
| `--install-bootloader` | Reinstall the boot loader. |

Flake flags pass through (`--override-input`, `--no-update-lock-file`, `--no-write-lock-file`, `--commit-lock-file`, `--refresh`, `--accept-flake-config`, `--impure`, `--show-trace`, and others). Two notes: `--target-host` ignores the real architecture of the target, so a mismatched `nixpkgs.crossSystem` makes activation fail; and `nixos-rebuild` doesn't start or stop user services, it only runs a `daemon-reload` for users with running user services.

A remote deploy as a normal user:

```shell
nixos-rebuild switch --flake .#alpha --target-host admin@alpha.example.com --elevate sudo
```

## Changing a machine safely

1. `nix flake check --no-build` evaluates every `nixosConfigurations.<name>.config.system.build.toplevel` (it printed "checking NixOS configuration 'nixosConfigurations.host'" in a measured run). Add `--all-systems` to cover other platforms. Without `--no-build` it also builds `checks`.
2. `nixos-rebuild build --flake .#alpha --diff`, or `nix store diff-closures /run/current-system ./result`, shows what changes.
3. `nixos-rebuild build-vm --flake .#alpha && ./result/bin/run-*-vm` runs the configuration in QEMU. The VM mounts the host store read-only, keeps its own disk in `./<host>.qcow2`, and has none of your host users: set `users.users.<you>.initialHashedPassword` temporarily. Delete the qcow2 file if you started the VM before fixing users. Forward a host port to the guest with `QEMU_NET_OPTS`, for example `QEMU_NET_OPTS="hostfwd=tcp:127.0.0.1:2222-:22" ./result/bin/run-*-vm` for SSH.
4. `nixos-rebuild test` activates it with a reboot as the escape hatch. Then `switch` or `boot`.

A VM approximates but doesn't equal the real hardware, boot loader, or secrets setup. For repeatable checks of your own modules, write a NixOS test instead ([VM tests](vm-tests.md), [NixOS modules](nixos-modules.md)).

## Evaluating without building

All of these were run against the example flake above:

```shell
nix eval .#nixosConfigurations.alpha.config.networking.hostName
nix eval --json .#nixosConfigurations.alpha.config.nix.settings.experimental-features
nix eval .#nixosConfigurations.alpha.config.system.build.toplevel.drvPath
nix eval --apply builtins.attrNames .#nixosConfigurations.alpha.config.specialisation
nix eval --json .#nixosConfigurations.alpha.options.networking.hostName.definitionsWithLocations --apply 'defs: map (d: d.file) defs'
nix repl .#nixosConfigurations.alpha
```

In the repl, `config`, `options`, `pkgs`, and `lib` are bound. `options.<path>.definitionsWithLocations` lists every definition and its file, and `options.<path>.highestPrio` gives the winning priority (100 for a plain definition, 1000 for `mkDefault`). `nix build --dry-run .#nixosConfigurations.alpha.config.system.build.vm` shows how much would build. `config.system.build` holds `toplevel`, `vm`, `vmWithBootLoader`, `images`, `etc`, `kernel`, `initialRamdisk`, and others.

### Diagnosing evaluation errors

- Add `--show-trace` (also accepted by `nixos-rebuild`). `nix eval --debugger` drops into an interactive environment when evaluation fails.
- "infinite recursion encountered" in a NixOS config usually means one of: `config` or a `_module.args` value used in `imports` (measured; the error text says so); `lib.optionalAttrs` or `if` on a `config` value choosing attribute names inside `config` (measured; use `mkIf`/`mkMerge`); a freeform `settings` key that reads another key (the manual says to declare an option for the dependency); or `rec` shadowing a name.
- "The option `x' has conflicting definition values" (measured) lists each definition's file and value: two modules set an option whose type can't merge them (`types.str`, an enum). "... is defined multiple times while it's expected to be unique" is the same problem for unique types. Resolve with `mkDefault` on the weaker definition, `mkForce` on the winner, or by removing one.
- "The option `x' does not exist" (measured) means the module that declares it isn't imported, or the option was renamed or removed; search `nixos/modules` and the release notes. "Failed assertions:" prints every failing message together, and each names the option to change.

## `system.stateVersion`

It records the NixOS release you first installed on this machine, so that modules and packages whose defaults would otherwise corrupt or orphan existing data (database major versions, on-disk formats) keep their old defaults. Set it once at install time. Don't bump it when you upgrade, and don't treat it as "the NixOS version I'm running": it doesn't change which nixpkgs you use, and an older value doesn't make a system outdated or insecure. Change it only after reading what each module does for the new value and migrating the data. Home Manager has its own `home.stateVersion` that follows the same logic.

## Generations, rollback, specialisations

Every `switch` and `boot` adds a generation to `/nix/var/nix/profiles/system` (links `system-N-link`) and a boot menu entry. If a new configuration misbehaves, pick an older entry at boot and then run `/run/current-system/bin/switch-to-configuration boot` to make it the default, or from a running system use `nixos-rebuild switch --rollback`. `nixos-rebuild list-generations` shows what exists.

```nix
{ pkgs, ... }:
{
  specialisation.alternate.configuration = {
    boot.kernelPackages = pkgs.linuxPackages_latest;
    environment.systemPackages = [ pkgs.hello ];
  };
}
```

A specialisation is an extra boot entry built from the same configuration plus changes. It inherits the parent unless `inheritParentConfig = false`; nested specialisations are ignored. Activate one with `nixos-rebuild switch --specialisation alternate` or `/run/current-system/specialisation/alternate/bin/switch-to-configuration test`. Use `--profile-name` for a configuration you want kept apart from the main line.

## Packages in a configuration: `nixpkgs.*`, overlays, overrides

- `nixpkgs.hostPlatform` sets the system; `nixpkgs.buildPlatform` plus `hostPlatform` cross-compile.
- `nixpkgs.config` takes the global nixpkgs config (`allowUnfree`, `allowUnfreePredicate`, `permittedInsecurePackages`, and so on). It's ignored when `nixpkgs.pkgs` is set, and it doesn't affect `nix-env` or `nix-shell`. A flake system also ignores `~/.config/nixpkgs/config.nix`; pass `config` explicitly when importing nixpkgs yourself.
- `nixpkgs.overlays` is a list of `final: prev: { ... }` functions applied to every module's `pkgs`.
- To share one `pkgs` across many hosts or evaluate it once, import nixpkgs yourself and import `nixpkgs.nixosModules.readOnlyPkgs`, then set `nixpkgs.pkgs`. The `nixpkgs.*` options are then read-only, so configure `config` and `overlays` where you import nixpkgs.

An overlay changes the package for everything that depends on it. Per-site overrides change only the place that uses them, and the manual states that overlays slow nixpkgs evaluation significantly and are harder to debug, which is why modules expose `package` options. Prefer the override at the use site:

```nix
{ pkgs, ... }:
{
  environment.systemPackages = [
    (pkgs.hello.overrideAttrs (old: {
      patches = (old.patches or [ ]) ++ [ ./fix.patch ];
    }))
  ];
}
```

Use `.override { ... }` for package arguments and `.overrideAttrs` for derivation attributes ([patches and overrides](patches-and-overrides.md)). Reserve an overlay for a change that every dependent should see, and expect those dependents to rebuild.

## Nix daemon settings, pinning, and cleanup

```nix
{
  nix.settings = {
    experimental-features = [ "nix-command" "flakes" ];
    auto-optimise-store = true;
  };
  nix.channel.enable = false;
  nix.gc = {
    automatic = true;
    dates = "weekly";
    options = "--delete-older-than 30d";
  };
}
```

- `nix.settings` is freeform: any `nix.conf` key works, and `nix.checkConfig` (default `true`) makes the build fail if Nix can't parse the result. `nix.extraOptions` appends raw text.
- Flake systems get `NIX_PATH = nixpkgs=flake:nixpkgs` and a pinned `nixpkgs` registry entry automatically (see above), so `nix run nixpkgs#hello` and `<nixpkgs>` use the same revision as the system. That makes the closure depend on the nixpkgs sources; turn `nixpkgs.flake.setNixPath` and `setFlakeRegistry` off on machines that never run Nix.
- Without flakes, pin `nix.nixPath` yourself, or set `nixpkgs.flake.source` to a store path from `fetchTarball` (the store path name must be `source`). nix.dev's advice is to avoid `<...>` lookups and to set `$NIX_PATH` in one version-controlled place.
- `nix.channel.enable = false` removes the `nix-channel` command and its state files, which suits flake-only machines. Disabling it doesn't delete existing channel state.
- `nix.registry.<name>.to` rewrites flake references system-wide (the `from` default is `type = "indirect"; id = <name>`).
- Garbage collection: `nix-collect-garbage` removes unreferenced paths but keeps old generations as roots, so rollback still works. `nix-collect-garbage -d` deletes old generations and ends that ability. `--delete-older-than 30d` is the middle ground. Run it as root to affect the system profile. `nix.gc.automatic` schedules it with the `dates` calendar expression.
- `nix.optimise.automatic = true` runs `nix-store --optimise` on a schedule, hard-linking duplicate files (the manual says often as much as 40% of the store); `nix.settings.auto-optimise-store` does it as paths are added.
- A full `/boot`: delete old generations, then `nixos-rebuild boot` (or `switch`) rewrites the entries. `boot.loader.systemd-boot.configurationLimit` and `boot.loader.grub.configurationLimit` cap the number kept.

## Secrets

NixOS has no option that provisions secrets. Modules take paths to files that exist at runtime, and something outside the Nix store puts them there. Everything built from a Nix expression, `pkgs.writeText`, `environment.etc.*.text`, and `builtins.readFile` of a secret included, is copied into the world-readable store.

- Module `*File` options (`passwordFile`, `tokenFile`, `environmentFile`), typed as paths outside the store. Pass a string like `"/run/secrets/token"`, not a path literal like `./token`, which would be copied into the store.
- `users.users.<name>.hashedPasswordFile` for login passwords; it's read at activation time, so the file must exist then.
- Per-service `serviceConfig.LoadCredential` (and `LoadCredentialEncrypted` for `systemd-creds` credentials) for your own units; see [NixOS modules](nixos-modules.md).
- Provisioning the files: third-party tools such as agenix and sops-nix (separate flakes outside nixpkgs; consult their own documentation for options) or your own deployment step. Whatever you choose, ship ciphertext or a reference in git and deliver plaintext only to the target host.

## Home Manager

Home Manager is a third-party project (`github:nix-community/home-manager`), not part of nixpkgs. As a NixOS module it's imported from its flake and configures per-user environments from the system configuration. These names were checked against its source and by evaluating a host that uses it:

```nix
{ inputs, ... }:
{
  imports = [ inputs.home-manager.nixosModules.home-manager ];

  home-manager = {
    useGlobalPkgs = true;
    useUserPackages = true;
    extraSpecialArgs = { inherit inputs; };
    users.alice =
      { ... }:
      {
        home.stateVersion = "26.05";
        programs.git.enable = true;
      };
  };
}
```

Declare the input with `inputs.nixpkgs.follows = "nixpkgs"` so there's one nixpkgs. `useGlobalPkgs` reuses the system `pkgs` (and disables Home Manager's own `nixpkgs.*` options); `useUserPackages` installs user packages through `users.users.<name>.packages`; `extraSpecialArgs` and `sharedModules` feed every user's modules; `backupFileExtension` renames existing files instead of failing on collision. Each user's configuration activates through a `home-manager-<user>.service` unit.

## Checkable rules

- A flake host sets `nixpkgs.hostPlatform` (directly or in `hardware-configuration.nix`).
- Nothing in `imports` reads `config` or `_module.args`; shared values arrive through `specialArgs`.
- `system.stateVersion` is set explicitly, and a diff doesn't change it without a migration note.
- No secret appears in a `.nix` file, `pkgs.writeText`, `environment.etc.*.text`, or `builtins.readFile` of a secret file; secret options are strings or paths outside the store.
- Overrides use `package` options with `overrideAttrs` at the use site; overlays are limited to changes every dependent needs.
- `nix flake check --no-build` passes, and deploy instructions use `--elevate sudo` (not `--use-remote-sudo`) with `--target-host`.
- Nix settings are under `nix.settings`, not hand-written `nix.conf` text, unless a key needs `extraOptions`.

## Dated advice to ignore

- `nixos-rebuild --use-remote-sudo`: deprecated; use `--elevate=sudo` (or `--sudo`).
- `nix flake lock --update-input` and `--recreate-lock-file` (and the same flags through `nixos-rebuild`): marked deprecated by `nix`; use `nix flake update [input]`. `--no-registries` is deprecated for `--no-use-registries`.
- `nixos-rebuild --upgrade` and `nix-channel --update` as the update mechanism on flake systems: they only update root's channels; update flake inputs with `nix flake update` instead.
- Passing `extraArgs` or `check` to `lib.nixosSystem`: removed in 26.11.
- `nixpkgs.system` and the `system` argument of `nixosSystem`: legacy aliases of `nixpkgs.hostPlatform`.
- `nixos/README.md` suggests `nixos-rebuild test -I nixpkgs=... --fast`; `-I` and channel-style `NIX_PATH` testing predates flakes. `--fast` isn't in the man page.
- `nixos-rebuild switch` as a way to restart user services: it doesn't.
