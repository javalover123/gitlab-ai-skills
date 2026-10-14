# EARS Requirement Syntax Patterns

The Easy Approach to Requirements Syntax (EARS), developed at Rolls-Royce, eliminates the most common forms of ambiguity in requirements. Every requirement fits one of these patterns.

## The Patterns

### 1. Ubiquitous (always active)

**Template:** The `<system>` SHALL `<response>`

Use when the requirement is always true, with no triggering condition.

```
GOOD: The API gateway SHALL validate JWT tokens on every request.
GOOD: The system SHALL log all authentication attempts.
BAD:  The system should generally validate tokens. (vague, no RFC 2119 keyword)
BAD:  Tokens are validated. (passive, no system named, no keyword)
```

### 2. Event-Driven (triggered by an event)

**Template:** **When** `<trigger>`, the `<system>` SHALL `<response>`

Use when something specific happens that triggers the behavior.

```
GOOD: When a user submits a login form, the authentication service SHALL
      validate credentials within 500ms.
GOOD: When a payment fails, the billing service SHALL retry up to 2 times
      with exponential backoff.
BAD:  The system handles login. (no trigger, no response detail)
BAD:  When stuff happens, deal with it. (vague everything)
```

### 3. State-Driven (active while a condition holds)

**Template:** **While** `<precondition>`, the `<system>` SHALL `<response>`

Use when the behavior is conditional on an ongoing state.

```
GOOD: While the system is in maintenance mode, the API SHALL return 503
      for all non-health-check requests.
GOOD: While the database connection pool is exhausted, the service SHALL
      queue requests for up to 30 seconds before returning 503.
BAD:  When maintenance mode, return errors. (missing system, missing specifics)
```

### 4. Optional Feature (conditionally present)

**Template:** **Where** `<feature>`, the `<system>` SHALL `<response>`

Use for features that may or may not be enabled (feature flags, optional modules).

```
GOOD: Where two-factor authentication is enabled, the auth service SHALL
      require a valid TOTP code after password verification.
GOOD: Where the analytics module is installed, the dashboard SHALL display
      request latency percentiles.
BAD:  If 2FA exists, use it. (wrong keyword, vague)
```

### 5. Unwanted Behavior (error/exception handling)

**Template:** **If** `<condition>`, **then** the `<system>` SHALL `<response>`

Use for error conditions, failure modes, and defensive behavior.

```
GOOD: If the upstream service returns a 5xx error, then the API gateway
      SHALL return cached data if available, or 502 if no cache exists.
GOOD: If a database transaction fails after 3 retries, then the service
      SHALL log the failure, notify the ops channel, and return 500 to
      the caller.
BAD:  Handle errors gracefully. (what errors? what's graceful?)
```

## Combining Patterns

Complex requirements sometimes combine patterns:

```
While the system is in degraded mode, when a user submits a write request,
the service SHALL queue the request and return 202 Accepted with an
estimated processing time.
```

## Common Mistakes

**Vague language:**
```
BAD:  The system should be user-friendly.
GOOD: The system SHALL complete the checkout flow in 4 or fewer steps.
```

**No measurable threshold:**
```
BAD:  The system SHALL be fast.
GOOD: The system SHALL return search results within 200ms at the 95th percentile.
```

**Multiple requirements in one statement:**
```
BAD:  The system SHALL validate input, hash passwords, and create sessions.
GOOD: FR-001: The system SHALL validate email format using RFC 5322.
      FR-002: The system SHALL hash passwords using bcrypt with cost factor 12.
      FR-003: When authentication succeeds, the system SHALL create a session
              with a 30-day TTL.
```

**Missing the system name:**
```
BAD:  Passwords shall be hashed.
GOOD: The authentication service SHALL hash passwords using bcrypt.
```

## RFC 2119 Keyword Usage

- **MUST/SHALL** — Absolute requirement. Tests fail if this isn't met.
- **MUST NOT/SHALL NOT** — Absolute prohibition. The system can't do this under any circumstances.
- **SHOULD/RECOMMENDED** — Strong preference. Deviation requires documented justification.
- **MAY/OPTIONAL** — Truly optional. Implementations work correctly either way.

Don't overuse MUST. If everything is MUST, nothing stands out. Reserve it for genuine hard requirements — security, data integrity, regulatory compliance. Use SHOULD for quality-of-life features and MAY for nice-to-haves.
