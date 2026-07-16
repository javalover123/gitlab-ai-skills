# Security Coverage Reference

## When to Apply Full STRIDE Coverage

Stories that cross any of these boundaries need all six STRIDE categories addressed:

- Data crosses a network boundary (API call, message bus, external service)
- A secret or credential is involved (tokens, keys, passwords)
- Multiple trust domains interact (agent → database, user → API, CI → registry)
- Data is written to a persistent store
- Authentication or authorization is checked

Stories that don't cross these boundaries (pure in-memory computation, read-only operations in a single trust domain) can have N/A for most STRIDE categories.

## STRIDE Coverage Checklist

For each relevant category, the story needs either a Gherkin scenario or an EARS constraint that addresses it:

### Spoofing
**What to verify:** The story has authentication — the system verifies WHO is making the request.
**Minimum evidence:** An error scenario where unauthenticated access is rejected.
```gherkin
When an unauthenticated request arrives
Then the system returns 401 and logs the attempt
```
Or EARS: `If a ZeroMQ connection fails CURVE authentication, then the agent shall reject the connection and log the attempt.`

### Tampering
**What to verify:** Data integrity is preserved in transit and at rest.
**Minimum evidence:** A check that modified data is detected or prevented.
Common pattern: verify audit records are append-only, graph writes are authenticated.

### Repudiation
**What to verify:** Actions are logged with enough detail to trace back to the actor.
**Minimum evidence:** A scenario or EARS constraint requiring audit logging.
```
The agent shall log every graph write with actor identity, timestamp, and correlation ID.
```

### Information Disclosure
**What to verify:** Sensitive data doesn't leak to unauthorized parties.
**Red flag:** A story that handles GitLab tokens, API keys, or personal data without any disclosure scenario.
**Minimum evidence:** Explicit prohibition on logging sensitive values, or a scenario verifying they don't appear in logs.

### Denial of Service
**What to verify:** Resource consumption is bounded under adversarial conditions.
**Minimum evidence:** An EARS constraint with a rate limit, queue depth limit, or timeout.
```
While processing scan jobs, the agent shall not accept more than 10 concurrent connections.
```

### Elevation of Privilege
**What to verify:** The actor can't do more than it's authorized to do.
**For agent stories:** The autonomy limits section addresses this — prohibited actions must be explicit.
**Minimum evidence:** A scenario or EARS constraint where attempted out-of-scope action is rejected.

## Supply Chain Standards Mapping

### SLSA v1.0 Quick Reference

| Story involves... | Map to SLSA |
|---|---|
| Build artifact production | L1: provenance generated |
| CI/CD pipeline | L2: hosted builds, signed provenance |
| Release workflow | L3: hardened, isolated, tamper-resistant |
| Dependency consumption only | N/A |

### OWASP SCVS Quick Reference

| Story involves... | SCVS control |
|---|---|
| Generating an SBOM | BOM-1, BOM-3 |
| Scanning for vulnerabilities | CA-1, CA-2 |
| Managing package dependencies | PM-1, PM-3 |
| Verifying component integrity | PM-5 |

### NIST SSDF Quick Reference

| Story involves... | SSDF practice |
|---|---|
| Developer security training requirements | PO.2 |
| Code signing or integrity checks | PS.1, PS.2 |
| Security testing in CI | PW.7, PW.8 |
| Vulnerability response process | RV.1, RV.2 |

### OpenSSF Scorecard Quick Reference

Stories that configure build or repo settings should reference relevant Scorecard checks:

- Branch protection rules → `branch-protection`
- Signed releases → `signed-releases`
- Dependency pinning → `pinned-dependencies`
- CI test coverage → `ci-tests`
- Code review requirements → `code-review`
- Vulnerability scanning → `vulnerabilities`
