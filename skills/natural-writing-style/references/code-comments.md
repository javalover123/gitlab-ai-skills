# Code Comment Style Guidelines

Comments exist for one reason: to tell future readers something they can't figure out from the code alone. If the code already says it, don't repeat it in a comment. If the code hides something surprising, that's where a comment earns its keep.

## The cardinal rule: WHY, not WHAT

The code tells you what it does. Comments tell you why it does it that way. Every comment should answer one of these questions:

- Why was this approach chosen over the obvious alternative?
- What constraint or edge case drove this decision?
- What would break if someone changed this without understanding the context?
- What did you learn the hard way that isn't obvious from reading the code?

If your comment just restates the code in English, delete it.

## Inline comments

Keep them under 15 words. They sit next to code, so they shouldn't compete for attention.

### Good vs bad inline comments

**Bad -- states the obvious:**
```c
int count = 0;  // initialize count to zero
users = fetch_all();  // fetch all users
if (len > MAX_BUF)  // check if length exceeds max buffer
```

**Good -- explains why:**
```c
int count = 0;  // reset between retries to avoid double-counting
users = fetch_all();  // cached locally; remote call only on first hit
if (len > MAX_BUF)  // kernel rejects writes over 64k on this device
```

**Bad -- too verbose for inline:**
```rust
let timeout = 30;  // we set the timeout to thirty seconds because the upstream API documentation recommends this value for batch operations
```

**Good -- concise, links to detail:**
```rust
let timeout = 30;  // upstream batch API recommendation; see DESIGN.md
```

## Block comments

Use block comments when the reasoning behind a chunk of code needs more than 15 words. The comment should explain the reasoning, not narrate what the code does line by line.

### Good vs bad block comments

**Bad -- describes the code:**
```c
/*
 * First we open the file. Then we read the header.
 * We check if the magic number matches. If it does,
 * we parse the rest of the file. If it doesn't, we
 * return an error.
 */
fd = open(path, O_RDONLY);
read(fd, &hdr, sizeof(hdr));
if (hdr.magic != EXPECTED_MAGIC)
    return -EINVAL;
parse_body(fd, &hdr);
```

**Good -- explains reasoning:**
```c
/*
 * We validate the magic number before touching any other
 * fields because older firmware versions wrote garbage to
 * the header struct. Without this check, parse_body()
 * will dereference invalid offsets from the v1 format.
 */
fd = open(path, O_RDONLY);
read(fd, &hdr, sizeof(hdr));
if (hdr.magic != EXPECTED_MAGIC)
    return -EINVAL;
parse_body(fd, &hdr);
```

## TODO format

```
// TODO(username): Description [TICKET-ID]
```

Always include who wrote it and a ticket reference if one exists. TODOs without owners rot in the codebase forever.

```c
// TODO(maria): Switch to mmap once we drop RHEL 7 support [INFRA-442]
// TODO(dan): This retry logic doesn't handle partial writes [BUG-1087]
```

Don't use TODO as a substitute for actually fixing something you could fix right now.

## Voice in comments

Use contractions. Comments aren't legal contracts -- they're notes from one developer to another.

**Stiff:**
```go
// This function should not be called from interrupt context.
// It is not safe to call without holding the lock.
// The caller must ensure that the buffer is not nil.
```

**Natural:**
```go
// Don't call this from interrupt context.
// Not safe without holding the lock.
// Caller must ensure buf isn't nil.
```

Never use banned words in comments. "Utilize," "leverage," "facilitate," "robust" -- they all have plain alternatives. Say "use" instead of "utilize." Say "apply" instead of "leverage." Say "help" instead of "facilitate." Say "solid" or "reliable" instead of "robust." <!-- voice-ok -->

## Docstrings

Lead with what the function does, in one sentence. Then parameters, return values, and error conditions. Follow whatever docstring convention your project already uses -- consistency matters more than any single style.

### Good vs bad docstrings

**Bad -- overly formal, uses banned words:**
```python
def connect(host, port, timeout=30):
    """
    This function facilitates the establishment of a robust <!-- voice-ok -->
    connection to the specified host utilizing the provided
    port number. It leverages a comprehensive timeout mechanism <!-- voice-ok -->
    to ensure seamless connectivity. <!-- voice-ok -->

    It should be noted that the connection will be retried
    in the event of a transient failure.
    """
```

**Good -- natural and precise:**
```python
def connect(host, port, timeout=30):
    """Connect to a remote host over TCP.

    Retries up to twice on transient failures (ECONNRESET,
    ETIMEDOUT) before giving up. The timeout applies to each
    attempt individually, not the total.

    Args:
        host: Hostname or IP address.
        port: TCP port number (1-65535).
        timeout: Per-attempt timeout in seconds. Defaults to 30.

    Returns:
        An open socket connected to host:port.

    Raises:
        ConnectionError: After all retry attempts fail.
        ValueError: If port is outside valid range.
    """
```

## Don't over-comment, don't under-comment

**Over-commenting** adds noise. Don't comment obvious code:

```rust
// Bad: every line restated
let mut v = Vec::new();  // create a new vector
v.push(item);            // push item onto vector
v.sort();                // sort the vector
```

**Under-commenting** hides traps. Always comment surprising code:

```rust
// Good: explains the non-obvious
v.sort_unstable();  // 2x faster than sort() here; ordering of equal elements doesn't matter
unsafe { ptr::copy_nonoverlapping(src, dst, n) };  // SAFETY: bounds checked on line 42, src/dst don't alias (different allocations)
```

The right amount of comments is the amount that lets someone understand your intent without reading every line of implementation.

---

## Domain-specific conventions

Different ecosystems have different documentation traditions. Match the convention of whatever you're writing in. Here's a quick reference for the most common ones.

### mdoc (BSD manual pages)

mdoc is the exception to every voice rule in this skill. Man pages use formal, terse prose with no contractions and passive voice. That's the convention -- follow it.

Key points: semantic markup (`.Fl` for flags, `.Ar` for arguments, `.Nm` for the command), one-line `.Nd` description, document every flag and exit code.

```
.Sh DESCRIPTION
.Nm
reads configuration from
.Ar file
and validates syntax.
If errors are found, a diagnostic is printed to standard error.
```

### rustdoc

First line is a summary that shows up in listings and autocomplete. Contractions are welcome. Use `# Examples`, `# Errors`, `# Panics`, and `# Safety` sections as needed. Examples must be valid code that `cargo test` can run.

```rust
/// Splits input at the first occurrence of `delimiter`.
///
/// Returns `None` if `delimiter` isn't found. You'll usually want
/// [`split_all`] if you need every segment.
///
/// # Examples
///
/// ```
/// let (left, right) = split_first("a:b:c", ':').unwrap();
/// assert_eq!(left, "a");
/// assert_eq!(right, "b:c");
/// ```
///
/// # Panics
///
/// Panics if `delimiter` is the null byte (legacy constraint from the C API).
```

### kernel-doc

Terse, no contractions, no personality. Format: `function_name - brief`, then `@param:` for each parameter, then longer description, then `Context:` and `Return:`. Always document locking requirements and whether the function can sleep.

```c
/**
 * dev_read_config - read device configuration from EEPROM
 * @dev: target device
 * @buf: output buffer, must be at least %DEV_CFG_SIZE bytes
 *
 * Reads the stored configuration. Caller must hold dev->lock.
 *
 * Context: Process context. May sleep.
 * Return: 0 on success, -EIO on read failure, -EINVAL if EEPROM is blank.
 */
```

### JSDoc

Brief description first, then `@param`, `@returns`, `@throws`, `@example`. Use `{type}` annotations. Mark optional params with `[]` and defaults with `=`.

```javascript
/**
 * Debounces a function call by the given delay.
 *
 * @param {Function} fn - Function to debounce
 * @param {number} delay - Delay in milliseconds
 * @param {Object} [options]
 * @param {boolean} [options.leading=false] - Fire on the leading edge
 * @returns {Function} Debounced wrapper
 * @example
 * const save = debounce(() => persist(data), 300);
 * input.addEventListener('keyup', save);
 */
```

### Python docstrings

Three styles exist -- Google, NumPy, and Sphinx. Pick whichever your project already uses. Starting fresh? Google style is the most readable for humans.

- **Google style:** `Args:`, `Returns:`, `Raises:` sections. Most common.
- **NumPy style:** Underline-separated sections. Standard in scientific Python.
- **Sphinx style:** `:param name:` tags. Older, but some projects still use it.

```python
def retry(fn, attempts=4, backoff=1.0):
    """Call fn with exponential backoff on failure.

    Args:
        fn: Callable that might raise on transient errors.
        attempts: Max number of tries. Defaults to 4.
        backoff: Initial delay in seconds, doubled each retry.

    Returns:
        Whatever fn returns on success.

    Raises:
        RetryExhausted: If all attempts fail. Wraps the last exception.
    """
```

### Go doc comments

Start with the name of what you're documenting. Write complete sentences. No tags, no annotations -- just prose. Examples use tab indentation inside comment blocks.

```go
// Retry calls fn up to maxAttempts times with exponential backoff.
// It returns the first successful result or the last error if all
// attempts fail. The initial delay is 100ms, doubled each retry.
func Retry(fn func() error, maxAttempts int) error {
```

Go's convention is straightforward: if you'd explain it to a colleague standing at your desk, that's roughly how the doc comment should read.
