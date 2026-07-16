# Helper Library Patterns

## CRITICAL: Analyze Before Refactoring

**Before you write ANY new code**, thoroughly catalog the project's existing helper
libraries. This isn't busywork — it's the single most effective way to prevent four
common refactoring mistakes:

1. **Creating duplicates** — Writing a function that already exists somewhere in the codebase
2. **Writing pointless wrappers** — Wrapping an existing helper with a thin function that adds zero value
3. **Wrong placement** — Putting a new helper in the wrong module because you didn't know where similar functions live
4. **Missed reuse** — Inline-coding logic that a helper already handles

Skip this step, and you'll spend half your refactoring session undoing your own mess.

## Cataloging Commands

The goal is always the same: list all public functions, constants, and types in the
project's utility/helper directories. Adapt these to your codebase's structure.

**Go:**
```bash
# List all exported functions in helper packages
grep -r '^func ' pkg/common/ pkg/util/ internal/helpers/ | head -40

# List exported constants
grep -r '^const\|^\tconst' pkg/common/ pkg/util/ | head -20

# List exported types
grep -r '^type ' pkg/common/ pkg/util/ | head -20
```

**Rust:**
```bash
# List public items in shared crates
rg '^pub fn|^pub const|^pub struct|^pub enum|^pub type|^pub trait' \
  --type rust crates/shared*/ src/utils/ src/helpers/

# Check re-exports in lib.rs
rg '^pub (use|mod)' --type rust crates/*/src/lib.rs
```

**Python:**
```bash
# List functions and classes in utility modules
rg '^def |^class ' --type py src/utils/ src/helpers/ lib/common/

# Check __init__.py exports
rg '^from .* import|^__all__' --type py src/utils/__init__.py
```

**C:**
```bash
# List function declarations in header files
rg '^\w+.*\(' --type h include/ src/util/

# List #define constants
rg '^#define [A-Z]' --type h include/
```

Write down what you find. Seriously — create a list of "this exists, here's where it
lives, here's what it does." You'll reference it constantly.

## Rules for Using and Creating Helpers

### Rule 1: NEVER create wrapper functions around existing helpers

If `pkg/util.NormalizeString()` exists, call it directly. Don't write
`myPackage.cleanString()` that just calls `util.NormalizeString()` underneath. Wrappers
add indirection, confuse other developers, and make the codebase harder to search.

### Rule 2: ALWAYS search helpers before writing new code

Before you write a new function, search for it:
```bash
# Search by likely function name fragments
rg -i 'normalize|clean|sanitize|format' --type <lang> src/ lib/ pkg/
```

If something similar exists, use it. If it *almost* works, consider extending the
existing function rather than creating a new one.

### Rule 3: Place new helpers in the most appropriate location

When you do need a new helper, put it where it belongs:

| Helper Type | Where It Goes |
|---|---|
| General utilities (strings, slices, maps) | `common/`, `util/`, `shared/` |
| I/O operations (file, network, stream) | `util/io/`, `helpers/io/` |
| Version handling and comparison | `version/`, `util/version/` |
| Domain-specific logic | `<domain>/helpers/`, `<ecosystem>/util/` |
| Database operations | `db/`, `store/`, `repository/` |

### Rule 4: New helpers need proper structure

Every new helper function must have:
- Doc comments explaining what it does and when to use it
- At least one example in the documentation
- Unit tests covering normal and edge cases
- Consistent naming with existing helpers in the same module

### Rule 5: Normalization functions must be idempotent

`normalize(normalize(x))` must always equal `normalize(x)`. If applying your function
twice produces a different result than applying it once, you've got a bug. Test for this
explicitly.

## Constant Management

Any literal string or number that appears 3+ times in the codebase should be a named
constant. Here's how to find candidates:

```bash
# Find repeated string literals
rg -oh '"[a-z_-]+"' --type <lang> | sort | uniq -c | sort -rn | head -30
```

Place constants in the same module as the helpers that use them. Group related constants
together. Use descriptive names — `MaxRetryCount` is better than `MAX_N`, and
`DefaultTimeout` is better than `TIMEOUT`.
