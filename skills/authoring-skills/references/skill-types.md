# Skill type taxonomy — a "which bucket?" checklist

Anthropic catalogued their internal skills and found they cluster into **nine
categories**. The framework's value for authoring: *the best skills fit cleanly
into one; the ones that try to do too much straddle several and confuse the
agent.* Use this list to (a) sanity-check that your idea is one job, and (b)
spot gaps in the skill library.

Where possible, each category points at a real skill **in this repository** (in
backticks, e.g. `glab`) so you can open it and copy the shape. Names from
Anthropic's post that don't exist here are clearly labelled "Post example" — treat
those as illustrations, not files to open.

## The nine categories

### 1. Library & API reference
Explains how to correctly use a library, CLI, or SDK — often a folder of
reference snippets plus a list of gotchas.
- In this repo: **`glab`** (every common `glab` sub-command + the backtick-
  escaping footgun), **`glab-glql`** (the GLQL query language + examples).

### 2. Product verification
Describes how to test/verify that code works, usually paired with a browser,
tmux, or other external driver. *Anthropic: verification skills had the most
measurable impact on output quality — worth an engineer-week to make excellent.*
- In this repo: **`playwright-cli`** (drive a headless browser, assert state),
  **`run-in-tmux-pane`** (interactive CLI/TTY testing).

### 3. Data fetching & analysis
Connects to data/monitoring stacks: credentials, dashboard IDs, canonical table
maps, common query workflows.
- In this repo: **`gitlab-clickhouse`** and **`gitlab-psql`** (connect to the
  data stores, canonical schemas, query patterns). Post examples: `funnel-query`,
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
- In this repo: **`mr-review`** and **`mr-adversarial-review`** (review a diff
  against a rubric; spawn a fresh-eyes critique). Post examples:
  `adversarial-review`, `code-style`.

### 7. CI/CD & deployment
Fetches, pushes, and deploys code; may reference data-fetching skills.
- In this repo: **`gitlab-babysit-mr`** (monitor pipeline → retry flaky → light
  fixes → report), **`gitlab-pipeline-watch`**, **`pushify`** (drive pre-push
  hooks to green).

### 8. Runbooks
Take a symptom (alert, error signature, Slack thread), walk a multi-tool
investigation, produce a structured report.
- Post examples: `<service>-debugging`, `oncall-runner`, `log-correlator`.
  (A pipeline-babysitting skill's failure-diagnosis phase, e.g.
  `gitlab-babysit-mr`, is a close cousin.)

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
