#!/usr/bin/env bash
# run-quality-checks.sh
# Automated quality tool orchestration for iterative improvement
#
# Usage: ./run-quality-checks.sh [language]
# If language not specified, auto-detects from project files

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Counters
CHECKS_RUN=0
CHECKS_PASSED=0
CHECKS_FAILED=0

# Function to run a check and track results
run_check() {
    local name="$1"
    shift
    local cmd="$*"

    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Running: $name"
    echo "Command: $cmd"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    CHECKS_RUN=$((CHECKS_RUN + 1))

    if eval "$cmd"; then
        echo -e "${GREEN}✓ $name passed${NC}\n"
        CHECKS_PASSED=$((CHECKS_PASSED + 1))
        return 0
    else
        echo -e "${RED}✗ $name failed${NC}\n"
        CHECKS_FAILED=$((CHECKS_FAILED + 1))
        return 1
    fi
}

# Auto-detect language
detect_language() {
    if [[ -f "Cargo.toml" ]]; then
        echo "rust"
    elif [[ -f "go.mod" ]]; then
        echo "go"
    elif [[ -f "pyproject.toml" ]] || [[ -f "setup.py" ]]; then
        echo "python"
    elif [[ -f "package.json" ]]; then
        echo "javascript"
    elif [[ -f "Makefile" ]] && grep -q "\.c\|\.h" Makefile; then
        echo "c"
    elif [[ -f "flake.nix" ]]; then
        echo "nix"
    else
        echo "unknown"
    fi
}

# Rust checks
check_rust() {
    echo "Running Rust quality checks..."

    # Format check
    if command -v cargo &> /dev/null; then
        run_check "Rust formatting" "cargo fmt --check" || true
        run_check "Clippy (linter)" "cargo clippy -- -D warnings" || true
        run_check "Tests" "cargo test --all-features" || true

        # Optional checks (don't fail if tools not installed)
        if command -v cargo-audit &> /dev/null; then
            run_check "Security audit" "cargo audit" || true
        else
            echo -e "${YELLOW}⚠ cargo-audit not installed, skipping security check${NC}"
        fi

        if command -v cargo-tarpaulin &> /dev/null; then
            run_check "Test coverage" "cargo tarpaulin --out Stdout" || true
        else
            echo -e "${YELLOW}⚠ cargo-tarpaulin not installed, skipping coverage${NC}"
        fi

        if command -v cargo-outdated &> /dev/null; then
            run_check "Dependency freshness" "cargo outdated --exit-code 1" || true
        else
            echo -e "${YELLOW}⚠ cargo-outdated not installed, skipping dependency check${NC}"
        fi
    else
        echo -e "${RED}cargo not found, cannot run Rust checks${NC}"
        exit 1
    fi
}

# Go checks
check_go() {
    echo "Running Go quality checks..."

    if command -v go &> /dev/null; then
        run_check "Go formatting" "test -z \$(gofmt -l .)" || true
        run_check "Go vet" "go vet ./..." || true
        run_check "Tests with race detector" "go test -race ./..." || true

        if command -v golangci-lint &> /dev/null; then
            run_check "golangci-lint" "golangci-lint run" || true
        else
            echo -e "${YELLOW}⚠ golangci-lint not installed${NC}"
        fi

        if command -v gosec &> /dev/null; then
            run_check "Security scan (gosec)" "gosec ./..." || true
        else
            echo -e "${YELLOW}⚠ gosec not installed${NC}"
        fi

        if command -v govulncheck &> /dev/null; then
            run_check "Vulnerability check" "govulncheck ./..." || true
        else
            echo -e "${YELLOW}⚠ govulncheck not installed${NC}"
        fi
    else
        echo -e "${RED}go not found, cannot run Go checks${NC}"
        exit 1
    fi
}

# Python checks
check_python() {
    echo "Running Python quality checks..."

    if command -v python3 &> /dev/null; then
        if command -v ruff &> /dev/null; then
            run_check "Ruff linter" "ruff check ." || true
            run_check "Ruff formatter" "ruff format --check ." || true
        else
            echo -e "${YELLOW}⚠ ruff not installed${NC}"
        fi

        if command -v mypy &> /dev/null; then
            run_check "Type checking (mypy)" "mypy ." || true
        else
            echo -e "${YELLOW}⚠ mypy not installed${NC}"
        fi

        if command -v bandit &> /dev/null; then
            run_check "Security scan (bandit)" "bandit -r . -ll" || true
        else
            echo -e "${YELLOW}⚠ bandit not installed${NC}"
        fi

        if command -v pytest &> /dev/null; then
            run_check "Tests with coverage" "pytest --cov" || true
        else
            echo -e "${YELLOW}⚠ pytest not installed${NC}"
        fi

        if command -v safety &> /dev/null; then
            run_check "Dependency vulnerabilities" "safety check" || true
        else
            echo -e "${YELLOW}⚠ safety not installed${NC}"
        fi
    else
        echo -e "${RED}python3 not found, cannot run Python checks${NC}"
        exit 1
    fi
}

# C checks
check_c() {
    echo "Running C quality checks..."

    if command -v gcc &> /dev/null || command -v clang &> /dev/null; then
        if [[ -f "Makefile" ]]; then
            run_check "Build with warnings" "make CFLAGS='-Wall -Wextra -Werror'" || true
        fi

        if command -v cppcheck &> /dev/null; then
            run_check "Static analysis (cppcheck)" "cppcheck --enable=all --error-exitcode=1 ." || true
        else
            echo -e "${YELLOW}⚠ cppcheck not installed${NC}"
        fi

        if command -v clang &> /dev/null; then
            run_check "Clang static analyzer" "scan-build make" || true
        else
            echo -e "${YELLOW}⚠ clang not installed${NC}"
        fi

        if [[ -f "test" ]] && command -v valgrind &> /dev/null; then
            run_check "Memory check (valgrind)" "valgrind --leak-check=full --error-exitcode=1 ./test" || true
        else
            echo -e "${YELLOW}⚠ valgrind not installed or no test binary${NC}"
        fi
    else
        echo -e "${RED}gcc/clang not found, cannot run C checks${NC}"
        exit 1
    fi
}

# JavaScript/TypeScript checks
check_javascript() {
    echo "Running JavaScript/TypeScript quality checks..."

    if [[ -f "package.json" ]]; then
        if command -v npm &> /dev/null; then
            run_check "npm audit" "npm audit --audit-level=moderate" || true

            if [[ -f "node_modules/.bin/eslint" ]]; then
                run_check "ESLint" "npm run lint" || true
            else
                echo -e "${YELLOW}⚠ ESLint not installed${NC}"
            fi

            if [[ -f "tsconfig.json" ]]; then
                run_check "TypeScript compilation" "npm run build" || true
            fi

            if grep -q "\"test\":" package.json; then
                run_check "Tests" "npm test" || true
            fi
        else
            echo -e "${RED}npm not found${NC}"
            exit 1
        fi
    else
        echo -e "${RED}package.json not found${NC}"
        exit 1
    fi
}

# Nix checks
check_nix() {
    echo "Running Nix quality checks..."

    if command -v nix &> /dev/null; then
        if [[ -f "flake.nix" ]]; then
            run_check "Flake check" "nix flake check" || true
        fi

        if command -v nixfmt &> /dev/null; then
            run_check "Nix formatting" "nixfmt --check ." || true
        else
            echo -e "${YELLOW}⚠ nixfmt not installed${NC}"
        fi

        if command -v statix &> /dev/null; then
            run_check "Static analysis (statix)" "statix check" || true
        else
            echo -e "${YELLOW}⚠ statix not installed${NC}"
        fi

        if command -v deadnix &> /dev/null; then
            run_check "Dead code detection" "deadnix --fail ." || true
        else
            echo -e "${YELLOW}⚠ deadnix not installed${NC}"
        fi
    else
        echo -e "${RED}nix not found, cannot run Nix checks${NC}"
        exit 1
    fi
}

# Main execution
main() {
    local language="${1:-$(detect_language)}"

    echo "╔════════════════════════════════════════════════╗"
    echo "║   Quality Checks — Iterate Skill               ║"
    echo "╚════════════════════════════════════════════════╝"
    echo ""
    echo "Detected language: $language"
    echo ""

    case "$language" in
        rust)
            check_rust
            ;;
        go)
            check_go
            ;;
        python)
            check_python
            ;;
        c)
            check_c
            ;;
        javascript|typescript)
            check_javascript
            ;;
        nix)
            check_nix
            ;;
        unknown)
            echo -e "${RED}Could not detect project language${NC}"
            echo "Supported: rust, go, python, c, javascript, nix"
            echo "Usage: $0 <language>"
            exit 1
            ;;
        *)
            echo -e "${RED}Unsupported language: $language${NC}"
            exit 1
            ;;
    esac

    # Summary
    echo ""
    echo "╔════════════════════════════════════════════════╗"
    echo "║   Quality Check Summary                        ║"
    echo "╚════════════════════════════════════════════════╝"
    echo ""
    echo "Total checks run: $CHECKS_RUN"
    echo -e "${GREEN}Passed: $CHECKS_PASSED${NC}"
    echo -e "${RED}Failed: $CHECKS_FAILED${NC}"
    echo ""

    if [[ $CHECKS_FAILED -eq 0 ]]; then
        echo -e "${GREEN}All quality checks passed! ✓${NC}"
        exit 0
    else
        echo -e "${RED}Some quality checks failed${NC}"
        echo "Review output above to identify gaps"
        exit 1
    fi
}

main "$@"
