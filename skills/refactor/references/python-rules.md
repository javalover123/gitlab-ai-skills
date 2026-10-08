# Python Code Quality Rules

## Type Safety

Python's dynamic typing is a feature, but type hints turn your IDE and CI into a safety net. Use them everywhere.

- Use type hints for ALL function signatures
  ```python
  # BAD: def process(data): ...
  # GOOD: def process(data: list[Item]) -> Result: ...
  ```
- Modern union syntax: `str | None` not `Optional[str]` (Python 3.10+)
- Builtin generics: `list[int]` not `List[int]` (Python 3.9+)
- Include a `py.typed` marker file so downstream consumers get type info
- Use `TypedDict` for structured dictionaries, not bare `dict[str, Any]`
- Avoid `Any` unless you're genuinely dealing with unknown types

## Error Handling

Catching every exception is worse than catching none -- at least with none you'll know something broke.

- Never use bare `except:` -- always specify the exception type
  ```python
  # BAD: try: ... except: pass
  # GOOD: try: ... except ValueError as e: logger.warning("bad input: %s", e)
  ```
- Explicit exception chaining: `raise NewError(...) from original`
- Build custom exception hierarchies rooted in a package base error
- Don't catch exceptions you can't meaningfully handle -- let them propagate
- Use `contextlib.suppress()` for intentional ignoring (it documents the intent)

## Anti-Patterns

These come up constantly in Python codebases. They're easy to miss in review and annoying to debug later.

- No mutable default arguments:
  ```python
  # BAD: def func(items=[]):
  # GOOD: def func(items: list | None = None):
  #     items = items or []
  ```
- No `from module import *` -- it pollutes the namespace and breaks tooling
- No `print()` in production code -- use `logging` with appropriate levels
- No bare string paths -- use `pathlib.Path` for filesystem operations
- No `type()` checks -- use `isinstance()` for type checking
- No string concatenation in loops -- use `str.join()` or f-strings

## Async (asyncio)

- Use `TaskGroup` (3.11+) over `gather` for structured concurrency -- it handles errors better
- Never block the event loop (use `run_in_executor` for sync code)
- Reuse `httpx.AsyncClient` or `aiohttp.ClientSession`, don't create per-request
- Use `asyncio.timeout()` (3.11+) instead of `asyncio.wait_for()`

## Testing

- pytest fixtures with appropriate scopes (`session` for expensive setup, `function` for isolation)
- `@pytest.mark.parametrize` for data-driven tests -- better than copy-pasting test functions
- Factory fixtures for flexible test data creation
- Use `tmp_path` fixture instead of manually creating temp dirs

## Detection Commands

```bash
# Bare except clauses
rg 'except\s*:' --type py

# Mutable default arguments
rg 'def \w+\(.*=\s*(\[\]|\{\}|set\(\))' --type py

# Star imports
rg 'from \S+ import \*' --type py

# Missing type hints on function definitions
rg '^def \w+\([^)]*\):' --type py

# Full lint and type check
ruff check . && mypy . --strict
```

## Package Structure

- Use src-layout: `src/mypackage/`
- Include `py.typed` marker for PEP 561
- `pyproject.toml` for all config (PEP 621) -- no more `setup.py` or `setup.cfg`
- Use `uv` or `poetry` for dependency management
- Pin exact versions in lock files, use compatible ranges in `pyproject.toml`
- Separate dev dependencies from runtime deps
