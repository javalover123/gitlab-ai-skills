# Final output shape

Post exactly this shape at the end of the workflow, nothing before or
after it. Every field must be backed by output you actually ran and saw —
don't fill in a field from expectation alone.

```
ISSUE:    <url>
CAUSE:    <one line>
FIX:      <file:line — one line>
EVIDENCE: <spec file> green · <live check, one line> · suite <n> examples, <f> failures
MR:       <url>
SKIPPED:  <E2E | security bail-out | …> — <why>, or none
```
