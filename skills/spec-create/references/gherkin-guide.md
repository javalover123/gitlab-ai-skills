# Gherkin Acceptance Criteria Guide

Gherkin turns requirements into executable test specifications. Every functional requirement in the spec should have at least one Gherkin scenario.

## Basic Structure

```gherkin
Feature: [Feature Name]
  As a [role]
  I want [capability]
  So that [benefit]

  Scenario: [Descriptive name for this test case]
    Given [precondition — what's true before the action]
    And [additional precondition if needed]
    When [action — what the user/system does]
    And [additional action if needed]
    Then [expected outcome — what MUST be true after]
    And [additional verification]
    But [something that MUST NOT be true]
```

## Writing Good Scenarios

### Target 4-7 scenarios per feature

Fewer than 4 means you're probably missing edge cases. More than 10 means the feature should be split into smaller features.

### Every happy path needs an unhappy companion

```gherkin
# Happy path
Scenario: Successful password reset
  Given a registered user with email "alice@example.com"
  When the user requests a password reset
  Then the system SHALL send a reset email to "alice@example.com"
  And the reset token SHALL expire in 1 hour

# Unhappy path
Scenario: Password reset for unknown email
  Given no user exists with email "nobody@example.com"
  When someone requests a password reset for "nobody@example.com"
  Then the system SHALL return a 200 response
  But the system SHALL NOT send any email
  And the system SHALL NOT reveal whether the email exists
```

### Use concrete values, not placeholders

```gherkin
# BAD — too abstract
Scenario: User logs in
  Given a valid user
  When they log in
  Then it works

# GOOD — concrete and testable
Scenario: User logs in with correct credentials
  Given a user registered with email "alice@example.com" and password "s3cure!Pass"
  When the user submits login with email "alice@example.com" and password "s3cure!Pass"
  Then the response status MUST be 200
  And the response body MUST contain a "token" field
  And the token MUST be a valid JWT with "sub" claim matching the user ID
```

### Scenario Outlines for parameterized tests

When testing the same behavior with different inputs:

```gherkin
Scenario Outline: Email validation rejects malformed addresses
  When a user attempts to register with email "<email>"
  Then the system SHALL reject the registration
  And the error message SHALL indicate invalid email format

  Examples:
    | email              |
    | notanemail         |
    | missing@domain     |
    | @example.com       |
    | user@.com          |
    | user@com           |
    | user name@test.com |
```

## Connecting Gherkin to Spec Requirements

Each scenario should reference the requirement ID it validates:

```gherkin
# Validates FR-003: Password Hashing
Scenario: Passwords are hashed before storage
  Given a new user registration with password "mypassword"
  When the registration is processed
  Then the stored password MUST NOT equal "mypassword"
  And the stored password MUST be a valid bcrypt hash
  And the bcrypt cost factor MUST be at least 12
```

## Background for shared preconditions

When multiple scenarios share the same setup:

```gherkin
Feature: Shopping Cart

  Background:
    Given a registered user "alice" is logged in
    And the product catalog contains:
      | id  | name        | price |
      | P01 | Widget      | 9.99  |
      | P02 | Gadget      | 19.99 |
      | P03 | Thingamajig | 4.99  |

  Scenario: Add item to empty cart
    When alice adds product "P01" to cart
    Then the cart SHALL contain 1 item
    And the cart total SHALL be 9.99

  Scenario: Add multiple different items
    When alice adds product "P01" to cart
    And alice adds product "P02" to cart
    Then the cart SHALL contain 2 items
    And the cart total SHALL be 29.98
```

## Anti-Patterns

**Testing implementation details instead of behavior:**
```gherkin
# BAD — tests how, not what
Scenario: Save user to database
  When user is created
  Then INSERT INTO users should be called
  And the redis cache should be invalidated

# GOOD — tests observable behavior
Scenario: Created user is retrievable
  When a user is created with email "alice@example.com"
  Then GET /users?email=alice@example.com SHALL return the user
  And the user's email SHALL be "alice@example.com"
```

**Vague assertions:**
```gherkin
# BAD
Then the system should handle it properly

# GOOD
Then the response status SHALL be 422
And the response body SHALL contain field "errors"
And errors SHALL include "email: invalid format"
```

## Security-Focused Gherkin

Derive these directly from threat model entries:

```gherkin
# From TM-AUTH-002: Brute Force Attack
Scenario: Rate limiting prevents brute force login
  Given a user with email "alice@example.com"
  When 6 failed login attempts are made within 1 minute
  Then the 6th attempt SHALL return 429 Too Many Requests
  And the response SHALL include a Retry-After header
  And the account SHALL NOT be locked (rate limit only)
```
