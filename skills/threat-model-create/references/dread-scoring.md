# DREAD Risk Scoring Rubric

DREAD scores threats on a 0-10 scale across five factors. The total (0-50) determines severity and response priority.

## Scoring Factors

### Damage Potential (0-10)

How bad is it if the threat is exploited?

| Score | Description | Example |
|---|---|---|
| 0 | No impact | Cosmetic defacement of unused page |
| 2 | Minor inconvenience | User sees wrong timezone |
| 4 | Data quality issue | Corrupted non-critical cache |
| 6 | Significant data loss | User loses unsaved work |
| 8 | Sensitive data exposed | PII leaked for subset of users |
| 10 | Complete system compromise | Admin access gained, all data exposed |

### Reproducibility (0-10)

How reliably can the attack be repeated?

| Score | Description | Example |
|---|---|---|
| 0 | Nearly impossible to reproduce | Race condition requiring exact timing |
| 2 | Requires specific conditions | Only works on certain OS versions |
| 4 | Requires authentication | Needs valid account |
| 6 | Requires knowledge of system | Needs to know internal endpoints |
| 8 | Easy with basic tools | Curl command can trigger it |
| 10 | Always works, trivially | Visit a URL, exploit fires |

### Exploitability (0-10)

What skill level and tooling are needed?

| Score | Description | Example |
|---|---|---|
| 0 | Requires custom zero-day | Novel kernel exploit |
| 2 | Requires expert knowledge | Timing attack on crypto implementation |
| 4 | Requires specialized tools | Custom fuzzer for binary protocol |
| 6 | Publicly known technique | SQL injection with sqlmap |
| 8 | Basic scripting skill | Python script to automate attack |
| 10 | No skill needed | Click a link, paste a URL |

### Affected Users (0-10)

How many users or systems are impacted?

| Score | Description | Example |
|---|---|---|
| 0 | None (self-inflicted only) | User can break own session |
| 2 | Single user | One user's data exposed |
| 4 | Small group | One team's workspace affected |
| 6 | Significant portion | 10-50% of users impacted |
| 8 | Most users | All users of a feature |
| 10 | All users/systems | Complete platform impact |

### Discoverability (0-10)

How easy is it to find the vulnerability?

| Score | Description | Example |
|---|---|---|
| 0 | Requires source code access + deep analysis | Logic flaw in internal service |
| 2 | Requires internal access | Only visible to authenticated admins |
| 4 | Requires specific probing | Found by fuzzing non-obvious parameters |
| 6 | Findable with standard scanning | Detected by automated vulnerability scanner |
| 8 | Visible in public documentation | API docs reveal the flaw |
| 10 | Obvious from the URL/interface | Visible in browser address bar |

## Severity Mapping

| Total Score | Severity | SLA | Color |
|---|---|---|---|
| 40-50 | **Critical** | Fix within 72 hours | Red |
| 25-39 | **High** | Fix within 2 weeks | Orange |
| 11-24 | **Medium** | Fix within 1 month | Yellow |
| 1-10 | **Low** | Monitor quarterly | Green |

## Calibration Examples

### Example: SQL Injection on Login (Critical)

| Factor | Score | Reasoning |
|---|---|---|
| Damage | 9 | Full database access, credential theft |
| Reproducibility | 9 | Works every time with known payload |
| Exploitability | 8 | sqlmap automates it, well-documented technique |
| Affected Users | 10 | All users' data at risk |
| Discoverability | 7 | Standard scanning tools find it |
| **Total** | **43** | **Critical** |

### Example: Missing Rate Limiting on Login (High)

| Factor | Score | Reasoning |
|---|---|---|
| Damage | 6 | Individual account compromise |
| Reproducibility | 9 | Trivially repeatable |
| Exploitability | 8 | Simple script |
| Affected Users | 4 | One account at a time |
| Discoverability | 6 | Try and observe no limiting |
| **Total** | **33** | **High** |

### Example: Verbose Error Messages (Medium)

| Factor | Score | Reasoning |
|---|---|---|
| Damage | 2 | Information useful for other attacks |
| Reproducibility | 10 | Always present |
| Exploitability | 2 | Information only, not direct exploit |
| Affected Users | 2 | Attacker targeting specific endpoint |
| Discoverability | 8 | Trigger any error and observe |
| **Total** | **24** | **Medium** |

### Example: Missing HSTS Header (Low)

| Factor | Score | Reasoning |
|---|---|---|
| Damage | 2 | Enables potential MitM for first request |
| Reproducibility | 2 | Requires network position |
| Exploitability | 2 | Requires MitM setup |
| Affected Users | 2 | Only new visitors on compromised networks |
| Discoverability | 2 | Requires checking headers |
| **Total** | **10** | **Low** |

## Limitations of DREAD

Microsoft discontinued DREAD internally because different analysts assigned very different scores to the same threat. To improve consistency:

- **Use the calibration examples above** as anchors
- **Score as a team** when possible — average multiple opinions
- **Focus on relative ranking** more than absolute scores — the exact numbers matter less than consistent ordering
- **Document your reasoning** for each factor, not just the number
