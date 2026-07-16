# Review Rubric — Detailed Scoring Criteria

## Dimension 1: INVEST Compliance

### Independent (I)

**Score 4:** No dependencies on stories that aren't in a completed or accepted state.
**Score 3:** Depends on 1 other story; that story is in progress with clear path to completion.
**Score 2:** Depends on multiple incomplete stories; can't be developed in isolation.
**Score 1:** Completely intertwined with another story — not separable without major rewrite.

**Common failure pattern:** "As a scanner agent, I want to process results (depends on STORY-NNN being done first)" — the dependency blocks the story entirely.

**Fix pattern:** Define an interface contract. Build against a stub. The story becomes independent by specifying what it consumes, not which story must finish first.

### Negotiable (N)

**Score 4:** HOW is completely open; only WHAT and WHY are specified.
**Score 3:** Minor implementation hints present but not prescriptive.
**Score 2:** Implementation technology prescribed in the story body ("use Redis for caching").
**Score 1:** Acceptance criteria describe code structure, not behavior.

**Common failure pattern:** "The system shall call `POST /api/v2/scan` with JSON body `{repo_url: ...}`" — this is an API contract, not a user story acceptance criterion.

### Valuable (V)

**Score 4:** "So that" clause describes a measurable business or user outcome.
**Score 3:** Outcome is real but could be more specific.
**Score 2:** "So that the system works correctly" — circular, no real value.
**Score 1:** No "so that" clause at all.

**Test:** Would a stakeholder who doesn't care about technology care about this outcome?

### Estimable (E)

**Score 4:** Team can scope this without asking additional questions.
**Score 3:** One or two minor open questions but enough detail to start.
**Score 2:** Acceptance criteria are too vague to estimate; major questions unanswered.
**Score 1:** Story is basically a title with no supporting detail.

### Small (S)

**Score 4:** 1-3 acceptance criteria; fits comfortably in a sprint.
**Score 3:** 4 acceptance criteria; at the limit but manageable.
**Score 2:** 5-6 acceptance criteria; should split.
**Score 1:** 7+ acceptance criteria or spans multiple user journeys.

**Split heuristic:** Find the smallest version that still delivers value. Make that story 1. Everything else is backlog.

### Testable (T)

**Score 4:** Every "Then" clause has a specific, observable, measurable outcome.
**Score 3:** Most criteria testable; one is slightly vague but could be clarified.
**Score 2:** One or more criteria contain subjective outcomes ("should feel fast", "should handle errors properly").
**Score 1:** No acceptance criteria present, or all are untestable.

**Test:** Can you write the assertion code for this "Then" clause right now? If not, it's not testable enough.

---

## Dimension 2: Gherkin Correctness

### Step type violations

**Given performs an action:**
```gherkin
# BAD — Given should not perform an action
Given the user logs in and navigates to the dashboard

# GOOD — Given establishes state
Given the user is authenticated and on the dashboard
```

**When describes multiple actions:**
```gherkin
# BAD — one trigger per When
When the user fills in the form and clicks Submit

# GOOD — one action
When the user clicks Submit
```

**Then describes internal state:**
```gherkin
# BAD — internal state is not observable
Then the cache is updated with the new values

# GOOD — observable outcome
Then the dashboard shows updated values within 5 seconds
```

### Missing coverage

A story that only has happy-path scenarios is incomplete unless the operation is provably safe (read-only, idempotent, no side effects). Most stories need at least one failure scenario.

---

## Dimension 6: Test Derivation

### Mapping Gherkin to test types

| Scenario characteristics | Test type | Rationale |
|---|---|---|
| Single agent, mocked dependencies | Unit | Fast, isolated, no infrastructure |
| Two agents interacting | Contract (Pact) | Validates interface without full stack |
| Multiple agents, real messages | Integration | Catches emergent interaction bugs |
| Full user journey end-to-end | E2E (Cucumber) | Maps directly to Gherkin feature file |
| Failure injection, timeouts | Chaos | Validates resilience claims |

### Rust-specific test mapping

```rust
// Gherkin: Given a scanner receives a ScanRequest
// When the request contains a valid repo URL
// Then an SBOM is written to the graph

#[tokio::test]
async fn scanner_produces_sbom_for_valid_request() {
    // Given
    let db = setup_test_surreal_db().await;
    let request = ScanRequest {
        job_id: "test-001".into(),
        repo_url: "https://github.com/example/repo".into(),
    };

    // When
    let result = scanner.process(request, &db).await;

    // Then
    assert!(result.is_ok());
    let sbom = db.query("SELECT * FROM sbom_records WHERE job_id = 'test-001'").await;
    assert!(!sbom.is_empty());
}
```

For property-based testing (boundary conditions):
```rust
use proptest::prelude::*;

proptest! {
    #[test]
    fn scanner_handles_arbitrary_repo_urls(url in "https://[a-z]{5,20}\\.[a-z]{2,4}/[a-z]{3,10}") {
        // Derived from: "Scanner handles malformed URLs without panicking"
        let result = validate_repo_url(&url);
        prop_assert!(result.is_ok() || result.is_err()); // No panics
    }
}
```
