# Dependency Update Requirements

## CRITICAL: Mandatory Dependency Updates

**This is a REQUIRED quality gate. You MUST NOT mark any review, iteration, or security assessment as complete without updating all dependencies to their latest versions.**

## Why This Matters

LLM training data includes outdated library versions. You MUST query actual package registries to determine current versions. Never assume you know the latest version based on training data.

## Language-Specific Update Procedures

### Rust Projects

**MUST install cargo-edit:**
```bash
cargo install cargo-edit
```

**MUST update all dependencies:**
```bash
# Check for outdated dependencies
cargo outdated

# Update all dependencies to latest compatible versions
cargo upgrade

# Update Cargo.lock
cargo update

# Verify build still works
cargo check
cargo test
```

**Quality gate:** Run `cargo outdated` after updates. Output MUST show "All dependencies are up to date".

### Go Projects

**MUST update all dependencies:**
```bash
# Update all dependencies to latest versions
go get -u ./...

# Clean up go.mod and go.sum
go mod tidy

# Verify build
go build ./...
go test ./...
```

**Quality gate:** Run `go list -u -m all` and verify no updates available.

### Python Projects

**MUST install pip-tools or use pip:**
```bash
# List outdated packages
pip list --outdated

# Update all packages (requirements.txt approach)
pip install --upgrade -r requirements.txt

# Or use pip-tools
pip-compile --upgrade requirements.in
pip-sync requirements.txt

# Verify
python -m pytest
```

**Quality gate:** Run `pip list --outdated`. Output MUST show no outdated packages.

### JavaScript/TypeScript Projects

**MUST install npm-check-updates:**
```bash
npm install -g npm-check-updates
```

**MUST update all dependencies:**
```bash
# Check for updates
ncu

# Update package.json to latest versions
ncu -u

# Install updated dependencies
npm install

# Verify
npm test
npm run build
```

**Quality gate:** Run `npm outdated`. Output MUST show no outdated packages.

**Alternative with yarn:**
```bash
yarn upgrade-interactive --latest
yarn install
yarn test
```

### Ruby Projects

**MUST update all gems:**
```bash
# Update all gems to latest versions
bundle update

# Verify Gemfile.lock updated
git diff Gemfile.lock

# Run tests
bundle exec rake test
```

**Quality gate:** Run `bundle outdated`. Output MUST show "Bundle up to date!".

## Security Scanning After Updates

After updating dependencies, you MUST run security scans:

**Rust:**
```bash
cargo audit
```

**Go:**
```bash
govulncheck ./...
```

**Python:**
```bash
pip-audit
# or
safety check
```

**JavaScript:**
```bash
npm audit fix
# or
yarn audit
```

**Ruby:**
```bash
bundle audit check --update
```

## Breaking Changes

**If dependency updates cause breaking changes:**

1. You MUST fix the breaking changes in the same iteration
2. You MUST NOT leave the project in a broken state
3. You MUST update code to work with latest dependency versions
4. If breaking changes are extensive, create an ADR documenting the migration

**Do NOT:**
- Pin to old versions to avoid fixing breaking changes
- Skip dependency updates because they're "too hard"
- Leave TODOs to update dependencies later

## Quality Gate Checklist

Before marking iteration/review complete, verify:

- [ ] Dependency update tool installed (cargo-edit, ncu, etc.)
- [ ] All dependencies updated to latest versions
- [ ] Verification command shows no outdated dependencies
- [ ] All tests still pass
- [ ] Security audit shows no vulnerabilities
- [ ] Breaking changes (if any) are fixed
- [ ] Dependency updates documented in changelog

## Edge Cases

**Monorepo with multiple languages:**
- MUST update dependencies for ALL languages in the monorepo
- Run language-specific update procedures for each ecosystem

**Private package registries:**
- MUST configure registry authentication before checking versions
- Use registry-specific tools (e.g., npm with private registry)

**Vendored dependencies:**
- MUST update vendored code to latest upstream versions
- Document vendoring decisions in ADR

## Verification

**To verify you've queried the actual registry:**

```bash
# Rust - shows latest versions from crates.io
cargo search <package-name>

# Go - shows latest module versions
go list -m -versions <module>

# Python - shows latest version from PyPI
pip index versions <package>

# JavaScript - shows latest from npm
npm view <package> version

# Ruby - shows latest from RubyGems
gem list --remote <gem-name>
```

**You MUST use these commands or equivalent to verify latest versions, not rely on training data.**
