# Real Nixpkgs Examples

Well-structured packages and modules from nixpkgs that demonstrate best practices.

**Contents:** [Exemplary Packages](#exemplary-packages) · [Exemplary Modules](#exemplary-modules) · [Well-Reviewed PRs](#well-reviewed-prs) · [Anti-Examples (What Not to Do)](#anti-examples-what-not-to-do) · [Finding More Examples](#finding-more-examples) · [Learning Resources](#learning-resources) · [How to Study Examples](#how-to-study-examples) · [References](#references)

## Exemplary Packages

### GNU Hello (Simple Package)

**Location:** [`pkgs/by-name/he/hello/package.nix`](https://github.com/NixOS/nixpkgs/blob/master/pkgs/by-name/he/hello/package.nix)

**Why it's good:**
- Perfect example of `pkgs/by-name` structure
- Uses the `finalAttrs` pattern correctly
- Proper meta attributes and clean, minimal dependencies
- Has `passthru.tests` (`testers.testVersion` and a separate `test.nix`) and `versionCheckHook` as an install check

**What to learn:**
- How to structure a simple C package
- Proper use of `fetchurl` with a `hash`
- Standard meta fields
- How to wire package tests

### ripgrep (Rust Package)

**Location:** [`pkgs/by-name/ri/ripgrep/package.nix`](https://github.com/NixOS/nixpkgs/blob/master/pkgs/by-name/ri/ripgrep/package.nix)

**Why it's good:**
- Shows Rust package best practices
- Uses `rustPlatform.buildRustPackage`
- Installs the man page and shell completions with `installShellFiles`
- Cross-compilation support: it only runs the freshly built `rg` when `stdenv.hostPlatform.emulatorAvailable buildPackages` is true

**What to learn:**
- Rust package patterns
- How to handle shell completions
- Man page installation
- Guarding build-time execution of the target binary

### bat (Rust Package with Install Checks)

**Location:** [`pkgs/by-name/ba/bat/package.nix`](https://github.com/NixOS/nixpkgs/blob/master/pkgs/by-name/ba/bat/package.nix)

**Why it's good:**
- Skips known-flaky upstream tests with `checkFlags`, each skip grouped under a reason
- Uses `versionCheckHook` plus a short `installCheckPhase` that calls `runHook preInstallCheck` and `runHook postInstallCheck`
- Shell completion and man page installation
- Good example of a Rust package

**What to learn:**
- How to configure unit tests around sandbox limits
- Install checks that run the installed binary
- Build-time vs runtime dependencies
- Commenting each skipped test with the reason

## Exemplary Modules

### Nginx Module

**Location:** [`nixos/modules/services/web-servers/nginx/default.nix`](https://github.com/NixOS/nixpkgs/blob/master/nixos/modules/services/web-servers/nginx/default.nix)

**Why it's good:**
- Complex module with many options
- Proper use of `mkEnableOption` and `mkOption`
- Systemd sandboxing (`ProtectSystem`, `PrivateTmp`, `SystemCallFilter` and more) in the service
- Extensive configuration generation

**What to learn:**
- How to structure complex modules
- Configuration file generation
- Security best practices
- Virtual host patterns

### PostgreSQL Module

**Location:** [`nixos/modules/services/databases/postgresql.nix`](https://github.com/NixOS/nixpkgs/blob/master/nixos/modules/services/databases/postgresql.nix)

**Why it's good:**
- Shows database service patterns
- Proper initialization scripts
- State management with `StateDirectory`
- A hardened systemd service

**What to learn:**
- Stateful service management
- Database initialization
- User/group handling
- Pre/post start hooks

It also derives `MemoryDenyWriteExecute` from the JIT setting instead of hardcoding it, because JIT needs writable-executable memory.

### Home Manager (Git Module)

**Location:** [`modules/programs/git.nix` in home-manager](https://github.com/nix-community/home-manager/blob/master/modules/programs/git.nix)

**Why it's good:**
- Great example of user-level configuration
- Structured settings with types
- Good use of `lib.generators`
- Broad option coverage

**What to learn:**
- User configuration patterns
- Settings type validation
- Config file generation
- Attribute merging

## Well-Reviewed PRs

Search merged nixpkgs PRs for these shapes rather than relying on a fixed list (the links this section used to carry couldn't be checked against the current tree):

- **Package addition**: a new `pkgs/by-name/<xx>/<name>/package.nix`, a focused commit message, `passthru.tests` or an install check, and visible responses to review feedback.
- **Module addition**: the module, a NixOS test registered in `nixos/tests/all-tests.nix`, and service hardening.
- **Package removal**: the package directory deleted, a `throw` alias added to `pkgs/top-level/aliases.nix`, and a commit message that gives the reason.
- **Breaking change**: a PR that targets `staging` when the rebuild count calls for it, with downstream testing (`nixpkgs-review`) and notes to the maintainers of affected packages.

## Anti-Examples (What Not to Do)

Learning from mistakes is valuable too. These were rejected or required significant rework:

### Common Rejection Reasons

1. **Missing tests** - Package added without any verification
2. **Wrong directory structure** - Not using `pkgs/by-name`
3. **Hardcoded paths** - Using `/usr/bin` or similar
4. **No security hardening** - Service running as root unnecessarily
5. **Poor commit messages** - "Update package" or "Fix stuff"
6. **Missing required meta** - `meta.license` and `meta.maintainers` not set (`pkgs/README.md` says both must be set for new packages)

See [nixpkgs pull requests labeled "needs: more info"](https://github.com/NixOS/nixpkgs/pulls?q=is%3Apr+label%3A%229.needs%3A+more+info%22) for examples.

## Finding More Examples

### Search Techniques

**By package name:**
```bash
# Find package in nixpkgs
find pkgs/by-name -name "package-name"
```

**By feature:**
```bash
# Find packages using specific pattern
rg "passthru\.tests" pkgs/by-name
rg "mkEnableOption" nixos/modules
```

**NixOS Options Search:**
Visit [search.nixos.org/options](https://search.nixos.org/options) to see module options and their implementations.

### GitHub Code Search

Use GitHub's code search for patterns:
- [`finalAttrs` in nixpkgs](https://github.com/search?q=repo%3ANixOS%2Fnixpkgs+finalAttrs&type=code)
- [`passthru.tests` in nixpkgs](https://github.com/search?q=repo%3ANixOS%2Fnixpkgs+passthru.tests&type=code)
- [`mkEnableOption` in NixOS modules](https://github.com/search?q=repo%3ANixOS%2Fnixpkgs+path%3Anixos%2Fmodules+mkEnableOption&type=code)

## Learning Resources

### Official Documentation

- [Nixpkgs Manual](https://nixos.org/manual/nixpkgs/stable/) - Package guidelines
- [NixOS Manual](https://nixos.org/manual/nixos/stable/) - Module system
- [nix.dev](https://nix.dev/) - Tutorials and guides
- [Nixpkgs Contributing Guide](https://github.com/NixOS/nixpkgs/blob/master/CONTRIBUTING.md)

### Community Resources

- [NixOS Discourse](https://discourse.nixos.org/) - Ask questions
- [NixOS Wiki](https://wiki.nixos.org/) - Community knowledge
- [Matrix Chat](https://matrix.to/#/#nixos:nixos.org) - Real-time help
- [Nixpkgs Issues](https://github.com/NixOS/nixpkgs/issues) - Known problems

### Review Tools

- [nixpkgs-review](https://github.com/Mic92/nixpkgs-review) - PR review automation
- [nixfmt](https://github.com/NixOS/nixfmt) - Official formatter
- [nixpkgs-vet](https://github.com/NixOS/nixpkgs-vet) - CI validation tool
- [ofborg](https://github.com/NixOS/ofborg) - Builds a PR's changed packages and their `passthru.tests`

## How to Study Examples

When looking at example packages/modules:

1. **Read the full file** - Don't just skim
2. **Check the git history** - See how it evolved
3. **Read linked PRs** - See review discussions
4. **Run the tests, then try modifications** - Understand what they verify, then learn by experimenting

**Example workflow:**
```bash
# Clone nixpkgs
git clone https://github.com/NixOS/nixpkgs.git
cd nixpkgs

# Study a package
cat pkgs/by-name/he/hello/package.nix

# See its history
git log --follow pkgs/by-name/he/hello/package.nix

# Build it
nix-build -A hello

# Run its tests
nix-build -A hello.tests
```

## References

- [Nixpkgs Repository](https://github.com/NixOS/nixpkgs)
- [Home Manager Repository](https://github.com/nix-community/home-manager)
- [NixOS Search](https://search.nixos.org/)
- [Nixpkgs PR Queue](https://github.com/NixOS/nixpkgs/pulls)
