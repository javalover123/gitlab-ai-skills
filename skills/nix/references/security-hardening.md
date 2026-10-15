# Security Hardening Patterns for NixOS Services

Security patterns based on RFC 0052 and systemd security best practices.

**Contents:** [User Management Patterns](#user-management-patterns) · [Permission Management Patterns](#permission-management-patterns) · [Service Hardening Patterns](#service-hardening-patterns) · [Security Decision Tree](#security-decision-tree) · [Common Patterns](#common-patterns) · [Testing Security Settings](#testing-security-settings) · [References](#references)

## User Management Patterns

### Pattern 1: DynamicUser (Preferred)

**When to use:**
- Service state is self-contained
- No shared state with other services
- No specific user name required for external auth
- No files need ownership outside service directories

**Template:**
```nix
systemd.services.myservice = {
  description = "My Service";
  wantedBy = [ "multi-user.target" ];

  serviceConfig = {
    DynamicUser = true;
    StateDirectory = "myservice";
    CacheDirectory = "myservice";
    LogsDirectory = "myservice";
    RuntimeDirectory = "myservice";

    # systemd.exec(5) says DynamicUser implies:
    # - PrivateTmp = "disconnected" (unless PrivateTmp is set explicitly)
    # - ProtectSystem = "strict"
    # - ProtectHome = "read-only" (not true; set ProtectHome = true to hide /home)
    # - NoNewPrivileges = true and RestrictSUIDSGID = true
    # - RemoveIPC = true
    # StateDirectory, CacheDirectory, LogsDirectory and RuntimeDirectory stay
    # writable, so no ReadWritePaths entry is needed for them.

    ExecStart = "${pkgs.myservice}/bin/myservice";
  };
};
```

**Advantages:**
- No persistent UID/GID allocated
- Automatic security restrictions (see the list above)
- State sits under a root-only `private` directory, which blocks access through UID recycling
- Simplest permission management

**State is not cleaned up automatically.** `StateDirectory`, `CacheDirectory`, and `LogsDirectory` aren't removed when the unit stops, and nothing removes them when you delete the service from your configuration. With `DynamicUser` they live under `/var/lib/private`, `/var/cache/private`, and `/var/log/private` (with symlinks at the usual paths). `systemctl clean` or a manual `rm` clears them. Only `RuntimeDirectory` is removed on stop.

### Pattern 2: Dynamic ID Allocation

**When to use:**
- State shared between multiple services
- Specific user name required (but not specific UID)
- Files need ownership outside StateDirectory
- Service needs to be referenced by name

**Template:**
```nix
{
  users.users.myservice = {
    description = "My Service daemon user";
    group = "myservice";
    isSystemUser = true;  # REQUIRED
    # Do NOT set uid
  };

  users.groups.myservice = {};
  # Do NOT set gid

  systemd.services.myservice = {
    description = "My Service";
    wantedBy = [ "multi-user.target" ];

    serviceConfig = {
      User = "myservice";
      Group = "myservice";
      StateDirectory = "myservice";
      StateDirectoryMode = "0750";

      ExecStart = "${pkgs.myservice}/bin/myservice";
    };
  };
}
```

**Why dynamic allocation:**
- Persistent across reboots (stored in `/var/lib/nixos/{u,g}id-map`)
- No central ID registry conflicts
- 600 available IDs (400-999 range)
- Simpler than static allocation

### Pattern 3: Static UID/GID (Rarely Justified)

**Only when:**
- Cross-system ID consistency required (NFS, distributed systems)
- External systems expect specific UID/GID
- Migration from legacy system with hardcoded IDs

**Template with justification.** Static ids live in the central list `nixos/modules/misc/ids.nix` (to avoid collisions) and modules read them through `config.ids`. The file's header says static ids are deprecated, dynamic allocation is required barring special circumstances, and new uids/gids must stay below 400 (NixOS allocates system ids in `400..999`; don't reuse an existing uid or gid). Add the entry in `ids.nix`:
```nix
{
  ids.uids.myservice = 330;
  ids.gids.myservice = 330;
}
```
and use it from the module:
```nix
{ config, ... }:
{
  # JUSTIFICATION: Service shares NFS mount with legacy systems
  # that expect UID 330 for service files. Cannot be changed
  # without breaking existing deployments.
  users.users.myservice = {
    uid = config.ids.uids.myservice;
    description = "My Service (NFS-shared UID)";
    group = "myservice";
    isSystemUser = true;
  };

  users.groups.myservice = {
    gid = config.ids.gids.myservice;
  };

  systemd.services.myservice = {
    # ... rest of service config
  };
}
```

**Document in commit message:**
```
services/myservice: add module

Uses static UID/GID 330 (registered in nixos/modules/misc/ids.nix) because service shares NFS mounts
with legacy infrastructure that expects this specific ID.
Coordinated with nixpkgs maintainers to reserve this ID.

See: https://github.com/NixOS/nixpkgs/issues/XXXXX
```

## Permission Management Patterns

### StateDirectory (Recommended)

**Instead of manual directory creation:**
```nix
# Bad: Manual permission management
systemd.services.myservice = {
  preStart = ''
    mkdir -p /var/lib/myservice
    chown myuser:mygroup /var/lib/myservice
    chmod 750 /var/lib/myservice
  '';
  serviceConfig.ExecStart = "${pkgs.myservice}/bin/myservice";
};
```

**Use StateDirectory:**
```nix
# Good: Declarative permission management
systemd.services.myservice = {
  serviceConfig = {
    User = "myservice";
    Group = "myservice";
    StateDirectory = "myservice";
    StateDirectoryMode = "0750";
    ExecStart = "${pkgs.myservice}/bin/myservice";
  };
};
```

**Multiple directories:**
```nix
systemd.services.myservice = {
  serviceConfig = {
    StateDirectory = [
      "myservice"
      "myservice/data"
      "myservice/backups"
    ];
    StateDirectoryMode = "0750";
  };
};
```

### Directory Hierarchy

**systemd provides several directory types:**

```nix
systemd.services.myservice.serviceConfig = {
  # /var/lib/myservice - persistent data
  StateDirectory = "myservice";
  StateDirectoryMode = "0750";

  # /var/cache/myservice - expendable cache
  CacheDirectory = "myservice";
  CacheDirectoryMode = "0750";

  # /var/log/myservice - logs
  LogsDirectory = "myservice";
  LogsDirectoryMode = "0750";

  # /run/myservice - runtime files (tmpfs)
  RuntimeDirectory = "myservice";
  RuntimeDirectoryMode = "0750";

  # /etc/myservice - configuration
  ConfigurationDirectory = "myservice";
  ConfigurationDirectoryMode = "0750";
};
```

**When directories are created:**
- StateDirectory, CacheDirectory, LogsDirectory: created at service start, persist after stop
- RuntimeDirectory: created at service start, deleted at service stop (tmpfs)
- ConfigurationDirectory: created at service start, persists

### Custom Directory Locations

**If you need non-standard paths:**
```nix
systemd.services.myservice = {
  serviceConfig = {
    # Bind mount custom location into expected location
    BindPaths = [
      "/mnt/data/myservice:/var/lib/myservice"
    ];
    StateDirectory = "myservice";  # Still creates /var/lib/myservice
  };
};
```

Don't combine `BindPaths` with `DynamicUser = true`: `systemd.exec(5)` warns that bind-mounted paths can end up holding files owned by the dynamic user that aren't covered by the UID-recycling protections.

**Or use tmpfiles.rules for non-service directories:**
```nix
systemd.tmpfiles.rules = [
  "d /var/custom/myservice 0750 myuser mygroup - -"
  "Z /var/custom/myservice - myuser mygroup - -"  # Recursively fix ownership
];
```

## Service Hardening Patterns

### Minimal Privilege Template

**Base hardening for most services:**
```nix
systemd.services.myservice.serviceConfig = {
  DynamicUser = true;
  StateDirectory = "myservice";

  # Filesystem protection
  PrivateTmp = true;
  ProtectSystem = "strict";
  ProtectHome = true;
  ProtectKernelTunables = true;
  ProtectKernelModules = true;
  ProtectControlGroups = true;

  # Restrict capabilities
  NoNewPrivileges = true;
  PrivateDevices = true;

  # Restrict system calls
  SystemCallFilter = [ "@system-service" "~@privileged" ];
  SystemCallArchitectures = "native";

  # Network restrictions (if service doesn't need network)
  PrivateNetwork = true;  # Remove if service needs network

  # StateDirectory is already writable under ProtectSystem = "strict"; add
  # ReadWritePaths only for other locations the service must write to

  # Process restrictions
  LockPersonality = true;
  RestrictRealtime = true;
  RestrictSUIDSGID = true;

  # Namespace restrictions
  RestrictNamespaces = true;
  PrivateMounts = true;
};
```

### Network Service Hardening

**For services that bind to network ports:**
```nix
systemd.services.webservice.serviceConfig = {
  DynamicUser = true;
  StateDirectory = "webservice";

  # Network binding (port <1024 needs AmbientCapabilities)
  AmbientCapabilities = [ "CAP_NET_BIND_SERVICE" ];

  # Filesystem protection
  PrivateTmp = true;
  ProtectSystem = "strict";
  ProtectHome = true;

  # Process restrictions
  NoNewPrivileges = true;
  PrivateDevices = true;
  ProtectKernelTunables = true;
  ProtectKernelModules = true;
  ProtectControlGroups = true;

  # Network allowed
  # PrivateNetwork = false (default)
  IPAddressDeny = [ "any" ];
  IPAddressAllow = [
    "127.0.0.1/8"
    "::1"
    "192.168.1.0/24"  # Allow specific subnets
  ];

  # Restrict system calls
  SystemCallFilter = [ "@system-service" "~@privileged" ];
};
```

### Database Service Hardening

**For services that manage data storage:**
```nix
systemd.services.database.serviceConfig = {
  User = "database";
  Group = "database";
  StateDirectory = "database";
  StateDirectoryMode = "0700";  # Stricter permissions for DB

  # Filesystem restrictions
  PrivateTmp = true;
  ProtectSystem = "strict";
  ProtectHome = true;
  ReadWritePaths = [
    "/var/lib/database"
  ];

  # Process restrictions
  NoNewPrivileges = true;
  PrivateDevices = true;
  ProtectKernelTunables = true;
  ProtectKernelModules = true;

  # Memory restrictions (prevent DoS)
  MemoryMax = "2G";
  MemoryHigh = "1.5G";

  # CPU restrictions
  CPUQuota = "200%";  # Max 2 cores worth

  # File descriptor limits
  LimitNOFILE = 65536;
};
```

### Service Requiring Root

**When root is truly necessary:**
```nix
systemd.services.privileged.serviceConfig = {
  # Must run as root to load kernel modules
  User = "root";

  # But restrict what root can do
  PrivateTmp = true;
  ProtectSystem = "strict";
  ProtectHome = true;

  # Only allow specific capabilities
  AmbientCapabilities = [ "CAP_SYS_MODULE" ];
  CapabilityBoundingSet = [ "CAP_SYS_MODULE" ];

  # Restrict syscalls
  SystemCallFilter = [
    "@system-service"
    "@module"  # For kernel module loading
    "~@privileged"
  ];

  # Document why root is needed
  # JUSTIFICATION: Requires CAP_SYS_MODULE to load kernel modules
  # for hardware acceleration. No alternative exists.
};
```

## Security Decision Tree

```
Is service state self-contained?
├─ Yes → Use DynamicUser
└─ No → Does service need persistent user name?
    ├─ No → Use DynamicUser anyway
    └─ Yes → Does service need specific UID/GID?
        ├─ No → Use dynamic ID allocation
        └─ Yes → Document justification, register the id in ids.nix, use static UID/GID

Does service need network access?
├─ No → Set PrivateNetwork = true
└─ Yes → Does it need port <1024?
    ├─ No → Run as non-root with DynamicUser
    └─ Yes → Use AmbientCapabilities = ["CAP_NET_BIND_SERVICE"]

Does service need to run as root?
├─ No → Use DynamicUser or dedicated user
└─ Yes → Document justification and restrict capabilities
    └─ Can you use capabilities instead?
        ├─ Yes → Use AmbientCapabilities, drop root
        └─ No → Keep root but maximize other restrictions
```

## Common Patterns

### Web Server

```nix
systemd.services.nginx = {
  serviceConfig = {
    User = "nginx";
    Group = "nginx";
    StateDirectory = "nginx";
    CacheDirectory = "nginx";
    LogsDirectory = "nginx";

    # Bind to port 80/443
    AmbientCapabilities = [ "CAP_NET_BIND_SERVICE" ];
    CapabilityBoundingSet = [ "CAP_NET_BIND_SERVICE" ];

    # Hardening
    NoNewPrivileges = true;
    PrivateDevices = true;
    PrivateTmp = true;
    ProtectSystem = "strict";
    ProtectHome = true;
    ReadWritePaths = [
      "/var/lib/nginx"
      "/var/cache/nginx"
      "/var/log/nginx"
    ];
  };
};
```

### Database

```nix
systemd.services.postgresql = {
  serviceConfig = {
    User = "postgres";
    Group = "postgres";
    StateDirectory = "postgresql";
    StateDirectoryMode = "0700";

    # PrivateNetwork stays off (the default) so clients can connect over TCP

    # Hardening
    NoNewPrivileges = true;
    PrivateDevices = true;
    PrivateTmp = true;
    ProtectSystem = "strict";
    ProtectHome = true;
    # MemoryDenyWriteExecute breaks JIT; the nixpkgs postgresql module only
    # enables it when settings.jit is "off"

    # Resource limits
    MemoryMax = "4G";
    LimitNOFILE = 65536;
  };
};
```

### Background Worker

```nix
systemd.services.worker = {
  serviceConfig = {
    DynamicUser = true;
    StateDirectory = "worker";
    CacheDirectory = "worker";

    # Needs network for API calls
    # PrivateNetwork = false (default)

    # Hardening
    NoNewPrivileges = true;
    PrivateDevices = true;
    PrivateTmp = true;
    ProtectSystem = "strict";
    ProtectHome = true;
    ProtectKernelTunables = true;
    ProtectKernelModules = true;

    # Restrict syscalls
    SystemCallFilter = [ "@system-service" "~@privileged" ];
  };
};
```

## Testing Security Settings

**Check what systemd actually set:**
```bash
# View service security analysis
systemd-analyze security myservice.service

# View effective service configuration
systemctl show myservice.service

# Test service isolation
systemctl status myservice.service
```

**Common issues:**

1. **Service fails to start after adding restrictions:**
   - Check logs: `journalctl -u myservice.service -n 50`
   - Look for "Permission denied" or "Operation not permitted"
   - Gradually add restrictions to find which one causes issues

2. **Files not accessible:**
   - Add path to `ReadWritePaths` or `ReadOnlyPaths`
   - Check directory ownership matches service user
   - Verify `StateDirectory` creates directories with right permissions

3. **Network doesn't work:**
   - Remove `PrivateNetwork = true` if service needs network
   - Check `IPAddressDeny`/`IPAddressAllow` settings
   - Verify firewall rules allow connection

## References

- [systemd.exec(5)](https://www.freedesktop.org/software/systemd/man/systemd.exec.html) - All serviceConfig options
- [systemd.resource-control(5)](https://www.freedesktop.org/software/systemd/man/systemd.resource-control.html) - Resource limits
- [RFC 0052](https://github.com/NixOS/rfcs/blob/master/rfcs/0052-dynamic-ids.md) - Dynamic IDs
- [systemd-analyze security](https://www.freedesktop.org/software/systemd/man/systemd-analyze.html) - Security analysis tool
- [NixOS Manual: systemd Services](https://nixos.org/manual/nixos/stable/index.html#sec-writing-modules-systemd) - NixOS-specific guidance
