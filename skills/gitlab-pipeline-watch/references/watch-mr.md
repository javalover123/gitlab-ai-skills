# watch_mr.py and mr_state.py: watch one MR at the job level

`scripts/watch_mr.py` polls one MR and returns on the **first** thing that
needs attention, including a blocking job failing while the rest of the
pipeline still runs. Each poll is a `scripts/mr_state.py` snapshot. Both are
read-only. Every flag is documented in the script's docstring
(`python3 scripts/watch_mr.py --help`).

## Snapshot (`mr_state.py [--files] <mr-url>`)

| Field | Notes |
|-------|-------|
| `state`, `sha`, `source_branch`, `target_branch`, `author`, `title`, `web_url` | The MR. `sha` is the MR head. |
| `auto_merge`, `merge_user`, `detailed_merge_status`, `merge_error` | Merge state. `auto_merge` is `merge_when_pipeline_succeeds`. |
| `pipeline` | Latest MR pipeline: `id`, `status`, `ref`, `sha`, `web_url`, and `kind`: `merged_result`, `detached`, `merge_train`, or `branch`. `null` if none. |
| `failed_jobs` | Blocking failures only: not `allow_failure`, not superseded by a retry. `id`, `name`, `stage`, `failure_reason`, `web_url`. |
| `failed_bridges` | Failed trigger jobs; the real failure is in `downstream_pipeline_id` of `downstream_project_id`. |
| `blocking_failure_count` | `len(failed_jobs) + len(failed_bridges)` |
| `changed_files` | With `--files`: every old and new path the MR touches. |
| `host`, `project`, `project_encoded`, `mr_iid` | For follow-up calls: `glab api --hostname <host> "projects/<project_encoded>/…"`. `host` comes from the MR URL. |

`pipeline.sha` is **not** the MR head: a merged-results pipeline runs on a
temporary merge commit. Compare the MR's `sha`.

## Watching

```bash
python3 scripts/watch_mr.py [--expect-sha SHA] [--auto-merge] [--newer-than ID] \
  [--seen IDS] [--grace N] [--mr-only] <mr-url>
```

It polls every 60 seconds and returns after about 8 minutes (`TIMEOUT`), so
one call fits a 10-minute tool limit. Raise `--timeout` if your agent allows
longer blocking calls. A timeout is never a failure: watch again.

| Flag | Use when |
|------|----------|
| `--expect-sha SHA` | Someone else's MR: a push should stop you (`SHA_CHANGED`). Omit it when you push fixes yourself. |
| `--auto-merge` | The MR is set to auto-merge: emits `AUTO_MERGE_OFF` if that's canceled, and keeps waiting through green until `MERGED`. |
| `--newer-than ID` | Right after pushing: ignores pipeline `ID` and older, and emits `NO_NEW_PIPELINE` if no newer one appears this call. Record `pipeline.id` **before** pushing so a fast pipeline isn't missed. |
| `--seen IDS` | Failed job/bridge IDs you already triaged, so they don't trigger `NEW_FAILURE` again. |
| `--grace N` | Right after retrying a pipeline (`--grace 120`): it can still read as failed for a moment. |
| `--mr-only` | Waiting on something else (an incident) while the pipeline sits failed: only MR changes return early. |

## Events

| Event | Meaning |
|-------|---------|
| `MERGED` / `CLOSED` | The MR left the open state. |
| `SHA_CHANGED` | (`--expect-sha`) The head moved: new commits were pushed. |
| `AUTO_MERGE_OFF` | (`--auto-merge`) Canceled by a person, or dropped from a merge train. |
| `NEW_FAILURE` | A blocking job failed; the pipeline is still running. |
| `PIPELINE_SUCCESS` | Green. Not emitted with `--auto-merge`, which waits for `MERGED`. |
| `PIPELINE_FAILED` / `_CANCELED` / `_SKIPPED` / `_MANUAL` | The pipeline stopped. `failed_jobs` can be empty on `PIPELINE_FAILED` (e.g. a CI config error). |
| `NO_PIPELINE` | The MR has no pipeline. |
| `NO_NEW_PIPELINE` | (`--newer-than`) No newer pipeline yet. Watch again until your own deadline. |
| `API_ERROR` | Three polls in a row failed; GitLab may be erroring. Carries the last good snapshot and `api_error`. |
| `TIMEOUT` | Nothing actionable yet. |

The output is the last snapshot plus `event`, so you rarely need a second
`mr_state.py` call to act on it.

## Job logs

```bash
python3 scripts/job_log_tail.py --hostname <host> <project_encoded> <job_id> [lines]   # default 150
```

Pass the snapshot's `host` so the call can't follow a different checkout's
instance. Prints job metadata as JSON, then the last N non-blank log lines with ANSI
colors, timestamps, and section markers stripped.

## From another skill

Skills that depend on this one (`gitlab-babysit-mr`, `gitlab-retry-until-merged`)
load it and run these scripts from **this skill's directory**, which they call
`$WATCH`:

- `$WATCH` is the directory holding this skill's `SKILL.md`. Claude Code shows it
  as the skill's base directory when the skill loads; other agents know the
  folder they read `SKILL.md` from.
- Shell variables don't persist between tool calls, so set it in every command:
  `WATCH=/path/to/gitlab-pipeline-watch; python3 "$WATCH/scripts/watch_mr.py" …`.
  An unset `$WATCH` silently becomes `/scripts/…`.
- If the skill can't be loaded, or `$WATCH/scripts/watch_mr.py` doesn't exist,
  it isn't installed: stop and ask the user to install `gitlab-pipeline-watch`
  (Claude Code: `/plugin install gitlab-pipeline-watch@gitlab-skills`). Don't
  recreate the scripts.
