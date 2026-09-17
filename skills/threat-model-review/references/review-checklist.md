# Threat Model Review Checklist

## Data Flow Diagram (DFD) Currency

### External Entities

- [ ] All current user roles represented
- [ ] All third-party services represented
- [ ] Removed entities marked or removed from model
- [ ] Trust levels are current for each entity

### Processes

- [ ] All running services represented
- [ ] Process descriptions match current functionality
- [ ] Technology stack information is current
- [ ] New services added since last review are included

### Data Stores

- [ ] All databases, caches, queues represented
- [ ] Data sensitivity classifications are current
- [ ] Storage technologies match what's deployed
- [ ] Removed stores are noted

### Data Flows

- [ ] All API endpoints covered
- [ ] Protocol information is current (HTTP/HTTPS/gRPC/WebSocket)
- [ ] Encryption status is accurate for each flow
- [ ] New inter-service communications are included

### Trust Boundaries

- [ ] Network boundaries match deployment architecture
- [ ] Authentication boundaries match implementation
- [ ] Authorization levels match current RBAC/ABAC setup
- [ ] Container/process isolation boundaries are current

## STRIDE Coverage Matrix

For each DFD element, verify applicable categories are analyzed:

| Element Type | S | T | R | I | D | E |
|---|---|---|---|---|---|---|
| External Entity | Required | — | Required | — | — | — |
| Process | Required | Required | Required | Required | Required | Required |
| Data Store | — | Required | — | Required | Required | — |
| Data Flow | — | Required | — | Required | Required | — |

"Required" means this combination must have at least one threat entry or an explicit "N/A — not applicable because [reason]."

## Risk Score Accuracy

- [ ] No threat scored before mitigation that hasn't been re-scored after
- [ ] Critical threats (40-50) aren't older than 72 hours without action
- [ ] High threats (25-39) have active mitigation plans
- [ ] Score justifications are documented (not just numbers)
- [ ] Similar threats have consistent scores
- [ ] Scores use the calibration examples from the DREAD guide as anchors

## Mitigation Tracking

- [ ] Every threat >= Medium has a mitigation (Mitigate, Accept, Transfer, or Eliminate)
- [ ] "Accepted" risks have documented justification and sign-off
- [ ] "Implemented" mitigations are verified in code
- [ ] "In Progress" mitigations have owners and timelines
- [ ] "Not Started" critical/high threats are escalated
- [ ] Mitigations reference specific implementation (file paths, config changes, not just descriptions)

## Cross-References

- [ ] Every mitigation links to a spec requirement
- [ ] Security decisions link to ADRs
- [ ] Spec security requirements link back to threat entries
- [ ] ADR security decisions link back to threat entries
- [ ] No broken links in any direction
- [ ] Cross-reference IDs use the correct format (`FR-XXX`, `ADR-NNNN`, `TM-COMPONENT-NNN`)

## Common Review Findings

### New attack surfaces not in model

- New API endpoints without threat analysis
- New third-party integrations without trust boundary documentation
- Infrastructure changes (new load balancer, new service mesh, new cloud service)
- WebSocket or real-time communication channels added without analysis

### Stale mitigations

- "In Progress" for more than one sprint/iteration
- "Implemented" but the code was later refactored or removed
- Dependencies that provided mitigation were updated or replaced
- Configuration-based mitigations that weren't carried over during infrastructure changes

### Score inflation/deflation

- Threats scored high to get attention but never actually that severe
- Threats scored low to avoid work but actually significant
- Scores haven't been updated after the system's user base or data sensitivity changed
- Mitigations implemented but scores not re-evaluated to reflect reduced risk

### Missing threat categories

- Privacy threats (LINDDUN) not considered for PII-handling systems
- Supply chain threats not considered for projects with many dependencies
- Insider threats not considered for systems with privileged access
- Physical security threats not considered for on-premises or edge deployments
