# Scope discovery for iteratotron

This reference is loaded on demand from the `iteratotron` skill during
Phase 2. It specifies what counts as a "scope" (a unit that one
`iterate` subagent dispatch can plausibly drive to 100% completion),
how to enumerate scopes per project type, and how to filter them.

A scope must satisfy two constraints:

1. **Bounded enough** that a single `iterate` run (potentially many
   internal iterations, but one dispatched subagent context) can drive
   it to completion. If a scope is so large that no `iterate` run
   could plausibly complete it within ~90 minutes, it must be
   decomposed.
2. **Coherent enough** that it has its own documentation artefacts (or
   *should* have them — `needs_all_aboard: true`). A scope where the
   spec lives in one place, the ADRs in another, and the threat model
   nowhere is a scope that hasn't been carved correctly.

## The scope record (canonical)

Each enumerated scope is written to
`${session_dir}/scopes/<scope_id>.md` with this frontmatter:

```yaml
---
scope_id: SCOPE-<8-hex>
kind: cargo-crate | language-package | feature-area | feature-branch | gh-issue | adr-section | spec-fr | story
primary_path: <filesystem path identifying the scope>
secondary_paths: [<additional paths within the scope>]
language: rust | python | go | typescript | nix | c | mixed
linked_artefacts:
  spec: <path or null>
  adrs: [<paths>]
  threat_model: <path or null>
  stories: [<IDs or paths>]
iteration_log: <path or null>
last_iterate_status: <value from iteration log's last line, or null>
last_iterate_session_id: <iteratotron session_id, if known>
last_complete_claim_at: <ISO timestamp from iteration log, or null>
needs_all_aboard: <bool — true if any of spec/adrs/threat_model missing>
discovery_method: <how this scope was enumerated>
---
```

The body of the file lists, in human-readable form, the contents of
the scope (file list with line counts, primary symbols/types, key
entry points). This becomes part of the iterate-subagent prompt at
dispatch time.

## Scope kinds, in detail

### 1. Cargo workspace crate (kind: `cargo-crate`)

The default scope for Rust projects. One `[workspace.members]` entry =
one scope.

**Discovery:**

```bash
# Enumerate all crates in a Cargo workspace
cargo metadata --no-deps --format-version 1 \
  | jq -r '.packages[] | select(.id | startswith("path+")) | .manifest_path' \
  | while read manifest; do
      crate_dir="$(dirname "$manifest")"
      crate_name="$(cargo metadata --no-deps --format-version 1 \
                    --manifest-path "$manifest" \
                    | jq -r '.packages[0].name')"
      echo "{\"kind\": \"cargo-crate\", \"primary_path\": \"$crate_dir\", \"name\": \"$crate_name\"}"
  done > "${session_dir}/scopes/cargo-discovery.jsonl"
```

**Linked artefacts (per-crate convention — adjust for project):**

- Spec: `docs/specs/${crate_name}.md` if exists, else workspace-level
  `docs/specs/${workspace}.md` with a section heading matching the
  crate name.
- ADRs: any ADR under `docs/adr/` (or `docs/decisions/`) that
  references the crate by name in its body.
- Threat model: any threat-model entry whose `TM-XXX-NNN` identifier
  references the crate, or the workspace-level threat model's section
  matching the crate name.
- Stories: any user story whose acceptance criteria reference the
  crate or its public types.

For finding linked artefacts cheaply:

```bash
crate_name="orchestrator"
rg -lF "$crate_name" docs/specs/ docs/adr/ docs/threat-models/ docs/stories/ 2>/dev/null
```

**Iteration log location:**

- Per-crate convention: `${crate_dir}/.iterate/iteration-log.md`.
- Workspace convention: `.iterate/iteration-log-${crate_name}.md`.
- Legacy: `${crate_dir}/.claude/iteration-log.md` or `docs/ITERATION-LOG-${crate_name}.md`.

Check all three in that order.

### 2. Language package (kind: `language-package`)

For non-Rust languages, the equivalent of a crate:

- **Python**: a directory containing `pyproject.toml` or `setup.py` (or
  a sub-package directory with `__init__.py` that's named in a top-
  level package's `pyproject.toml`'s `packages` field).
- **Go**: a directory containing `go.mod`, or a sub-package directory
  that's a `package` declaration with its own coherent surface.
- **TypeScript / Node**: a directory containing `package.json`, or a
  workspace member of a `pnpm-workspace.yaml` / `lerna.json` /
  `package.json#workspaces`.
- **Nix**: a flake output (`packages.${system}.<name>`) or a module
  directory with its own `default.nix`.
- **C**: typically not packaged per-directory; treat each component
  directory under `src/` or `lib/` with its own `Makefile` /
  `CMakeLists.txt` / `meson.build` section as a package.

**Discovery commands per language:**

```bash
# Python
find . -name 'pyproject.toml' -not -path '*/\.*' -not -path '*/node_modules/*' \
  | while read manifest; do
      pkg_name="$(grep -E '^name\s*=' "$manifest" | head -1 | awk -F'"' '{print $2}')"
      echo "{\"kind\": \"language-package\", \"language\": \"python\", \"primary_path\": \"$(dirname "$manifest")\", \"name\": \"$pkg_name\"}"
  done

# Go
find . -name 'go.mod' -not -path '*/\.*' \
  | while read manifest; do
      mod_path="$(awk '/^module/ {print $2; exit}' "$manifest")"
      echo "{\"kind\": \"language-package\", \"language\": \"go\", \"primary_path\": \"$(dirname "$manifest")\", \"name\": \"$mod_path\"}"
  done

# TypeScript / Node
find . -name 'package.json' -not -path '*/node_modules/*' -not -path '*/\.*' \
  | while read manifest; do
      pkg_name="$(jq -r .name "$manifest" 2>/dev/null)"
      [[ "$pkg_name" != "null" && -n "$pkg_name" ]] && \
        echo "{\"kind\": \"language-package\", \"language\": \"typescript\", \"primary_path\": \"$(dirname "$manifest")\", \"name\": \"$pkg_name\"}"
  done

# Nix flakes
test -f flake.nix && nix flake show --json 2>/dev/null \
  | jq -r '.packages | to_entries[] | .key as $sys | .value | to_entries[] | "{\"kind\": \"language-package\", \"language\": \"nix\", \"primary_path\": \".#packages.\($sys).\(.key)\", \"name\": \"\(.key)\"}"'
```

### 3. Feature area (kind: `feature-area`)

A scope that spans multiple crates/packages but represents one coherent
feature. The classic example: a user-facing feature whose backend is
in crate A, API contract is in crate B, frontend client is in crate C.

`iterate`'s guidance ("implement complete vertical slices") means
feature-area scopes are *often the right level*, not crate scopes —
especially for new features that crosscut.

**Discovery:**

Feature areas are inferred from:

- **Stories.** Every user story is a candidate feature area; its
  acceptance criteria define the scope's boundary.
- **Spec FR sections.** Each functional requirement (FR-NNN) in the
  spec is a candidate; its description identifies the touched
  components.
- **Branch-naming conventions.** If a branch is named
  `feature/<area>`, the changed files since fork-point define the
  scope.

```bash
# Stories with code references
find docs/stories/ -name '*.md' 2>/dev/null \
  | while read story; do
      story_id="$(basename "$story" .md)"
      # Find code files cited in the story
      code_refs="$(rg -oN '`([a-z_/]+\.rs|[a-z_/]+\.py|[a-z_/]+\.ts)`' "$story" | sort -u | tr '\n' ',')"
      [[ -n "$code_refs" ]] && \
        echo "{\"kind\": \"feature-area\", \"primary_path\": \"$story\", \"name\": \"$story_id\", \"code_refs\": \"$code_refs\"}"
  done

# Spec FRs as candidate feature areas
find docs/specs/ -name '*.md' 2>/dev/null \
  | xargs rg -oP '^##\s+(FR-\d+):\s+(.+)$' --no-filename \
  | while read line; do
      fr_id="$(echo "$line" | awk -F: '{print $1}')"
      title="$(echo "$line" | awk -F: '{print $2}' | sed 's/^\s*//')"
      echo "{\"kind\": \"feature-area\", \"name\": \"$fr_id\", \"title\": \"$title\"}"
  done
```

**Scope boundary determination:** for each feature-area candidate,
build the file-set by:

1. Collecting explicit code references from the artefact.
2. `rg` for any symbol mentioned in the artefact's acceptance criteria
   across the workspace.
3. Walking imports/uses one hop from those files.

The resulting file-set is the scope's `secondary_paths`. If the
file-set spans >5 crates, the scope is too large — flag for human
decomposition rather than dispatching as-is.

### 4. Feature branch (kind: `feature-branch`)

Every git branch other than the integration branch is a candidate
scope. The scope's content is the union of files changed in that
branch relative to fork-point.

**Discovery:**

```bash
integration_branch="$(git rev-parse --abbrev-ref HEAD)"
git for-each-ref --format='%(refname:short)' refs/heads/ \
  | grep -v "^${integration_branch}$" \
  | while read br; do
      fork="$(git merge-base "$integration_branch" "$br")"
      changed_files="$(git diff --name-only "$fork".."$br" | tr '\n' ',')"
      echo "{\"kind\": \"feature-branch\", \"name\": \"$br\", \"primary_path\": \"$br\", \"changed_files\": \"$changed_files\"}"
  done
```

**Hygiene rule:** if a feature branch has uncommitted local changes in
its worktree, do NOT dispatch it automatically — the dispatcher will
clobber user work. Flag in `${session_dir}/needs_human/` with a note.

### 5. GitLab issue / story (kind: `gh-issue`)

Open issues tagged with completion-tracking labels are first-class
scopes. The scope's content is whatever code is needed to satisfy the
issue's acceptance criteria.

**Discovery:**

```bash
# GitLab
project="<path-or-id>"
curl -sH "PRIVATE-TOKEN: $GITLAB_TOKEN" \
  "https://gitlab.com/api/v4/projects/${project}/issues?state=opened&labels=WIP,partial,needs-implementation&per_page=100" \
  | jq -c '.[] | {kind: "gh-issue", name: ("issue-" + (.iid|tostring)), title: .title, body: .description, url: .web_url, labels: .labels}'

# GitHub
gh issue list --label WIP,partial,needs-implementation --state open \
  --json number,title,body,labels,url \
  | jq -c '.[] | {kind: "gh-issue", name: ("issue-" + (.number|tostring)), title, body, url, labels: [.labels[].name]}'
```

For these scopes, the body of the issue is the spec; if it doesn't
reference an actual spec/ADR/story, the scope is `needs_all_aboard:
true`.

### 6. ADR section / spec FR / story (kinds: `adr-section`, `spec-fr`, `story`)

The finest-grained scopes: each individual ADR's Decision against its
implementation, each spec FR row against its claimed status, each
story's acceptance criteria.

These are typically used when iterating *late* in a project — most
gaps have closed and the remaining work is verifying specific
artefact-implementation alignments.

**Discovery:**

```bash
# Each ADR
find docs/adr docs/decisions -name '*.md' 2>/dev/null \
  | while read adr; do
      adr_id="$(basename "$adr" .md | grep -oE '^[0-9]+' | head -1)"
      status="$(grep -iE '^\s*status:' "$adr" | head -1 | awk -F: '{print $2}' | xargs)"
      [[ "$status" =~ ^(accepted|proposed)$ ]] && \
        echo "{\"kind\": \"adr-section\", \"name\": \"ADR-$adr_id\", \"primary_path\": \"$adr\"}"
  done

# Each spec FR
find docs/specs -name '*.md' 2>/dev/null \
  | xargs rg -oP '^\|\s*(FR-\d+)\s*\|\s*([^|]+)\s*\|\s*(Partial|Draft|Implemented)\s*\|' \
  | awk -F: '{print $2}' \
  | while read row; do
      fr_id="$(echo "$row" | grep -oP 'FR-\d+')"
      status="$(echo "$row" | grep -oP '(Partial|Draft|Implemented)')"
      [[ "$status" != "Implemented" ]] && \
        echo "{\"kind\": \"spec-fr\", \"name\": \"$fr_id\", \"status\": \"$status\"}"
  done

# Each story
find docs/stories -name '*.md' 2>/dev/null \
  | while read story; do
      story_id="$(grep -m1 -oP 'STORY-\d+' "$story" || basename "$story" .md)"
      status="$(grep -iE '^\s*status:' "$story" | head -1 | awk -F: '{print $2}' | xargs)"
      [[ "$status" != "Implemented" && "$status" != "Done" ]] && \
        echo "{\"kind\": \"story\", \"name\": \"$story_id\", \"primary_path\": \"$story\", \"status\": \"$status\"}"
  done
```

## Filter rules

After enumeration, filter the candidate scope list:

### Skip rules

1. **Recently complete and clean.** If `last_iterate_status` says
   "complete (YYYY-MM-DD): all Step 6 criteria passed, stop hook
   confirmed." within the last 7 days, AND `git log
   ${last_complete_commit}..HEAD -- <scope paths>` is empty, AND Phase
   3's stop-bias scan against the scope returns zero findings →
   `skipped_recently_complete`.

2. **User-excluded.** Match against `--exclude` arguments;
   skip records of those scopes.

3. **Out-of-tree.** Scopes pointing to paths outside the repo root
   (e.g., a `cargo-crate` discovered via path that's a sibling repo)
   are filtered with a warning.

4. **Vendored / third-party.** Skip scopes under `vendor/`,
   `third_party/`, `node_modules/`, `target/`, `dist/`, `build/`,
   `.venv/`. Configurable via `.iteratotron.yaml` (analogous to
   `.iterate.json`).

### Surface-but-don't-auto-queue rules

1. **Dirty working tree.** Scope's path has uncommitted changes → put
   in `${session_dir}/needs_human/`, do not auto-queue.

2. **Scope too large.** A feature-area scope spanning >5 crates is too
   large for one iterate dispatch — record as `requires_decomposition:
   true`, surface in the report.

3. **No linked artefacts AND no `needs_all_aboard` indication.** The
   scope is real code but has no spec/ADR/threat-model AND the user
   hasn't said "create them". Surface for user decision before
   dispatching.

### Configuration via `.iteratotron.yaml`

Per-project config, sibling to `.iterate.json`:

```yaml
# .iteratotron.yaml
scopes:
  include:
    - kind: cargo-crate
    - kind: feature-area
  exclude:
    - kind: feature-branch
    - path: "crates/legacy-*"
    - path: "vendor/"

filters:
  skip_recently_complete_days: 7
  max_scope_crate_span: 5
  treat_dirty_as: surface  # surface | skip | queue

dispatch:
  default_parallelism: 3
  per_scope_timeout_min: 90
  session_timeout_hours: 4
```

The skill reads this file at Phase 1 if present.

## Deduplication of scope candidates

After enumeration, the same code can be claimed by multiple scope
kinds: a story scope and a feature-area scope and a feature-branch
scope may all cover the same files. Resolve overlaps:

1. **Priority order**: `feature-area` > `story` > `spec-fr` >
   `cargo-crate` > `language-package` > `feature-branch` > `gh-issue`
   > `adr-section`. Higher-priority kinds preserve the scope; lower-
   priority kinds covering the same file-set are merged in as
   `related_scopes`.
2. **Cargo-crate atomicity**: a cargo-crate scope is *never* dropped,
   even if a feature-area also covers part of it. The feature-area
   scope is preferred for dispatch, but the cargo-crate scope is
   retained as a fallback record (e.g., if the feature-area completes
   but lint gates only run at crate granularity).

The result is a clean candidate list where each file belongs to one
"primary" scope, with `related_scopes` pointers for cross-reference.

## What goes into Phase 3 (gap audit)

The output of scope discovery is a list of records. Phase 3 reads each
record, walks its `primary_path` + `secondary_paths`, and runs the
gap-audit pipeline (four-kind gap inventory + stop-bias-pattern scan).
At that point, the scope record gets enriched with a gap inventory and
becomes a queue entry candidate.

The scope-discovery output should not include speculative gap counts.
Gap counts come from Phase 3's actual scan; mixing the two phases
makes the queue noisy.
