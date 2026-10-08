#!/usr/bin/env bash
# Audits dependencies for unused packages, duplicate versions, and security issues.
# Install the tools with: cargo install cargo-machete cargo-audit

set -euo pipefail

echo "=== Duplicate Dependency Versions ==="
echo "(Each duplicate version is compiled separately — costs time and binary size)"
echo ""
cargo tree -d 2>/dev/null | head -60 || echo "cargo tree failed (requires cargo 1.44+)"

echo ""
echo "=== Unused Dependencies ==="
if command -v cargo-machete &>/dev/null; then
    cargo machete 2>/dev/null || true
elif command -v cargo-shear &>/dev/null; then
    cargo shear 2>/dev/null || true
else
    echo "No unused-dep tool found. Install one:"
    echo "  cargo install cargo-machete    # fast regex-based (stable)"
    echo "  cargo install cargo-shear      # accurate parser-based, has --fix"
fi

echo ""
echo "=== Security Advisories ==="
if command -v cargo-audit &>/dev/null; then
    cargo audit 2>/dev/null || true
else
    echo "cargo-audit not found. Install: cargo install cargo-audit"
fi

echo ""
echo "=== Summary ==="
echo "To set up CI enforcement, add cargo-deny:"
echo "  cargo install cargo-deny"
echo "  cargo deny check"
echo "See references/dependency-optimization.md for deny.toml configuration."
