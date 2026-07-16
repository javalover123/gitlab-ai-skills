# Test Derivation Guide

## The Pipeline

Each acceptance criterion in a story maps to one or more concrete test cases. The pipeline:

1. Parse acceptance criteria from the story
2. For each criterion: identify test type, framework, and required setup
3. Build traceability matrix
4. Flag criteria that can't be derived into tests (that's a quality gate failure)

## Test Type Selection

| Gherkin scenario type | Test type | Why |
|---|---|---|
| Single actor, no external deps | Unit test | Fastest, most isolated |
| Two agents passing messages | Contract test (Pact) | Validates interface without full stack |
| Multiple agents with real infrastructure | Integration test | Catches emergent interaction |
| Full user journey from trigger to observable outcome | E2E test (Cucumber) | Maps directly to Gherkin |
| Failure injection (timeouts, disconnects, resource exhaustion) | Chaos/resilience test | Validates EARS unwanted-behavior constraints |
| Edge cases with generated inputs | Property-based test (proptest) | Finds edge cases acceptance criteria miss |

## Traceability Matrix Format

```markdown
| Criterion ID | Scenario | Test Type | Framework | Test File |
|---|---|---|---|---|
| AC-1 | Happy path — scan completes | Integration | cucumber | features/scanner.feature |
| AC-1 | Happy path — scan completes | Property | proptest | tests/scanner_props.rs |
| AC-2 | Auth required — no token | Unit | #[test] | tests/scanner_unit.rs |
| AC-3 | Scan timeout | Integration | cucumber | features/scanner.feature |
```

Every acceptance criterion should appear at least once. Empty rows are gaps.

## Rust Test Skeletons

### From Given/When/Then to `#[test]`

```rust
// Criterion: "Given a valid ScanRequest, When processed, Then SBOM is written"
#[tokio::test]
async fn scan_request_produces_sbom() {
    // Given
    let db = TestDatabase::new().await;
    let request = ScanRequest::new("https://example.com/repo", "job-001");

    // When
    let scanner = Scanner::new(&db);
    let result = scanner.process(request).await;

    // Then
    assert!(result.is_ok());
    let record = db.find_sbom("job-001").await.unwrap();
    assert!(!record.components.is_empty());
}
```

### From EARS constraints to property tests

EARS constraints often describe invariants that hold across all inputs — those map well to proptest:

```rust
// EARS: "The agent shall complete processing within 300 seconds"
use proptest::prelude::*;
use std::time::Instant;

proptest! {
    #[test]
    fn scan_always_completes_within_timeout(
        repo_size in 1usize..10_000,
        dep_count in 0usize..500,
    ) {
        let start = Instant::now();
        let result = scan_synthetic_repo(repo_size, dep_count);
        let elapsed = start.elapsed();

        prop_assert!(elapsed.as_secs() < 300, "Scan took {:?}", elapsed);
        prop_assert!(result.is_ok() || result.is_err()); // No panics
    }
}
```

### From security scenarios to contract tests

```rust
// Pact consumer test for SBOM scanner → graph writer interface
use pact_consumer::prelude::*;

#[tokio::test]
async fn scanner_sends_valid_sbom_record() {
    let pact = PactBuilder::new("sbom-scanner", "graph-writer")
        .interaction("writes an SBOM record", |i| {
            i.given("scanner produces a valid SBOM")
             .upon_receiving("write request for SBOM record")
             .with(|req| {
                 req.method("POST")
                    .path("/sbom_records")
                    .json_body(json_pattern!({
                        "job_id": like!("job-001"),
                        "components": each_like!({"name": like!("crate-name"), "version": like!("1.0.0")}),
                    }))
             })
             .will_respond_with(|res| {
                 res.status(201);
             })
        })
        .build();
    // ... test the scanner against the pact
}
```

## Cucumber Feature File Generation

For E2E stories, the Gherkin scenarios map directly to `.feature` files:

```gherkin
# features/sbom_scanner.feature — generated from STORY-042 acceptance criteria

Feature: SBOM Scanner Agent
  As an SBOM Scanner Agent
  I need to scan repositories for dependencies
  So that the audit dashboard shows current SBOM coverage

  Scenario: Successful scan of public repository
    Given the agent is running and connected to the message bus
    When the agent receives a ScanRequest for a valid public repository
    Then an SPDX-format SBOM is written to the graph under the job ID
    And a ScanComplete event is published with the SBOM record ID

  Scenario: Authentication required for private repository
    Given the agent is running
    When the agent receives a ScanRequest without an auth token for a private repository
    Then a ScanFailed event is published with code "AUTH_REQUIRED"
    And no data is written to the graph

  Scenario: Scan timeout
    Given the agent is processing a scan that takes longer than 5 minutes
    When the timeout triggers
    Then a ScanTimeout event is published with the job ID and elapsed seconds
    And any partial writes are rolled back
```

## Coverage Metrics

Good test coverage from stories means:

- Every acceptance criterion has at least one test
- Every EARS constraint has at least one property test or chaos test
- Every security mapping entry has at least one negative/adversarial test case
- No acceptance criterion is covered only by manual testing
