# Writing the `description` (the discovery trigger)

When a session starts, the agent builds a listing of every skill's
`description` and scans it to decide *"is there a skill for this request?"* So
the `description` is **not a summary — it is a description of when to trigger
the skill.** Write it for the model, not for humans. This is the single
highest-leverage field in a skill: a great body behind a summary-style
description never fires.

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

- **`orbit`** lists answerable question shapes rather than describing the DSL:
  > "Use for code-structure questions (who calls this function, where is this
  > symbol defined), cross-project dependency and blast-radius analysis,
  > merge-request and contributor queries…"
  A user who types "who calls `foo`?" matches even though they never said
  "knowledge graph".

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
> `description: Runs graph queries against ClickHouse via a CLI.`

A user asking "what's the blast radius if I change this function?" won't match
"runs graph queries against ClickHouse."

✅ **After (situation enumeration, modelled on the real `orbit`):**
> `description: …Use for code-structure questions (who calls this function,
> where is this symbol defined), cross-project dependency and blast-radius
> analysis, merge-request and contributor queries, and any question answerable
> by traversing GitLab's unified entity graph.`

## The litmus / trigger test (do this before shipping)

1. Write **3–5 prompts that SHOULD fire the skill** and **2–3 that should NOT.**
2. Read **only the `description`** (not the body) and predict, for each prompt,
   whether it fires.
3. If your predictions don't match your intent, the description is wrong — fix
   it before touching the body.
   - Misses on should-fire prompts → add the missing literal trigger phrases.
   - Hits on should-not prompts → add/tighten a boundary clause.
4. Re-run until predictions are correct. (This mirrors the post's finding that
   verification rigour pays off most — apply it to the description itself.)

> Rule of thumb: if you can't predict which prompts fire it by reading only the
> description, neither can the agent.
