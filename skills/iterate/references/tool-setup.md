# Tool Setup and Configuration

How to install and configure quality tools for iterative improvement.

## Tool Selection by Language

### Rust

**Essential tools:**
```bash
# Linter
rustup component add clippy

# Formatter
rustup component add rustfmt

# Security auditor
cargo install cargo-audit

# Coverage
cargo install cargo-tarpaulin

# Outdated dependencies
cargo install cargo-outdated

# Unused dependencies
cargo install cargo-udeps

# License checking
cargo install cargo-deny
```

**Configuration (clippy):**

Create `.cargo/config.toml` or add to `Cargo.toml`:
```toml
[lints.rust]
unsafe_code = "deny"
missing_docs = "warn"

[lints.clippy]
all = "warn"
pedantic = "warn"
unwrap_used = "deny"
expect_used = "deny"
panic = "deny"
todo = "deny"
```

**Configuration (rustfmt):**

Create `rustfmt.toml`:
```toml
max_width = 100
hard_tabs = false
tab_spaces = 4
newline_style = "Unix"
use_small_heuristics = "Default"
reorder_imports = true
reorder_modules = true
```

### Go

**Essential tools:**
```bash
# Meta-linter (includes many linters)
go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest

# Security scanner
go install github.com/securego/gosec/v2/cmd/gosec@latest

# Static analysis
go install honnef.co/go/tools/cmd/staticcheck@latest

# Vulnerability scanning
go install golang.org/x/vuln/cmd/govulncheck@latest
```

**Configuration (golangci-lint):**

Create `.golangci.yml`:
```yaml
run:
  timeout: 5m
  tests: true

linters:
  enable:
    - gofmt
    - govet
    - staticcheck
    - gosec
    - errcheck
    - ineffassign
    - unused
    - misspell
    - gocyclo
    - goconst
    - unconvert

linters-settings:
  gocyclo:
    min-complexity: 15
  goconst:
    min-len: 3
    min-occurrences: 3

issues:
  exclude-use-default: false
  max-issues-per-linter: 0
  max-same-issues: 0
```

### Python

**Essential tools:**
```bash
# Linter and formatter (fast, modern)
pip install ruff

# Type checker
pip install mypy

# Security scanner
pip install bandit

# Testing and coverage
pip install pytest pytest-cov

# Dependency vulnerability scanner
pip install safety

# Import sorting
pip install isort
```

**Configuration (ruff):**

Create `pyproject.toml`:
```toml
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "W", "C90", "I", "N", "UP", "S", "B", "A", "C4"]
ignore = []

[tool.ruff.lint.per-file-ignores]
"tests/*" = ["S101"]  # Allow assert in tests

[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--cov=mypackage --cov-report=term-missing"
```

### C/C++

**Essential tools:**
```bash
# Ubuntu/Debian
apt-get install cppcheck clang clang-tools valgrind

# macOS
brew install cppcheck llvm valgrind

# Arch
pacman -S cppcheck clang valgrind
```

**Configuration (cppcheck):**

Create `.cppcheck`:
```
--enable=all
--suppress=missingIncludeSystem
--inline-suppr
--error-exitcode=1
```

**Configuration (clang-tidy):**

Create `.clang-tidy`:
```yaml
Checks: >
  clang-analyzer-*,
  bugprone-*,
  cert-*,
  cppcoreguidelines-*,
  modernize-*,
  performance-*,
  portability-*,
  readability-*,
  -modernize-use-trailing-return-type

WarningsAsErrors: '*'
HeaderFilterRegex: '.*'
FormatStyle: file
```

**Compiler flags for security:**
```makefile
CFLAGS = -Wall -Wextra -Werror \
         -fstack-protector-strong \
         -D_FORTIFY_SOURCE=2 \
         -pie -fPIE \
         -Wformat -Wformat-security \
         -Wl,-z,relro,-z,now
```

### JavaScript/TypeScript

**Essential tools:**
```bash
# Linter
npm install --save-dev eslint

# TypeScript
npm install --save-dev typescript

# Security scanner
npm install --save-dev eslint-plugin-security

# Testing
npm install --save-dev jest

# Code formatter
npm install --save-dev prettier
```

**Configuration (ESLint):**

Create `.eslintrc.json`:
```json
{
  "env": {
    "es2022": true,
    "node": true
  },
  "extends": [
    "eslint:recommended",
    "plugin:security/recommended"
  ],
  "rules": {
    "no-console": "warn",
    "no-unused-vars": "error",
    "security/detect-object-injection": "off"
  }
}
```

**Configuration (TypeScript):**

Create `tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "commonjs",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noImplicitReturns": true
  }
}
```

### Nix

**Essential tools:**
```bash
# Formatter
nix-env -iA nixpkgs.nixfmt-rfc-style

# Linter
nix-env -iA nixpkgs.statix

# Dead code detection
nix-env -iA nixpkgs.deadnix
```

**Configuration (via Nix):**

In `flake.nix`:
```nix
{
  devShells.default = pkgs.mkShell {
    nativeBuildInputs = with pkgs; [
      nixfmt-rfc-style
      statix
      deadnix
      nix-linter
    ];
  };
}
```

## Continuous Integration Setup

### GitHub Actions (Rust)

Create `.github/workflows/ci.yml`:
```yaml
name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: dtolnay/rust-toolchain@stable
        with:
          components: clippy, rustfmt

      - name: Check formatting
        run: cargo fmt --check

      - name: Clippy
        run: cargo clippy -- -D warnings

      - name: Tests
        run: cargo test --all-features

      - name: Security audit
        run: |
          cargo install cargo-audit
          cargo audit

      - name: Coverage
        run: |
          cargo install cargo-tarpaulin
          cargo tarpaulin --out Xml

      - name: Upload coverage
        uses: codecov/codecov-action@v4
```

### GitLab CI (Go)

Create `.gitlab-ci.yml`:
```yaml
image: golang:1.22

stages:
  - test
  - security

test:
  stage: test
  script:
    - go fmt ./...
    - go vet ./...
    - go test -race -cover ./...
  coverage: '/coverage: \d+.\d+% of statements/'

lint:
  stage: test
  script:
    - curl -sSfL https://raw.githubusercontent.com/golangci/golangci-lint/master/install.sh | sh -s -- -b $(go env GOPATH)/bin
    - golangci-lint run

security:
  stage: security
  script:
    - go install github.com/securego/gosec/v2/cmd/gosec@latest
    - gosec ./...
    - go install golang.org/x/vuln/cmd/govulncheck@latest
    - govulncheck ./...
```

### Pre-commit Hooks

**Install pre-commit:**
```bash
pip install pre-commit
```

**Create `.pre-commit-config.yaml`:**
```yaml
repos:
  # Rust
  - repo: https://github.com/doublify/pre-commit-rust
    rev: v1.0
    hooks:
      - id: fmt
      - id: clippy
      - id: cargo-check

  # Go
  - repo: https://github.com/dnephin/pre-commit-golang
    rev: v0.5.1
    hooks:
      - id: go-fmt
      - id: go-vet
      - id: go-lint

  # Python
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.3.0
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]
      - id: ruff-format

  # General
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
```

**Install hooks:**
```bash
pre-commit install
```

## Editor Integration

### VS Code

**Extensions:**
- Rust: rust-analyzer
- Go: Go Team at Google
- Python: Pylance
- C/C++: clangd

**Settings (`.vscode/settings.json`):**
```json
{
  "rust-analyzer.checkOnSave.command": "clippy",
  "editor.formatOnSave": true,
  "go.lintOnSave": "workspace",
  "go.lintTool": "golangci-lint",
  "python.linting.enabled": true,
  "python.linting.ruffEnabled": true,
  "C_Cpp.clang_format_style": "file"
}
```

### Neovim

**Using built-in LSP:**
```lua
-- ~/.config/nvim/init.lua
local lspconfig = require('lspconfig')

-- Rust
lspconfig.rust_analyzer.setup{
  settings = {
    ['rust-analyzer'] = {
      checkOnSave = {
        command = "clippy"
      }
    }
  }
}

-- Go
lspconfig.gopls.setup{}

-- Python
lspconfig.pyright.setup{}

-- C/C++
lspconfig.clangd.setup{}
```

## Quality Metrics Dashboard

### Collecting Metrics

Create `scripts/collect-metrics.sh`:
```bash
#!/bin/bash
set -euo pipefail

# Rust example
echo "=== Metrics for $(date) ==="

echo "Clippy warnings:"
cargo clippy 2>&1 | grep -c "warning:" || echo "0"

echo "Test results:"
cargo test 2>&1 | grep "test result:" || echo "No tests"

echo "Coverage:"
cargo tarpaulin --out Stdout 2>&1 | grep "Coverage:" || echo "N/A"

echo "Security issues:"
cargo audit 2>&1 | grep "vulnerabilities found" || echo "0"

echo "Outdated dependencies:"
cargo outdated --exit-code 0 | wc -l
```

### Tracking Over Time

Create iteration metrics file:
```markdown
# Quality Metrics

## Iteration 1 (2024-03-15)
- Clippy warnings: 23
- Test coverage: 45%
- Security issues: 8
- Failing tests: 6

## Iteration 2 (2024-03-16)
- Clippy warnings: 15 ↓
- Test coverage: 52% ↑
- Security issues: 0 ✓
- Failing tests: 0 ✓

## Iteration 3 (2024-03-17)
- Clippy warnings: 0 ✓
- Test coverage: 84% ↑
- Security issues: 0 ✓
- Failing tests: 0 ✓
```

## NixOS Integration

**In `flake.nix`:**
```nix
{
  description = "Project with quality tools";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    rust-overlay.url = "github:oxalica/rust-overlay";
  };

  outputs = { self, nixpkgs, rust-overlay }:
    let
      system = "x86_64-linux";
      pkgs = import nixpkgs {
        inherit system;
        overlays = [ rust-overlay.overlays.default ];
      };
    in {
      devShells.${system}.default = pkgs.mkShell {
        nativeBuildInputs = with pkgs; [
          # Rust
          (rust-bin.stable.latest.default.override {
            extensions = [ "rust-src" "clippy" "rustfmt" ];
          })
          cargo-audit
          cargo-tarpaulin
          cargo-outdated

          # Go
          go
          golangci-lint
          gosec

          # Python
          python311
          python311Packages.ruff
          python311Packages.mypy
          python311Packages.bandit

          # C/C++
          clang
          clang-tools
          cppcheck
          valgrind

          # General
          pre-commit
          git
        ];

        shellHook = ''
          echo "Quality tools loaded!"
          echo "Run 'make check' to run all quality checks"
        '';
      };
    };
}
```

## Makefile Integration

Create `Makefile`:
```makefile
.PHONY: check fmt lint test security coverage

check: fmt lint test security coverage

# Rust
fmt:
	cargo fmt --check

lint:
	cargo clippy -- -D warnings

test:
	cargo test --all-features

security:
	cargo audit

coverage:
	cargo tarpaulin --out Stdout

# Or Go
fmt:
	go fmt ./...

lint:
	golangci-lint run

test:
	go test -race -cover ./...

security:
	gosec ./...
	govulncheck ./...

coverage:
	go test -coverprofile=coverage.out ./...
	go tool cover -func=coverage.out
```

## Troubleshooting

### "Tool not found"

**Solution**: Ensure tool is installed and in PATH
```bash
# Check if tool exists
which cargo-clippy

# Add cargo bin to PATH
export PATH="$HOME/.cargo/bin:$PATH"
```

### "False positives from linter"

**Solution**: Suppress with justification
```rust
#[allow(clippy::similar_names)] // domain terms are similar
fn process_user_data() { ... }
```

### "Coverage tool fails"

**Solution**: Check dependencies
```bash
# Rust: need llvm-tools-preview
rustup component add llvm-tools-preview

# C: need gcov
apt-get install gcov
```

### "CI too slow"

**Solution**: Cache dependencies
```yaml
# GitHub Actions
- uses: actions/cache@v4
  with:
    path: |
      ~/.cargo/registry
      ~/.cargo/git
      target
    key: ${{ runner.os }}-cargo-${{ hashFiles('**/Cargo.lock') }}
```

## Resources

- **Rust tools**: https://rust-lang.github.io/rustup/
- **Go tools**: https://github.com/golangci/golangci-lint
- **Python tools**: https://docs.astral.sh/ruff/
- **C tools**: http://cppcheck.sourceforge.net/
- **Pre-commit**: https://pre-commit.com/
- **GitHub Actions**: https://docs.github.com/en/actions
