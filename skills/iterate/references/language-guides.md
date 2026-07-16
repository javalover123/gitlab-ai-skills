# Language-Specific Iteration Patterns

Patterns for iterative improvement specific to each language ecosystem.

## Rust

### Common Iteration Focus Areas

**Error handling maturity:**
```rust
// Initial implementation (gaps)
fn process(data: &str) -> String {
    let parsed = parse(data).unwrap(); // ← gap: panics on invalid input
    transform(parsed)
}

// After iteration 1 (better)
fn process(data: &str) -> Result<String, Error> {
    let parsed = parse(data)?;
    Ok(transform(parsed))
}

// After iteration 2 (best)
fn process(data: &str) -> Result<String, ProcessError> {
    let parsed = parse(data)
        .map_err(|e| ProcessError::InvalidInput(e))?;
    Ok(transform(parsed))
}
```

**Unsafe code review:**
```rust
// Iteration focus: minimize unsafe, document invariants
unsafe fn read_unchecked(ptr: *const u8, len: usize) -> &[u8] {
    // SAFETY: Caller guarantees:
    // 1. ptr is valid for reads of len bytes
    // 2. ptr is properly aligned
    // 3. Data at ptr is initialized
    // 4. No mutable references exist
    std::slice::from_raw_parts(ptr, len)
}
```

**Clippy progression:**
```toml
# Iteration 1: Fix denials
[lints.clippy]
unwrap_used = "deny"
expect_used = "deny"
panic = "deny"

# Iteration 2: Enable pedantic
pedantic = "warn"

# Iteration 3: Enable nursery (opt-in)
nursery = "warn"

# Iteration 4: Specific denials
missing_docs_in_private_items = "warn"
```

### Rust Iteration Checklist

**Iteration 1 — Critical:**
- [ ] Remove all unwrap()/expect() on external input
- [ ] Fix unsafe code or document safety invariants
- [ ] Update dependencies (cargo-audit, cargo-outdated)
- [ ] Fix all clippy::correctness lints

**Iteration 2 — Quality:**
- [ ] Enable clippy::pedantic, fix violations
- [ ] Add #[must_use] to functions with important return values
- [ ] Document all public items
- [ ] Add #![forbid(unsafe_code)] if possible

**Iteration 3 — Coverage:**
- [ ] Unit tests for all public functions
- [ ] Property tests for parsers/encoders
- [ ] Integration tests for APIs
- [ ] Target 80%+ line coverage

**Iteration 4 — Polish:**
- [ ] Add examples to documentation
- [ ] Verify README is complete
- [ ] Check CHANGELOG follows keep-a-changelog
- [ ] Run cargo publish --dry-run

## Go

### Common Iteration Focus Areas

**Error handling patterns:**
```go
// Initial (gap: silent failure)
func process(data string) string {
    parsed, _ := parse(data) // ← ignoring error
    return transform(parsed)
}

// After iteration 1
func process(data string) (string, error) {
    parsed, err := parse(data)
    if err != nil {
        return "", err
    }
    return transform(parsed), nil
}

// After iteration 2 (wrapped errors)
func process(data string) (string, error) {
    parsed, err := parse(data)
    if err != nil {
        return "", fmt.Errorf("parsing input: %w", err)
    }
    return transform(parsed), nil
}
```

**Race condition fixes:**
```go
// Initial (gap: race condition)
type Counter struct {
    count int
}

func (c *Counter) Increment() {
    c.count++ // ← race
}

// After iteration (fixed with mutex)
type Counter struct {
    mu    sync.Mutex
    count int
}

func (c *Counter) Increment() {
    c.mu.Lock()
    defer c.mu.Unlock()
    c.count++
}
```

**Context propagation:**
```go
// Initial (gap: no cancellation)
func fetchData() ([]byte, error) {
    resp, err := http.Get(url)
    // ...
}

// After iteration
func fetchData(ctx context.Context) ([]byte, error) {
    req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
    if err != nil {
        return nil, err
    }
    resp, err := http.DefaultClient.Do(req)
    // ...
}
```

### Go Iteration Checklist

**Iteration 1 — Critical:**
- [ ] Fix all error checks (no ignored errors)
- [ ] Run go test -race, fix race conditions
- [ ] Run govulncheck, update vulnerable dependencies
- [ ] Fix all staticcheck errors

**Iteration 2 — Quality:**
- [ ] Run golangci-lint, fix violations
- [ ] Add context.Context to long-running operations
- [ ] Wrap errors with context (fmt.Errorf with %w)
- [ ] Run gofmt/goimports

**Iteration 3 — Coverage:**
- [ ] Table-driven tests for functions with multiple cases
- [ ] Test error paths
- [ ] Add examples (ExampleXxx functions)
- [ ] Target 70%+ coverage

**Iteration 4 — Polish:**
- [ ] Godoc comments for all exported items
- [ ] Add package-level documentation (doc.go)
- [ ] Verify README is complete
- [ ] Run go mod tidy

## Python

### Common Iteration Focus Areas

**Type annotations:**
```python
# Initial (gap: no types)
def process(data):
    parsed = parse(data)
    return transform(parsed)

# After iteration 1
def process(data: str) -> dict[str, Any]:
    parsed: dict = parse(data)
    return transform(parsed)

# After iteration 2 (precise types)
from typing import TypedDict

class ParsedData(TypedDict):
    name: str
    count: int

def process(data: str) -> ParsedData:
    parsed = parse(data)
    return transform(parsed)
```

**Error handling:**
```python
# Initial (gap: bare except)
try:
    result = risky_operation()
except:  # ← catches everything, even KeyboardInterrupt
    result = None

# After iteration 1
try:
    result = risky_operation()
except ValueError:
    result = None

# After iteration 2 (logging)
try:
    result = risky_operation()
except ValueError as e:
    logger.error("Failed to process: %s", e)
    raise ProcessingError("Invalid input") from e
```

**Resource management:**
```python
# Initial (gap: file not closed on exception)
f = open("file.txt")
data = f.read()
f.close()

# After iteration (with context manager)
with open("file.txt") as f:
    data = f.read()
```

### Python Iteration Checklist

**Iteration 1 — Critical:**
- [ ] Fix bandit security issues
- [ ] Run safety check, update vulnerable dependencies
- [ ] Fix bare except clauses
- [ ] Add type hints to public functions

**Iteration 2 — Quality:**
- [ ] Run ruff, fix violations
- [ ] Run mypy --strict, fix type errors
- [ ] Use context managers for resources
- [ ] Format with ruff format

**Iteration 3 — Coverage:**
- [ ] pytest with fixtures for common setups
- [ ] Use pytest.mark.parametrize for multiple inputs
- [ ] Mock external dependencies
- [ ] Target 80%+ coverage

**Iteration 4 — Polish:**
- [ ] Docstrings for all public functions (Google/NumPy style)
- [ ] Add py.typed marker for type hints
- [ ] Verify README is complete
- [ ] Check setup.py/pyproject.toml is correct

## C

### Common Iteration Focus Areas

**Buffer safety:**
```c
// Initial (gap: buffer overflow)
void copy_string(char *dest, const char *src) {
    strcpy(dest, src); // ← unsafe
}

// After iteration 1 (bounded copy)
void copy_string(char *dest, size_t dest_size, const char *src) {
    strlcpy(dest, src, dest_size);
    // Or: strncpy + manual null termination
}

// After iteration 2 (checking return)
int copy_string(char *dest, size_t dest_size, const char *src) {
    if (strlcpy(dest, src, dest_size) >= dest_size) {
        return -1; // Truncation occurred
    }
    return 0;
}
```

**Memory leak fixes:**
```c
// Initial (gap: memory leak on error path)
char *process(const char *input) {
    char *buffer = malloc(SIZE);
    if (risky_operation(buffer) < 0)
        return NULL; // ← leak
    return buffer;
}

// After iteration
char *process(const char *input) {
    char *buffer = malloc(SIZE);
    if (buffer == NULL)
        return NULL;

    if (risky_operation(buffer) < 0) {
        free(buffer);
        return NULL;
    }
    return buffer;
}
```

**Format string safety:**
```c
// Initial (gap: format string vulnerability)
void log_message(const char *msg) {
    printf(msg); // ← if msg contains %s, undefined behavior
}

// After iteration
void log_message(const char *msg) {
    printf("%s", msg);
}
```

### C Iteration Checklist

**Iteration 1 — Critical:**
- [ ] Run cppcheck, fix all errors
- [ ] Run valgrind, fix memory leaks
- [ ] Replace unsafe functions (strcpy → strlcpy, sprintf → snprintf)
- [ ] Fix all compiler warnings with -Wall -Wextra

**Iteration 2 — Quality:**
- [ ] Run clang-static-analyzer
- [ ] Enable -Werror (warnings as errors)
- [ ] Add const to read-only pointers
- [ ] Use size_t for sizes, not int

**Iteration 3 — Coverage:**
- [ ] Unit tests with assertions
- [ ] Valgrind on test suite
- [ ] AddressSanitizer builds
- [ ] Test error paths

**Iteration 4 — Polish:**
- [ ] Comments for complex algorithms
- [ ] Header guards (#ifndef/#define)
- [ ] Consistent style (K&R, OpenBSD KNF, etc.)
- [ ] Verify README is complete

## JavaScript/TypeScript

### Common Iteration Focus Areas

**TypeScript conversion:**
```typescript
// Initial JavaScript (gaps)
function process(data) {
    return data.map(x => x.value);
}

// After iteration 1 (TypeScript)
function process(data: Array<{value: string}>): string[] {
    return data.map(x => x.value);
}

// After iteration 2 (generics)
interface HasValue<T> {
    value: T;
}

function process<T>(data: HasValue<T>[]): T[] {
    return data.map(x => x.value);
}
```

**Async/await conversion:**
```typescript
// Initial (callback hell)
function fetchData(callback) {
    fetch(url)
        .then(res => res.json())
        .then(data => callback(null, data))
        .catch(err => callback(err));
}

// After iteration (async/await)
async function fetchData(): Promise<Data> {
    const res = await fetch(url);
    return await res.json();
}
```

**Error handling:**
```typescript
// Initial (silent failure)
async function process() {
    const data = await fetch(url);
    return data.json();
}

// After iteration
async function process(): Promise<Data> {
    let response: Response;
    try {
        response = await fetch(url);
    } catch (err) {
        throw new NetworkError("Failed to fetch", { cause: err });
    }

    if (!response.ok) {
        throw new APIError(`HTTP ${response.status}`);
    }

    return await response.json();
}
```

### JavaScript/TypeScript Iteration Checklist

**Iteration 1 — Critical:**
- [ ] Convert to TypeScript (if JavaScript)
- [ ] Run npm audit, fix vulnerabilities
- [ ] Fix ESLint errors
- [ ] Enable strict mode in tsconfig.json

**Iteration 2 — Quality:**
- [ ] Run ESLint with security plugin
- [ ] Enable stricter TypeScript checks (noImplicitAny, etc.)
- [ ] Replace var with const/let
- [ ] Format with Prettier

**Iteration 3 — Coverage:**
- [ ] Jest tests for all functions
- [ ] Mock fetch/HTTP requests
- [ ] Test error paths
- [ ] Target 80%+ coverage

**Iteration 4 — Polish:**
- [ ] JSDoc comments for public API
- [ ] Generate API documentation (TypeDoc)
- [ ] Verify README is complete
- [ ] Check package.json metadata

## Common Cross-Language Patterns

### Pattern: Dead Code Removal

Iterate through:
1. Run language-specific dead code detector
2. Review why code is unused (incomplete feature?)
3. If truly dead, delete it
4. If incomplete, finish implementing it
5. Re-run tests to ensure nothing broke

### Pattern: TODO Completion

Iterate through:
1. Search codebase for TODO/FIXME/XXX
2. For each TODO, decide: implement now or file issue
3. Implement critical TODOs in this iteration
4. Create tracked issues for future TODOs
5. Remove completed TODOs

### Pattern: Dependency Update

Iterate through:
1. Run dependency update tool (cargo-outdated, npm outdated)
2. Update patch versions (safe)
3. Test
4. Update minor versions (usually safe)
5. Test
6. Update major versions (review breaking changes)
7. Test each major version separately

### Pattern: Documentation Improvement

Iterate through:
1. Run doc coverage tool
2. Add missing docstrings/comments
3. Add usage examples
4. Update README if outdated
5. Add architecture/design docs if needed

## Resources

- **Rust patterns**: https://rust-lang.github.io/api-guidelines/
- **Go best practices**: https://go.dev/doc/effective_go
- **Python typing**: https://mypy.readthedocs.io/
- **C security**: https://wiki.sei.cmu.edu/confluence/display/c
- **TypeScript handbook**: https://www.typescriptlang.org/docs/handbook/
