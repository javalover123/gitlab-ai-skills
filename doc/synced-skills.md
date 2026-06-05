# Synced skills

Some skills in this repo have their **source of truth (SSoT) in another
repository**. This repo is only the destination: the canonical copy is edited
upstream and pulled in here automatically. This document explains the mechanism
and how to maintain the bot token behind it.

## Concept

A *synced skill* is listed in [`synced-skills.yml`](../synced-skills.yml). For
each entry the manifest records where the SSoT lives:

```yaml
skills:
  glab:
    source_project: gitlab-org/gitlab        # SSoT repo
    source_path: .claude/skills/glab         # path within that repo
    source_ref: master                       # branch/tag/ref to track
    mode: mr                                  # mr | direct
```

Two pieces enforce the model:

1. **Inbound sync** (`sync-skills` CI job, scheduled) — pulls the upstream copy
   in and opens an MR.
2. **Edit guard** (`guard-synced-skills` CI job, merge requests) — fails any MR
   that edits a synced skill directly, pointing the author at the SSoT.

## The sync job

`scripts/sync_external_skills.py` does the content mirroring (no git/MR side
effects, so it is testable in isolation):

- Lists the source skill tree via `glab api` and mirrors every file into
  `skills/<name>/`.
- **Removes** local files that no longer exist upstream (so deletions sync too).
- Adopts the upstream `version` — synced skills are **not** version-bumped here.
- Runs `lefthook run auto-fix` to regenerate README / ToC / catalog /
  distribution manifests.

The `sync-skills` CI job wraps it with the git ceremony: create a `sync/*`
branch, commit, push, and `glab mr create`. With `mode: mr` it opens an MR for
review; `mode: direct` would commit straight to the default branch (not used
today).

Run it locally to preview drift:

```sh
glab auth status                                   # must be authenticated
scripts/sync_external_skills.py --check            # report drift, exit 1 if any
scripts/sync_external_skills.py --skill glab       # apply for one skill
```

### Scheduling

Create a **pipeline schedule** (Build → Pipeline schedules) on the default
branch with CI variable `SCHEDULE_TYPE=sync_skills`. The `sync-skills` job only
runs when `$CI_PIPELINE_SOURCE == "schedule"` and that variable is set, so the
schedule can coexist with any other scheduled pipelines.

To trigger a sync on demand, run a manual pipeline (Build → Pipelines → Run
pipeline) on the default branch with variable `RUN_SYNC=true`.

## The edit guard

`scripts/check_synced_skills_untouched.sh` runs on merge request pipelines. It
diffs the MR against its target branch and fails if any changed path falls under
a synced skill directory. The sync bot's own MR is exempt because it:

- runs as the project access token bot (`GITLAB_USER_LOGIN` matches
  `project_<id>_bot_<hex>`), **and**
- pushes from a `sync/*` branch.

## Bot token (maintenance)

The sync job authenticates as a **project access token** so its commits/MRs are
attributable to a bot and the guard can recognize them.

| Property | Value |
|---|---|
| Token name | `skills-sync-bot` |
| Token id | `24341787` |
| Bot user | `project_80188013_bot_03b2e04f243ae78d02a9f6169e37eb65` |
| Scope | `api` |
| Role | Developer (`access_level=30`) |
| Expiry | yearly — **must be rotated before it lapses** |

`api` scope + Developer is the least privilege that still allows pushing a
`sync/*` branch and creating an MR. Developer cannot push to protected `main`,
which is correct — the bot opens an MR, it never pushes to `main`.

### CI variables

| Key | Masked | Protected | Purpose |
|---|---|---|---|
| `SYNC_BOT_TOKEN` | yes | no | the project access token value |
| `SYNC_BOT_EMAIL` | no | no | git author email for the sync commit |
| `SYNC_BOT_NAME` | no | no | git author name for the sync commit |

`SYNC_BOT_TOKEN` is **unprotected** on purpose: the sync job runs on `sync/*`
branches, which are not protected, so a protected variable would not be exposed
to it.

### Creating or rotating the token

You need Owner/Maintainer on the project. The token value is shown **only once**
— pipe it straight into the CI variable, never to stdout.

Create:

```sh
printf '{"name":"skills-sync-bot","scopes":["api"],"access_level":30,"expires_at":"YYYY-MM-DD"}' \
  | glab api -X POST "projects/gitlab-org%2Fai%2Fskills/access_tokens" \
      -H "Content-Type: application/json" --input -
```

Rotate (before expiry) and update the CI variable in one shot:

```sh
NEWTOKEN="$(glab api -X POST \
  'projects/gitlab-org%2Fai%2Fskills/access_tokens/24341787/rotate' \
  -H 'Content-Type: application/json' --input - <<<'{"expires_at":"YYYY-MM-DD"}' \
  | jq -r '.token')"

glab api -X PUT 'projects/gitlab-org%2Fai%2Fskills/variables/SYNC_BOT_TOKEN' \
  --field "value=$NEWTOKEN"
NEWTOKEN=""
```

If the bot user changes (a fresh token = same bot user; a brand-new token may be
a new bot user), update the `SYNC_BOT_EMAIL` value and the bot user reference
above. The guard regex (`project_<id>_bot_<hex>`) is format-based and does not
need per-rotation changes.
