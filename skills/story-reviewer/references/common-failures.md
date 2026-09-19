# Common Story Failures and Fixes

These patterns come up in nearly every batch of AI-generated or rushed stories. Recognizing them quickly saves iteration time.

## Failure: Vague "so that" clause

**Example:** "As a user, I want to view the dashboard, so that I can see information."

**Why it fails:** INVEST Valuable. The outcome doesn't describe anything a stakeholder cares about. "See information" is circular — you're just saying "so that the feature exists."

**Fix:** Ask "what does the user do differently because of this?" That answer becomes the "so that" clause. "So that I can identify critical CVEs that need patching this week" is specific; "so that I can see information" is not.

---

## Failure: Acceptance criteria that can't be asserted

**Example:** "The scan should be fast" / "The system should handle errors properly" / "Users should feel confident the data is secure"

**Why it fails:** INVEST Testable. No assertion can be written for "fast" or "properly" without a threshold.

**Fix:** Add the missing measurement. "Fast" → "The scan shall complete within 30 seconds at the 95th percentile for repositories under 10,000 files." "Handle errors properly" → write a Gherkin scenario for each error type.

---

## Failure: Given performs an action

**Example:**
```gherkin
Given the user opens the application and navigates to Settings and clicks "New Scan"
When the user fills in the repo URL
```

**Why it fails:** Gherkin Correctness. Given should describe state, not actions. The navigation actions are When steps that got collapsed into Given.

**Fix:** Move actions to When. Given should only set up the precondition state:
```gherkin
Given the user is on the New Scan form
When the user enters a repo URL and clicks Submit
```

---

## Failure: Agent story missing prohibited actions

**Example:**
```
Autonomy Limits:
- Maximum actions per cycle: 1
- Escalation threshold: when something goes wrong
- Prohibited actions: harmful things
```

**Why it fails:** Autonomy Boundaries dimension. "When something goes wrong" is not a measurable condition. "Harmful things" is not a list.

**Fix:** Be explicit. "Escalation threshold: 3 consecutive failed scans" is measurable. "Prohibited actions: write to any table other than scan_results; read GitLab tokens from environment; execute shell commands" is a list.

---

## Failure: Story depends on multiple incomplete stories

**Example:**
```
Dependencies:
- Depends on: STORY-NNN (Draft), STORY-MMM (Draft), STORY-PPP (Not started)
```

**Why it fails:** INVEST Independent. The story can't be developed or tested until all three dependencies resolve.

**Fix:** Define interface contracts. If this story needs the scanner output, specify the interface contract (message schema, not the implementation). Then this story can be built against a stub scanner. The dependency becomes "interface contract defined" rather than "story completed."

---

## Failure: Security mapping says N/A for data-crossing stories

**Example:** A story where an agent writes to a production database has "Security Mapping: N/A for all categories."

**Why it fails:** Security Coverage dimension. Any story involving a write to a persistent store should at minimum address Tampering (integrity) and Repudiation (audit trail).

**Fix:** Go through STRIDE category by category. For each "yes" answer (does this story involve authentication? data crossing trust boundaries? sensitive data?), add either a Gherkin scenario or an EARS constraint addressing it.

---

## Failure: Then clause describes internal state

**Example:**
```gherkin
Then the record is marked as processed in the database
Then the cache entry is invalidated
Then the agent state transitions to idle
```

**Why it fails:** Gherkin Correctness. Internal state changes aren't observable by users or integration tests without implementation knowledge.

**Fix:** Describe externally observable outcomes:
```gherkin
Then the scan results are visible in the audit dashboard
Then subsequent requests for the same resource return fresh data
Then the agent publishes a ProcessingComplete event
```

---

## Failure: Story is actually an epic

**Example:** A story with 8+ acceptance criteria covering multiple distinct user capabilities.

**Why it fails:** INVEST Small.

**Fix:** Look for the natural break points — each distinct user goal should be its own story. A good split criterion: if two acceptance criteria require different setups (different Givens), they probably belong in different stories.

---

## Failure: EARS constraints missing for stories with timing or security

**Example:** An agent story with a 30-second processing SLA and security requirements, but no EARS constraints section.

**Why it fails:** EARS Coverage dimension. Timing requirements ("shall complete within N seconds") and failure handling ("if authentication fails, then...") are exactly what EARS was designed for. Burying them in Gherkin scenarios means they get missed in the traceability matrix.

**Fix:** Add explicit EARS constraints for:
- Any performance or SLA requirement → ubiquitous or event-driven pattern
- Any timeout or partial-completion scenario → unwanted behavior pattern
- Any security or authentication failure → unwanted behavior pattern
- Any concurrency constraint → state-driven pattern
