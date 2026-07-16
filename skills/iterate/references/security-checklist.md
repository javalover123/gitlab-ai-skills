# Security Hardening Checklist

Full security review checklist for closing security gaps during iteration.

## Input Validation

### User Input
- [ ] All user input validated against expected format/range
- [ ] Input length limits enforced (prevent DoS)
- [ ] Special characters sanitized or rejected
- [ ] Null bytes rejected (in C/unsafe contexts)
- [ ] Path traversal attempts detected (no ../ in paths)

### API Input
- [ ] Request body size limits enforced
- [ ] Content-Type validation
- [ ] Rate limiting implemented
- [ ] Authentication required for sensitive endpoints
- [ ] Input schema validation (JSON Schema, protobuf, etc.)

### File Input
- [ ] File type validation (not just extension)
- [ ] File size limits enforced
- [ ] Files opened read-only when possible
- [ ] Temporary files created securely (mkstemp, not predictable names)
- [ ] File uploads stored outside webroot

## Memory Safety (C/C++/Unsafe Rust)

### Buffer Operations
- [ ] No strcpy/strcat (use strlcpy/strlcat or snprintf)
- [ ] No gets() (use fgets)
- [ ] Buffer sizes checked before operations
- [ ] Array access bounds-checked
- [ ] Off-by-one errors verified against

### Pointer Safety
- [ ] Null pointer checks before dereference
- [ ] Use-after-free prevented (no dangling pointers)
- [ ] Double-free prevented
- [ ] Memory leaks checked (valgrind, AddressSanitizer)

### Integer Safety
- [ ] Integer overflow checked (especially in size calculations)
- [ ] Signed/unsigned mixing avoided
- [ ] Truncation considered (size_t → int conversions)

## Authentication & Authorization

### Authentication
- [ ] Passwords hashed with modern algorithm (Argon2, scrypt, bcrypt)
- [ ] No plaintext credential storage
- [ ] Session tokens cryptographically random
- [ ] Token expiration implemented
- [ ] Logout invalidates session server-side

### Authorization
- [ ] Permission checks on every protected operation
- [ ] No authorization logic in client-side code
- [ ] User can only access their own data (checked server-side)
- [ ] Privilege escalation paths audited
- [ ] Default deny (not default allow)

## Cryptography

### Key Management
- [ ] Keys not hardcoded in source
- [ ] Keys loaded from secure storage (env vars, secrets manager)
- [ ] Key rotation supported
- [ ] Separate keys for different environments (dev/staging/prod)

### Encryption
- [ ] No custom crypto (use standard libraries)
- [ ] Modern algorithms only (AES-256-GCM, ChaCha20-Poly1305)
- [ ] No deprecated algorithms (DES, MD5, SHA1 for signatures)
- [ ] Random IVs/nonces (never reused)
- [ ] Authenticated encryption (GCM, Poly1305, not CBC alone)

### TLS/SSL
- [ ] TLS 1.2+ required (not 1.0/1.1)
- [ ] Certificate validation enabled
- [ ] No self-signed certs in production
- [ ] Strong cipher suites only

## Dependency Security

### Dependency Scanning
- [ ] Run cargo-audit (Rust), npm audit (Node), safety (Python), etc.
- [ ] All known CVEs patched
- [ ] Dependencies updated to latest secure versions
- [ ] Unused dependencies removed

### Supply Chain
- [ ] Dependencies from trusted sources only
- [ ] Lock files committed (Cargo.lock, package-lock.json, etc.)
- [ ] Checksum verification enabled
- [ ] Minimal dependency tree (avoid bloat)

## Error Handling

### Error Messages
- [ ] No sensitive data in error messages
- [ ] Generic errors to users (detailed logs server-side only)
- [ ] Stack traces not exposed to users
- [ ] Database errors not leaked (no raw SQL in output)

### Error Propagation
- [ ] Errors logged with context
- [ ] No silent failures (unwrap() removed or justified)
- [ ] Panic handlers catch crashes gracefully
- [ ] Recovery mechanisms for transient errors

## Logging & Monitoring

### What to Log
- [ ] Authentication attempts (success and failure)
- [ ] Authorization failures
- [ ] Input validation failures
- [ ] System errors and exceptions
- [ ] Configuration changes

### What NOT to Log
- [ ] Passwords or credentials
- [ ] Session tokens
- [ ] Personal data (PII) without masking
- [ ] Credit card numbers
- [ ] API keys

## Configuration Security

### Secrets Management
- [ ] No secrets in source code
- [ ] No secrets in version control (check .git history)
- [ ] Secrets in environment variables or secrets manager
- [ ] Development secrets different from production

### Secure Defaults
- [ ] Debug mode disabled in production
- [ ] Detailed logging disabled in production
- [ ] CORS restrictive (not allow *)
- [ ] CSP headers configured
- [ ] HTTPS redirects enabled

## Language-Specific Issues

### Rust
- [ ] Unsafe blocks minimized and audited
- [ ] Unsafe blocks documented with safety invariants
- [ ] No unwrap() or expect() on untrusted input
- [ ] FFI boundaries validated
- [ ] Send/Sync implemented correctly

### C
- [ ] Format string vulnerabilities eliminated (no printf(user_input))
- [ ] Signal handlers safe (only async-signal-safe functions)
- [ ] TOCTOU races eliminated (time-of-check/time-of-use)
- [ ] Setuid binaries audited (if applicable)

### Go
- [ ] Race detector run (go test -race)
- [ ] SQL injection prevented (use parameterized queries)
- [ ] Template injection prevented (use html/template)
- [ ] Path traversal prevented (filepath.Clean)

### Python
- [ ] No eval() on untrusted input
- [ ] No pickle on untrusted data
- [ ] No shell=True in subprocess (use list args)
- [ ] SQL injection prevented (use parameterized queries)

## Web-Specific Issues

### XSS Prevention
- [ ] Output encoding (HTML entities, JavaScript escaping)
- [ ] CSP headers configured
- [ ] No innerHTML with user data
- [ ] Framework auto-escaping enabled

### CSRF Prevention
- [ ] CSRF tokens on state-changing operations
- [ ] SameSite cookies configured
- [ ] Origin header validation

### SQL Injection Prevention
- [ ] Parameterized queries everywhere
- [ ] No string concatenation for SQL
- [ ] ORM used correctly (not raw SQL strings)
- [ ] Least privilege database user

## Static Analysis Integration

### Tools to Run
- **Rust**: cargo-audit, cargo-clippy with security lints
- **C/C++**: cppcheck, clang-static-analyzer, Coverity
- **Go**: gosec, staticcheck
- **Python**: bandit, semgrep
- **JavaScript**: ESLint with security plugins

### Compiler Hardening
- **C/C++**: `-fstack-protector-strong`, `-D_FORTIFY_SOURCE=2`, `-pie`, `-fPIE`
- **Rust**: `overflow-checks = true`, `panic = "abort"`
- **Go**: Build with `-buildmode=pie`

## Threat Modeling

Answer these questions:

1. **What assets need protection?** (user data, credentials, IP)
2. **Who are the adversaries?** (external attackers, malicious users, insiders)
3. **What are the attack surfaces?** (APIs, file uploads, user input fields)
4. **What's the damage if breached?** (data loss, service disruption, reputation)
5. **What controls mitigate risks?** (validation, encryption, auth, logging)

## Penetration Testing

### Manual Testing
- [ ] Fuzz critical parsers
- [ ] Try SQL injection payloads
- [ ] Try XSS payloads
- [ ] Test authentication bypass
- [ ] Test authorization bypass
- [ ] Attempt path traversal
- [ ] Test for CSRF
- [ ] Test session handling

### Automated Scanning
- [ ] Run OWASP ZAP or Burp Suite (for web apps)
- [ ] Run AFL or libFuzzer (for parsers/file handlers)
- [ ] Run dependency scanners

## Compliance Checklists

### OWASP Top 10 (2021)
- [ ] A01: Broken Access Control
- [ ] A02: Cryptographic Failures
- [ ] A03: Injection
- [ ] A04: Insecure Design
- [ ] A05: Security Misconfiguration
- [ ] A06: Vulnerable Components
- [ ] A07: Authentication Failures
- [ ] A08: Software and Data Integrity Failures
- [ ] A09: Security Logging and Monitoring Failures
- [ ] A10: Server-Side Request Forgery

### CWE Top 25 (2024)
See [CWE Top 25](https://cwe.mitre.org/top25/) for current rankings.

Focus areas:
- Out-of-bounds write (CWE-787)
- Cross-site scripting (CWE-79)
- SQL injection (CWE-89)
- Use after free (CWE-416)
- OS command injection (CWE-78)
- Improper input validation (CWE-20)

## Resources

- **OWASP**: https://owasp.org/
- **CWE Top 25**: https://cwe.mitre.org/top25/
- **CERT Secure Coding**: https://wiki.sei.cmu.edu/confluence/display/seccode
- **NIST Guidelines**: https://csrc.nist.gov/publications
- **Rust Security**: https://anssi-fr.github.io/rust-guide/
