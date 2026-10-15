# Nix RFC Summary for Code Review

Guidance extracted from Nix RFCs for code review.

**Contents:** [Module Design (RFC 0042)](#module-design-rfc-0042) · [Security & User Management (RFC 0052)](#security--user-management-rfc-0052) · [Package Structure (RFC 0140)](#package-structure-rfc-0140) · [Testing Hierarchy (RFC 0119)](#testing-hierarchy-rfc-0119) · [Metadata Requirements (RFC 0089)](#metadata-requirements-rfc-0089) · [Documentation Standards (RFC 0145 + RFC 0072)](#documentation-standards-rfc-0145--rfc-0072) · [Breaking Changes (RFC 0088)](#breaking-changes-rfc-0088) · [Staging Workflow (RFC 0026)](#staging-workflow-rfc-0026) · [Platform Support (RFC 0046)](#platform-support-rfc-0046) · [Formatting Details (RFC 0166)](#formatting-details-rfc-0166) · [Design Patterns](#design-patterns) · [Common Mistakes](#common-mistakes) · [Problem Declaration (RFC 0127)](#problem-declaration-rfc-0127) · [Package Categories (RFC 0146)](#package-categories-rfc-0146) · [Documentation Format (RFC 0072)](#documentation-format-rfc-0072) · [Package Removal (RFC 0180)](#package-removal-rfc-0180) · [Code Review Checklist](#code-review-checklist)

## Module Design (RFC 0042)

**Core principle:** Use structural `settings` options instead of dozens of individual options or stringly-typed `extraConfig`.

### Part 1: Settings Pattern

**Instead of this (old way):**
```nix
services.foo = {
  enable = true;
  port = 8080;
  listenAddress = "0.0.0.0";
  logLevel = "info";
  maxConnections = 100;
  timeout = 30;
  enableFeatureA = true;
  enableFeatureB = false;
  # ... 20 more individual options ...
  extraConfig = ''
    custom-setting = value
  '';
};
```

**Do this (settings pattern):**
```nix
{
  options.services.foo = {
    enable = lib.mkEnableOption "foo service";

    settings = lib.mkOption {
      type = lib.types.submodule {
        freeformType = settingsFormat.type;

        # Only expose critical/commonly-used options:
        options.port = lib.mkOption {
          type = lib.types.port;
          default = 8080;
          description = "Port to listen on.";
        };
      };
      default = {};
      description = ''
        Configuration for foo. See
        <https://example.com/docs>
        for all supported options.
      '';
    };
  };

  config = lib.mkIf cfg.enable {
    # Set defaults with mkDefault so users can override:
    services.foo.settings = {
      log_level = lib.mkDefault "WARN";
      data_path = "/var/lib/foo";  # Required, no mkDefault
    };

    environment.etc."foo.json".source =
      settingsFormat.generate "foo-config.json" cfg.settings;
  };
}
```

**Advantages:**
- Users can set any upstream option without waiting for module updates
- Proper merging (multiple assignments combine correctly)
- Priorities work (`mkDefault`, `mkForce`)
- Values are inspectable (not opaque strings)
- Defaults can be overridden
- Module stays small and maintainable

### Part 2: Balance Option Count

**Only create explicit options for "valuable" settings:**

| Type | Criteria | Examples | Why |
|------|----------|----------|-----|
| **Main/popular** | Needed for basic usage by most users | `port`, `address`, `enable` | Good discoverability, common use case |
| **Mandatory** | Must be set for service to work | `hydraURL`, `organizationName` | Forces user to configure, clear error |
| **Sensitive** | Passwords, API keys, credentials | `passwordFile`, `secretKeyFile` | Keeps secrets out of Nix store |

**Don't create explicit options for:**
- Obscure settings few users need
- Settings that mirror entire upstream config
- Settings only for advanced users
- Settings that change frequently upstream

**Quality gates:**
- Module has >10-15 individual options? Probably should use `settings`
- Using `extraConfig` or similar string option? Should use `settings`
- Copy-pasting upstream config docs into NixOS options? Use `settings` instead
- Module duplicates upstream's config structure? Use `settings` with link to upstream docs

**Using `pkgs.formats` for config generation:**
```nix
let
  settingsFormat = pkgs.formats.json {};  # or .yaml, .toml, .ini
in {
  options.services.foo.settings = lib.mkOption {
    type = lib.types.submodule {
      freeformType = settingsFormat.type;
      # ...
    };
  };

  config = {
    environment.etc."foo.json".source =
      settingsFormat.generate "foo-config.json" cfg.settings;
  };
}
```

**Available formats:** `pkgs.formats` has many more generators than the common four: for example `json`, `yaml`, `toml`, `ini`, `iniWithGlobalSection`, `gitIni`, `keyValue`, `javaProperties`, `hocon`, `hcl1`, `libconfig`, `lua`, `php`, `plist`, `pythonVars`, `systemd`, `xml`, `elixirConf`, `configobj`, `nixConf`, and `cdn`. The list is in `pkgs/pkgs-lib/formats.nix`, and the NixOS manual chapter "Options for Program Settings" documents each one's arguments, so check there before hand-writing a generator. Option descriptions are plain Nixpkgs-flavored Markdown (no DocBook `<link>` tags, no `lib.mdDoc`).

### When NOT to use settings pattern

- Config format can't map to Nix (bash, Python scripts, etc.)
- Service has <5 total options
- Existing module with backwards compatibility constraints (use migration plan)

## Security & User Management (RFC 0052)

**Core principle:** Don't use static UIDs/GIDs. Prefer `DynamicUser` or dynamic allocation.

### Prefer DynamicUser

**When applicable** (service state is self-contained):
```nix
systemd.services.myservice = {
  serviceConfig = {
    DynamicUser = true;
    StateDirectory = "myservice";      # Creates /var/lib/myservice
    CacheDirectory = "myservice";      # Creates /var/cache/myservice
    LogsDirectory = "myservice";       # Creates /var/log/myservice
    ConfigurationDirectory = "myservice";  # Creates /etc/myservice
  };
};
```

**Advantages:**
- No persistent UID/GID allocated
- Automatic permission management
- Security restrictions enabled by default
- State isolated to service

**When DynamicUser doesn't work:**
- State shared between multiple services
- Files need specific ownership outside service directories
- Service needs specific user name for external auth

### Dynamic ID Allocation

**When DynamicUser doesn't fit:**
```nix
{
  users.users.myservice = {
    description = "My service user";
    group = "myservice";
    isSystemUser = true;  # REQUIRED - allocates from system UID range
    # Do NOT set uid - let NixOS allocate dynamically
  };

  users.groups.myservice = {};
  # Do NOT set gid - let NixOS allocate dynamically

  systemd.services.myservice.serviceConfig = {
    User = "myservice";
    Group = "myservice";
    StateDirectory = "myservice";  # Creates /var/lib/myservice, owned by myservice
  };
}
```

**Key points:**
- Dynamic UIDs persistent across reboots (stored in `/var/lib/nixos/uid-map`)
- Range: 400-999 (600 available IDs)
- Use `StateDirectory` instead of manual `chown`
- `isSystemUser = true` is **required** for services

### Avoid Static UIDs/GIDs

**Static allocation requires explicit justification:**
```nix
# Only when absolutely necessary (example: NFS ID consistency).
# Static IDs are registered in the central list, nixos/modules/misc/ids.nix:
ids.uids.specialservice = 330;  # keep below 400; don't reuse an existing uid or gid
ids.gids.specialservice = 330;

# The module then refers to the registered value; never a bare number
users.users.specialservice = {
  uid = config.ids.uids.specialservice;
  group = "specialservice";
  isSystemUser = true;
  # Must document WHY a static UID is needed
};
users.groups.specialservice.gid = config.ids.gids.specialservice;
```

`ids.nix` itself says static ids are deprecated within NixOS, that dynamic allocation is required barring special circumstances, and that uids above 399 must not be added there because NixOS allocates system ids in `400..999`.

**When static IDs are justified:**
- Cross-system ID consistency required (NFS, distributed systems)
- External systems expect specific UID/GID
- Migration from legacy system with hardcoded IDs

**When they're NOT justified:**
- "It's simpler" - No, dynamic allocation is simpler
- "I like consistent IDs" - Dynamic IDs are consistent on same system
- "Other modules do it" - Old pattern, being phased out

### Permission Management

**Use systemd directives instead of manual permission fixes:**

**Good:**
```nix
systemd.services.foo.serviceConfig = {
  StateDirectory = "foo";           # /var/lib/foo
  StateDirectoryMode = "0750";      # Custom permissions
  CacheDirectory = "foo";           # /var/cache/foo
  LogsDirectory = "foo";            # /var/log/foo
  RuntimeDirectory = "foo";         # /run/foo
};
```

**Avoid:**
```nix
# Don't do this:
systemd.services.foo.preStart = ''
  mkdir -p /var/lib/foo
  chown myuser:mygroup /var/lib/foo
  chmod 750 /var/lib/foo
'';
```

**Why:** `StateDirectory` runs on service start, handles permissions automatically, works with DynamicUser, and is more declarative.

### Security Hardening Checklist

- [ ] Service uses `DynamicUser = true` when possible
- [ ] If persistent user needed: uses `isSystemUser = true`, no static `uid`/`gid`
- [ ] Uses `StateDirectory`/`CacheDirectory`/`LogsDirectory` for directories
- [ ] Service doesn't run as root unless absolutely required
- [ ] Static UID/GID has justification documented in commit message and is registered in `nixos/modules/misc/ids.nix`
- [ ] Sensitive data uses `*File` options, not direct values

## Package Structure (RFC 0140)

**Directory layout:**
```
pkgs/by-name/${shard}/${name}/package.nix
```

- Shard = lowercased first 2 letters
- Example: `pkgs/by-name/he/hello/package.nix` → `pkgs.hello`
- Names: ASCII alphanumerics + hyphens/underscores only
- Must be unique when lowercased

**Self-contained packages:**
- Each package directory is isolated
- No file references outside package dir
- No shared files between packages
- CI enforces strict containment

**Automatic binding:**
```text
# Auto-generated, no all-packages.nix entry needed (pseudo-code)
pkgs.${name} = callPackage pkgs/by-name/${shard}/${name}/package.nix { };
```

**Package variants:**
```nix
# Option 1: .override
{
  graphviz_nox = graphviz.override { withXorg = false; };
}
```
```nix
# Option 2: custom callPackage
{
  graphviz_nox = callPackage ../by-name/gr/graphviz/package.nix {
    withXorg = false;
  };
}
```

## Testing Hierarchy (RFC 0119)

The tiers below follow `pkgs/README.md` ("Package tests") and `doc/stdenv/passthru.chapter.md`. The RFC text isn't in the tree, so its attribution here is unchecked.

**Three tiers:**

### 1. checkPhase (fast unit tests)
```nix
checkPhase = ''
  runHook preCheck
  make test
  runHook postCheck
'';
```

Characteristics:
- Runs during build
- Quick execution (minimize build time)
- Unit tests only
- No external dependencies

### 2. installCheckPhase / versionCheckHook (post-install smoke tests)
```nix
nativeInstallCheckInputs = [ versionCheckHook ];
doInstallCheck = true;
```

A hand-written `installCheckPhase` also works; `versionCheckHook` is what the stdenv chapter recommends for sources that ship no tests.

Characteristics:
- Trivial verification
- Check programs linked correctly
- Basic functionality check

### 3. passthru.tests (integration tests)
```nix
passthru.tests = {
  # NixOS module test, registered in nixos/tests/all-tests.nix
  integration = nixosTests.foo;
  # Any derivation can be a test; this one lives in tests.nix beside the package
  simple-execution = callPackage ./tests.nix { };
};
```

Characteristics:
- Expensive tests (heavy resources)
- Can reference downstream dependencies
- Regression testing for dependant packages
- NixOS VM tests need the `kvm` system feature (`apple-virt` on macOS)

**Best practices:**
- Prioritize fast builds (long tests → passthru.tests)
- Test build correctness (checkPhase) AND API compatibility (passthru.tests)
- Use existing nixosTests when possible
- Review tools (ofborg, nixpkgs-review) check these

## Metadata Requirements (RFC 0089)

**Meta attributes:** `pkgs/README.md` says `meta.description` and `meta.license` must be set, `meta.maintainers` must be set for new packages, `meta.mainProgram` must be set when there is a primary executable, and `meta.sourceProvenance` must be set if the package isn't built from source. `homepage` and `platforms` are optional but customary.
```nix
meta = {
  description = "One-line description (no ending period)";
  homepage = "https://example.com";
  license = lib.licenses.mit;  # Use a lib.licenses.* value (lowerCamelCase: mit, asl20, gpl3Plus, unfree)
  maintainers = with lib.maintainers; [ username ];
  platforms = lib.platforms.linux;  # or lib.platforms.unix, lib.platforms.all

  # For packages not built from source:
  sourceProvenance = with lib.sourceTypes; [
    binaryNativeCode
    # or: binaryBytecode, binaryFirmware, fromSource
  ];
};
```

**Source provenance types:**
- `fromSource` - built from source
- `binaryNativeCode` - native binaries included
- `binaryBytecode` - third-party bytecode for a VM or JIT (for example prebuilt `.jar` files)
- `binaryFirmware` - firmware blobs

`lib.sourceTypes.obfuscatedCode` also exists, for intentionally obfuscated code. Use multiple values if the package contains mixed content.

**Common mistakes:**
- Hardcoding license strings (use `lib.licenses.*`)
- Missing sourceProvenance for binary packages
- Vague descriptions

## Documentation Standards (RFC 0145 + RFC 0072)

**Doc-comment format:**
````nix
{
  /**
    Brief description of function.

    Longer explanation can go here.

    # Inputs

    `arg`

    : Description of argument

    # Type

    ```
    funcName :: { arg :: String } -> Derivation
    ```

    # Examples

    ```nix
    funcName { arg = "value"; }
    => expectedResult
    ```
  */
  functionName = { arg }: arg;
}
````

The section order and `# Inputs` / `# Type` / `# Examples` headings follow the doc-comments in `lib/lists.nix`; `doc/README.md` shows the matching `Inputs` and `Examples` convention for manual sections.

**Placement rules:**
- Doc before documentable node (function, binding, lambda formal)
- Only whitespace or non-doc comments between doc and node
- Closer doc has precedence for ambiguous cases

**Content format:**
- Use CommonMark (standard Markdown)
- Avoid HTML in source
- Supported extensions: tables, cross-references, YAML frontmatter
- No deeply nested structures

**Standard sections:**
- Description (required)
- Examples (code blocks with input → output)
- Type signature (Haskell-style)
- Inputs (each argument with a description)

## Breaking Changes (RFC 0088)

**Procedure:**

1. **Prepare PR** with breaking changes
2. **Test sample:**
   - ≥100 packages OR
   - ≥3h build time
   - Include `passthru.tests` tests
3. **Review** (involve affected maintainers if possible)
4. **Notify sub-maintainers:**
   - PR link + context
   - Ping in PR or via GitHub issues
5. **Grace period:** 7 days minimum for fixes
6. **Merge target** branch into PR
7. **Mark broken** packages as `broken = true;` in meta
8. **Merge** to target

**Key rules:**
- NixOS channel constituents block (exception to 7-day rule)
- Sub-maintainers expected to respond within 7 days
- Sample testing must cover downstream impact

**Common mistakes:**
- Merging with broken dependencies
- Not testing downstream packages
- Not notifying maintainers
- Insufficient grace period

## Staging Workflow (RFC 0026)

**Branch strategy** (from `CONTRIBUTING.md`, "Staging"):
```
master ←── staging-next ←── staging
 (Hydra)     (Hydra builds,    (not built by Hydra directly;
              fixes only)       mass rebuilds land here)
```

**Branch selection:**

| Branch | Use for | Rebuild count |
|--------|---------|---------------|
| master | Everything else | Under about 500 |
| staging | Mass rebuilds | 500 or more: consider `staging`; 1000 or more: should target it |
| staging-next | Fixes to Hydra builds only; ask the Staging room first for anything else | n/a |

Release branches use `release-YY.MM`, `staging-YY.MM`, and `staging-next-YY.MM`.

**Merge flow:**
1. Open the PR against the branch the rebuild count calls for
2. `staging` is merged into `staging-next` manually and regularly; Hydra builds `staging-next`
3. Once there are no major regressions, `staging-next` is merged into `master` through a PR
4. Automated merges keep `staging-next` and `staging` current with `master`

## Platform Support (RFC 0046)

**Support tiers:**

| Tier | Impact | Examples | Package Coverage |
|------|--------|----------|------------------|
| 1 | Block updates | x86_64-linux | Almost all |
| 2 | Investigate | aarch64-linux, x86_64-darwin | Most |
| 3 | Toolchain fixes | i686-linux, ARM variants | Popular |
| 4 | Generic fixes | Exotic architectures | Some |
| 5+ | WIP/minimal | wasm-wasi, emerging | Few/none |

**Platform-specific code:**
- Keep fixes in toolchain when possible
- Generic implementations preferred
- Non-generic code acceptable for higher tiers
- Tier determines breaking change tolerance

## Formatting Details (RFC 0166)

**Indentation:**
- 2 spaces per level (NEVER tabs)
- Increase by max 1 level per line
- Decrease can be arbitrary

**Line length:**
- 100 char soft limit (excluding indentation)
- Strings/paths/comments can exceed

**Spacing:**
- Inside brackets: `[ foo ]`
- Empty: `[ ]` and `{ }`
- After operators: `foo ++ bar`
- Around bindings and lambdas: `foo = bar;`, `x: y`

**Multi-line rules** (checked against `nixfmt` 1.5.0 output):
- Lists with more than one item are expanded, one item per line; a single short item may stay inline (`[ foo ]`)
- The first item never stays on the line with the opening bracket
- Non-empty attribute sets are expanded, one binding per line; a short set as a call argument (`foo.bar { x = 1; }`) can stay inline
- `let ... in` is always expanded across lines

**Function applications:**
```nix
# All fit
function arg1 arg2 arg3

# Last arg absorbed
function arg1 arg2 {
  attr = value;
}

# Overflow
function arg1 arg2
  arg3
  arg4
```

**Bindings:**
```nix
# Single-line
foo = "bar";

# Absorbed
foo = function {
  args;
};

# Multi-line
foo =
  function
    arg1
    arg2;
```

**Control flow:**
```nix
# if-then-else
if cond then
  value1
else if cond2 then
  value2
else
  value3

# let-in (always multi-line)
let
  foo = "bar";
in
body

# with (absorb when possible)
foo = with lib; [
  item1
];

# assert (like binding)
foo =
  assert condition;
  value;
```

**inherit:**
```nix
# Single-line
inherit foo bar;

# Multi-line (semicolon on own line)
inherit
  foo
  bar
  baz
  ;

# From expression
inherit (pkgs) app1 app2;

inherit (pkgs)
  app1
  app2
  ;
```

**Comments:**
- Single-line: `#` (preserve everything after)
- Multi-line: `/* */` (each on own line, indented)
- Doc-comments: `/** */` (RFC 0145 format)

**Strings:**
- Preserve quote style (`"` vs `''`)
- Don't auto-escape (`\n` stays `\n`)
- Simple interpolations inline
- Complex interpolations on new line

## Design Patterns

**Use lib combinators:**
```nix
# Good
lib.optional (hasFeature) "flag"
lib.optionals (doX) [ "--enable-x" ]

# Bad
if hasFeature then [ "flag" ] else [ ]
```

**callPackage:**
```nix
# Good - arguments match function params
callPackage ./foo.nix { customArg = value; }

# Bad - passing unrelated arguments
callPackage ./foo.nix pkgs  # pkgs already available
```

**Package variants:**
```nix
# Minor variations
variant = pkg.override { option = false; };

# Breaking changes
variant = callPackage ./path.nix { option = false; };

# Default arguments
{ option ? false }:
mkDerivation (lib.optionalAttrs option { ... })
```

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Cross-package file references | Self-contained packages only |
| Mixing test types | checkPhase=fast, passthru.tests=slow |
| Missing sourceProvenance | Always set for binaries |
| Platform-specific hacks | Keep in toolchain or generic |
| Breaking changes without notice | 7-day grace period + testing |
| Vertical alignment | Let formatter handle |
| Comments explaining WHAT | Explain WHY instead |
| Hardcoded license strings | Use `lib.licenses.*` |

## Problem Declaration (RFC 0127)

**System for declaring package/module issues:**

### meta.problems Structure

```nix
meta.problems = {
  python2-eol = {
    kind = "deprecated";
    message = "This package depends on Python 2, which has reached end of life.";
    urls = [ "https://github.com/NixOS/nixpkgs/issues/148779" ];
  };
  removal = {
    # kind = "removal"; # Inferred from attribute name
    message = "The application has been abandoned upstream, use libfoo instead.";
  };
};
```

**Problem kinds** (per `doc/using/configuration.chapter.md` and `pkgs/stdenv/generic/problems.nix`; a problem's name is also its kind when the name matches one):
- `removal` - Package scheduled for removal (at most one per package)
- `deprecated` - Package relies on software that reached end of life
- `maintainerless` - Generated automatically when `meta.maintainers` and `meta.teams` are empty; can't be declared manually
- `broken` - Generated automatically from `meta.broken = true`

Insecure packages still use `meta.knownVulnerabilities`, not `meta.problems`. Users choose a handler (`error`, `warn`, `ignore`) per package and problem with `config.problems.handlers` or `config.problems.matchers`; the default warns on `removal`.

**When to use:**
- Dependency is EOL (Python 2, old Node.js, etc.): `deprecated`
- Package is scheduled for removal from nixpkgs: `removal`

## Package Categories (RFC 0146)

This section previously showed `meta.categories = with lib.categories; [ ... ]`. Neither `lib.categories` nor a `meta.categories` check exists in the current tree (`lib/`, `pkgs/stdenv/generic/check-meta.nix`, and the meta chapter don't mention them). Don't add `meta.categories` to packages.

## Documentation Format (RFC 0072)

**CommonMark (Markdown) for all documentation:**

**Requirements:**
- Use CommonMark (standard Markdown)
- **No HTML tags in source** (breaks non-HTML output formats)
- YAML frontmatter OK
- Tables extension OK (widely supported)

**Good:**
```nix
longDescription = ''
  Tool for **building** packages.

  See the [upstream docs](https://example.com).
'';
```

**Bad:**
```nix
longDescription = ''
  Tool for <strong>building</strong> packages.

  <div class="note">See upstream docs</div>
'';
```

`meta.longDescription` is CommonMark; `meta.description` is a short plain-text phrase. NixOS option descriptions are Markdown too, and DocBook such as `<link xlink:href="..."/>` or `<literal>` is obsolete.

**Why:** HTML tags prevent rendering to man pages, epub, or other formats. Pure CommonMark is portable.

**Doc-comment content:**
````nix
{
  /**
    Brief description.

    # Type

    ```
    functionName :: { arg :: String } -> Derivation
    ```

    # Examples

    ```nix
    functionName { arg = "value"; }
    => result
    ```
  */
  functionName = { arg }: arg;
}
````

**Supported Markdown features:**
- Headings (`#`, `##`, `###`)
- **Bold**, *italic*, `code`
- Lists (ordered, unordered, nested)
- Tables (extension)
- Links `[text](url)`
- Code blocks with language specifiers
- Cross-references (via linking)

## Package Removal (RFC 0180)

`pkgs/README.md` ("Deprecating/removing packages") says there is currently no policy for when to remove a package, and asks you to try to find a new maintainer or fix smaller issues first. The one-release-cycle timeline this section used to list isn't in the tree, so don't present it as policy.

**Steps to remove a package** (from `pkgs/README.md`):
1. Delete the package directory and its `all-packages.nix` entry (if any)
2. Add a `throw` alias in `pkgs/top-level/aliases.nix`, with a short reason and the date: `foo = throw "foo was discontinued upstream"; # added 2026-01-01`
3. Check evaluation with `nix-env -qaP -f . --show-trace`
4. Commit with a message that explains why the package was removed, with a link if upstream declared it discontinued

Package removals don't get a release note; the throwing alias is the notice (`CONTRIBUTING.md`).

## Code Review Checklist

Module design (if NixOS/Home Manager module):
- [ ] Uses `settings` pattern for >10 options
- [ ] Only explicit options are "valuable" (main/mandatory/sensitive)
- [ ] Uses `pkgs.formats.*` with freeformType
- [ ] No `extraConfig` string options

Security & users (if service module):
- [ ] Uses `DynamicUser = true` when applicable
- [ ] If persistent user: `isSystemUser = true`, no static `uid`/`gid`
- [ ] Uses `StateDirectory`/`CacheDirectory`/`LogsDirectory`
- [ ] Doesn't run as root unnecessarily
- [ ] Static UID/GID has justification and is registered in `nixos/modules/misc/ids.nix`

Package structure:
- [ ] Uses `pkgs/by-name/${shard}/${name}/package.nix`
- [ ] Self-contained (no external file refs)
- [ ] Unique lowercased name

Testing:
- [ ] checkPhase for fast unit tests
- [ ] installCheckPhase for smoke tests
- [ ] passthru.tests for integration tests
- [ ] Tests pass locally

Metadata:
- [ ] description present and concise
- [ ] license uses `lib.licenses.*`
- [ ] maintainers listed
- [ ] platforms specified
- [ ] sourceProvenance set (if binary package)
- [ ] problems declared if applicable

Documentation:
- [ ] Doc-comments use `/** */` format
- [ ] CommonMark content (no HTML tags)
- [ ] Examples show input → output
- [ ] Type signatures included (when helpful)

Formatting:
- [ ] 2-space indentation
- [ ] 100 char soft limit
- [ ] Proper spacing in brackets
- [ ] Multi-line expansion rules followed
- [ ] Comments explain WHY not WHAT

Breaking changes:
- [ ] Sample testing done (100+ packages)
- [ ] Maintainers notified
- [ ] 7-day grace period
- [ ] Broken packages marked

Platform support:
- [ ] Tier-appropriate fixes
- [ ] Generic implementations preferred
- [ ] Platform-specific code isolated
