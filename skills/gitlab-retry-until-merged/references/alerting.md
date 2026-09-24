# Phase 5: Alerting the User

The user is the only audience. It's someone else's MR, so **don't post to it**
unless the user asks. An uninvited bot comment pings the author and reviewers.
If the user does ask, post a plain note (no `/` quick actions, no `@`
mentions of bots) and nothing else.

## How to alert

1. End the loop with a report in chat, in the format below.
2. If your environment offers a desktop or push notification tool, also send a
   one-line notification. The user may have walked away while you watched.

## Report

```markdown
## <MERGED | Needs you | Gave up after <max> retries | Stopped>: !<iid> <title>

**MR**: <web_url> · **Author**: @<author> · **Pipeline**: <pipeline.web_url> (`<kind>`)
**Retries used**: <n> of <max, default 3> · **Waited on incidents**: <total minutes or "no">

### Why I stopped
<one or two sentences: the event, e.g. "`rspec unit 3/12` fails in
`spec/models/foo_spec.rb:42`, a file this MR changes." or "Auto-merge was
canceled at 14:02 UTC." or "Merged at 15:31 UTC.">

### Failures
| Job | Class | Evidence | Action |
|-----|-------|----------|--------|
| [`<name>`](<web_url>) | MR_RELATED | <file/line, error, link to flaky/incident issue> | none: needs the author |

### What you can do
- <concrete options that need a human, for example: ask the author to fix X; re-add
  the MR to the merge train; wait for incident <link>; retry manually if you
  disagree with the classification>
```

Keep each retry's history in the report (what was retried, when, and why) so
the user can check the reasoning. Don't make any change on the user's behalf,
including the ones you list under "What you can do".
