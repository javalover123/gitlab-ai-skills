# Refactoring Catalog

Common refactoring patterns with before/after examples. When you spot a code smell,
look here for the matching fix.

## Extract Function

When a function does too many things, pull out coherent chunks into their own functions.
The original function becomes a high-level orchestrator that reads like a table of contents.

**Before:**
```python
def process_order(order):
    # Calculate total
    total = 0
    for item in order.items:
        price = item.price * item.quantity
        if item.discount:
            price *= (1 - item.discount)
        total += price
    tax = total * 0.08
    total += tax

    # Send confirmation
    subject = f"Order #{order.id} Confirmed"
    body = f"Your total is ${total:.2f}"
    send_email(order.customer.email, subject, body)
    log_notification(order.id, "email_sent")

    return total
```

**After:**
```python
def process_order(order):
    total = calculate_total(order)
    send_confirmation_email(order, total)
    return total

def calculate_total(order):
    subtotal = sum(
        item.price * item.quantity * (1 - (item.discount or 0))
        for item in order.items
    )
    return subtotal * 1.08

def send_confirmation_email(order, total):
    subject = f"Order #{order.id} Confirmed"
    body = f"Your total is ${total:.2f}"
    send_email(order.customer.email, subject, body)
    log_notification(order.id, "email_sent")
```

Each function now does one thing. You can test `calculate_total` without sending emails,
and test `send_confirmation_email` without calculating prices.

## Rename for Clarity

Names should tell you what something *is* or *does* without reading the implementation.
If you need a comment to explain a variable, the variable has the wrong name.

**Before:**
```javascript
function p(d) {
    if (d > 100) return d * 0.1;
    if (d > 50) return d * 0.05;
    return 0;
}
```

**After:**
```javascript
function calculateDiscount(orderAmount) {
    if (orderAmount > 100) return orderAmount * 0.1;
    if (orderAmount > 50) return orderAmount * 0.05;
    return 0;
}
```

Same logic, but now you don't need to read the function body to understand it.

## Remove Duplication / DRY

When you see the same pattern repeated, extract it into a shared function. But be
careful — only consolidate code that should *always* change together.

**Before (Rust):**
```rust
fn validate_name(name: &str) -> Result<(), ValidationError> {
    if name.is_empty() {
        return Err(ValidationError::Empty("name".to_string()));
    }
    if name.len() > 255 {
        return Err(ValidationError::TooLong("name".to_string(), 255));
    }
    Ok(())
}

fn validate_description(desc: &str) -> Result<(), ValidationError> {
    if desc.is_empty() {
        return Err(ValidationError::Empty("description".to_string()));
    }
    if desc.len() > 255 {
        return Err(ValidationError::TooLong("description".to_string(), 255));
    }
    Ok(())
}
```

**After:**
```rust
fn validate_field(value: &str, field_name: &str, max_len: usize) -> Result<(), ValidationError> {
    if value.is_empty() {
        return Err(ValidationError::Empty(field_name.to_string()));
    }
    if value.len() > max_len {
        return Err(ValidationError::TooLong(field_name.to_string(), max_len));
    }
    Ok(())
}

// Usage:
validate_field(name, "name", 255)?;
validate_field(description, "description", 255)?;
```

One function, parameterized. Now when you need to add a new validation rule (like
trimming whitespace), you change it once.

## Replace Magic Numbers

Hardcoded values are a maintenance nightmare. Give them names so future readers
(including you in two weeks) know what they mean.

**Before (C):**
```c
if (retry_count > 3) {
    sleep(5);
    return -1;
}
buf = malloc(4096);
```

**After (C):**
```c
#define MAX_RETRIES       3
#define RETRY_DELAY_SECS  5
#define READ_BUFFER_SIZE  4096

if (retry_count > MAX_RETRIES) {
    sleep(RETRY_DELAY_SECS);
    return -1;
}
buf = malloc(READ_BUFFER_SIZE);
```

Now you can change `MAX_RETRIES` in one place instead of hunting for every `3` in the
codebase. And `READ_BUFFER_SIZE` tells you *why* it's 4096 — it's a read buffer, not
a page size or a protocol limit.

## Simplify Conditionals

Nested conditionals are hard to read and harder to test. Flatten them with early returns
or extract the condition into a named boolean.

**Before (Python):**
```python
def can_moderate(user, post):
    if user is not None:
        if user.is_active:
            if user.role in ("admin", "moderator"):
                if post.community_id == user.community_id:
                    return True
    return False
```

**After (Python):**
```python
def can_moderate(user, post):
    if user is None:
        return False
    if not user.is_active:
        return False
    if user.role not in ("admin", "moderator"):
        return False
    if post.community_id != user.community_id:
        return False
    return True
```

Same logic, zero nesting. Each condition is a clear guard clause. And if you want to
add a new check (say, account age), you just add another guard — no re-indenting the
whole function.

## Replace Comments with Code

If a comment explains *what* code does, the code isn't clear enough. Make the code
explain itself.

**Before (JavaScript):**
```javascript
// Check if user can access admin panel
if (user.role === "admin" && user.active && !user.suspended && user.mfaEnabled) {
    showAdminPanel();
}
```

**After (JavaScript):**
```javascript
function canAccessAdminPanel(user) {
    return user.role === "admin"
        && user.active
        && !user.suspended
        && user.mfaEnabled;
}

if (canAccessAdminPanel(user)) {
    showAdminPanel();
}
```

The function name *is* the comment. And now it's testable, too.

## Code Smells

When you spot these patterns, reach for the matching refactoring above.

**Long Function:** 50+ lines or does multiple distinct things. Extract functions until
each one has a single responsibility.

**Large Class/Module:** 10+ methods or 500+ lines. Look for clusters of methods that
work on the same subset of data — they probably belong in their own type.

**Long Parameter List:** 4+ parameters on a function. Group related parameters into
a struct, config object, or builder pattern.

**Nested Conditionals:** 3+ levels deep. Use early returns, extract conditions into
named booleans, or break the function into smaller pieces.

**Duplicated Code:** Same pattern appears 3+ times. Extract to a shared function
(but read the "When to Deduplicate" section in
[duplication-detection.md](duplication-detection.md) first — not all duplication
deserves consolidation).

**Feature Envy:** A function that uses more data from another module than from its own.
It probably belongs in that other module.

## Red Flags (When to Stop Refactoring)

Sometimes you need to put the refactoring tools down. Stop if:

- Tests start failing and you don't understand why
- You're changing behavior, not just structure
- You're sneaking in new features (that's not refactoring)
- The code is getting more complex, not simpler

Refactoring should make things clearer. If it's making them murkier, revert and
rethink your approach.

## When to Refactor

**Good times:**
- Before adding a feature (clean up the area you're about to work in)
- After getting code working (make it right, then make it clean)
- During code review (when you see patterns worth consolidating)
- When a pattern repeats for the fourth time (the rule of four, not the rule of two)

**Bad times:**
- While debugging a production issue (fix the bug first)
- Without tests (you won't know if you broke something)
- In code you don't understand yet (read first, refactor later)
- Under deadline pressure (you'll cut corners and introduce bugs)
