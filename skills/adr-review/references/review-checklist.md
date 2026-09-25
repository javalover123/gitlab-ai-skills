# ADR Review Checklist

## Per-ADR Quality Checks

### Format
- [ ] YAML frontmatter present
- [ ] `status` field set (proposed/accepted/deprecated/superseded)
- [ ] `date` field present
- [ ] `decision-makers` field present (at least for significant decisions)
- [ ] File named `NNNN-kebab-case-title.md`
- [ ] Title is a noun phrase ("Use Redis for Caching", not "Why We Chose Redis")

### Context Section
- [ ] Describes the situation and forces at play
- [ ] Value-neutral — doesn't presuppose the conclusion
- [ ] Sufficient detail for a new team member to understand the decision
- [ ] Doesn't repeat information from other sections

### Options Analysis
- [ ] At least 2 options considered
- [ ] Each option has genuine pros and cons
- [ ] Rejected options aren't strawmen
- [ ] Options are distinct (not minor variations of the same approach)

### Decision Outcome
- [ ] Chosen option is clearly stated
- [ ] Justification connects back to decision drivers
- [ ] Reasoning is specific, not generic

### Consequences
- [ ] "Good" consequences are listed
- [ ] "Bad" consequences are listed (every decision has trade-offs)
- [ ] Consequences are specific and observable
- [ ] No consequences that should actually be in the context section

### Cross-References
- [ ] Spec requirements linked where applicable
- [ ] Threat model entries linked where applicable
- [ ] Related ADRs linked
- [ ] Superseded ADRs correctly updated

## Decision Log Completeness

### Technology Decisions
- [ ] Primary programming language choice
- [ ] Web framework / application framework
- [ ] Database technology and ORM/query layer
- [ ] Authentication mechanism
- [ ] Caching strategy
- [ ] Message queue / event system (if used)
- [ ] Deployment platform and strategy
- [ ] CI/CD pipeline technology

### Architecture Decisions
- [ ] System architecture pattern (monolith, microservices, serverless)
- [ ] API design approach (REST, GraphQL, gRPC)
- [ ] Data consistency model
- [ ] Error handling strategy
- [ ] Logging and observability approach
- [ ] Configuration management approach

### Security Decisions
- [ ] Authentication protocol (JWT, sessions, OAuth)
- [ ] Authorization model (RBAC, ABAC, ACL)
- [ ] Encryption approach (at rest, in transit)
- [ ] Secret management strategy
- [ ] Rate limiting approach
- [ ] Dependency security scanning strategy

## Decision Freshness

For each accepted ADR, verify:

- [ ] The decision driver forces still hold
- [ ] The chosen technology/pattern is still in use
- [ ] No major changes have invalidated the decision
- [ ] The consequences listed have played out as expected (or haven't — which is worth noting)

If any of these are no longer true, the ADR should be superseded with a new one.
