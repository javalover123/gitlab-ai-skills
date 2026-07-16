# Code Duplication Detection

Finding duplicate code, measuring complexity, and knowing when to actually consolidate
things. Not every duplication is bad — but you need the tools to tell the difference.

## Clone Detection Tools

### Go
```bash
# dupl — finds duplicated Go code blocks
go install github.com/mibk/dupl@latest
dupl -t 100 ./...    # threshold of 100 tokens
```

### Rust
```bash
# No single dominant tool. Use IDE built-in clone detection (IntelliJ/RustRover)
# or jscpd for language-agnostic detection:
npx jscpd --pattern "**/*.rs" --min-tokens 50
```

### Python
```bash
# jscpd works well for Python too
npx jscpd --pattern "**/*.py" --min-tokens 50

# Or use pylint's built-in duplicate-code checker
pylint --disable=all --enable=duplicate-code src/
```

### C
```bash
# CPD (Copy-Paste Detector) from PMD
pmd cpd --minimum-tokens 100 --language c --dir src/

# Simian (Similarity Analyser)
simian -threshold=6 src/**/*.c src/**/*.h

# duplo
duplo -ml 6 -pt 100 src/
```

### Nix
No automated tools for Nix duplication. Manual review is your friend — search for
repeated patterns in module definitions and derivation attributes.

## Complexity Analysis

### Go
```bash
# gocyclo — cyclomatic complexity
go install github.com/fzipp/gocyclo/cmd/gocyclo@latest
gocyclo -over 15 .

# gocognit — cognitive complexity (often more useful)
go install github.com/uudashr/gocognit/cmd/gocognit@latest
gocognit -over 15 .

# golangci-lint with funlen (function length checker)
golangci-lint run --enable funlen
```

### Rust
```bash
# clippy has a cognitive_complexity lint
cargo clippy -- -W clippy::cognitive_complexity

# For more detailed metrics, use cargo-geiger or IDE tools
```

### Python
```bash
# radon — cyclomatic complexity + maintainability index
pip install radon
radon cc src/ -a -nc        # show average, sort by complexity
radon mi src/ -nc           # maintainability index

# mccabe via ruff or pylint
ruff check --select C901 src/
```

### C
```bash
# lizard — multi-language complexity analyzer
pip install lizard
lizard src/ -l c -T cyclomatic_complexity=15

# pmccabe
pmccabe src/*.c | sort -rn | head -20

# clang-tidy readability checks
clang-tidy -checks='readability-function-cognitive-complexity' src/*.c
```

## Refactoring Analysis Tools

These tools help you find dead code, unused dependencies, and structural issues
that point to refactoring opportunities.

### Multi-language

**Semgrep** — Structural pattern matching. Write rules to find specific anti-patterns:

```bash
pip install semgrep

# Run with a custom rule
semgrep --config .semgrep.yml src/
```

Example `.semgrep.yml` rule for catching unwrapped Results in Rust:
```yaml
rules:
  - id: no-unwrap-in-library
    pattern: $EXPR.unwrap()
    message: "Don't use .unwrap() in library code — use ? or proper error handling"
    languages: [rust]
    severity: WARNING
    paths:
      exclude:
        - "*_test.rs"
        - "tests/"
```

**Tokei** — Fast code statistics (lines, comments, blanks by language):
```bash
cargo install tokei
tokei .
```

### Python

```bash
# vulture — finds unused code
pip install vulture
vulture src/ --min-confidence 80    # higher = fewer false positives

# ruff — fast linter with auto-fix capabilities
pip install ruff
ruff check --fix src/
```

### Rust

```bash
# cargo-udeps — finds unused dependencies (requires nightly)
cargo +nightly udeps

# cargo-machete — faster alternative, doesn't need nightly
cargo install cargo-machete
cargo machete

# cargo-bloat — find what's making your binary large
cargo install cargo-bloat
cargo bloat --release --crates
```

### JavaScript / TypeScript

```bash
# depcheck — unused dependencies
npx depcheck

# madge — circular dependency detection
npx madge --circular --extensions ts src/

# knip — unused files, dependencies, and exports
npx knip
```

### Go

```bash
# deadcode — finds unreachable functions
go install golang.org/x/tools/cmd/deadcode@latest
deadcode ./...

# gocyclo — complexity
gocyclo -over 15 .

# staticcheck U1000 — unused code
staticcheck -checks U1000 ./...
```

### C

```bash
# CMetrics — code metrics for C
cmetrics src/*.c

# cppcheck — unused function detection
cppcheck --enable=unusedFunction src/

# include-what-you-use (IWYU) — unnecessary includes
iwyu src/*.c
```

## Manual Detection Patterns

Automated tools miss things. These `rg` commands catch patterns that tools often don't:

```bash
# Finding similar function signatures (potential duplicates)
rg '^(pub )?(async )?fn (fetch|list|create|update|delete)' --type rust
rg '^func (Fetch|List|Create|Update|Delete)' --type go
rg '^def (fetch|list|create|update|delete)' --type py

# Finding repeated error handling patterns
rg 'if err != nil' --type go -A3
rg '\.unwrap\(\)' --type rust
rg 'except.*:' --type py -A2
rg 'if.*== NULL' --type c -A2

# Finding magic strings (candidates for constants)
rg -oh '"[a-z_-]+"' --type go | sort | uniq -c | sort -rn | head -40

# Finding inline normalization (should use centralized helpers)
rg 'ToLower|to_lowercase|\.lower\(\)|tolower' --type go
rg 'strings\.Replace|\.replace\(' --type go
```

## Complexity Thresholds

Use these as investigation starting points, not hard rules.

| Metric | Acceptable | Review | Refactor | Critical |
|---|---|---|---|---|
| Cyclomatic complexity | 1-15 | 15-20 | 20-30 | 30+ |
| Cognitive complexity | 1-15 | 15-25 | 25-35 | 35+ |
| Function lines | 1-80 | 80-120 | 120-200 | 200+ |
| File lines | 1-500 | 500-800 | 800-1200 | 1200+ |
| Duplicate tokens | -- | 50-100 | 100-150 | 150+ |

**A word of caution:** Not every metric violation needs refactoring. A `switch` over 40
enum variants has high cyclomatic complexity, but it might be the clearest way to express
that logic. A 600-line file might be perfectly cohesive. Use metrics as starting points
for investigation, not as mechanical rules.

## Identifying Refactoring Targets

| Signal | What It Means | Tool to Use |
|---|---|---|
| High cyclomatic complexity | Function does too many things | radon, gocyclo, lizard |
| Unused code | Dead weight in the codebase | vulture, deadcode, cargo-udeps |
| Circular dependencies | Tangled architecture | madge, go mod graph |
| Duplicate code | Missing abstraction (or intentional) | jscpd, dupl, CPD |
| Large files | Possible god-object | tokei, wc -l |
| Deep nesting | Readability and testability problem | Custom lint rules, lizard |

## When to Deduplicate

Not all duplication is bad. Here's when to consolidate and when to leave things alone.

**DO consolidate:**
- Business logic that must stay consistent across call sites
- Error handling patterns that should follow a single policy
- Data transformation pipelines that do the same thing in multiple places
- Security-sensitive code (auth checks, input validation, crypto usage)

**DON'T over-consolidate:**
- Test fixtures (duplication in tests often improves readability)
- Parallel implementations that may intentionally diverge later
- "Similar" code that serves different requirements (looks alike now, won't forever)
- Generated code (fix the generator instead)
