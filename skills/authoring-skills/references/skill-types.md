# Skill type taxonomy — a "which bucket?" checklist

Anthropic catalogued their internal skills and found they cluster into **nine
categories**. The framework's value for authoring: *the best skills fit cleanly
into one; the ones that try to do too much straddle several and confuse the
agent.* Use this list to (a) sanity-check that your idea is one job, and (b)
spot gaps in the skill library.

Each category gives an example shape. "Post example" names come from Anthropic's
*Lessons from building Claude Code: how we use skills*; skills named as
`gitlab-org/ai/skills` skills exist in that repository only — treat all as illustrations, not files you can assume are installed.

## The nine categories

### 1. Library & API reference
Explains how to correctly use a library, CLI, or SDK — often a folder of
reference snippets plus a list of gotchas.
- Shape: a CLI-reference skill (every common sub-command plus gotchas), e.g. the
  `glab` skill in `gitlab-org/ai/skills`; or a query-language skill with examples.

### 2. Product verification
Describes how to test/verify that code works, usually paired with a browser,
tmux, or other external driver. *Anthropic: verification skills had the most
measurable impact on output quality — worth an engineer-week to make excellent.*
- Shape: drive a headless browser and assert state, or test an interactive CLI
  in a TTY (e.g. `playwright-cli`, `run-in-tmux-pane` in `gitlab-org/ai/skills`).

### 3. Data fetching & analysis
Connects to data/monitoring stacks: credentials, dashboard IDs, canonical table
maps, common query workflows.
- Shape: connect to a data store with canonical schemas and query patterns (e.g.
  `gitlab-clickhouse`, `gitlab-psql` in `gitlab-org/ai/skills`). Post examples: `funnel-query`,
  `grafana`.

### 4. Business process & team automation
Collapses a repetitive workflow into one command; simple instructions but may
depend on other skills/MCPs. Logging past runs helps consistency.
- Shape: a task/issue-tracker automation skill (e.g. create a ticket → enforce
  schema → notify reviewer), an inbox-triage skill, a standup generator. Post
  examples: `standup-post`, `weekly-recap`.

### 5. Code scaffolding & templates
Generates framework boilerplate where natural-language requirements can't be
captured purely in code.
- Post examples: `new-<framework>-workflow`, `new-migration`, `create-app`.

### 6. Code quality & review
Enforces org code quality / reviews code; may use deterministic scripts and run
from hooks or CI.
- Shape: review a diff against a rubric, or spawn a fresh-eyes critique (e.g.
  `mr-review`, `mr-adversarial-review` in `gitlab-org/ai/skills`). Post examples:
  `adversarial-review`, `code-style`.

### 7. CI/CD & deployment
Fetches, pushes, and deploys code; may reference data-fetching skills.
- Shape: monitor a pipeline → retry flaky jobs → light fixes → report, or drive
  pre-push hooks to green (e.g. `gitlab-babysit-mr`, `pushify` in
  `gitlab-org/ai/skills`).

### 8. Runbooks
Take a symptom (alert, error signature, Slack thread), walk a multi-tool
investigation, produce a structured report.
- Post examples: `<service>-debugging`, `oncall-runner`, `log-correlator`.
  (A pipeline-babysitting skill's failure-diagnosis phase, e.g.
  `gitlab-babysit-mr` in `gitlab-org/ai/skills`, is a close cousin.)

### 9. Infrastructure operations
Routine maintenance / operational procedures, sometimes destructive — benefit
from guardrails.
- Post examples: `<resource>-orphans`, `dependency-management`,
  `cost-investigation`.

## Decision aid (Step 0)

Before writing anything, answer in order:

1. **Which single category above does this fit?**
   - Fits exactly one → good, proceed.
   - Fits two or more → **split into two skills.** A skill that straddles
     categories confuses the trigger and the body. (e.g. "fetch data *and*
     deploy" → a data skill + a deploy skill that references it.)
   - Fits none → it may not be a skill at all; re-check Step 0.2/0.3 below.
2. **Does it push the model off its defaults?** If it only restates what the
   model already does well, **stop — write nothing** (see SKILL.md Gotcha /
   anti-pattern "stating the obvious").
3. **Will it be reused?** One-off → task note. Reused → skill.

> Tip from the post: *most of our best skills began as a few lines and a single
> gotcha.* Pick the category, write the smallest useful version, and grow it as
> the agent hits new edge cases.
