# Constitution Check — Spec Kit's gate, borrowed

The Constitution Check is the first gate before every iteratotron dispatch
at iteratotron Phase 6 (Orchestrate). It's borrowed verbatim from GitHub's Spec Kit
(open-sourced 2025), which formalised the pattern: a project-level
constitution.md declares MUST / SHOULD principles, every plan is checked
against it before any code is written, and a Complexity Justification
(Spec Kit's Article-IX-style exception) is the only path past a
violation.

## Where the constitution lives

`.specify/memory/constitution.md` — Spec Kit's canonical path. Genesis
respects it. Sample structure:

```markdown
# Project Constitution

## Article I — MUST principles (non-negotiable)

1. **No unsafe Rust without ADR**. Every `unsafe` block requires an
   accepted ADR documenting why safe alternatives are insufficient and
   what invariants the block upholds.
2. **All public API is documented**. `#[deny(missing_docs)]` is on by
   default; suppressions require an ADR.
3. **No silent data loss on shutdown**. Daemons must drain their work
   queues on SIGTERM and emit a structured exit record.
4. **Test-first for any new feature touching auth, crypto, or
   persistence**. PRs without a failing test that the change makes pass
   are blocked.

## Article II — SHOULD principles (preferences)

1. **Prefer cargo-deny over cargo-audit**. cargo-deny supersedes audit
   and adds licence + bans + sources checks.
2. **Prefer ratatui over termion for TUIs**.
3. **Default to property tests for any function with > 4 inputs**.

## Article IX — Complexity Justification (the exception process)

A plan may violate a MUST principle only when:

1. The justification is recorded as a new ADR in the plan itself.
2. The ADR's "Alternatives Considered" section names ≥ 2 alternatives
   and explains why each is worse.
3. The deviation is time-bounded (with a measurable date or condition
   for re-evaluation).

The Constitution Check fails closed: a plan that violates a MUST and
does NOT include the Complexity Justification ADR is rejected.
```

## The Check itself

Run before each iteratotron dispatch as a stateless `claude -p`:

```bash
claude -p "$(cat <<EOF
You are running the Constitution Check gate.

Constitution:
$(cat .specify/memory/constitution.md)

Scope plan:
$(cat .iteratotron/scopes/<scope-id>/plan.md)

Return JSON only:
{
  "pass": true | false,
  "violations": [
    {
      "principle": "Article I.<n>",
      "scope_path": "...",
      "evidence": "...",
      "justification_present": true | false,
      "justification_adr": "<adr-id-or-null>"
    }
  ]
}
EOF
)" \
  --output-format json \
  --model haiku \
  --max-turns 1 \
  --disallowed-tools "Edit,Write,Bash,WebFetch,WebSearch" \
  --permission-mode bypassPermissions
```

Haiku is the right model — the task is structured pattern-matching
against a closed rubric. Sonnet is overkill. Opus is wasteful.

## Failure handling

When the Check returns `pass: false`:

1. **Genesis does not dispatch.** The scope returns to the queue with
   `status: needs_human` and the violation details attached.
2. **Genesis invokes `human-review`** (or `AskUserQuestion` when run
   without that skill installed) with the violation and three options:
   - **Amend the plan** to comply with the constitution.
   - **Amend the constitution** to allow the deviation (rare —
     constitutions are supposed to be stable).
   - **Add a Complexity Justification ADR** (per Article IX).
3. **Re-run the Check** after any of the three. Loop until pass or the
   human elects to defer the scope.

## Why this gate is non-optional

Without the Constitution Check, projects drift. A team's principles
(test-first, no unsafe without ADR, etc.) live only in tribal
knowledge; the LLM agent doesn't see them; the agent ships code that
contradicts them; nobody catches it until much later.

The Microsoft Developer blog comment on Spec Kit captured the failure
mode: a user reported "the AI states it has implemented everything
but most of the functionality is missing and there are zero tests."
That kind of confident-but-wrong output is exactly what a
constitution prevents — when the project's MUST is "test-first for
any feature touching auth", an LLM agent's attempt to ship zero-test
code triggers the gate, not a post-hoc human review.

## Building a constitution if one doesn't exist

Phase 1 of iteratotron includes a `/constitution-create` invocation when
none is present (or, if the skill isn't installed, composes one from
the project's existing CLAUDE.md + README + any extant ADRs). The
generation prompt:

```
Read CLAUDE.md, README.md, and every file in adrs/ and threat-models/.
Identify the project's standing principles — things the team has
already decided are non-negotiable.

Output as .specify/memory/constitution.md with the Article I / Article
II / Article IX structure. Each MUST entry must be specific enough that
a Constitution Check can detect violation (not "be good at testing"
— concrete rules like "PRs without a failing test that the change
makes pass are blocked").
```

The generated constitution is then shown to the human via
`AskUserQuestion` for amendment before iteratotron proceeds. This is one
of the few interactive gates in Phase 0 — the constitution is the
contract for the whole iteratotron run (in genesis mode).

## Constitution + Tier-3 triggers

Some MUST principles imply Tier-3 escalation triggers. Example:

- "All cryptographic primitives must pass Wycheproof vectors" → adds
  Wycheproof to Tier-3 for any scope touching crypto, even if the
  spec didn't explicitly request it.
- "Distributed-state correctness must be verified deterministically"
  → adds madsim to Tier-3 for any scope touching distributed state.

These are recorded in `harness_vector#tier3_from_constitution` and
applied alongside `harness_vector#tier3_from_spec` at scope dispatch.

## Caveats

- **The Check is a soft gate when no constitution exists.** Genesis
  builds one in Phase 0 if missing — but a generated constitution is
  weaker than a hand-crafted one (it captures observed patterns, not
  the team's deeper intent). Encourage the human to amend the
  generated draft before the inner loop starts.
- **Haiku occasionally misses subtle violations.** When a Complexity
  Justification ADR is present but the ADR itself doesn't actually
  argue against the alternatives, Haiku tends to accept the
  justification anyway. The adversarial reviewer (Phase 7) catches
  these on the way back; the Check is the first line, not the only line.
- **Article IX deviations should be time-bounded.** Without a date or
  condition for re-evaluation, "temporary" deviations become permanent.
  The Check verifies the ADR includes a re-evaluation trigger; reject
  if missing.
