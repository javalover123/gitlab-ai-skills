# GitLab AI Skills

![Pipeline Status](https://gitlab.com/gitlab-org/ai/skills/badges/main/pipeline.svg)

Reusable agent skills for GitLab projects. Skills are structured prompt files that AI coding assistants (like [pi](https://github.com/badlogic/pi-mono), [OpenCode](https://opencode.ai) and [Claude Code](https://code.claude.com)) can load on demand to gain domain-specific knowledge and workflows.

## Table of Contents

<!-- TOC_START -->
  - [Table of Contents](#table-of-contents)
  - [What is a Skill?](#what-is-a-skill)
  - [Skills](#skills)
    - [Development Workflow](#development-workflow)
    - [Database](#database)
    - [Testing](#testing)
    - [Shell & Environment](#shell--environment)
    - [Agent Tooling](#agent-tooling)
    - [Research & Notes](#research--notes)
    - [Documentation](#documentation)
    - [Meta / Authoring](#meta--authoring)
    - [Other](#other)
  - [Installing Skills](#installing-skills)
    - [`.agents/skills/` (Zed, GitLab Duo CLI)](#agentsskills-zed-gitlab-duo-cli)
    - [Pi (Package)](#pi-package)
    - [OpenCode (Native)](#opencode-native)
    - [Via `skills` CLI (npx)](#via-skills-cli-npx)
    - [Claude Code Plugin Marketplace](#claude-code-plugin-marketplace)
  - [Contributing](#contributing)
  - [Related](#related)
<!-- TOC_END -->

## What is a Skill?

This repo follows the [Agent Skills](https://agentskills.io) open format ([spec](https://agentskills.io/specification)).

A skill is a directory containing a `SKILL.md` file with:
- **YAML frontmatter** — `name`, `description`, `license`, `compatibility`, and optional `metadata` fields
- **Markdown content** — step-by-step workflows, code examples, reference tables, checklists, and anything else the agent needs

Skills are loaded explicitly by the agent when relevant to a task (e.g. "load the `glab` skill") rather than being injected into every prompt. This keeps context lean and focused.

## Skills

<!-- SKILLS_START -->
### Development Workflow

#### bug-burndown

Runs a continuous, autonomous bug burndown session — collecting defects from logs, tests, issue queues, and spec drift; deduplicating and triaging them through an 8-phase pipeline; then dispatching bounded parallel bugfix subagents in isolated worktrees until the queue is empty or the time budget runs out. Use when asked to burn down the bugs, clear the backlog, triage CI failures, find regressions, run a fix session, or anything that's batch quality-improvement rather than a single targeted bug fix. → [`SKILL.md`](skills/bug-burndown/SKILL.md)

#### bugfix

Drives a rigorous, evidence-gated bug fix or regression investigation from first report to Definition-of-Done. When invoked without a specific target, proactively scans logs, code, docs, git history, and issue trackers to discover bug candidates autonomously. User-given direction (bug report, issue ref, log path, class of bugs) takes priority. Enforces reproducer-first testing, root-cause fixes, a three-way diff between desired/documented/implemented behaviour, mandatory delegation to companion doc skills, and a hostile adversarial review before any done claim. Use when fixing bugs, investigating regressions, chasing spec/ADR/threat-model drift, or running a routine bug-hunting pass, especially for changes touching auth, crypto, supply chain, concurrency, persistence, or any trust boundary. → [`SKILL.md`](skills/bugfix/SKILL.md)

#### commit-messages

Use when creating git commits, writing commit messages, or when about to run git commit -- enforces structured commit message format with imperative mood, capitalized subjects, 72-char wrapping, and atomic commits → [`SKILL.md`](skills/commit-messages/SKILL.md)

#### gitlab-agent-plan

Read or write a GitLab work item's Workplan / Agent Plan widget — the AI work plan property — via GraphQL. Use when asked to get/show/pull or attach/set/update a work item's workplan or agent plan, as opposed to its description or comments. → [`SKILL.md`](skills/gitlab-agent-plan/SKILL.md)

#### gitlab-babysit-mr

Monitor a GitLab MR's pipeline until green. Classifies failures (flaky, master-broken, lint, coverage, real), retries jobs where appropriate, makes light-touch auto-fixes, and posts findings as an MR comment. → [`SKILL.md`](skills/gitlab-babysit-mr/SKILL.md)

#### gitlab-implement

End-to-end feature implementation workflow for a GitLab issue or epic — scopes it, asks clarifying questions, writes and adversarially reviews a plan, posts the plan on the issue and waits for approval, then implements, verifies, commits, and opens an MR. Use when asked to build or implement a GitLab feature end-to-end, from issue or epic to open MR. → [`SKILL.md`](skills/gitlab-implement/SKILL.md)

#### gitlab-mr-description

Write or update a GitLab MR description. Reads the branch diff, drafts structured markdown using GitLab's standard sections, and applies conventions for feature flags, database queries, and local testing matrices. Use when opening a new MR or refreshing an existing description. → [`SKILL.md`](skills/gitlab-mr-description/SKILL.md)

#### gitlab-pipeline-watch

Watch GitLab MR pipelines and react to state changes → [`SKILL.md`](skills/gitlab-pipeline-watch/SKILL.md)

#### gitlab-stacked-mrs

Manages stacked GitLab merge requests end-to-end: decomposing a feature branch into logical, independently-reviewable MRs; maintaining a suppression ledger for early-stack dead code; re-syncing the stack after merges (GitLab only auto-retargets 4 MRs, not the full 20-entry limit); triaging reviewer feedback back to the owning entry; and verifying parity with the feature branch throughout. Triggers: stacked MRs, stacked diffs, glab stack, split MR, decompose change, chain merge requests, stack workflow, stacked review, retarget stack, mid-stack rebase. → [`SKILL.md`](skills/gitlab-stacked-mrs/SKILL.md)

#### glab

GitLab CLI (glab) workflow automation for GitLab repositories, merge requests, issues, CI/CD pipelines, and APIs. Use when interacting with GitLab via the glab CLI, when given a GitLab URL (such as an MR or issue), or when asked to: view, diff, checkout, review, create, update, label, or comment on merge requests (MRs); post a note, review comment, or reply to discussions; view, search, create, close, or update issues, work items, or epics; inspect pipeline status, stream or view CI logs and traces (glab ci trace), or retry jobs; call the GitLab REST or GraphQL API through "glab api"; or configure glab auth against gitlab.com, a self-managed instance, or a local GDK. Read this skill before any glab write operation, because several field flags fail silently - they exit 0 while posting the wrong content. Triggers: glab, glab CLI, GitLab CLI, GitLab URL, MR diff, view MR, review MR, issue view, CI trace, job logs. → [`SKILL.md`](skills/glab/SKILL.md)

#### harness-builder

Scaffolds project-specific harness crates or modules that drive a project through its natural interface, observe and instrument the output, and triage it against documented requirements (stories, ADRs, specs, threat-model items) to schedule and burn down implementation gaps and defects in a continuous loop. Generates a runtime quality harness, an implementation genesis harness, or both, and can audit an existing harness up to standard. Use when asked to build a harness, scaffold project genesis, drive X and fix what breaks, loop until clean, build a closed-loop harness, or burn down bugs agentically. → [`SKILL.md`](skills/harness-builder/SKILL.md)

#### iterate

Brings projects to 100% completion through iterative cycles — implementing missing features, fixing security/correctness gaps, and refining code until all specs, ADRs, and threat model requirements are met. Runs gap analysis, prioritizes by security/correctness/quality/coverage, and auto-iterates until nothing remains. Use when completing an incomplete project, implementing remaining features from specs, addressing technical debt, or reaching production readiness. Triggers: iterate, bring to completion, implement remaining features, production readiness, gap analysis, address all gaps, complete project, iterative development. → [`SKILL.md`](skills/iterate/SKILL.md)

#### mcp-creator

Guides building production-quality MCP servers in Rust using the rmcp crate. Covers protocol design, tool implementation, testing, security hardening, and AI-tool integration. Use when building an MCP server, creating MCP tools, implementing MCP in Rust, adding tools/resources/prompts to an MCP server, or starting a new MCP project. → [`SKILL.md`](skills/mcp-creator/SKILL.md)

#### mcp-review

Reviews and improves existing MCP server implementations for protocol compliance, tool quality, Rust best practices, security, and testing coverage. Lists available MCP servers for selection when none specified. Use when reviewing an MCP server, auditing MCP tool quality, checking protocol compliance, improving MCP server code, or when the user mentions MCP review, MCP audit, or MCP server quality. → [`SKILL.md`](skills/mcp-review/SKILL.md)

#### mr-adversarial-review

Use when running a critical, skeptical pass over a GitLab MR — either as the author before requesting human review, or as a reviewer wanting a structured first cut — produces a severity-bucketed findings report (High / Medium / Low / Done well) and posts it as a single comment on the MR. → [`SKILL.md`](skills/mr-adversarial-review/SKILL.md)

#### mr-guided-review

Use when you want to understand and review a GitLab MR as a reasoning companion rather than an automated reviewer. Phase 1 explains the MR's goal and purpose concisely with a concrete example, then gates on your confirmation before Phase 2 does a thorough code review that surfaces genuine issues, not nitpicks. Read-only — never posts anything to the MR; you post any feedback yourself. Triggers when you want to review, understand, or walk through an MR. → [`SKILL.md`](skills/mr-guided-review/SKILL.md)

#### mr-label

Apply the correct GitLab MR type/subtype labels and evidence-based milestone when creating or updating a merge request. Use when opening or updating an MR. → [`SKILL.md`](skills/mr-label/SKILL.md)

#### mr-review

Review a GitLab merge request - read diffs, analyze changes, present findings, and optionally post comments on the MR → [`SKILL.md`](skills/mr-review/SKILL.md)

#### nix

Write, review, and fix Nix so it is minimal, tested, and upstreamable: flakes, dev shells, nixpkgs packages, NixOS modules and system configs, language builders, and nixpkgs PRs. Use when editing flake.nix, shell.nix, default.nix, package.nix, an overlay, or a NixOS module; packaging software with mkDerivation, buildGoModule, buildPythonPackage, or buildRustPackage; reviewing or preparing a nixpkgs PR; fixing a Nix eval or build failure; or when asked to nixify a project, add reproducible builds, or set up nix develop and direnv. Not for installing Nix or general shell questions. → [`SKILL.md`](skills/nix/SKILL.md)

#### prep-review

Check the status of, review, or respond to feedback on an existing GitLab Platform Readiness Enablement Process (PREP) assessment. Use when asked to review a PREP merge request, check if a PREP/readiness assessment is complete or ready for GA, evaluate PREP evidence quality as a reviewer, or address/respond to PREP reviewer feedback. Do not use for starting a brand-new PREP assessment; use prep-start for that instead. → [`SKILL.md`](skills/prep-review/SKILL.md)

#### prep-start

Start a GitLab Platform Readiness Enablement Process (PREP) assessment for a new feature, service, or infra change. Use when asked whether a feature needs PREP, to kick off/begin a PREP or readiness assessment, to create a PREP tracking issue, or to set up the first PREP merge request. Do not use for checking the status of, reviewing, or responding to feedback on an already-started PREP; use prep-review for that instead. → [`SKILL.md`](skills/prep-start/SKILL.md)

#### pushify

Run pre-push lefthook checks and iteratively fix failures (up to 3 iterations, then escalate). Invoke when: (a) about to push and wanting hooks to pass cleanly, (b) `git push` has just failed on a pre-push hook and the failure needs to be driven to resolution, or (c) preparing a clean working tree without pushing — e.g. before opening a Draft MR for early review. → [`SKILL.md`](skills/pushify/SKILL.md)

#### refactor

Performs codebase review and systematic refactoring for code quality, reliability, maintainability, and test coverage across Go, Rust, Python, C, and Nix. Use when running quality improvement passes, reviewing code for anti-patterns, cleaning up technical debt, improving test coverage, or when the user mentions refactor, code quality, or review-code. → [`SKILL.md`](skills/refactor/SKILL.md)

#### rust-compile-memory

Profiles Rust compilation memory usage with rustc nightly and measureme tools, identifies high-memory patterns (monomorphization, large types, LLVM bottlenecks), and refactors code to reduce compilation RSS. Use when Rust builds trigger the OOM killer or consume excessive memory. Triggers: compilation memory, rustc OOM, reduce compile memory, profile compilation. → [`SKILL.md`](skills/rust-compile-memory/SKILL.md)

#### rust-idioms

Write, review, and refactor Rust so it survives review: Result instead of panics on caller misuse, reuse of existing helpers, no dead API, typed values over strings and magic numbers, and iterator and allocation choices. Use when adding or changing .rs files, implementing a Rust feature or fix, or reviewing a Rust change. Not for repo-wide quality or tech-debt passes (refactor), unsafe/FFI (rust-unsafe-ffi-review), build speed or runtime perf (rust-performance-optimizer), compile memory (rust-compile-memory), Cargo/CI config, or non-Rust code. → [`SKILL.md`](skills/rust-idioms/SKILL.md)

#### rust-performance-optimizer

Analyzes and tunes Rust project performance across build speed, runtime memory, binary size, and test throughput. Applies Cargo profile tuning, linker selection, dependency auditing, profiling, and workspace restructuring to fix bottlenecks. Use when Rust builds are slow, binaries are too large, memory is high at runtime, or CI times are painful. Triggers: "slow rust build", "binary size", "reduce memory", "rust profiling", "cargo timing", "cargo flamegraph", "nextest", "dependency audit". → [`SKILL.md`](skills/rust-performance-optimizer/SKILL.md)

#### smart-rebase

Orchestrates intelligent git rebases by identifying the merge base between the current branch, its upstream tracking branch, and the default branch, then carefully reconciling all changes to produce a cleanly mergeable result. Use when rebasing a diverged feature branch onto an updated main/master, when preparing a branch for merge after the default branch has advanced, or when manual rebase conflicts risk clobbering default branch changes. Triggers: rebase, merge base, diverged branch, catch up with main, rebase onto main, reconcile branches, update feature branch. → [`SKILL.md`](skills/smart-rebase/SKILL.md)

#### stack-changes

Splits a large local change (uncommitted or committed) into a stacked-MR chain. Use when the user asks to split an MR they find too big to review, wants stacked diffs, has sprawling AI-mode work to publish, or types /stack-changes. → [`SKILL.md`](skills/stack-changes/SKILL.md)

### Database

#### gitlab-clickhouse

Inspect GitLab local ClickHouse tables, schemas, ingestion paths, and data patterns. Use for CH table questions, DESCRIBE TABLE, schema and source-of-truth checks under db/click_house, ingestion debugging, and investigating aggregates, distributions, outliers, or anomalous ClickHouse data in a GitLab GDK environment. → [`SKILL.md`](skills/gitlab-clickhouse/SKILL.md)

#### gitlab-psql

Inspect GitLab GDK PostgreSQL test and development databases with gdk psql. Use for Postgres schema checks, table and index inspection, read-only SQL queries, migration verification, and investigating GitLab application data in local test or development databases. → [`SKILL.md`](skills/gitlab-psql/SKILL.md)

#### postgresai

Run EXPLAIN / EXPLAIN ANALYZE, test indexes, and measure query cost on PostgresAI Database Lab thin clones with the PostgresAI CLI (postgresai, pgai, Joe). Use when asked to explain or optimize a query, check a plan at production scale, try an index on realistic data, or prepare a GitLab database review. → [`SKILL.md`](skills/postgresai/SKILL.md)

### Testing

#### playwright-cli

Automates browser interactions for web testing, form filling, screenshots, and data extraction. Use when the user needs to navigate websites, interact with web pages, fill forms, take screenshots, test web applications, or extract information from web pages. → [`SKILL.md`](skills/playwright-cli/SKILL.md)

#### rust-unsafe-ffi-review

Reviews Rust unsafe code and FFI bindings for memory safety and soundness issues. Use when auditing unsafe blocks, FFI interfaces, or preparing Rust code for security-critical use. → [`SKILL.md`](skills/rust-unsafe-ffi-review/SKILL.md)

#### self-service-performance-testing

Help engineers write performance tests that detect regressions, using k6 for load testing, sitespeed.io for frontend Core Web Vitals, rspec-benchmark for unit-level perf assertions, and Ruby profilers (Stackprof, memory_profiler, derailed_benchmarks, etc.) for investigating slow code paths. Use when the user is adding or changing API endpoints, database queries, critical paths, or frontend pages and needs to decide whether to write a performance test, what kind, or how to integrate it into CI. Also activate when the user mentions load testing, stress testing, response times, benchmarking, performance budgets, CPT, component performance testing, MR pipeline performance testing, profiling slow Ruby code, memory bloat, or wants to run tests against staging - this skill enforces shared infrastructure safety rules. Does not cover APM or debugging production incidents. → [`SKILL.md`](skills/self-service-performance-testing/SKILL.md)

### Shell & Environment

#### run-in-tmux-pane

Use for commands that require an interactive shell, a TTY, or shell-only functions. Run them in a temporary tmux pane with the full zsh environment. Use the shell tool directly for ordinary non-interactive commands. → [`SKILL.md`](skills/run-in-tmux-pane/SKILL.md)

#### skopeo

Interrogate container images and registries with skopeo — read manifests, configs, layers, platforms, and tags over the network without pulling the image or running a daemon. Use when asked about an image's digest, platforms, labels, entrypoint, layers, size, or available tags, instead of reaching for docker pull / docker inspect. → [`SKILL.md`](skills/skopeo/SKILL.md)

#### write-large-file

Write large files reliably using chunked bash append (>> heredoc) → [`SKILL.md`](skills/write-large-file/SKILL.md)

### Agent Tooling

#### handoff

Compact the current session into a handoff document so a fresh agent can continue the work. Use when the user says hand off, wrap up, save context, continue later, pick this up in a new session, running low on context, or context is getting long. → [`SKILL.md`](skills/handoff/SKILL.md)

#### human-review

Interactively resolves items that iteratotron and bug-burndown have escalated to needs_human or requires_human_review status. Reads the active session queues, reconstructs each item's context from linked specs/ADRs/threat-model entries plus the current gap analysis, drafts 2-4 candidate resolutions consistent with the in-flight scope, and runs an interview per item. Records each decision and re-queues actionable items so the parent skill re-engages. Scans all sessions by default, including the bug-burndown sessions a harness-builder runtime harness spawns per iteration. Use when iteratotron or bug-burndown has parked items for human input, when a harness loop won't converge because of parked needs_human items, or to clear the human review queue between sessions. → [`SKILL.md`](skills/human-review/SKILL.md)

#### opencode-refine

Iteratively test and refine prompts, skills, and agent configurations using opencode run → [`SKILL.md`](skills/opencode-refine/SKILL.md)

### Research & Notes

#### video-takeaways

Video URLs and YouTube links: extract actionable takeaways with timestamp hyperlinks, then save approved notes as Markdown, to Memos, as an EPUB for Kindle, or to another requested destination. Use when asked to summarize learnings, lessons, rules of thumb, practical advice, Markdown notes, EPUBs, or Send to Kindle documents from a video, talk, tutorial, or interview. → [`SKILL.md`](skills/video-takeaways/SKILL.md)

### Documentation

#### adr-create

Creates and manages Architecture Decision Records using MADR 4.0.0 format with Nygard's immutability principles. Handles new ADRs, superseding existing ones, and retroactively documenting past decisions from code analysis. Links decisions to spec requirements and threat model entries. Use when documenting an architecture decision, choosing between technologies, recording why a design choice was made, or backfilling undocumented decisions. Triggers: create ADR, document decision, architecture decision, why did we choose, record decision, backfill ADR. → [`SKILL.md`](skills/adr-create/SKILL.md)

#### adr-review

Reviews Architecture Decision Records for quality, completeness, and consistency. Identifies undocumented decisions by analyzing code, specs, and threat models. Backfills missing ADRs for past decisions, validates cross-references, and checks the decision log for staleness or contradictions. Use when auditing ADRs, finding missing decisions, reviewing ADR quality, checking for undocumented architecture choices, or when spec-review or threat-model-review flags missing ADRs. Triggers: review ADR, audit decisions, missing ADRs, ADR quality, backfill ADRs, decision log, undocumented decisions. → [`SKILL.md`](skills/adr-review/SKILL.md)

#### gitlab-demo-videos

Make a narrated walkthrough or demo video (MP4 with voiceover and captions) of a GitLab UI flow with synthetic data and no GitLab instance. Pages are built from GitLab's own frontend source at a pinned release tag, clicked through with Playwright, and voiced with a local text-to-speech model. Use when asked for a GitLab demo video, feature walkthrough, how-to or enablement video, a screen recording with fake data, or a voiceover for a GitLab feature, including GitLab.com-only settings and dashboards that a local instance cannot show. Not for screens outside the gitlab-org/gitlab codebase (such as the Customers Portal) or for real customer data. → [`SKILL.md`](skills/gitlab-demo-videos/SKILL.md)

#### spec-create

Creates and updates implementation specifications using IEEE 830 structure, RFC 2119 requirement levels, EARS syntax, and Gherkin acceptance criteria. Produces traceable, testable specs with cross-references to ADRs and threat models. Use when writing a spec, creating a specification document, defining requirements, documenting acceptance criteria, or updating an existing spec to cover new functionality. Triggers: write spec, create specification, document requirements, define acceptance criteria, update spec, spec gaps. → [`SKILL.md`](skills/spec-create/SKILL.md)

#### story-creator

Creates formal E2E user stories with BDD acceptance criteria, EARS constraints, and INVEST compliance through interactive user prompting. Use when creating new feature stories, documenting agent behaviors, writing acceptance criteria for multi-agent systems, or starting a new feature that needs behavioral verification coverage. Triggers: write user story, create story, BDD story, acceptance criteria, feature story, E2E behavior, agent story, INVEST story, Gherkin story. → [`SKILL.md`](skills/story-creator/SKILL.md)

#### story-reviewer

Reviews E2E user stories for INVEST compliance, Gherkin correctness, EARS constraint coverage, and test derivation quality. Produces a structured verdict with per-dimension scores, specific issues, and actionable feedback. Use when validating a story before sprint planning, reviewing stories created by story-creator or an AI generator, or auditing story quality in a PR. Triggers: review story, validate story, story quality, BDD review, acceptance criteria review, story audit, story feedback, INVEST check. → [`SKILL.md`](skills/story-reviewer/SKILL.md)

#### threat-model-create

Use when creating a new threat model, updating one after implementation changes, performing STRIDE analysis, scoring risk with DREAD, assessing attack surface, or when spec-create flags missing security analysis. Triggers: threat model, STRIDE, DREAD, security analysis, attack surface, identify threats, risk assessment. → [`SKILL.md`](skills/threat-model-create/SKILL.md)

#### threat-model-review

Reviews threat models for completeness, accuracy, and alignment with current implementation. Identifies drift between threat model and code, uncovered attack surfaces, missing STRIDE categories, incorrect risk scores, and unlinked mitigations. Creates threat models when none exist. Use when auditing a threat model, checking security coverage, finding unmodeled threats, validating risk scores, or when implementation has changed since the threat model was written. Triggers: review threat model, audit threats, threat model drift, security coverage, unmodeled threats, validate risk, threat model gaps. → [`SKILL.md`](skills/threat-model-review/SKILL.md)

### Meta / Authoring

#### authoring-skills

Author a new agent skill or improve an existing one - write the SKILL.md frontmatter and description, structure the body, and fix skills that under- or over-trigger. Use when asked to create/write a skill, make a SKILL.md, improve/refactor a skill, or fix a skill's description. → [`SKILL.md`](skills/authoring-skills/SKILL.md)

#### natural-writing-style

Enforces team writing style guidelines across all written output. Apply whenever writing, editing, or reviewing code comments, docstrings, documentation, README files, MR/PR descriptions, commit messages, issue descriptions, changelogs, technical specifications, API docs, inline comments, or any other text-based output. Also apply when reviewing existing text for style compliance. Triggers on all writing, documentation, review, and communication tasks. → [`SKILL.md`](skills/natural-writing-style/SKILL.md)

### Other

#### glab-glql

Execute GLQL queries against GitLab projects and groups using glab CLI → [`SKILL.md`](skills/glab-glql/SKILL.md)
<!-- SKILLS_END -->

> Skills are grouped by category and auto-generated from skill frontmatter. Run `python3 scripts/update_skills_list.py` to regenerate after adding or modifying skills.

## Installing Skills

> [!NOTE]
> **Windows users:** this repo uses symlinks for skill distribution. Before cloning, ensure Git is configured to create real symlinks:
>
> ```bash
> git config --global core.symlinks true
> ```
>
> You may also need to enable [Developer Mode](https://learn.microsoft.com/en-us/windows/apps/get-started/enable-your-device-for-development) or run Git as Administrator for symlink creation to work.

### `.agents/skills/` (Zed, GitLab Duo CLI)

This repo ships `.agents/skills/` with a symlink for each skill. That is the cross-tool discovery location defined by the [Agent Skills spec](https://agentskills.io), so multiple tools can read it:

- **Zed** loads skills from a project-local `<worktree>/.agents/skills/` (in a trusted worktree) as well as the global `~/.agents/skills/`. Cloning this repo is enough for project-local discovery, no extra step needed. See the [Zed skills docs](https://zed.dev/docs/ai/skills).
- **GitLab Duo CLI** discovers global skills from `~/.agents/skills/` (or `~/.gitlab/duo/skills/`).

For global discovery, symlink the shipped skills into `~/.agents/skills/`:

```bash
git clone https://gitlab.com/gitlab-org/ai/skills.git ~/gitlab-skills

for skill in ~/gitlab-skills/.agents/skills/*/; do
  ln -s "$skill" ~/.agents/skills/
done
```

### Pi (Package)

This repo ships as a [pi package](https://github.com/badlogic/pi-mono). Install globally or per-project:

```bash
# From git (global)
pi install git:gitlab.com/gitlab-org/ai/skills

# From local clone
pi install /path/to/skills

# Per-project (writes to .pi/settings.json)
pi install -l git:gitlab.com/gitlab-org/ai/skills
```

Pi auto-discovers all skills under `skills/` via the `package.json` manifest. To filter which skills load, use package filtering in `.pi/settings.json`.

### OpenCode (Native)

This repo ships `.opencode/skills/` with symlinks for each skill. Clone the repo and OpenCode discovers them automatically — no extra install step needed.

```bash
git clone https://gitlab.com/gitlab-org/ai/skills.git ~/gitlab-skills
# OpenCode picks up .opencode/skills/ from the cloned directory
```

Or symlink into your global OpenCode config:

```bash
for skill in ~/gitlab-skills/.opencode/skills/*/; do
  ln -s "$skill" ~/.config/opencode/skills/
done
```

### Via `skills` CLI (npx)

[`vercel-labs/skills`](https://github.com/vercel-labs/skills) supports installing and updating GitLab-hosted skills (verified with `skills@1.6.0`). Run it with `npx` without a global install.

```bash
# Install all skills from this repo globally (for OpenCode)
npx skills add https://gitlab.com/gitlab-org/ai/skills/-/tree/main/skills --global --agent opencode

# Install all skills from this repo globally (for Claude Code)
npx skills add https://gitlab.com/gitlab-org/ai/skills/-/tree/main/skills --global --agent claude-code

# Apply updates
npx skills update

# List installed skills
npx skills list -g
```

### Claude Code Plugin Marketplace

This repo ships as a [Claude Code plugin marketplace](https://code.claude.com/docs/en/plugin-marketplaces):

```shell
/plugin marketplace add https://gitlab.com/gitlab-org/ai/skills.git
/plugin install glab@gitlab-skills
```

<!-- CLAUDECODE_PLUGINS_START -->
| Plugin | Skills | Description | Version |
| ------ | ------ | ----------- | ------- |
| [`adr-create`](.claude-plugin/plugins/adr-create) | [`adr-create`](skills/adr-create/SKILL.md) | Creates and manages Architecture Decision Records using MADR 4.0.0 format with Nygard's immutability principles. Handles new ADRs, superseding existing ones, and retroactively documenting past decisions from code analysis. Links decisions to spec requirements and threat model entries. Use when documenting an architecture decision, choosing between technologies, recording why a design choice was made, or backfilling undocumented decisions. Triggers: create ADR, document decision, architecture decision, why did we choose, record decision, backfill ADR. | 1.0.1 |
| [`adr-review`](.claude-plugin/plugins/adr-review) | [`adr-review`](skills/adr-review/SKILL.md) | Reviews Architecture Decision Records for quality, completeness, and consistency. Identifies undocumented decisions by analyzing code, specs, and threat models. Backfills missing ADRs for past decisions, validates cross-references, and checks the decision log for staleness or contradictions. Use when auditing ADRs, finding missing decisions, reviewing ADR quality, checking for undocumented architecture choices, or when spec-review or threat-model-review flags missing ADRs. Triggers: review ADR, audit decisions, missing ADRs, ADR quality, backfill ADRs, decision log, undocumented decisions. | 1.0.1 |
| [`authoring-skills`](.claude-plugin/plugins/authoring-skills) | [`authoring-skills`](skills/authoring-skills/SKILL.md) | Author a new agent skill or improve an existing one - write the SKILL.md frontmatter and description, structure the body, and fix skills that under- or over-trigger. Use when asked to create/write a skill, make a SKILL.md, improve/refactor a skill, or fix a skill's description. | 0.6.2 |
| [`bug-burndown`](.claude-plugin/plugins/bug-burndown) | [`bug-burndown`](skills/bug-burndown/SKILL.md) | Runs a continuous, autonomous bug burndown session — collecting defects from logs, tests, issue queues, and spec drift; deduplicating and triaging them through an 8-phase pipeline; then dispatching bounded parallel bugfix subagents in isolated worktrees until the queue is empty or the time budget runs out. Use when asked to burn down the bugs, clear the backlog, triage CI failures, find regressions, run a fix session, or anything that's batch quality-improvement rather than a single targeted bug fix. | 1.0.0 |
| [`bugfix`](.claude-plugin/plugins/bugfix) | [`bugfix`](skills/bugfix/SKILL.md) | Drives a rigorous, evidence-gated bug fix or regression investigation from first report to Definition-of-Done. When invoked without a specific target, proactively scans logs, code, docs, git history, and issue trackers to discover bug candidates autonomously. User-given direction (bug report, issue ref, log path, class of bugs) takes priority. Enforces reproducer-first testing, root-cause fixes, a three-way diff between desired/documented/implemented behaviour, mandatory delegation to companion doc skills, and a hostile adversarial review before any done claim. Use when fixing bugs, investigating regressions, chasing spec/ADR/threat-model drift, or running a routine bug-hunting pass, especially for changes touching auth, crypto, supply chain, concurrency, persistence, or any trust boundary. | 1.0.1 |
| [`commit-messages`](.claude-plugin/plugins/commit-messages) | [`commit-messages`](skills/commit-messages/SKILL.md) | Use when creating git commits, writing commit messages, or when about to run git commit -- enforces structured commit message format with imperative mood, capitalized subjects, 72-char wrapping, and atomic commits | 1.0.3 |
| [`gitlab-agent-plan`](.claude-plugin/plugins/gitlab-agent-plan) | [`gitlab-agent-plan`](skills/gitlab-agent-plan/SKILL.md) | Read or write a GitLab work item's Workplan / Agent Plan widget — the AI work plan property — via GraphQL. Use when asked to get/show/pull or attach/set/update a work item's workplan or agent plan, as opposed to its description or comments. | 0.1.1 |
| [`gitlab-babysit-mr`](.claude-plugin/plugins/gitlab-babysit-mr) | [`gitlab-babysit-mr`](skills/gitlab-babysit-mr/SKILL.md) | Monitor a GitLab MR's pipeline until green. Classifies failures (flaky, master-broken, lint, coverage, real), retries jobs where appropriate, makes light-touch auto-fixes, and posts findings as an MR comment. | 0.12.5 |
| [`gitlab-clickhouse`](.claude-plugin/plugins/gitlab-clickhouse) | [`gitlab-clickhouse`](skills/gitlab-clickhouse/SKILL.md) | Inspect GitLab local ClickHouse tables, schemas, ingestion paths, and data patterns. Use for CH table questions, DESCRIBE TABLE, schema and source-of-truth checks under db/click_house, ingestion debugging, and investigating aggregates, distributions, outliers, or anomalous ClickHouse data in a GitLab GDK environment. | 1.0.1 |
| [`gitlab-demo-videos`](.claude-plugin/plugins/gitlab-demo-videos) | [`gitlab-demo-videos`](skills/gitlab-demo-videos/SKILL.md) | Make a narrated walkthrough or demo video (MP4 with voiceover and captions) of a GitLab UI flow with synthetic data and no GitLab instance. Pages are built from GitLab's own frontend source at a pinned release tag, clicked through with Playwright, and voiced with a local text-to-speech model. Use when asked for a GitLab demo video, feature walkthrough, how-to or enablement video, a screen recording with fake data, or a voiceover for a GitLab feature, including GitLab.com-only settings and dashboards that a local instance cannot show. Not for screens outside the gitlab-org/gitlab codebase (such as the Customers Portal) or for real customer data. | 1.0.0 |
| [`gitlab-implement`](.claude-plugin/plugins/gitlab-implement) | [`gitlab-implement`](skills/gitlab-implement/SKILL.md) | End-to-end feature implementation workflow for a GitLab issue or epic — scopes it, asks clarifying questions, writes and adversarially reviews a plan, posts the plan on the issue and waits for approval, then implements, verifies, commits, and opens an MR. Use when asked to build or implement a GitLab feature end-to-end, from issue or epic to open MR. | 1.0.0 |
| [`gitlab-mr-description`](.claude-plugin/plugins/gitlab-mr-description) | [`gitlab-mr-description`](skills/gitlab-mr-description/SKILL.md) | Write or update a GitLab MR description. Reads the branch diff, drafts structured markdown using GitLab's standard sections, and applies conventions for feature flags, database queries, and local testing matrices. Use when opening a new MR or refreshing an existing description. | 1.1.0 |
| [`gitlab-pipeline-watch`](.claude-plugin/plugins/gitlab-pipeline-watch) | [`gitlab-pipeline-watch`](skills/gitlab-pipeline-watch/SKILL.md) | Watch GitLab MR pipelines and react to state changes | 1.0.2 |
| [`gitlab-psql`](.claude-plugin/plugins/gitlab-psql) | [`gitlab-psql`](skills/gitlab-psql/SKILL.md) | Inspect GitLab GDK PostgreSQL test and development databases with gdk psql. Use for Postgres schema checks, table and index inspection, read-only SQL queries, migration verification, and investigating GitLab application data in local test or development databases. | 1.0.1 |
| [`gitlab-stacked-mrs`](.claude-plugin/plugins/gitlab-stacked-mrs) | [`gitlab-stacked-mrs`](skills/gitlab-stacked-mrs/SKILL.md) | Manages stacked GitLab merge requests end-to-end: decomposing a feature branch into logical, independently-reviewable MRs; maintaining a suppression ledger for early-stack dead code; re-syncing the stack after merges (GitLab only auto-retargets 4 MRs, not the full 20-entry limit); triaging reviewer feedback back to the owning entry; and verifying parity with the feature branch throughout. Triggers: stacked MRs, stacked diffs, glab stack, split MR, decompose change, chain merge requests, stack workflow, stacked review, retarget stack, mid-stack rebase. | 1.0.0 |
| [`glab`](.claude-plugin/plugins/glab) | [`glab`](skills/glab/SKILL.md) | GitLab CLI (glab) workflow automation for GitLab repositories, merge requests, issues, CI/CD pipelines, and APIs. Use when interacting with GitLab via the glab CLI, when given a GitLab URL (such as an MR or issue), or when asked to: view, diff, checkout, review, create, update, label, or comment on merge requests (MRs); post a note, review comment, or reply to discussions; view, search, create, close, or update issues, work items, or epics; inspect pipeline status, stream or view CI logs and traces (glab ci trace), or retry jobs; call the GitLab REST or GraphQL API through "glab api"; or configure glab auth against gitlab.com, a self-managed instance, or a local GDK. Read this skill before any glab write operation, because several field flags fail silently - they exit 0 while posting the wrong content. Triggers: glab, glab CLI, GitLab CLI, GitLab URL, MR diff, view MR, review MR, issue view, CI trace, job logs. | 1.15.0 |
| [`glab-glql`](.claude-plugin/plugins/glab-glql) | [`glab-glql`](skills/glab-glql/SKILL.md) | Execute GLQL queries against GitLab projects and groups using glab CLI | 1.0.0 |
| [`handoff`](.claude-plugin/plugins/handoff) | [`handoff`](skills/handoff/SKILL.md) | Compact the current session into a handoff document so a fresh agent can continue the work. Use when the user says hand off, wrap up, save context, continue later, pick this up in a new session, running low on context, or context is getting long. | 0.5.1 |
| [`harness-builder`](.claude-plugin/plugins/harness-builder) | [`harness-builder`](skills/harness-builder/SKILL.md) | Scaffolds project-specific harness crates or modules that drive a project through its natural interface, observe and instrument the output, and triage it against documented requirements (stories, ADRs, specs, threat-model items) to schedule and burn down implementation gaps and defects in a continuous loop. Generates a runtime quality harness, an implementation genesis harness, or both, and can audit an existing harness up to standard. Use when asked to build a harness, scaffold project genesis, drive X and fix what breaks, loop until clean, build a closed-loop harness, or burn down bugs agentically. | 2.3.0 |
| [`human-review`](.claude-plugin/plugins/human-review) | [`human-review`](skills/human-review/SKILL.md) | Interactively resolves items that iteratotron and bug-burndown have escalated to needs_human or requires_human_review status. Reads the active session queues, reconstructs each item's context from linked specs/ADRs/threat-model entries plus the current gap analysis, drafts 2-4 candidate resolutions consistent with the in-flight scope, and runs an interview per item. Records each decision and re-queues actionable items so the parent skill re-engages. Scans all sessions by default, including the bug-burndown sessions a harness-builder runtime harness spawns per iteration. Use when iteratotron or bug-burndown has parked items for human input, when a harness loop won't converge because of parked needs_human items, or to clear the human review queue between sessions. | 1.0.0 |
| [`iterate`](.claude-plugin/plugins/iterate) | [`iterate`](skills/iterate/SKILL.md) | Brings projects to 100% completion through iterative cycles — implementing missing features, fixing security/correctness gaps, and refining code until all specs, ADRs, and threat model requirements are met. Runs gap analysis, prioritizes by security/correctness/quality/coverage, and auto-iterates until nothing remains. Use when completing an incomplete project, implementing remaining features from specs, addressing technical debt, or reaching production readiness. Triggers: iterate, bring to completion, implement remaining features, production readiness, gap analysis, address all gaps, complete project, iterative development. | 1.0.2 |
| [`mcp-creator`](.claude-plugin/plugins/mcp-creator) | [`mcp-creator`](skills/mcp-creator/SKILL.md) | Guides building production-quality MCP servers in Rust using the rmcp crate. Covers protocol design, tool implementation, testing, security hardening, and AI-tool integration. Use when building an MCP server, creating MCP tools, implementing MCP in Rust, adding tools/resources/prompts to an MCP server, or starting a new MCP project. | 1.0.0 |
| [`mcp-review`](.claude-plugin/plugins/mcp-review) | [`mcp-review`](skills/mcp-review/SKILL.md) | Reviews and improves existing MCP server implementations for protocol compliance, tool quality, Rust best practices, security, and testing coverage. Lists available MCP servers for selection when none specified. Use when reviewing an MCP server, auditing MCP tool quality, checking protocol compliance, improving MCP server code, or when the user mentions MCP review, MCP audit, or MCP server quality. | 1.0.0 |
| [`mr-adversarial-review`](.claude-plugin/plugins/mr-adversarial-review) | [`mr-adversarial-review`](skills/mr-adversarial-review/SKILL.md) | Use when running a critical, skeptical pass over a GitLab MR — either as the author before requesting human review, or as a reviewer wanting a structured first cut — produces a severity-bucketed findings report (High / Medium / Low / Done well) and posts it as a single comment on the MR. | 0.1.0 |
| [`mr-guided-review`](.claude-plugin/plugins/mr-guided-review) | [`mr-guided-review`](skills/mr-guided-review/SKILL.md) | Use when you want to understand and review a GitLab MR as a reasoning companion rather than an automated reviewer. Phase 1 explains the MR's goal and purpose concisely with a concrete example, then gates on your confirmation before Phase 2 does a thorough code review that surfaces genuine issues, not nitpicks. Read-only — never posts anything to the MR; you post any feedback yourself. Triggers when you want to review, understand, or walk through an MR. | 0.1.0 |
| [`mr-label`](.claude-plugin/plugins/mr-label) | [`mr-label`](skills/mr-label/SKILL.md) | Apply the correct GitLab MR type/subtype labels and evidence-based milestone when creating or updating a merge request. Use when opening or updating an MR. | 0.1.0 |
| [`mr-review`](.claude-plugin/plugins/mr-review) | [`mr-review`](skills/mr-review/SKILL.md) | Review a GitLab merge request — read diffs, analyze changes, present findings, and optionally post comments on the MR | 0.1.0 |
| [`natural-writing-style`](.claude-plugin/plugins/natural-writing-style) | [`natural-writing-style`](skills/natural-writing-style/SKILL.md) | Enforces team writing style guidelines across all written output. Apply whenever writing, editing, or reviewing code comments, docstrings, documentation, README files, MR/PR descriptions, commit messages, issue descriptions, changelogs, technical specifications, API docs, inline comments, or any other text-based output. Also apply when reviewing existing text for style compliance. Triggers on all writing, documentation, review, and communication tasks. | 1.0.0 |
| [`nix`](.claude-plugin/plugins/nix) | [`nix`](skills/nix/SKILL.md) | Write, review, and fix Nix so it is minimal, tested, and upstreamable: flakes, dev shells, nixpkgs packages, NixOS modules and system configs, language builders, and nixpkgs PRs. Use when editing flake.nix, shell.nix, default.nix, package.nix, an overlay, or a NixOS module; packaging software with mkDerivation, buildGoModule, buildPythonPackage, or buildRustPackage; reviewing or preparing a nixpkgs PR; fixing a Nix eval or build failure; or when asked to nixify a project, add reproducible builds, or set up nix develop and direnv. Not for installing Nix or general shell questions. | 0.1.0 |
| [`postgresai`](.claude-plugin/plugins/postgresai) | [`postgresai`](skills/postgresai/SKILL.md) | Run EXPLAIN / EXPLAIN ANALYZE, test indexes, and measure query cost on PostgresAI Database Lab thin clones with the PostgresAI CLI (postgresai, pgai, Joe). Use when asked to explain or optimize a query, check a plan at production scale, try an index on realistic data, or prepare a GitLab database review. | 1.0.3 |
| [`prep-review`](.claude-plugin/plugins/prep-review) | [`prep-review`](skills/prep-review/SKILL.md) | Check the status of, review, or respond to feedback on an existing GitLab Platform Readiness Enablement Process (PREP) assessment. Use when asked to review a PREP merge request, check if a PREP/readiness assessment is complete or ready for GA, evaluate PREP evidence quality as a reviewer, or address/respond to PREP reviewer feedback. Do not use for starting a brand-new PREP assessment; use prep-start for that instead. | 0.1.0 |
| [`prep-start`](.claude-plugin/plugins/prep-start) | [`prep-start`](skills/prep-start/SKILL.md) | Start a GitLab Platform Readiness Enablement Process (PREP) assessment for a new feature, service, or infra change. Use when asked whether a feature needs PREP, to kick off/begin a PREP or readiness assessment, to create a PREP tracking issue, or to set up the first PREP merge request. Do not use for checking the status of, reviewing, or responding to feedback on an already-started PREP; use prep-review for that instead. | 0.1.0 |
| [`pushify`](.claude-plugin/plugins/pushify) | [`pushify`](skills/pushify/SKILL.md) | Run pre-push lefthook checks and iteratively fix failures (up to 3 iterations, then escalate). Invoke when: (a) about to push and wanting hooks to pass cleanly, (b) `git push` has just failed on a pre-push hook and the failure needs to be driven to resolution, or (c) preparing a clean working tree without pushing — e.g. before opening a Draft MR for early review. | 1.1.0 |
| [`refactor`](.claude-plugin/plugins/refactor) | [`refactor`](skills/refactor/SKILL.md) | Performs codebase review and systematic refactoring for code quality, reliability, maintainability, and test coverage across Go, Rust, Python, C, and Nix. Use when running quality improvement passes, reviewing code for anti-patterns, cleaning up technical debt, improving test coverage, or when the user mentions refactor, code quality, or review-code. | 1.0.1 |
| [`run-in-tmux-pane`](.claude-plugin/plugins/run-in-tmux-pane) | [`run-in-tmux-pane`](skills/run-in-tmux-pane/SKILL.md) | Run commands in a temporary tmux pane with full interactive zsh environment (login shell, shims, PATH, aliases, TTY). | 2.0.0 |
| [`rust-compile-memory`](.claude-plugin/plugins/rust-compile-memory) | [`rust-compile-memory`](skills/rust-compile-memory/SKILL.md) | Profiles Rust compilation memory usage with rustc nightly and measureme tools, identifies high-memory patterns (monomorphization, large types, LLVM bottlenecks), and refactors code to reduce compilation RSS. Use when Rust builds trigger the OOM killer or consume excessive memory. Triggers: compilation memory, rustc OOM, reduce compile memory, profile compilation. | 1.0.1 |
| [`rust-idioms`](.claude-plugin/plugins/rust-idioms) | [`rust-idioms`](skills/rust-idioms/SKILL.md) | Write, review, and refactor Rust so it survives review: Result instead of panics on caller misuse, reuse of existing helpers, no dead API, typed values over strings and magic numbers, and iterator and allocation choices. Use when adding or changing .rs files, implementing a Rust feature or fix, or reviewing a Rust change. Not for repo-wide quality or tech-debt passes (refactor), unsafe/FFI (rust-unsafe-ffi-review), build speed or runtime perf (rust-performance-optimizer), compile memory (rust-compile-memory), Cargo/CI config, or non-Rust code. | 1.0.0 |
| [`rust-performance-optimizer`](.claude-plugin/plugins/rust-performance-optimizer) | [`rust-performance-optimizer`](skills/rust-performance-optimizer/SKILL.md) | Analyzes and tunes Rust project performance across build speed, runtime memory, binary size, and test throughput. Applies Cargo profile tuning, linker selection, dependency auditing, profiling, and workspace restructuring to fix bottlenecks. Use when Rust builds are slow, binaries are too large, memory is high at runtime, or CI times are painful. Triggers: "slow rust build", "binary size", "reduce memory", "rust profiling", "cargo timing", "cargo flamegraph", "nextest", "dependency audit". | 1.0.1 |
| [`rust-unsafe-ffi-review`](.claude-plugin/plugins/rust-unsafe-ffi-review) | [`rust-unsafe-ffi-review`](skills/rust-unsafe-ffi-review/SKILL.md) | Reviews Rust unsafe code and FFI bindings for memory safety and soundness issues. Use when auditing unsafe blocks, FFI interfaces, or preparing Rust code for security-critical use. | 1.0.0 |
| [`self-service-performance-testing`](.claude-plugin/plugins/self-service-performance-testing) | [`self-service-performance-testing`](skills/self-service-performance-testing/SKILL.md) | Help engineers write performance tests that detect regressions, using k6 for load testing, sitespeed.io for frontend Core Web Vitals, rspec-benchmark for unit-level perf assertions, and Ruby profilers (Stackprof, memory_profiler, derailed_benchmarks, etc.) for investigating slow code paths. Use when the user is adding or changing API endpoints, database queries, critical paths, or frontend pages and needs to decide whether to write a performance test, what kind, or how to integrate it into CI. Also activate when the user mentions load testing, stress testing, response times, benchmarking, performance budgets, CPT, component performance testing, MR pipeline performance testing, profiling slow Ruby code, memory bloat, or wants to run tests against staging - this skill enforces shared infrastructure safety rules. Does not cover APM or debugging production incidents. | 0.4.1 |
| [`skopeo`](.claude-plugin/plugins/skopeo) | [`skopeo`](skills/skopeo/SKILL.md) | Interrogate container images and registries with skopeo — read manifests, configs, layers, platforms, and tags over the network without pulling the image or running a daemon. Use when asked about an image's digest, platforms, labels, entrypoint, layers, size, or available tags, instead of reaching for docker pull / docker inspect. | 0.1.0 |
| [`stack-changes`](.claude-plugin/plugins/stack-changes) | [`stack-changes`](skills/stack-changes/SKILL.md) | Splits a large local change (uncommitted or committed) into a stacked-MR chain. Use when the user asks to split an MR they find too big to review, wants stacked diffs, has sprawling AI-mode work to publish, or types /stack-changes. | 0.1.1 |
| [`threat-model-create`](.claude-plugin/plugins/threat-model-create) | [`threat-model-create`](skills/threat-model-create/SKILL.md) | Use when creating a new threat model, updating one after implementation changes, performing STRIDE analysis, scoring risk with DREAD, assessing attack surface, or when spec-create flags missing security analysis. Triggers: threat model, STRIDE, DREAD, security analysis, attack surface, identify threats, risk assessment. | 1.0.2 |
| [`video-takeaways`](.claude-plugin/plugins/video-takeaways) | [`video-takeaways`](skills/video-takeaways/SKILL.md) | Video URLs and YouTube links: extract actionable takeaways with timestamp hyperlinks, then save approved notes as Markdown, to Memos, as an EPUB for Kindle, or to another requested destination. Use when asked to summarize learnings, lessons, rules of thumb, practical advice, Markdown notes, EPUBs, or Send to Kindle documents from a video, talk, tutorial, or interview. | 1.0.2 |
| [`write-large-file`](.claude-plugin/plugins/write-large-file) | [`write-large-file`](skills/write-large-file/SKILL.md) | Write large files reliably using chunked bash append (>> heredoc) | 1.0.0 |
<!-- CLAUDECODE_PLUGINS_END -->

## Contributing

To add a new skill:

1. Create `skills/<skill-name>/SKILL.md` with required frontmatter (`name`, `description`, `version`)
2. Run `bin/distribute-skill <skill-name>` to register it in `.opencode/` and `.claude-plugin/`
3. Run `lefthook run auto-fix` to regenerate all derived files (README table, ToC, catalog, plugin manifests)
4. Run `bin/ci-checks` to verify CI checks locally.
5. Commit, push and open a MR

See [doc/contributing.md](doc/contributing.md) for full details, frontmatter reference, and development setup (including lefthook installation).

## Related

- [Search Team AI Skills](https://gitlab.com/gitlab-org/search-team/ai/skills) — team-specific skills collection that inspired this repo's conventions
- [OpenCode Documentation](https://opencode.ai/docs)
- [Claude Code Plugin Marketplace Docs](https://code.claude.com/docs/en/plugin-marketplaces)
