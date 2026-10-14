# Spec Completeness Checklist

Use this checklist during Phase 3 of the review workflow. Each section covers a different dimension of spec quality.

## Structural Completeness

- [ ] RFC 2119 boilerplate is present
- [ ] Scope section clearly defines boundaries (in-scope and out-of-scope)
- [ ] Definitions/glossary section exists for domain terms
- [ ] References section links to related ADRs, threat model, external standards
- [ ] Traceability matrix is present and current
- [ ] Definition of Done is specified
- [ ] Open issues section exists
- [ ] Changelog records spec evolution

## Functional Requirements

- [ ] Every feature has at least one functional requirement
- [ ] Every requirement has a unique, stable ID (FR-XXX)
- [ ] Requirements use EARS syntax patterns
- [ ] Requirements use RFC 2119 keywords (MUST, SHALL, SHOULD, MAY)
- [ ] Every requirement has Gherkin acceptance criteria
- [ ] Happy path and error paths are both specified
- [ ] No requirement contains "and" joining unrelated behaviors
- [ ] No requirement uses vague language ("user-friendly", "fast", "secure")
- [ ] No requirement references "obvious" or "common sense" behavior

## Non-Functional Requirements

- [ ] Performance requirements have measurable thresholds
- [ ] Availability requirements specify uptime percentage and measurement period
- [ ] Scalability requirements specify load levels
- [ ] Security requirements trace to threat model entries
- [ ] Data retention requirements are specified
- [ ] Backup and recovery requirements are specified
- [ ] Compliance requirements are listed if applicable (GDPR, HIPAA, PCI-DSS)
- [ ] Logging and monitoring requirements are specified

## Interface Requirements

- [ ] All external APIs are documented (endpoints, methods, request/response formats)
- [ ] API versioning strategy is specified
- [ ] Authentication mechanism is documented
- [ ] Error response format is consistent
- [ ] Rate limiting rules are specified
- [ ] All service-to-service interfaces are documented

## Data Requirements

- [ ] Data models are defined (entities, relationships, constraints)
- [ ] Data validation rules are specified
- [ ] Data migration strategy is documented (if applicable)
- [ ] Data sensitivity classification is applied
- [ ] PII handling requirements are specified
- [ ] Data backup frequency and retention are defined

## Traceability

- [ ] Every requirement traces to at least one test case
- [ ] Every security requirement traces to a threat model entry
- [ ] Every technology choice traces to an ADR
- [ ] No orphan tests (tests without requirements)
- [ ] No orphan requirements (requirements without tests)
- [ ] Forward and backward traceability both verified

## Cross-Reference Integrity

- [ ] All ADR links resolve to existing documents
- [ ] All threat model links resolve to existing entries
- [ ] All test case references match actual test files
- [ ] No broken internal links within the spec
- [ ] Requirement ID numbering is consistent (no gaps from deletions)

## Common Gaps by Project Type

### Web Applications

- [ ] CSRF protection requirements
- [ ] XSS prevention requirements
- [ ] Content Security Policy requirements
- [ ] Cookie security requirements (Secure, HttpOnly, SameSite)
- [ ] CORS configuration requirements
- [ ] Clickjacking protection requirements (X-Frame-Options, frame-ancestors)

### APIs

- [ ] Rate limiting per client/endpoint
- [ ] Request size limits
- [ ] Timeout requirements
- [ ] Pagination requirements for list endpoints
- [ ] Idempotency requirements for mutations
- [ ] Versioning strategy for breaking changes

### Microservices

- [ ] Service discovery requirements
- [ ] Circuit breaker requirements
- [ ] Distributed tracing requirements
- [ ] Configuration management requirements
- [ ] Health check endpoint requirements
- [ ] Graceful shutdown and deployment strategy requirements

### Data-Intensive Systems

- [ ] Data consistency model (strong, eventual)
- [ ] Conflict resolution strategy
- [ ] Replication requirements
- [ ] Archival and purge requirements
