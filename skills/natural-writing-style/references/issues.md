# Issue description guidelines

A well-written issue saves everyone time -- the person triaging it, the person picking it up, and future-you who comes back six months later wondering what this was about. The goal isn't ceremony. It's giving the reader enough context to act without a follow-up conversation.

## Lead with the problem or goal

Your first sentence should answer: what's broken, or what do you want to exist? Don't open with background. Don't open with "I was working on X when I noticed Y." Start with the thing that matters.

For bugs: state what's happening that shouldn't be, or what isn't happening that should be. "The retry logic in `WorkerPool.dispatch` silently drops jobs after the third failure instead of moving them to the dead letter queue."

For features: state the user need. "Users can't filter audit logs by date range, so finding a specific event means scrolling through the full list."

One clear sentence up front tells the reader whether this issue is relevant to them before they invest time reading the rest.

## Context

After the lead sentence, add enough context for someone unfamiliar with the area to understand why this matters. You don't need a history lesson -- just the pieces that explain the impact or urgency. A sentence or two usually does it.

"This affects any worker pool running more than 10 concurrent jobs, which is every production instance. The dropped jobs don't show up in any log, so failures are invisible until a customer reports missing data."

If you're filing a feature request and you know the broader context -- a product goal, a user research finding, a support ticket pattern -- mention it briefly. Don't write an essay; link to the source if it exists.

## Bug reports

For bugs, include these sections. Skip any that genuinely don't apply, but don't skip them out of laziness.

**Observed behaviour.** What actually happens. Be specific. Include error messages, unexpected output, or the absence of expected output. Copy-paste the actual error text; don't paraphrase it.

**Expected behaviour.** What should happen instead. This sounds obvious, but it often isn't -- especially when the "correct" behaviour depends on a spec or business rule that not everyone has memorised.

**Steps to reproduce.** Numbered steps that someone else can follow to see the bug. Include the environment details that matter (OS, version, config) and leave out the ones that don't. If you can't reproduce it reliably, say so and describe the conditions where you've seen it.

**Additional context.** Logs, screenshots, stack traces, links to related issues. Anything that helps the person investigating.

## Feature requests

For features, cover these:

**The user need.** What problem does this solve, and for whom? "As an admin, I need to..." is fine but not required. What matters is that the need is concrete, not abstract. "Better logging" is abstract. "Structured JSON log output so we can pipe it to our monitoring stack" is concrete.

**Proposed approach.** If you have an idea of how to solve it, describe it. If you don't, that's fine too -- just leave this section out rather than filling it with vague suggestions. If you know the solution, say so directly. If you're uncertain, frame it as one option: "One approach would be to add a `--format` flag to the CLI, but there might be a better way to handle this at the library level."

**Acceptance criteria.** Write these as testable statements. Each one should be something you could check off as done or not done with no ambiguity.

Don't write acceptance criteria like "the feature works well" or "the UI is intuitive." Write them like "the `/audit` endpoint accepts `start_date` and `end_date` query parameters in ISO 8601 format" and "requests with an `end_date` before `start_date` return a 400 with a descriptive error message."

## Tone

No emojis. No exclamation points. Be helpful through clarity and completeness, not through performed enthusiasm.

Don't over-hedge. "I think maybe this could possibly be a bug" wastes everyone's time. If you've verified the behaviour, state it as fact. If you haven't, say what you observed and note that you haven't fully verified it. There's a difference between honest uncertainty and reflexive hedging.

Don't under-commit either. If you know the root cause, say so. "The null pointer dereference happens because `get_config()` returns NULL when the file doesn't exist, and the caller doesn't check" is more useful than "something seems wrong with config loading."

Avoid all banned words and phrases -- the ones from the blocklist in [banned-patterns.md](banned-patterns.md). If you catch yourself reaching for corporate-sounding adjectives or filler phrases, swap them for plain language.

## GOOD bug report example

```markdown
**Title:** Worker pool silently drops jobs after third retry failure

The retry logic in `WorkerPool.dispatch` drops jobs after three
consecutive failures. The dropped jobs don't reach the dead letter
queue and don't produce any log output, so the failures are invisible
until a customer reports missing data. This affects all production
instances running more than 10 concurrent workers.

**Observed behaviour**

When a job fails three times, `dispatch()` calls `retire_job()` which
removes it from the active queue. The dead letter insertion that should
follow on line 247 of `worker_pool.go` never executes because the
error check on line 245 compares against `ErrMaxRetries` using `==`
instead of `errors.Is()`, and the wrapped error doesn't match.

**Expected behaviour**

Jobs that exhaust their retry budget should land in the dead letter
queue with the full error chain attached. The `worker.failures` metric
should increment. A warning-level log entry should record the job ID
and final error.

**Steps to reproduce**

1. Configure a worker pool with `max_retries: 3`
2. Enqueue a job that always returns a wrapped error (e.g.,
   `fmt.Errorf("boom: %w", ErrTimeout)`)
3. Wait for the job to fail three times
4. Check the dead letter queue (empty) and the logs (no mention of
   the dropped job)

Reproduced on v2.4.1 and v2.5.0-rc1 running on Linux (Go 1.22).

**Additional context**

The fix is likely a one-line change on line 245: replace `==` with
`errors.Is()`. I haven't confirmed whether there are other callers
of `retire_job` with the same pattern.

Related: #1842, #1790 (both reported missing data symptoms but
didn't identify this as the cause)
```

## GOOD feature request example

```markdown
**Title:** Add date range filtering to audit log endpoint

Users can't filter audit logs by date range. Finding a specific event
means paginating through the entire log, which is unusable for
organisations with more than a few hundred entries. Three support
tickets in the last month have asked for this.

**Proposed approach**

Add `start_date` and `end_date` query parameters to the `/audit`
endpoint. Both should accept ISO 8601 timestamps. The existing
database index on `created_at` should make the filtered query
fast without any schema changes.

The frontend already has a date picker component in the shared UI
library, so wiring it into the audit log view should be
straightforward.

**Acceptance criteria**

- GET `/audit?start_date=2026-01-01T00:00:00Z&end_date=2026-01-31T23:59:59Z` returns only events within that range
- Omitting `start_date` returns events from the beginning of time up to `end_date`
- Omitting `end_date` returns events from `start_date` to now
- Providing both with `end_date` before `start_date` returns a 400 response with a message explaining the constraint
- The audit log UI includes date picker inputs that populate these parameters
- Pagination continues to work correctly with date filters applied
```

## What to avoid

- Vague titles. "Bug in worker" tells the triager nothing. "Worker pool silently drops jobs after third retry failure" tells them exactly what's happening.
- Missing reproduction steps. "It's broken" isn't a bug report. If you can't reproduce it, say so and describe the conditions where you've seen it.
- Acceptance criteria that can't be tested. "The feature should be easy to use" isn't testable. "The endpoint returns results in under 200ms for date ranges spanning up to one year" is.
- Walls of text with no structure. Use headings. Use blank lines. Make it scannable.
- Decorative warmth. "Thanks so much for looking at this!!" doesn't help anyone triage or fix the issue. Be helpful by being clear.
- Rehashing known information. If there's a linked issue or design doc, reference it. Don't paste its contents into the new issue.

## Quick checklist

Before you submit, scan your issue for these:

- Does the first sentence state the problem or goal clearly?
- Would someone unfamiliar with the codebase understand why this matters?
- For bugs: did you include observed behaviour, expected behaviour, and reproduction steps?
- For features: are the acceptance criteria specific and testable?
- Are there any banned words or phrases?
- Is the description structured with headings and whitespace so it's easy to scan?
