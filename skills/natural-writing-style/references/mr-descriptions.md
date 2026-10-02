# Merge request description guidelines

A good MR description saves your reviewer's time. That's the whole point -- not decoration, not ceremony, not filling in a template because someone said you should. You're writing for a person who needs to understand what changed and why, quickly enough to give you a useful review.

## Lead with what changed and why

Your opening sentence or two should answer: what did you do, and why did you do it? Don't make the reviewer scroll past a wall of context to figure out what they're looking at.

The summary isn't a commit log. It's a plain-language explanation of the change, written for someone who wasn't in your head when you wrote it. If you changed four files across two subsystems, describe the effect: "Replaced the polling-based health check with a streaming gRPC watcher so we detect node failures in seconds instead of minutes."

## Structure

A typical description has a few sections. You don't need all of them every time -- use what's relevant.

**Changes.** Describe what was done in plain language. Group related changes together. Focus on the effect of the changes, not a file-by-file diff summary. If the diff is small and obvious, a sentence or two is plenty. If it touches multiple areas, break it into logical groups.

**Why / Context.** Briefly explain the motivation. Link to the issue if there is one, but don't just repeat the issue title. Add what's relevant for the reviewer: the constraint that shaped your approach, the tradeoff you made, the alternative you considered and rejected.

**Testing notes.** If the reviewer should know how to verify the change, say so. "Run `make test-integration` with a local Postgres instance" is more helpful than "tested locally." If there are edge cases you specifically tested or couldn't test, mention them.

**Deployment considerations.** Only include this when there's something non-obvious. A migration that needs to run first, a feature flag that gates the change, a dependency that needs updating in production. If the deploy is straightforward, skip this section.

## Tone and formatting

No emojis. No exclamation points. No decorative warmth like "Thanks for reviewing!" at the end. Save your reviewer's time by being clear, not by being cheerful.

Sentence case for section headings. "Testing notes" not "Testing Notes."

Don't repeat "this MR" over and over. Instead of "This MR adds a new endpoint that..." just write "Adds a new endpoint that..." or "The new endpoint handles..." You can reference the change directly without constantly pointing at the container it lives in.

Don't copy the issue title or description verbatim. The reviewer can click the link. Summarise what matters for the review and add anything that isn't in the issue -- your implementation approach, tradeoffs, scope decisions.

Keep it scannable. Short paragraphs, clear section breaks, and enough whitespace that someone glancing at the description can orient themselves in a few seconds. Bullet points work well for listing discrete changes, but don't default to a bulleted list when a sentence would do.

## What to avoid

- Commit logs pasted as the description. Commit messages are written for version history; MR descriptions are written for reviewers. Different audiences, different needs.
- Vague hand-waving. "Refactored some things" or "cleaned up the code" tells the reviewer nothing. Say what you refactored and what drove the cleanup.
- Over-explaining obvious changes. If you renamed a variable, you don't need a paragraph justifying it. Let the diff speak.
- Banned words and phrases. Check your text against the blocklist in [banned-patterns.md](banned-patterns.md). Corporate-sounding adjectives and filler phrases don't belong in MR descriptions.
- Opening with "This MR..." on every line. Vary your sentence structure. Describe what was done, not what "this MR" does.
- Walls of text with no structure. Even a two-paragraph description reads better with a blank line between the what and the why.

## GOOD example

```markdown
## Changes

Replaced the polling-based health check in the node monitor with a
streaming gRPC watcher. The monitor now receives failure notifications
within 2 seconds instead of waiting for the next 30-second poll cycle.

Removed the `poll_interval` config option since it's no longer relevant.
Added `grpc_watch_timeout` to control how long the watcher waits before
reconnecting after a stream drop.

Updated the integration tests to use a mock gRPC server instead of
sleeping through poll intervals, which cut the test suite time from
~45 seconds to ~8 seconds.

## Why

The 30-second polling window was causing cascading timeouts in the
orchestrator during node failures (see #1842). We'd already tried
reducing the interval to 5 seconds, but that put too much load on the
control plane. Streaming sidesteps the tradeoff entirely.

## Testing notes

`make test-integration` covers the new watcher behaviour. You'll need
a local gRPC endpoint running -- `make dev-deps` sets one up. The mock
server in `testutil/grpc.go` simulates stream drops if you want to
poke at reconnection manually.

## Deployment

The `grpc_watch_timeout` config defaults to 10 seconds, which matches
our production latency profile. No migration needed. The old
`poll_interval` key is ignored if present in existing configs.
```

## BAD example

```markdown
## Overview

This MR leverages the power of gRPC streaming to provide a more robust <!-- voice-ok -->
and comprehensive health monitoring solution. This MR replaces the <!-- voice-ok -->
existing polling mechanism with a cutting-edge streaming approach. <!-- voice-ok -->

## What This MR Does

- This MR removes polling
- This MR adds gRPC streaming
- This MR updates tests

## Why This MR Is Needed

It is important to note that the current polling approach has
limitations. This MR addresses these limitations by implementing a
streamlined solution that facilitates faster failure detection.

In conclusion, this MR improves the health check system significantly. <!-- voice-ok -->

## Testing

Tested locally. All tests pass.
```

What's wrong here? The description is packed with blocklisted words (six of them in two sentences). It repeats "this MR" six times. The bullet list has exactly three items. The "Why" section uses filler phrases and ends with an announced conclusion. The testing section tells the reviewer nothing useful.

## Quick checklist

Before you submit, scan your description for these:

- Does the opening sentence explain what changed and why?
- Could a reviewer unfamiliar with the code understand the approach from the description alone?
- Did you link the issue but avoid parroting its text?
- Are there any banned words or phrases?
- Did you skip unnecessary "this MR" repetition?
- Is every section earning its place, or can something be cut?
