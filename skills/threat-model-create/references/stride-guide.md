# STRIDE Threat Identification Guide

STRIDE is a systematic method for identifying threats by analyzing each element in a Data Flow Diagram against six threat categories. Originally developed at Microsoft, it remains the most widely used architectural threat identification framework.

## The Six Categories

### Spoofing (violates Authentication)

Can an attacker pretend to be someone or something they're not?

**For External Entities:**
- Can a user impersonate another user?
- Can an attacker forge API keys or tokens?
- Can a rogue service impersonate a legitimate one?
- Can expired or revoked credentials still be used?

**For Processes:**
- Can an attacker trick the process into accepting forged credentials?
- Can the process be replaced with a malicious version?

**Common attacks:** Credential stuffing, session hijacking, token forgery, DNS spoofing, certificate impersonation, replay attacks.

**Standard mitigations:**
- Multi-factor authentication
- Strong session token generation (cryptographically random, sufficient entropy)
- Certificate pinning for service-to-service communication
- Mutual TLS between services
- Anti-replay mechanisms (nonces, timestamps)
- Token expiration and rotation policies

### Tampering (violates Integrity)

Can an attacker modify data they shouldn't be able to?

**For Processes:**
- Can input be crafted to alter process behavior? (injection)
- Can configuration be modified by unauthorized parties?

**For Data Stores:**
- Can an attacker modify database records directly?
- Can stored data be corrupted without detection?

**For Data Flows:**
- Can data be modified in transit? (man-in-the-middle)
- Can request parameters be manipulated?

**Common attacks:** SQL injection, command injection, parameter tampering, man-in-the-middle, config file manipulation, binary patching.

**Standard mitigations:**
- Input validation (allowlist, not denylist)
- Parameterized queries (never string concatenation for SQL)
- TLS for all data in transit
- Digital signatures for critical data
- File integrity monitoring
- Immutable infrastructure patterns

### Repudiation (violates Non-repudiation)

Can an attacker deny performing an action?

**For External Entities:**
- Can a user deny making a transaction?
- Can a user deny accessing sensitive data?

**For Processes:**
- Are actions logged with sufficient detail?
- Are logs tamper-evident?

**Common attacks:** Log deletion, log manipulation, unsigned transactions, shared credentials (can't attribute actions).

**Standard mitigations:**
- Audit logging with timestamps, actor identity, action, and outcome
- Tamper-evident log storage (append-only, signed, or shipped to separate system)
- Digital signatures on transactions
- Individual credentials (never shared accounts)

### Information Disclosure (violates Confidentiality)

Can an attacker access data they shouldn't see?

**For Processes:**
- Do error messages reveal internal details? (stack traces, SQL errors)
- Does the process log sensitive data?

**For Data Stores:**
- Is data encrypted at rest?
- Are database backups protected?
- Are access controls enforced?
- Are connection strings and credentials stored securely?

**For Data Flows:**
- Is data encrypted in transit?
- Can an attacker sniff traffic between services?

**Common attacks:** Directory traversal, error message information leakage, memory dumps, side-channel attacks, insecure backup exposure, missing access controls.

**Standard mitigations:**
- Encryption at rest (AES-256 or equivalent)
- TLS 1.2+ for all network communication
- Minimal error messages (log details server-side, show generic messages to users)
- Access controls on all data stores
- Data classification and handling policies
- Secure disposal of temporary files and caches containing sensitive data

### Denial of Service (violates Availability)

Can an attacker make the system unavailable?

**For Processes:**
- Can an attacker exhaust CPU, memory, or connections?
- Can algorithmic complexity attacks slow the system?

**For Data Stores:**
- Can an attacker fill storage?
- Can an attacker lock database resources?

**For Data Flows:**
- Can an attacker flood the network?
- Can an attacker exhaust connection pools?

**Common attacks:** Volumetric flooding, slowloris, algorithmic complexity (hash collision, regex backtracking), resource exhaustion, distributed denial of service.

**Standard mitigations:**
- Rate limiting per client/IP
- Request size limits
- Timeouts on all operations
- Circuit breakers for downstream services
- Resource quotas (CPU, memory, connections, storage)
- CDN and DDoS protection services
- Graceful degradation under load

### Elevation of Privilege (violates Authorization)

Can an attacker gain access they shouldn't have?

**For Processes:**
- Can a regular user access admin functions?
- Can a user access another user's data? (IDOR)
- Can a lower-privilege process gain higher privileges?
- Can JWT claims or session attributes be manipulated to change roles?

**Common attacks:** Insecure Direct Object Reference (IDOR), privilege escalation via parameter manipulation, missing function-level access control, JWT claim manipulation, role bypass.

**Standard mitigations:**
- Authorization checks at every endpoint (not just the UI)
- Role-Based Access Control (RBAC) or Attribute-Based Access Control (ABAC)
- Principle of least privilege for service accounts
- Indirect object references (don't expose database IDs)
- Server-side authorization (never trust client-side checks)
- Input validation on role/permission fields to prevent injection into authorization logic

## STRIDE-per-Element Worksheet

For systematic analysis, work through each DFD element:

```markdown
### Element: [Name] ([Type: Entity/Process/Store/Flow])

| Category | Applicable? | Threat Description | Severity | Mitigation |
|---|---|---|---|---|
| Spoofing | [Yes/No/NA] | [description] | [DREAD score] | [mitigation] |
| Tampering | [Yes/No/NA] | [description] | [DREAD score] | [mitigation] |
| Repudiation | [Yes/No/NA] | [description] | [DREAD score] | [mitigation] |
| Info Disclosure | [Yes/No/NA] | [description] | [DREAD score] | [mitigation] |
| Denial of Service | [Yes/No/NA] | [description] | [DREAD score] | [mitigation] |
| Elev. of Privilege | [Yes/No/NA] | [description] | [DREAD score] | [mitigation] |
```

## LINDDUN Privacy Extension

For systems handling personal data, extend STRIDE with LINDDUN:

| Category | Threat | Example |
|---|---|---|
| **Linking** | Correlating data across sources to identify users | Combining logs with purchase history |
| **Identifying** | Determining a person's identity from data | IP address + browsing pattern = identity |
| **Non-repudiation** | Inability to deny involvement (privacy concern, opposite of security) | Over-logging that proves user actions they'd prefer private |
| **Detecting** | Determining someone uses a service | Traffic analysis reveals healthcare app usage |
| **Data Disclosure** | Exposing personal data | Database breach, unauthorized access |
| **Unawareness** | Users don't know how their data is used | No privacy policy, hidden data sharing |
| **Non-compliance** | Violating privacy regulations | GDPR violations, missing data deletion |

Apply LINDDUN when the system processes PII, health data, financial data, or is subject to GDPR/CCPA/HIPAA.
