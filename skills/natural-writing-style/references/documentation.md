# Technical Documentation Style Guidelines

Good docs don't just describe software -- they make people successful with it. The difference between documentation that gets read and documentation that gets skipped comes down to voice, structure, and respect for the reader's time.

## Voice and tone

Address the reader as "you." Always. Not "the user," not "users should," not "one might consider." You're talking to a person. Talk to them directly.

Show genuine enthusiasm for what you're documenting. If you've built something that solves a real problem, it's okay to say so. "This handles concurrent writes without locking, which means you won't hit the bottleneck that plagues most queue implementations" is better than "This module provides write functionality."

Be technically precise. Commands, paths, flags, version numbers, error codes -- these must be exact. If you tell someone to run `curl -sL https://example.com/install.sh | bash` and the flag is actually `-sSL`, you've wasted their time and eroded their trust. Precision is a form of care.

Mix sentence lengths deliberately. Short sentences punch. Longer ones give you room to connect ideas and provide context that would feel cramped in a terse statement. Read your draft aloud -- if it sounds like a metronome, rewrite it. If it sounds like you're reading a legal contract, definitely rewrite it.

Use contractions. They're not informal; they're normal. "You'll need to configure the database connection before running migrations" reads like a human wrote it. "You will need to configure the database connection before running migrations" reads like a manual from 1997.

## The Diataxis framework

Don't mix document types. This is probably the single most common documentation mistake, and it's the one that causes the most confusion. There are four distinct kinds of documentation, and each one has its own job.

**Tutorials** are learning-oriented. You're walking someone through a complete experience, start to finish. They're safe to experiment with -- nothing should break if the reader follows along. The reader doesn't know what they don't know yet, so you hold their hand. "Let's build a small API together" is a tutorial.

**How-to guides** are problem-oriented. The reader has a specific thing they want to accomplish and they already know the basics. "How to deploy to production" or "How to add a custom authentication provider" -- these assume context and skip the hand-holding. Get to the solution.

**Reference docs** are information-oriented. Complete, accurate, structured by the code's own organization (not by user tasks). API references, configuration option lists, CLI flag documentation. Don't editorialize here -- just be thorough and precise.

**Explanation docs** are understanding-oriented. Why was this designed this way? What tradeoffs were made? How does this concept relate to that one? These are the docs people read when they want to really get it, not just use it.

When a tutorial starts explaining architecture decisions mid-walkthrough, the reader gets lost. When a reference doc tries to be a how-to guide, it buries the facts in narrative. Keep them separate.

## Structure and formatting

Not every section needs a list. Prose is often better for conveying ideas that have nuance, context, or caveats. Lists work well for genuinely parallel items (CLI flags, configuration options, steps in a sequence). They work badly for things that need explanation.

Start documents with something specific and interesting, not with broad context-setting. "In the world of containerized applications..." is a stalling tactic. "This tool watches your source files and rebuilds the container on every save -- no more manual docker-build cycles" tells the reader exactly what they're getting.

Headers should be statements or noun phrases, not questions (unless you're writing an FAQ). "Authentication" or "How authentication works" beats "What is authentication?" which reads like a chatbot.

Avoid the AI-tell structural patterns: don't open every paragraph the same way, don't end sections with summary restatements, don't use exactly 3 or 5 items in lists.

## GOOD and BAD examples

### README introductions

**GOOD:**
```markdown
# snapblast

Take consistent, reproducible snapshots of your PostgreSQL database
in under two seconds. Built for dev teams who are tired of waiting
for pg_dump on large schemas.

snapblast works by using PostgreSQL's file-system-level snapshot
capabilities instead of logical dumps. You get a complete, mountable
copy of your database that's ready to query immediately.

## Getting started

You'll need PostgreSQL 14+ and ZFS (or Btrfs) on your data volume.

    pip install snapblast
    snapblast init --pgdata /var/lib/postgresql/14/main
    snapblast snap my-first-snapshot

That's it. `snapblast ls` shows your snapshots, and
`snapblast mount my-first-snapshot` gives you a read-only copy
you can point any PG client at.
```

Why this works: it tells you what the tool does, why you'd care, and how to start using it in about 15 seconds of reading. The enthusiasm is specific ("under two seconds," "ready to query immediately"), not generic.

**BAD:**
```markdown
# snapblast

## Overview

snapblast is a comprehensive database snapshot solution designed to <!-- voice-ok -->
streamline the process of creating and managing PostgreSQL database <!-- voice-ok -->
snapshots. It provides robust functionality for development teams <!-- voice-ok -->
seeking to optimize their database workflow. <!-- voice-ok -->

## Features

- Comprehensive snapshot management <!-- voice-ok -->
- Seamless integration with PostgreSQL <!-- voice-ok -->
- Robust error handling <!-- voice-ok -->
- Cutting-edge snapshot technology <!-- voice-ok -->
- Innovative approach to database backups <!-- voice-ok -->
```

Why this fails: it's a wall of banned words ("comprehensive," "streamline," "robust," "seamless," "cutting-edge," "innovative") that says nothing specific. The feature list has exactly 5 items (an AI tell) and none of them tell you what the tool actually does differently from pg_dump. <!-- voice-ok -->

### API documentation

**GOOD:**
```markdown
## `client.upload(file, opts)`

Uploads a file to the configured storage backend. Returns a `FileRef`
on success.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `file` | `str` or `Path` | yes | Local path to the file |
| `opts.acl` | `str` | no | Access control. Defaults to `"private"` |
| `opts.content_type` | `str` | no | MIME type. Auto-detected from extension if omitted |
| `opts.max_retries` | `int` | no | Retry count on transient failures. Defaults to `4` |

**Returns:** `FileRef` with `.url`, `.size_bytes`, `.etag`, `.uploaded_at`

**Raises:**

- `StorageError` -- connection failed or bucket doesn't exist
- `QuotaExceededError` -- account storage limit reached
- `FileNotFoundError` -- local file path doesn't resolve

**Example:**

```python
ref = client.upload("./report.pdf", opts={"acl": "public-read"})
print(f"Uploaded to {ref.url} ({ref.size_bytes} bytes)")
```

If the upload gets interrupted, the client retries automatically
up to `max_retries` times with exponential backoff starting at
500ms. Partially uploaded files are cleaned up server-side.
```

Why this works: every parameter has a type and a default. The error cases are specific. The example is short and realistic. The note about retry behavior answers the question you'd actually have after reading the API surface.

**BAD:**
```markdown
## Upload Method

The upload method facilitates the uploading of files to the storage <!-- voice-ok -->
backend. It provides comprehensive file management capabilities and <!-- voice-ok -->
robust error handling to ensure seamless file transfers. <!-- voice-ok -->

### Usage

To utilize the upload functionality, simply call the upload method <!-- voice-ok -->
with the appropriate parameters. The method will handle the rest.

### Parameters

The method accepts various parameters to customize the upload
behavior. Refer to the source code for detailed parameter
descriptions.
```

Why this fails: it uses banned words ("facilitates," "comprehensive," "robust," "seamless," "utilize"), doesn't actually document the parameters, and "refer to the source code" is a documentation failure -- the whole point of docs is that you don't have to read the source. <!-- voice-ok -->

## The precision test

Before you publish any technical doc, check these:
- Can someone copy-paste every command and have it work?
- Are version numbers, paths, and flag names current?
- Did you test the "Getting started" section on a clean machine (or at least mentally walk through it)?
- If a step can fail, did you say what the error looks like and how to fix it?

Docs that are warm but wrong are worse than docs that are dry but correct. Get the facts right first. Then make them pleasant to read.
