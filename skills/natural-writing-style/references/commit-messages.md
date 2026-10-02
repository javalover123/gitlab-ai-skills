# Commit Message Guidelines

A commit message is the smallest piece of documentation you'll write, and paradoxically one of the most important. Six months from now, when someone's bisecting a regression and lands on your commit, the message is the only context they've got. Make it count.

## The subject line

Keep it under 72 characters. Use imperative mood -- write it as a command, like you're telling the codebase what to do. "Add retry logic for flaky API calls" not "Added retry logic" or "This commit adds retry logic."

No period at the end. It's a title, not a sentence.

Capitalize the first word but don't use Title Case for the whole thing. "Fix null pointer in session cleanup" reads better than "Fix Null Pointer in Session Cleanup."

If you need the word "and" in your subject line, you're probably describing two separate changes. Split them into two commits.

## The body

Not every commit needs a body. A one-line `Fix typo in README` is perfectly fine on its own. But when you're making a non-obvious change, the body is where you explain **why**.

The diff already shows what changed. Don't repeat it in prose. Instead, answer:
- What problem does this solve?
- Why this approach instead of the alternatives you considered?
- Are there side effects or things reviewers should watch for?
- How can the reader verify the fix, if that isn't obvious from the diff?

Wrap body text at 72 characters. Separate it from the subject with a blank line.

Reference issue or ticket numbers when they exist. Put them in the body or as a trailer, not crammed into the subject: `Fixes #1234` or `Relates-to: PROJ-567`.

## What to avoid

Don't use banned words -- the same ones that make docs sound like AI output make commit messages sound like AI output. "Refactor authentication module" is fine; "Refactor authentication to provide a more streamlined and holistic approach" isn't. <!-- voice-ok -->

Don't use emojis unless your project follows a conventional-commits emoji scheme. If the project does, match whatever convention is already established.

Don't write commit messages that describe the files touched. `Update main.c, util.h, and Makefile` tells the reader nothing they can't get from `git show --stat`.

Don't use vague verbs. "Update code" and "Fix stuff" and "Changes" are useless. Be specific about what you did and to what.

## GOOD examples

```
Add connection pooling for PostgreSQL backend

The existing per-request connection model caused latency spikes under
load because each request paid the full TCP + TLS handshake cost.
Connection pooling amortizes that across requests.

Pool size defaults to 10, configurable via DATABASE_POOL_SIZE.

Fixes #892
```

```
Fix off-by-one in ring buffer wraparound

The write index wasn't being masked after increment, so writes at
exactly the buffer boundary would overwrite index 0 instead of
wrapping to it cleanly. Found by fuzzing with afl++.
```

```
Drop Python 3.8 support from CI matrix

Python 3.8 reached end-of-life in October 2024. Two of our
dependencies already dropped it, and maintaining the compatibility
shims wasn't worth the effort for zero known users on that version.
```

```
Rate-limit login attempts to 6 per minute

Brute-force attempts were hitting the auth endpoint at ~200 req/s
from rotating IPs. Per-account rate limiting with a token bucket
handles this without affecting normal users. The limit resets after
60 seconds of inactivity.

Relates-to: SEC-2341
```

## BAD examples

```
fix bug
```
Which bug? Where? This tells the reader absolutely nothing. Even `Fix null deref in parser` is miles better.

```
Updated the authentication module to streamline the login flow and <!-- voice-ok -->
enhance the overall user experience by refactoring the session <!-- voice-ok -->
management layer to be more robust <!-- voice-ok -->
```
Too long for a subject line, uses banned words ("streamline," "enhance," "robust"), describes implementation instead of intent, and tries to cram everything into one line. <!-- voice-ok -->

```
WIP
```
Don't commit work-in-progress to shared branches. If you need WIP commits locally, squash them before pushing. A commit message should describe a complete, logical change.

```
Refactor code and fix tests and update docs
```
Three changes in one commit. Split them. Each commit should have one clear purpose -- that's what makes `git bisect` and `git revert` actually useful.

## One logical change per commit

This is the rule that makes everything else work. A commit should represent a single coherent change. Not "everything I did today." Not "a bunch of related-ish fixes."

Think of it this way: if you had to revert this commit, would the revert make sense on its own? Would it undo exactly one thing? If reverting your commit would partially undo two different features, it should've been two commits.

Rebasing and squashing are your friends here. It's totally fine to make messy commits while you're working and clean them up before you push. The commit history is for the people who come after you, not a diary of your working process.
