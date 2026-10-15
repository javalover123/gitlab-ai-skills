# Nix Linting Tools

Tools for linting, formatting, and validating Nix code. The Nix ecosystem has fewer dedicated analyzers than most languages, but these cover the critical checks.

**Contents:** [Linters](#linters) · [Formatters](#formatters) · [Review and validation tools](#review-and-validation-tools) · [Pre-commit integration](#pre-commit-integration) · [Tool selection by task](#tool-selection-by-task)

## Linters

### statix

Linter for the Nix programming language. Catches anti-patterns and suggests fixes.

```bash
# Install
nix profile install nixpkgs#statix
# or in flake devShell
packages = [ pkgs.statix ];

# Check for issues
statix check .

# Auto-fix what it can
statix fix .

# Check a specific file
statix check flake.nix

# JSON output
statix check --format json .
```

**What to look for:**
- `bool_comparison` — comparing to `true`/`false` explicitly (`if x == true` → `if x`)
- `empty_let_in` — `let in expr` with no bindings
- `manual_inherit` — `x = x;` instead of `inherit x;`
- `manual_inherit_from` — `x = set.x;` instead of `inherit (set) x;`
- `useless_parens` — unnecessary parentheses
- `deprecated_to_path` — `builtins.toPath` is deprecated
- `empty_pattern` — an empty variadic pattern `{ ... }:`; prefer `_:` (this fires on NixOS modules that ignore their arguments)

`statix list` prints the lints in your installed version.
- `eta_reduction` — `x: f x` can be simplified to `f`

### deadnix

Finds unused variable bindings in Nix code. Dead code in Nix derivations often indicates stale dependencies or broken references.

```bash
# Install
nix profile install nixpkgs#deadnix
# or in flake devShell
packages = [ pkgs.deadnix ];

# Check for dead code
deadnix .

# Check specific files
deadnix default.nix flake.nix

# Auto-fix (remove dead bindings)
deadnix --edit .

# Quiet mode (exit code only)
deadnix --quiet .
```

**What to look for:** unused `let` bindings, unused function arguments, unused `inherit` entries. In nixpkgs, dead inputs in `callPackage` argument lists often signal that a dependency was removed but the package expression wasn't updated.

## Formatters

### nixfmt

The official Nix formatter (RFC 166). Enforces consistent style. The package is `nixfmt`; `nixfmt-rfc-style` is now a deprecated alias for it and `nixfmt-classic` has been removed.

```bash
# Install
nix profile install nixpkgs#nixfmt
# or
packages = [ pkgs.nixfmt ];

# Format a file
nixfmt file.nix

# Check without modifying (CI mode)
nixfmt --check file.nix

# Format all .nix files
find . -name '*.nix' -exec nixfmt {} +

# Verify formatting in CI
nixfmt --check $(find . -name '*.nix')
```

`nixfmt` can be pointed at a directory, but that now prints a deprecation warning; use the `nixfmt-tree` wrapper (`pkgs.nixfmt-tree`, a treefmt configuration that formats every `.nix` file under the current directory) or treefmt-nix for whole-tree runs.

**When to use:** before every commit. nixpkgs CI runs nixfmt on contributions — format locally to avoid CI failures.

## Review and validation tools

### nixpkgs-review

Tests package builds affected by a nixpkgs PR. The standard tool for validating nixpkgs contributions.

```bash
# Install
nix profile install nixpkgs#nixpkgs-review

# Review a PR by number
nixpkgs-review pr 12345

# Review local changes (staged or committed)
nixpkgs-review rev HEAD

# Review with specific systems (--system is deprecated in favor of --systems)
nixpkgs-review pr 12345 --systems x86_64-linux
```

**When to use:** before submitting any nixpkgs PR. nixpkgs-review builds every package affected by your change and reports build failures. It's the primary quality gate for nixpkgs contributions.

### nixpkgs-vet

CI validation tool that checks nixpkgs conventions and best practices.

```bash
# Typically runs in CI, but can be run locally from a nixpkgs checkout
# (BASE_BRANCH is the branch your PR targets):
./ci/nixpkgs-vet.sh master
```

**When to use:** nixpkgs CI runs this automatically; `ci/nixpkgs-vet.sh` closely matches it. `pkgs/by-name/README.md` ("Validation") describes its checks of the `pkgs/by-name` structure: for example that new top-level `callPackage` packages go through `pkgs/by-name` and that packages there don't refer to files outside their own directory. The tool's own README lists the full set. (The older `nix-build -A tests.nixpkgs-vet` attribute doesn't exist in the current tree.)

## Pre-commit integration

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: nixfmt
        name: nixfmt
        entry: nixfmt
        language: system
        files: '\.nix$'

      - id: statix
        name: statix check
        entry: statix check
        language: system
        pass_filenames: false  # statix check takes a single target, default "."
        files: '\.nix$'

      - id: deadnix
        name: deadnix
        entry: deadnix --fail
        language: system
        files: '\.nix$'
```

## Tool selection by task

| Task | Tools |
|------|-------|
| Pre-commit formatting | nixfmt |
| Lint for anti-patterns | statix |
| Find unused code | deadnix |
| Validate nixpkgs PR | nixpkgs-review + nixpkgs-vet |
| Full CI pipeline | nixfmt --check + statix check + deadnix --quiet |
