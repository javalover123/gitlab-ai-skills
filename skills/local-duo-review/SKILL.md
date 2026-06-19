---
name: local-duo-review
description: Run a GitLab Duo Code Review locally — detect a project's custom review instructions in `.gitlab/duo/mr-review-instructions.yaml`, match changed files against each instruction group's glob filters, and review the local diff against only those user-defined rules, emulating Duo before you push or open an MR. Use when asked to apply custom/duo review instructions, check changes against `.gitlab/duo` rules, or preview a Duo review locally. Do not use for a general MR review (use `mr-review`) or a skeptical critique (use `mr-adversarial-review`).
version: 0.1.0
category: Development Workflow
license: MIT
compatibility: opencode
metadata:
  audience: developers
  workflow: gitlab
---

# local-duo-review

Emulate [GitLab Duo Code Review's custom review instructions](https://docs.gitlab.com/user/gitlab_duo/customize_duo/review_instructions/)
locally: read the project's `.gitlab/duo/mr-review-instructions.yaml`, work out
which instruction group applies to each locally-changed file, and review the
diff against **only those user-defined rules** — so you see what Duo would flag
before you push or open an MR. Assumes a git checkout with local changes; no MR
or network is required.

## When to use

- "Run a duo review locally", "preview what Duo will flag on my changes".
- "Check my diff against the custom/`.gitlab/duo` review instructions".
- Before pushing, to satisfy the project's own review rules up front.

## When NOT to use

- General quality review of an MR → `mr-review`.
- Skeptical, severity-bucketed critique → `mr-adversarial-review`.
- The project has **no** `.gitlab/duo/mr-review-instructions.yaml` → tell the
  user and suggest `mr-review` instead.

## Gotchas

- **Custom instructions are *additive*.** Duo appends them to its standard
  criteria. This skill deliberately reviews against the **custom rules only** —
  say so in the output; don't claim full Duo coverage.
- **Glob filters are root-anchored with subtle semantics** (the helper handles
  them, don't hand-match): `*.rb` matches root-level files **only**; `**/*.rb`
  matches at any depth; `!pattern` excludes; `{js,jsx}` is a union (GitLab
  19.1+). A group with *only* `!` filters applies to everything except its
  exclusions; an empty/missing `fileFilters` applies to every file. The helper
  *approximates* Duo's doublestar matcher — close on common patterns, but treat
  the mapping as a strong guide, not a byte-for-byte guarantee.
- **Renames/moves are reported by their new path only.** Deletions are filtered
  out, so a file moved into a watched glob is reviewed at its destination, but
  its old path won't appear — don't expect it in the changed set.
- **One file can match several groups** — review it against *each* group's rules.
- **Group-level template instructions live in another project**, not on disk, so
  they are not auto-resolved. Pass them with a second `--instructions <path>` to
  load their groups alongside the on-disk ones (collected into one flat list, not
  merged into a matching group).
- **"Local" includes uncommitted work by default** (committed + staged + unstaged
  + untracked vs the **fork point** with the target branch) — the pre-MR state
  Duo would see. The base is the local `git merge-base`, matching how GitLab
  computes an MR diff; no remote/network lookup is performed.
- Judge the **added** lines (`+`); never suggest adding what the diff already adds.

## Workflow

Determine `SKILL_DIR` (the directory containing this SKILL.md), then:

### 1. Match changed files to instruction groups

```bash
python3 "$SKILL_DIR/scripts/match-instructions.py" --target <branch>
```

Omit `--target` to auto-detect, preferring **local** refs (the clone's recorded
default branch, then local `main`/`master`) and only falling back to
remote-tracking `origin/main`/`origin/master` if no local branch exists. The
comparison base is the local `git merge-base` (fork point) of `HEAD` and the
target — the same commit GitLab diffs an MR against — computed **without any
network access**. The script prints `=== INSTRUCTIONS ===`, `=== BASE ===`,
`=== CHANGED_FILES ===`, `=== MATCHES ===` (group → instructions + files),
`=== GROUPS_WITHOUT_MATCHES ===` (groups whose globs matched nothing — check for
misconfigured filters), `=== UNMATCHED_FILES ===`, and `=== DIFFS ===` (per-file
diff tagged with the groups that apply). Pass `--no-diff` if you only need the mapping, or a second
`--instructions <path>` to load additional instruction groups (e.g. a group template).

If `=== INSTRUCTIONS ===` reports `status: none`, stop: the project has no custom
instructions. Report that and suggest `mr-review`.

### 2. Review each matched file against its group(s)

For every file in `=== DIFFS ===`, evaluate the added lines against **each**
group listed on its `groups:` tag. Flag a line only when it genuinely violates a
specific numbered instruction — precision over recall, one finding per issue,
code in backticks.

### 3. Report findings locally

Group findings by file. For each, reproduce Duo's attribution format so it reads
like a real Duo comment:

```
According to custom instructions in '<group name>': <specific feedback>
```

End with a short summary: files reviewed, groups applied, files with no
applicable instruction (out of scope). This is a **local report** — do not post
comments on any MR (that's `mr-review`'s job).

## Rules

1. Review against the **custom instructions only**; state that scope explicitly.
2. Never hand-roll glob matching — trust the script's file→group mapping.
3. Apply **every** group that matches a file, not just the first.
4. Only flag added lines that violate a concrete instruction; don't invent rules.
5. Produce a local report; never post to an MR.
