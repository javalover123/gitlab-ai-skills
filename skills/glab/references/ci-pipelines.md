# CI/CD Pipelines (`glab ci`)

How to read pipeline state from a script or an agent, and which of
`glab ci status` / `glab ci get` answers which question.

The behavior below was checked against `glab 1.118.0` and the command source at
[`v1.118.0`](https://gitlab.com/gitlab-org/cli/-/blob/v1.118.0/internal/commands/ci/status/status.go).
Some TTY and polling cases are source-checked, not live-tested.

## Which command

| You must … | Use |
|---|---|
| Get a verdict in a script, by exit code | `GLAB_NO_PROMPT=1 glab ci status --compact` |
| Parse pipeline and job fields | `glab ci status -F json` |
| Address one pipeline by ID | `glab ci get -p <id>` |
| Address the head pipeline of an MR | `glab ci get --merge-request <iid>` |
| Block until the pipeline finishes | `glab ci status --wait` |
| Watch a pipeline at a terminal | `glab ci status --live` |
| Read one job log | `glab ci trace <job-id \| job-name>` |
| List or filter many pipelines | `glab ci list --status=failed` |

`glab ci view` is a full-screen TUI. It has no output format flag. Do not start
it from an agent.

## `glab ci status`: what it selects

`--branch/-b` is the only selector. There is no `--pipeline-id` and no
`--merge-request`.

1. With no `-b`, glab uses the current git branch. Outside a repository, or when
   the branch is unknown, it uses the project default branch. `-R <other/repo>`
   does **not** change this: glab keeps your local branch name and looks for that
   branch in the other project.
2. glab reads the **newest** pipeline for that ref. You cannot select an older
   pipeline on the same ref.
3. If that lookup fails or the pipeline has no jobs, glab may fall back to the
   head pipeline of an MR with that source branch. Do not rely on the fallback:
   when no push pipeline exists (MR-pipeline-only projects), `-b` can return the
   MR pipeline. When several MRs share a branch, including merged MRs, MR lookup
   can fail with prompts off and glab can keep a skipped, job-less push pipeline.
   With prompts enabled it may ask you to pick an MR.
4. If nothing resolves, the command reports `no pipeline found …` and exits 1.

A push pipeline and an MR pipeline can finish at different times. `-b <branch>`
can return either one. For an MR verdict use `glab ci get --merge-request <iid>`;
for a specific pipeline use `glab ci get -p <id>`. A full
`refs/merge-requests/<iid>/head` ref is accepted by `-b`, but rule 2 still applies.

## The interactive menu (agent hazard)

In text or `--compact` mode, `glab ci status` prints the job list and then opens
a `Choose an action:` menu with `View logs`, `Retry` and `Exit` when stdin, stdout
and stderr are all TTYs and prompts are enabled. Without `--live`, it opens even
for a running pipeline; with `--live`, it opens once the pipeline ends. It blocks
until somebody answers, and `Retry` retries the whole pipeline, so a read command
can start a write.

Any one of these turns off the menu:

- `GLAB_NO_PROMPT=1` (or the `no_prompt` config key): the agent-safe default;
  it also disables other glab prompts, including the MR picker during fallback.
- `--wait`, which sets `live` and disables prompts.
- `-F json`, which returns before the menu.
- Redirecting stdin, stdout or stderr away from the terminal.

## Blocking

`--wait` polls every 3 seconds until the pipeline reaches a state that does not
change by itself. It returns immediately for `success`, `failed`, `canceled`,
`skipped` and `manual`. A pipeline that is blocked on a manual job is **not**
waited for.

While polling with `--live` or `--wait`, a pipeline that becomes `canceled` makes
glab look for a newer pipeline on the same branch and follow it. This keeps the
command attached across an auto-cancel from a rebase or a new push.

## Exit codes

| Command | Pipeline failed | Any other state | No pipeline |
|---|---|---|---|
| `glab ci status` (text or `--compact`) | 1, no message | 0 | 1 with a message |
| `glab ci status -F json` | **0** | 0 | 1 with a message |
| `glab ci get` (any format) | **0** | 0 | non-zero |

Only the literal state `failed` sets the exit code. A `canceled`, `skipped` or
`manual` pipeline exits 0 from every one of these commands. Test the status field
when you need more than pass/fail.

The exit code is a property of the command, not of the pipeline. On one and the
same failed pipeline, `glab ci status -b <ref>` exits 1 while
`glab ci get -p <id>` exits 0. There are three ways to lose the signal: change to
`ci get`, add `-F json`, or both. An agent that moves to `ci get` for `-p` or
`--merge-request` addressability must then read `.status` itself.

Exit 1 is also overloaded: a red pipeline and a failed lookup both give it.
**Separate them by stdout.** A resolved pipeline prints `Pipeline state: <status>`
even in `--compact` mode; a failed lookup prints a `✘ …` error line there
instead (usually `no pipeline found …`). Do not test for empty stderr: glab can
write update notices or update-check errors on any command, with or without a
TTY.

```bash
if OUT=$(GLAB_NO_PROMPT=1 glab ci status --compact); then
  echo "not failed: $(grep '^Pipeline state:' <<<"$OUT")"
elif grep -q '^Pipeline state: failed' <<<"$OUT"; then
  echo "pipeline is red"
else
  echo "could not resolve a pipeline"
fi
```

## JSON shapes differ between the two commands

```bash
# ci status wraps the pipeline: {"pipeline": {...}, "jobs": [...]}
glab ci status -F json --jq '.pipeline.status'   # → failed
glab ci status -F json --jq '.status'            # → null, exit 0

# ci get returns the pipeline object itself
glab ci get -p 2866467485 -F json --jq '.status' # → failed
```

A jq filter moved from one command to the other returns `null` at exit 0 instead
of failing. Always check which command produced the document.

Two more rules on these flags:

- `--jq` needs `--output json`. Without it the command exits 1 and writes to
  stderr: `Using --jq requires --output=json (got "text").` This holds for every
  glab subcommand, `glab issue list` and `glab mr list` included. Match the text
  case-insensitively: the Go error is lowercase `using …` with no period, and
  glab's error renderer capitalizes the first letter and adds the period.
- `-F json` cannot be combined with `--live`, `--wait` or `--compact`. glab exits
  1 with `--output json cannot be used with --live, --wait, or --compact flags`.

## `glab ci get` job filters

`--status` filters the **jobs** of the selected pipeline. It does not select a
pipeline by status. `glab ci get --merge-request=42 --status=failed` on a
successful pipeline prints the pipeline and an empty job list, at exit 0. Read it
as "failed jobs of MR 42's head pipeline", never as "the failed pipeline of MR 42".

Add `-d`/`--with-job-details` for job URLs, durations and stages.

## Live flag lists

Run `glab ci status --help` and `glab ci get --help` for the live flag lists.
