# Definition of Done — bugfix

Emit this checklist literally as the final message of a bugfix. Every box ticked
with cited evidence (test output, `file:line`, or tool result).

```
## Definition of Done

- [ ] Bug statement recorded (expected, observed, environment, smallest
      input, regressed signal).        Evidence: <link or block>
- [ ] Context-sufficiency check completed (code, logs, docs, AC located or
      explicitly silent).               Evidence: <paths>
- [ ] Reproducer test added, initially failed FOR THE RIGHT REASON, now
      passes; revert confirms red.      Evidence: <test name + output>
- [ ] Causal-discrepancy doc (three-way diff) emitted; classification and
      authoritative source named.       Evidence: <block>
- [ ] >=3 hypotheses enumerated with falsification searches; surviving
      hypothesis explains all symptoms. Evidence: <block>
- [ ] Rubber-duck trace of suspect code with divergence line identified.
                                        Evidence: <block>
- [ ] Structural fix at originating layer; structural audit >=4 Yes;
      sibling-case sweep documented.    Evidence: <diff + audit block>
- [ ] Blast radius respected; no scope creep.   Evidence: <diff scope>
- [ ] Every applicable test layer green (unit, component, workflow,
      invariant).                       Evidence: <command outputs>
- [ ] Mutation testing on changed lines: 0 survivors.
                                        Evidence: <cargo-mutants / mutmut output>
- [ ] Lint / format / build clean on touched modules.   Evidence: <output>
- [ ] If the project mandates a verification harness, every Phase 6 command
      was routed through it.            Evidence: <invocations, or N/A>
- [ ] ADR delta filed (or all triggers N with rationale).
                                        Evidence: <path or N/A>
- [ ] Spec / AC delta filed (or N/A).   Evidence: <path or N/A>
- [ ] Threat-model delta filed (SLSA level recorded for any dep change, or
      N/A).                             Evidence: <path or N/A>
- [ ] User-story delta filed (or N/A).  Evidence: <path or N/A>
- [ ] Adversarial review APPROVED with every subsection filled.
                                        Evidence: <Phase 8 block>
- [ ] Final-message hygiene: Evidence / Remaining Risks / Not Tested
      sections emitted.                 Evidence: <below>

## Evidence
<verbatim test output, diffs, command results>

## Remaining Risks
- <risk 1, with mitigation or "accepted">
- <risk 2>

## Not Tested
- <input class / code path / scenario>
```

## Self-anchoring

At the start of every phase after Phase 1, re-emit the one-sentence Bug
statement and the causal-discrepancy classification. If either has drifted from
your current plan, stop and reconcile — you may be solving a different problem
than the one reported.

After every failed verification, append a `LESSONS_LEARNED` entry: what you
expected, what actually happened, the mechanism you missed, and what to check
first next time. Each next attempt must reference each prior lesson explicitly.

## Circuit breaker

Stop and emit a `## Blocked` report when ALL hold: five or more hypotheses tried
and falsified; every context rung exhausted (code, logs, docs, user); the
reproducer can't be made deterministic or fails for the wrong reason after three
attempts; and your mental model still doesn't match observed behaviour. Name the
simplest experiment that would break the impasse and the info/tool/access you'd
need. Don't thrash further.
