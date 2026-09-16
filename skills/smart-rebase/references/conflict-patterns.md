# Conflict Resolution Patterns

Detailed patterns for resolving common conflict types during smart rebase. The core principle: **current branch wins, but default branch intent is preserved**.

## Pattern 1: Same Function Modified Differently

**Scenario:** Both branches modified the same function body.

**Default branch** (bug fix):
```diff
- result = process(data)
+ result = process(data) if data is not None else default_value
```

**Current branch** (refactored signature):
```diff
- result = process(data)
+ result = process_with_context(data, ctx)
```

**Resolution:** Apply both intents:
```python
result = process_with_context(data, ctx) if data is not None else default_value
```

The current branch's architectural change (new function, new parameter) stays. The default branch's null-safety fix gets integrated into the new call pattern.

## Pattern 2: Import/Include Conflicts

**Scenario:** Both branches added imports to the same region.

**Default branch:**
```diff
  import os
+ import pathlib
  import sys
```

**Current branch:**
```diff
  import os
+ import json
  import sys
```

**Resolution:** Keep both imports, maintain alphabetical ordering:
```python
import json
import os
import pathlib
import sys
```

This is almost always a clean merge. If git marks it as a conflict, just combine both additions.

## Pattern 3: Structural Refactor vs. Feature Addition

**Scenario:** Current branch restructured a module while default branch added new functionality to the old structure.

**Default branch** added a new method to `class Handler`:
```python
class Handler:
    def existing_method(self):
        ...
    def new_feature(self):
        """Added on default branch"""
        return do_something()
```

**Current branch** split `Handler` into two classes:
```python
class BaseHandler:
    def existing_method(self):
        ...

class SpecializedHandler(BaseHandler):
    def specialized_work(self):
        ...
```

**Resolution:** Port the default branch's new feature into the current branch's architecture:
```python
class BaseHandler:
    def existing_method(self):
        ...
    def new_feature(self):
        """Ported from default branch's Handler addition"""
        return do_something()

class SpecializedHandler(BaseHandler):
    def specialized_work(self):
        ...
```

Decide which class the new method belongs to based on its purpose. If it's general, put it in `BaseHandler`. If it's specific, put it in `SpecializedHandler`.

## Pattern 4: Configuration/Schema Changes

**Scenario:** Both branches modified a config file, database schema, or API spec.

**Default branch** added a new field:
```yaml
database:
  host: localhost
  port: 5432
+ pool_size: 10
```

**Current branch** changed the structure:
```yaml
database:
  primary:
    host: localhost
    port: 5432
  replica:
    host: replica.local
    port: 5432
```

**Resolution:** Merge the new field into the current branch's structure:
```yaml
database:
  primary:
    host: localhost
    port: 5432
    pool_size: 10
  replica:
    host: replica.local
    port: 5432
    pool_size: 10
```

## Pattern 5: Deleted vs. Modified

**Scenario:** Default branch deleted a file or function that the current branch modified.

**Default branch:** Deleted `legacy_handler.py` (replaced with `new_handler.py`)

**Current branch:** Modified `legacy_handler.py` to add a feature

**Resolution options (ask the user):**

1. **If the replacement exists:** Port current branch's changes into the new file
2. **If the deletion was cleanup:** Re-evaluate whether the current branch still needs this code
3. **If the deletion was premature:** Keep the file, note the upstream intent to remove it

## Pattern 6: Test File Conflicts

**Scenario:** Both branches added tests or modified test fixtures.

**General approach:** Keep ALL tests from both branches. Tests are additive. If test names conflict, rename one. If fixtures conflict, merge them.

**Exception:** If the default branch's tests cover functionality that the current branch has fundamentally redesigned, the default branch tests may need rewriting to match the new architecture. Don't just drop them — rewrite them to test the same behavior through the new interface.

## Pattern 7: Lock Files and Generated Content

**Scenario:** `package-lock.json`, `Cargo.lock`, `go.sum`, or other generated files conflict.

**Resolution:** Don't manually merge these. After resolving all source-level conflicts:

```bash
# For npm
rm package-lock.json && npm install

# For Cargo
cargo generate-lockfile

# For Go
go mod tidy
```

Then stage the regenerated file and continue.

## Pattern 8: Documentation Conflicts

**Scenario:** Both branches updated README, CHANGELOG, or API docs.

**Resolution:** Combine both changes. Documentation is almost always additive. For CHANGELOGs, include entries from both branches in chronological order.

## Decision Framework

When facing an unfamiliar conflict pattern:

1. **What did the default branch intend?** Read the commit message and surrounding changes
2. **What did the current branch intend?** Same analysis
3. **Are these intents compatible?** Usually yes — they're solving different problems
4. **If incompatible:** Current branch wins, but document why the default branch's approach was set aside
5. **If uncertain:** Stop and ask the user. Show both versions, explain both intents, propose a resolution

The worst outcome is silently reverting a default branch change. When in doubt, flag it for review rather than guessing.
