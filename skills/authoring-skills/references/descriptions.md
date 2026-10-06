# Writing the `description` (the discovery trigger)

When a session starts, the agent builds a listing of every skill's
`description` and scans it to decide *"is there a skill for this request?"* So
the `description` is **not a summary — it is a description of when to trigger
the skill.** Write it for the model, not for humans. This is the single
highest-leverage field in a skill: a great body behind a summary-style
description never fires.

## Contents

- Hard constraints
- The four properties of a good description
- Worked before / after
- The litmus / trigger test

## Hard constraints

- Say both **what** the skill does and **when** to use it.
- Non-empty, **at most 1,024 characters**, no XML angle brackets (`<`, `>`) —
  the text is injected into the system prompt, so markup could inject
  instructions.
- **Third person.** "Processes Excel files…", not "I can help you…" or "You can
  use this to…" — mixed point of view hurts discovery.
- Include the concrete terms users say: task verbs, file types/extensions, tool
  names, jargon. Vague ("Helps with documents"), trigger-less ("Creates
  sophisticated documentation systems"), and implementation-only ("Implements
  the Project entity model") descriptions all fail.
- Quote values containing colons (repo rule; invalid YAML otherwise).

## The four properties of a good description

### 1. Lead with the trigger surface
Pack in the literal verbs, nouns, and phrases a user would actually type.

- **`gitlab-babysit-mr`** embeds the trigger word *babysit*:
  > "Monitor a GitLab MR's pipeline until green. Classifies failures (flaky,
  > master-broken, lint, coverage, real), retries jobs…"
  The colloquial word *babysit* in the skill name + the concrete verbs
  (*monitor, classify, retry*) cover how people phrase the request.

### 2. Enumerate situations, not mechanics
List the kinds of request it covers — breadth here is deliberate so many
phrasings match.

- **`playwright-cli`** lists the tasks it covers rather than how it works:
  > "Use when the user needs to navigate websites, interact with web pages, fill
  > forms, take screenshots, test web applications, or extract information from
  > web pages."
  A user who types "fill out this form on example.com" matches even though they
  never said "browser automation".

### 3. State the boundary when a sibling could also match
If two skills could plausibly fire on the same prompt, add a "use when… / do
not use for…" clause so the agent disambiguates.

- **`customize-opencode`** is explicit:
  > "Use ONLY when the user is editing or creating opencode's own configuration…
  > Do not use for the user's own application code, or for any project that is
  > not configuring opencode itself."
  Without that boundary it would over-trigger on every "edit a config file".

### 4. Third-person present, no fluff
Well-written skills open with a present-tense verb phrase ("Monitor a GitLab
MR's pipeline…", "Query the GitLab Knowledge Graph…", "Author a new skill…").
No "This skill will help you…" preamble — it wastes the listing budget.

## Worked before / after

### Example A — summary → trigger (under-triggering fix)

❌ **Before (summary):**
> `description: A tool for working with GitLab merge request pipelines.`

Problems: no trigger words a user types, no situations, reads like docs. A
prompt "can you babysit my MR until CI is green?" may not match "tool for
working with pipelines".

✅ **After (trigger-shaped, modelled on the real `gitlab-babysit-mr`):**
> `description: Monitor a GitLab MR's pipeline until green. Classifies failures
> (flaky, master-broken, lint, coverage, real), retries jobs where appropriate,
> makes light-touch auto-fixes, and posts findings as an MR comment.`

Now the verbs (*monitor, classify, retry, fix, post*) and the failure
vocabulary match how the request is actually phrased.

### Example B — too broad → bounded (over-triggering fix)

❌ **Before (over-broad):**
> `description: Helps you edit configuration files and set up tools.`

This fires on *any* config edit — including the user's own app config, which it
shouldn't touch.

✅ **After (bounded, modelled on `customize-opencode`):**
> `description: Use ONLY when the user is editing or creating opencode's own
> configuration: opencode.json, files under .opencode/ or ~/.config/opencode/.
> Also use for opencode agents, skills, plugins, MCP servers, permission rules.
> Do not use for the user's own application code.`

The explicit allow-list + "Do not use for…" clause stops the false positives.

### Example C — mechanics → situations (breadth fix)

❌ **Before (mechanics):**
> `description: Drives a headless browser via a CLI wrapper.`

A user asking "fill out this signup form and screenshot the result" won't match
"drives a headless browser via a CLI wrapper."

✅ **After (situation enumeration, modelled on the real `playwright-cli`):**
> `description: …Use when the user needs to navigate websites, interact with web
> pages, fill forms, take screenshots, test web applications, or extract
> information from web pages.`

## The litmus / trigger test (do this before shipping)

1. Write **3–5 prompts that SHOULD fire the skill** and **2–3 that should NOT.**
2. Read **only the `description`** (not the body) and predict, for each prompt,
   whether it fires.
3. If your predictions don't match your intent, the description is wrong — fix
   it before touching the body.
   - Misses on should-fire prompts → add the missing literal trigger phrases.
   - Hits on should-not prompts → add/tighten a boundary clause.
4. Include *paraphrased* should-fire prompts, not just ones that echo the
   description. Cheap probe in a live session: ask the agent "when would you
   use the `<name>` skill?" and compare its answer with your intent.
5. Re-run until predictions are correct. (This mirrors the post's finding that
   verification rigour pays off most — apply it to the description itself.)

> Rule of thumb: if you can't predict which prompts fire it by reading only the
> description, neither can the agent.
