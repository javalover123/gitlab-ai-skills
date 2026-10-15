# Common Mistakes in Nix Code

Based on [nixpkgs contributing guidelines](https://github.com/NixOS/nixpkgs/blob/master/CONTRIBUTING.md) and common review feedback.

**Contents:** [Package Structure Mistakes](#package-structure-mistakes) · [Testing Mistakes](#testing-mistakes) · [Metadata Mistakes](#metadata-mistakes) · [NixOS Module Mistakes](#nixos-module-mistakes) · [Formatting Mistakes](#formatting-mistakes) · [Breaking Change Mistakes](#breaking-change-mistakes) · [Platform-Specific Mistakes](#platform-specific-mistakes) · [References](#references)

## Package Structure Mistakes

### Cross-Package File References

**Issue:** Package references files outside its directory.

**Why it's wrong:** Violates [RFC 0140](https://github.com/NixOS/rfcs/blob/master/rfcs/0140-simple-package-paths.md) self-containment requirement. Makes packages harder to move, refactor, or maintain.

**Before:**
```nix
# pkgs/by-name/ex/example/package.nix
{
  lib,
  stdenv,
}:
stdenv.mkDerivation {
  pname = "example";
  version = "1.0.0";

  # Bad: references outside package directory
  src = ../../../common/source.tar.gz;
}
```

**After:**
```nix
{
  lib,
  stdenv,
  fetchurl,
}:
stdenv.mkDerivation (finalAttrs: {
  pname = "example";
  version = "1.0.0";

  # Good: self-contained, fetches from upstream
  src = fetchurl {
    url = "https://example.com/releases/v${finalAttrs.version}/source.tar.gz";
    hash = "sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=";
  };
})
```

### Using `rec` Unnecessarily

**Issue:** Using `rec` when `finalAttrs` pattern is better.

**Why it's wrong:** `rec` makes debugging harder (infinite recursion errors) and doesn't work well with overrides.

**Before:**
```nix
stdenv.mkDerivation rec {
  name = "example-${version}";
  version = "1.0.0";

  src = fetchurl {
    url = "https://example.com/${name}.tar.gz";
    # ...
  };
}
```

**After:**
```nix
stdenv.mkDerivation (finalAttrs: {
  pname = "example";
  version = "1.0.0";

  src = fetchurl {
    url = "https://example.com/${finalAttrs.pname}-${finalAttrs.version}.tar.gz";
    # ...
  };
})
```

### Wrong Directory Shard

**Issue:** Package in wrong shard directory.

**Why it's wrong:** Breaks CI checks and package discovery.

**Before:**
```bash
# Bad: "example" starts with "ex", not "he"
pkgs/by-name/he/example/package.nix
```

**After:**
```bash
# Good: shard matches first 2 lowercase letters
pkgs/by-name/ex/example/package.nix
```

## Testing Mistakes

### Expensive Tests in checkPhase

**Issue:** Long-running or resource-intensive tests in checkPhase.

**Why it's wrong:** `checkPhase` runs during every build and should execute the unit tests shipped with the source. The test section of `pkgs/README.md` sends heavier integration tests to `passthru.tests` or NixOS module tests instead. Slow tests increase build times for everyone.

**Before:**
```nix
checkPhase = ''
  # Bad: runs the full integration suite during every build
  ./run-full-integration-suite
  ./benchmark-all-features
'';
```

**After:**
```nix
checkPhase = ''
  runHook preCheck
  # Good: fast unit tests only
  make quick-test
  runHook postCheck
'';

# Heavy tests go in passthru.tests. `nixosTests` is a package argument that
# links a test registered in nixos/tests/all-tests.nix.
passthru.tests = {
  integration = nixosTests.example;
};
```

### No installCheckPhase

**Issue:** Package installs binaries but doesn't verify they work.

**Why it's wrong:** Can't catch basic issues like missing runtime dependencies or broken executables. The stdenv chapter recommends at least `versionCheckHook` for sources that ship no tests.

**Before:**
```nix
stdenv.mkDerivation {
  # ... builds and installs ...
  # No verification!
}
```

**After:**
```nix
stdenv.mkDerivation {
  # ...

  nativeInstallCheckInputs = [ versionCheckHook ];
  doInstallCheck = true;
}
```

## Metadata Mistakes

### Hardcoded License Strings

**Issue:** Using string literals instead of `lib.licenses.*`.

**Why it's wrong:** Not machine-readable, inconsistent across packages, hard to query. The meta chapter wants a value from `lib.licenses` where one exists.

**Before:**
```nix
meta = {
  license = "MIT"; # Bad: string literal ("Apache 2.0" and similar are just as bad)
};
```

**After:**
```nix
meta = {
  license = lib.licenses.mit; # Good: standardized
};
```

For several licenses, use a list:
```nix
meta = {
  license = with lib.licenses; [ asl20 mit ];
};
```

Attribute names are lowerCamelCase (`mit`, `asl20`, `gpl3Plus`, `bsd3`, `unfree`). `lib.licenses.MIT`, `Apache2`, and `proprietary` don't exist. See the [license list](https://github.com/NixOS/nixpkgs/blob/master/lib/licenses/licenses.nix) for every available name.

### Missing sourceProvenance for Binaries

**Issue:** Binary package doesn't declare `sourceProvenance`.

**Why it's wrong:** `pkgs/README.md` says `meta.sourceProvenance` must be set if the package isn't built from source ([RFC 0089](https://github.com/NixOS/rfcs/blob/master/rfcs/0089-collect-non-source-package-meta.md)). Without it, users can't filter or set policy by provenance.

**Before:**
```nix
# Package contains pre-built binaries
stdenv.mkDerivation {
  # ...
  meta = {
    description = "Binary package";
    # Missing sourceProvenance!
  };
}
```

**After:**
```nix
stdenv.mkDerivation {
  # ...
  meta = {
    description = "Binary package";
    sourceProvenance = with lib.sourceTypes; [
      binaryNativeCode
    ];
  };
}
```

### Description Ends with Period

**Issue:** Description has trailing period.

**Why it's wrong:** The meta chapter says a description doesn't end with a period (or any punctuation), doesn't start with an article or the package name, and is capitalized. Descriptions are phrases, not sentences.

**Before:**
```nix
meta = {
  description = "A tool for doing things.";  # Bad: has period
};
```

**After:**
```nix
meta = {
  description = "Tool for doing things";  # Good: no period
};
```

## NixOS Module Mistakes

### Not Using mkEnableOption

**Issue:** Manually creating boolean enable option.

**Why it's wrong:** Verbose, inconsistent with other modules, missing standard description.

**Before:**
```nix
options.services.myapp.enable = lib.mkOption {
  type = lib.types.bool;
  default = false;
  description = "Enable myapp service";
};
```

**After:**
```nix
options.services.myapp.enable = lib.mkEnableOption "myapp service";
```

### Not Using mkPackageOption

**Issue:** Manually creating package option.

**Why it's wrong:** Verbose, doesn't follow nixpkgs conventions.

**Before:**
```nix
options.services.myapp.package = lib.mkOption {
  type = lib.types.package;
  default = pkgs.myapp;
  description = "The myapp package to use";
};
```

**After:**
```nix
options.services.myapp.package = lib.mkPackageOption pkgs "myapp" { };
```

### Config Not Wrapped in mkIf

**Issue:** Module config always active, even when disabled.

**Why it's wrong:** Wastes resources, may cause conflicts when service is disabled.

**Before:**
```nix
config = {
  # Bad: runs even when enable = false
  systemd.services.myapp = {
    description = "My App";
    wantedBy = [ "multi-user.target" ];
    # ...
  };
};
```

**After:**
```nix
config = lib.mkIf cfg.enable {
  # Good: only active when enabled
  systemd.services.myapp = {
    description = "My App";
    wantedBy = [ "multi-user.target" ];
    # ...
  };
};
```

### Service Running as Root

**Issue:** Systemd service runs as root without justification.

**Why it's wrong:** Security risk. Most services don't need root.

**Before:**
```nix
serviceConfig = {
  ExecStart = "${cfg.package}/bin/myapp";
  # Bad: no User specified, runs as root
};
```

**After:**
```nix
serviceConfig = {
  ExecStart = "${cfg.package}/bin/myapp";
  DynamicUser = true;  # Good: creates unprivileged user
  # Or specify a dedicated user
  User = cfg.user;
  Group = cfg.group;
};
```

### Weak Settings Types

**Issue:** Accepting strings for all settings.

**Why it's wrong:** No validation, easy to make mistakes, unclear what's valid.

**Before:**
```nix
options.services.myapp.settings = lib.mkOption {
  type = lib.types.attrsOf lib.types.str;  # Bad: everything is a string
  # ...
};
```

**After:**
```nix
# Good: use proper format with schema
settingsFormat = pkgs.formats.toml { };

options.services.myapp.settings = lib.mkOption {
  type = settingsFormat.type;  # Good: validates structure
  # ...
};
```

## Formatting Mistakes

### Using Tabs

**Issue:** Code uses tabs instead of spaces.

**Why it's wrong:** The official formatter, `nixfmt` ([RFC 0166](https://github.com/NixOS/rfcs/blob/master/rfcs/0166-nix-formatting.md)), indents with 2 spaces and rewrites tabs.

**Before:**
```nix
{
	buildInputs = [
		foo
		bar
	];
}
```

**After:**
```nix
{
  buildInputs = [
    foo
    bar
  ];
}
```

Run `nixfmt --check file.nix` or use your editor's "convert tabs to spaces" feature.

### Irregular Indentation and Bracket Layout

**Issue:** Indentation jumps by more than one level, or the opening bracket and the first item share a line while the rest wrap.

**Why it's wrong:** `nixfmt` output puts the opening bracket at the end of the binding line, indents the items by one level (2 spaces), and puts the closing bracket at the binding's indentation. Hand-formatted code that differs fails the CI format check and creates formatting-only diffs later.

**Before:**
```nix
{
  buildInputs = [
      foo  # Bad: 4 spaces, closing bracket indented
    ];
  nativeBuildInputs = [ pkg-config
    cmake
  ];
}
```

**After:**
```nix
{
  buildInputs = [
    foo
  ];
  nativeBuildInputs = [
    pkg-config
    cmake
  ];
}
```

`nixfmt` 1.x expands any list with more than one item onto separate lines and keeps a one-item list on one line (`[ foo ]`) when it was written that way. Don't hand-tune this; run the formatter (the repository's `treefmt` setup in `ci/treefmt.nix` runs `nixfmt`).

## Breaking Change Mistakes

### No Downstream Testing

**Issue:** Breaking change merged without testing affected packages.

**Why it's wrong:** Per [RFC 0088](https://github.com/NixOS/rfcs/blob/master/rfcs/0088-nixpkgs-breaking-change-policy.md), must test ≥100 packages or 3h build time.

**Before:**
```bash
# Bad: just merge the PR
git merge pr-branch
git push origin master
```

**After:**
```bash
# Good: test downstream impact first
nixpkgs-review pr 12345 --systems "x86_64-linux"

# Or test specific packages
nix-build -A python3Packages.foo
nix-build -A python3Packages.bar
# ... test 100+ affected packages

# Only then merge
```

Use [nixpkgs-review](https://github.com/Mic92/nixpkgs-review) to automate downstream testing.

### No Grace Period

**Issue:** Breaking change merged immediately after notifying maintainers.

**Why it's wrong:** RFC 0088 requires 7-day grace period for fixes.

**Before:**
```
Day 1: Notify maintainers
Day 1: Merge breaking change  # Bad: no time to fix
```

**After:**
```
Day 1: Notify maintainers with PR link
Day 8+: Merge breaking change  # Good: 7 days to respond
```

### Wrong Branch for Mass Rebuild

**Issue:** PR that rebuilds a large number of packages targets `master` instead of `staging`.

**Why it's wrong:** `CONTRIBUTING.md` (see [RFC 0026](https://github.com/NixOS/rfcs/blob/master/rfcs/0026-staging-workflow.md)) says mass rebuilds go to `staging` (`staging-YY.MM` for a release branch). It treats 500 or more rebuilds as a reason to consider `staging` and 1000 or more as a mass rebuild that should target it.

**Before:** the PR is based on `master` and CI reports a `10.rebuild-linux` label in a high bucket.

**After:** the PR targets `staging`. Rebase onto the merge base so you don't rebuild locally, then switch the base branch in the GitHub PR (Edit button):
```bash
git rebase --onto upstream/staging... upstream/master
```

Find the rebuild count in the labels CI adds to the PR (`10.rebuild-linux: N-M`, `10.rebuild-darwin: N-M`) rather than counting by hand.

## Platform-Specific Mistakes

### Hardcoding Platform Assumptions

**Issue:** Code assumes Linux or specific architecture.

**Why it's wrong:** Breaks on Darwin, ARM, etc. Not portable per [RFC 0046](https://github.com/NixOS/rfcs/blob/master/rfcs/0046-platform-support-tiers.md).

**Before:**
```nix
# Bad: assumes Linux-specific paths
postInstall = ''
  mkdir -p $out/lib
  cp -r /usr/lib/x86_64-linux-gnu/* $out/lib/
'';
```

**After:**
```nix
# Good: take files from $src or declared inputs, never from the host
postInstall = ''
  mkdir -p $out/lib
  cp -r lib/* $out/lib/
'';
```

### Platform-Specific Patches Without Justification

**Issue:** Adding platform-specific patches instead of fixing root cause.

**Why it's wrong:** Technical debt, makes code harder to maintain.

**Before:**
```nix
patches =
  lib.optional stdenv.hostPlatform.isDarwin ./darwin-workaround.patch
  ++ lib.optional stdenv.hostPlatform.isLinux ./linux-workaround.patch;
```

**After (preferred):**
```nix
# Good: generic fix that works everywhere
patches = [ ./fix-build-system.patch ];
```

Or if truly platform-specific:
```nix
# Acceptable: documented reason
patches =
  # Darwin lacks epoll, use kqueue instead
  lib.optional stdenv.hostPlatform.isDarwin ./darwin-workaround.patch;
```

Write `stdenv.hostPlatform.isDarwin`, `isLinux`, and the other platform predicates; the `stdenv.isDarwin`-style shorthands warn as deprecated in current nixpkgs.

## References

- [Nixpkgs Contributing Guidelines](https://github.com/NixOS/nixpkgs/blob/master/CONTRIBUTING.md)
- [RFC 0140: Package Structure](https://github.com/NixOS/rfcs/blob/master/rfcs/0140-simple-package-paths.md)
- [RFC 0119: Testing Conventions](https://github.com/NixOS/rfcs/blob/master/rfcs/0119-testing-conventions.md)
- [RFC 0089: Package Metadata](https://github.com/NixOS/rfcs/blob/master/rfcs/0089-collect-non-source-package-meta.md)
- [RFC 0166: Formatting](https://github.com/NixOS/rfcs/blob/master/rfcs/0166-nix-formatting.md)
- [RFC 0088: Breaking Changes](https://github.com/NixOS/rfcs/blob/master/rfcs/0088-nixpkgs-breaking-change-policy.md)
- [RFC 0026: Staging Workflow](https://github.com/NixOS/rfcs/blob/master/rfcs/0026-staging-workflow.md)
- [RFC 0046: Platform Support](https://github.com/NixOS/rfcs/blob/master/rfcs/0046-platform-support-tiers.md)
