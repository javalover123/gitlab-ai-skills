# NixOS/Home Manager Module Design Quality Gates

Thorough checklist for reviewing module design against RFC standards.

**Contents:** [RFC 0042: Module Design & Option Count](#rfc-0042-module-design--option-count) · [RFC 0052: Security & User Management](#rfc-0052-security--user-management) · [RFC 0119: Testing Conventions](#rfc-0119-testing-conventions) · [RFC 0089: Metadata Requirements](#rfc-0089-metadata-requirements) · [RFC 0145 & 0072: Documentation](#rfc-0145--0072-documentation) · [RFC 0166: Formatting](#rfc-0166-formatting) · [RFC 0088: Breaking Changes](#rfc-0088-breaking-changes) · [RFC 0140: Package Structure](#rfc-0140-package-structure) · [RFC 0127: Problem Declaration](#rfc-0127-problem-declaration) · [RFC 0146: Package Categories](#rfc-0146-package-categories) · [Common Anti-Patterns to Avoid](#common-anti-patterns-to-avoid) · [Quality Gate Summary](#quality-gate-summary)

## RFC 0042: Module Design & Option Count

### Settings Pattern Usage

**When to use `settings` pattern:**
- [ ] Config file format is mappable to Nix (JSON, YAML, TOML, INI)
- [ ] Service has configuration file (not pure command-line args)
- [ ] Upstream has >15 configuration options
- [ ] Module would have >10-15 individual NixOS options

**Settings pattern implementation:**
- [ ] Uses `pkgs.formats.*` (json, yaml, toml, ini, keyValue, hocon, libconfig, lua, and others; the NixOS manual's settings chapter lists them)
- [ ] Has `freeformType = settingsFormat.type` in settings option
- [ ] Links to upstream documentation in settings description, written as a plain Markdown string (no `lib.mdDoc` wrapper, removed in 24.11; no DocBook tags)
- [ ] Config file generated using `settingsFormat.generate`

### Valuable Options Selection

**Only create explicit options for:**

**Main/Popular Settings:**
- [ ] Option is needed by >50% of users for basic usage
- [ ] Option fundamentally changes service behavior
- [ ] Option is commonly set in examples/tutorials
- Examples: `enable`, `port`, `address`, `dataDir`

**Mandatory Values:**
- [ ] Value must be set for service to function
- [ ] No sensible default exists
- [ ] Evaluation error if not set helps user
- Examples: `organizationName`, `hydraURL`, `serverUrl`

**Sensitive Data:**
- [ ] Value is a password, API key, or credential
- [ ] Should not appear in Nix store
- [ ] Uses `*File` pattern (path to file containing secret)
- Examples: `passwordFile`, `apiKeyFile`, `certificateFile`

**Options NOT to create:**
- [ ] Obscure settings few users need
- [ ] Settings that exactly mirror upstream config structure
- [ ] Settings only for advanced users (they can use `settings`)
- [ ] Settings that change frequently in upstream releases

### Settings Defaults

- [ ] Critical settings set with `lib.mkDefault` in config section
- [ ] Required settings set without `mkDefault` (force user to override with `mkForce`)
- [ ] User-specific settings left unset (no defaults)
- [ ] Defaults don't duplicate upstream defaults (link to upstream docs instead)

### Migration from Old Patterns

**If module uses `extraConfig`:**
- [ ] Migrate to `settings` pattern
- [ ] Keep `extraConfig` deprecated with warning (backwards compat)
- [ ] Document migration path in module changelog

**If module has many individual options:**
- [ ] Identify which are "valuable" (keep these)
- [ ] Move rest to `settings` pattern
- [ ] Deprecate old options with aliases
- [ ] Provide migration guide

## RFC 0052: Security & User Management

### DynamicUser Assessment

**Service is candidate for DynamicUser if:**
- [ ] State is self-contained (only this service uses it)
- [ ] No shared state with other services
- [ ] No files need specific ownership outside service directories
- [ ] No specific user name required for external authentication

**DynamicUser implementation:**
- [ ] `systemd.services.<name>.serviceConfig.DynamicUser = true`
- [ ] Uses `StateDirectory` for persistent state
- [ ] Uses `CacheDirectory` for cache
- [ ] Uses `LogsDirectory` for logs
- [ ] Uses `RuntimeDirectory` for runtime files

### Dynamic ID Allocation

**If DynamicUser doesn't fit:**
- [ ] User created with `isSystemUser = true`
- [ ] No static `uid` set (let NixOS allocate)
- [ ] No static `gid` set (let NixOS allocate)
- [ ] Group created without static `gid`
- [ ] User has meaningful `description`

### Static ID Justification

**If static UID/GID used, must have justification for:**
- [ ] Cross-system ID consistency (NFS, distributed systems)
- [ ] External systems expect specific UID/GID
- [ ] Migration from legacy system with hardcoded IDs
- [ ] Justification documented in commit message, and the id registered in `nixos/modules/misc/ids.nix` (`ids.uids.<name>` / `ids.gids.<name>`, below 400) so the module uses `config.ids.uids.<name>`, not a bare number

**Static ID is NOT justified for:**
- "It's simpler" - Dynamic allocation is simpler
- "I want consistent IDs" - Dynamic IDs are consistent per system
- "Other modules do it" - Old pattern being phased out

### Permission Management

**Use systemd directives instead of manual permission management:**
- [ ] `StateDirectory` instead of `mkdir -p /var/lib/foo && chown`
- [ ] `CacheDirectory` instead of `mkdir -p /var/cache/foo && chown`
- [ ] `LogsDirectory` instead of `mkdir -p /var/log/foo && chown`
- [ ] `RuntimeDirectory` instead of `mkdir -p /run/foo && chown`
- [ ] Custom permissions via `*DirectoryMode` options

**Avoid manual permission fixes:**
- [ ] No `chown` in `preStart` or `ExecStartPre`
- [ ] No `chmod` in service scripts
- [ ] No `tmpfiles.rules` for service-owned directories (use Directory options)

### Root Usage

**Service runs as root - needs justification:**
- [ ] Requires privileged operations (binding port <1024, loading kernel modules)
- [ ] No capability-based alternative exists
- [ ] Documented why root is required
- [ ] Uses other hardening options to limit root scope

**Hardening for root services:**
- [ ] `PrivateTmp = true`
- [ ] `ProtectSystem = "strict"` or "full"
- [ ] `ProtectHome = true`
- [ ] `NoNewPrivileges = true`
- [ ] `PrivateDevices = true` (if devices not needed)

## RFC 0119: Testing Conventions

### Test Tier Selection

**checkPhase (fast unit tests):**
- [ ] Runs during package build
- [ ] Short enough not to dominate build time (the docs set no fixed limit)
- [ ] No external dependencies
- [ ] No network access
- [ ] Tests basic correctness

**installCheckPhase (smoke tests):**
- [ ] Verifies installation succeeded
- [ ] Checks programs are executable
- [ ] Runs `--version` or `--help` (`versionCheckHook` does this and fails the build if the version string is missing)
- [ ] No complex functionality testing

**passthru.tests (integration tests):**
- [ ] Tests service integration
- [ ] Links NixOS VM tests through the `nixosTests` package argument (`passthru.tests.foo = nixosTests.foo;`)
- [ ] Tests dependent packages work
- [ ] Can run for minutes (not in build path)
- [ ] VM tests need the `kvm` system feature (`apple-virt` on macOS)

### NixOS Module Testing

**For service modules:**
- [ ] Has a test module in `nixos/tests/<name>.nix`, registered in `nixos/tests/all-tests.nix`
- [ ] Tests service starts successfully
- [ ] Tests basic functionality works
- [ ] Tests the service can be restarted and that configuration changes apply

**VM test structure** (the file `nixos/tests/myservice.nix` is a test module; it is not placed inside the service module):
```nix
{
  name = "myservice-integration";
  nodes.machine = {
    services.myservice.enable = true;
  };
  testScript = ''
    machine.wait_for_unit("myservice.service")
    machine.succeed("myservice-cli --version")
  '';
}
```

Register it in `all-tests.nix` as `myservice = runTest ./myservice.nix;`, and link it from the package with `passthru.tests.myservice = nixosTests.myservice;`.

## RFC 0089: Metadata Requirements

### Required Attributes

`pkgs/README.md` requires `description`, `license`, `maintainers` (for new packages), `mainProgram` (when there is a primary executable), and `sourceProvenance` (when the package isn't built from source). `homepage` and `platforms` are optional but customary.

- [ ] `description` - one-line, concise, capitalized, no ending period, no leading article
- [ ] `homepage` - upstream project URL (optional but customary)
- [ ] `license` - uses `lib.licenses.*` not strings (names are lowerCamelCase: `mit`, `asl20`, `unfree`)
- [ ] `maintainers` - at least one maintainer listed

### Binary Package Metadata

**If package contains binaries:**
- [ ] `sourceProvenance` set with appropriate values:
  - `fromSource` - built from source
  - `binaryNativeCode` - native binaries included
  - `binaryBytecode` - third-party bytecode for a VM or JIT (such as prebuilt `.jar` files)
  - `binaryFirmware` - firmware blobs

### Optional But Recommended

- [ ] `longDescription` - detailed description (if needed)
- [ ] `changelog` - link to upstream changelog

## RFC 0145 & 0072: Documentation

### Doc-Comment Format

**If functions are documented:**
- [ ] Uses `/** */` multi-line format
- [ ] Placed directly before function
- [ ] Contains brief description
- [ ] Has examples section with input → output
- [ ] Has type signature (Haskell-style)

### Content Requirements

- [ ] Uses CommonMark (standard Markdown)
- [ ] No HTML tags (breaks non-HTML output formats)
- [ ] Code blocks have language specifiers
- [ ] Links use `[text](url)` format
- [ ] Lists and tables formatted correctly

## RFC 0166: Formatting

### Indentation & Spacing

- [ ] 2 spaces per level (never tabs)
- [ ] 100 char soft limit (excluding indentation)
- [ ] Spaces inside brackets: `[ foo ]`
- [ ] Empty: `[ ]` and `{ }`

### Multi-line Consistency

- [ ] Lists with more than one item have each item on its own line (`nixfmt` 1.x output); a single short item may stay inline
- [ ] First item doesn't stay with opening bracket
- [ ] Non-empty attribute sets are expanded, one binding per line
- [ ] Consistent indentation throughout

### Comments

- [ ] Explain WHY not WHAT
- [ ] Single-line: `# comment`
- [ ] Multi-line: `/* ... */`
- [ ] Doc-comments: `/** ... */`

## RFC 0088: Breaking Changes

**If PR introduces breaking changes:**
- [ ] Sample testing done (≥100 packages OR ≥3h build time)
- [ ] Affected maintainers notified via PR ping
- [ ] Grace period provided (7 days minimum)
- [ ] Broken packages marked `broken = true;`
- [ ] If the rebuild count is 500 or more, consider `staging`; at 1000 or more the PR should target `staging` (`CONTRIBUTING.md`)

## RFC 0140: Package Structure

**For nixpkgs packages:**
- [ ] Uses `pkgs/by-name/${shard}/${name}/package.nix`
- [ ] Shard = lowercased first 2 letters of name
- [ ] Self-contained (no file refs outside package dir)
- [ ] Name is ASCII alphanumerics + hyphens/underscores
- [ ] Unique when lowercased

## RFC 0127: Problem Declaration

**If package has known issues:**
- [ ] Uses `meta.problems` attribute
- [ ] Problem kind is one of the manually declarable kinds, `deprecated` or `removal` (`broken` and `maintainerless` are generated; insecure packages use `meta.knownVulnerabilities`)
- [ ] Message is clear and actionable
- [ ] URLs provided for context (issues, PRs, docs)

## RFC 0146: Package Categories

Don't add `meta.categories`: neither `lib.categories` nor a `meta.categories` check exists in the current nixpkgs tree.

## Common Anti-Patterns to Avoid

### Module Design
- Avoid: 20+ individual options mirroring upstream config
- Prefer: `settings` with freeformType, selective explicit options

### User Management
- Avoid: Static UID/GID without justification
- Prefer: `DynamicUser = true` or dynamic allocation

### Permissions
- Avoid: `mkdir -p /var/lib/foo && chown user:group /var/lib/foo` in preStart
- Prefer: `systemd.services.foo.serviceConfig.StateDirectory = "foo"`

### Testing
- Avoid: Slow integration tests in checkPhase
- Prefer: Fast unit tests in checkPhase, slow tests in passthru.tests

### Documentation
- Avoid: `<div class="note">Important!</div>` in descriptions
- Prefer: Pure CommonMark without HTML tags

### Config Generation
- Avoid: `extraConfig = ''string-based-config''`
- Prefer: `settings` with `pkgs.formats.json` and freeformType

## Quality Gate Summary

**Module must pass ALL these gates:**

1. **Module Design:** Uses settings pattern if >10-15 options
2. **Security:** Uses DynamicUser or dynamic IDs, no static UIDs without justification
3. **Testing:** Appropriate test tier for each test type
4. **Metadata:** All required fields present and correct
5. **Documentation:** CommonMark format, no HTML, proper doc-comments
6. **Formatting:** 2-space indentation, proper spacing, multi-line consistency
7. **Breaking Changes:** Proper procedure if applicable
8. **Package Structure:** Self-contained, proper naming, correct location

**Any gate failure = needs revision before merge**
