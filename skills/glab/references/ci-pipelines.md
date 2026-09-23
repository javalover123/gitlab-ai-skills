# CI/CD Pipelines (`glab ci`)

How to read pipeline state from a script or an agent, and which of
`glab ci status` / `glab ci get` answers which question.

All behavior below was checked against `glab 1.118.0` and the command source in
[`gitlab-org/cli`](https://gitlab.com/gitlab-org/cli/-/blob/main/internal/commands/ci/status/status.go).

## Which command

| You must … | Use |
|---|---|
| Get a verdict in a script, by exit code | `glab ci status --compact` |
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
3. If that pipeline has no jobs (for example a detached or merged-results
   pipeline), glab finds the merge request whose source branch matches and uses
   its head pipeline instead.
4. If both lookups fail, the command prints `no pipeline found for branch …` and
   exits 1.

A full `refs/merge-requests/<iid>/head` ref is accepted by `-b`, but rule 2 still
applies: you get the newest pipeline on that ref, not the one you have in mind.
Use `glab ci get -p <id>` when the pipeline identity matters.

## The interactive menu (agent hazard)

When stdin is a TTY and the pipeline is not running, `glab ci status` prints the
job list and then opens a `Choose an action:` menu with `View logs`, `Retry` and
`Exit`. It blocks until somebody answers. `Retry` retries the whole pipeline, so
a read command can start a write.

Verified with a pseudo-terminal, `glab 1.118.0`:

| Invocation | With a TTY | Without a TTY |
|---|---|---|
| `glab ci status` | blocks on the menu | prints and exits |
| `glab ci status --compact` | blocks on the menu | prints and exits |
| `glab ci status --live` | blocks on the menu after the pipeline ends | prints and exits |
| `glab ci status --wait` | prints and exits | prints and exits |
| `glab ci status -F json` | prints and exits | prints and exits |

`--wait` is the only flag that turns the menu off: it sets `live` and disables
prompts. Redirecting stdin (`< /dev/null`) also removes the TTY and gives the
one-shot behavior.

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
**Separate them by stderr**, which is the reliable test. A red pipeline writes
nothing to stderr. Every lookup failure writes an `ERROR` block there — a project
that does not exist, a project you cannot read, and a branch with no pipeline all
produce the same shape, because GitLab answers 404 for a missing and an
unreadable project alike.

```bash
ERR=$(mktemp)
if glab ci status --compact 2>"$ERR"; then
  echo "green"
elif [ -s "$ERR" ]; then
  echo "could not resolve a pipeline"; cat "$ERR"
else
  echo "pipeline is red"
fi
```

The status line is a confirmation, not a test, and it needs care: stdout ends
with a **blank** line, so `tail -1` gives you an empty string.

```bash
glab ci status | tail -1                            # → "" , reads as falsy
glab ci status | grep -v '^[[:space:]]*$' | tail -1  # → Pipeline state: failed
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

- `--jq` needs `--output json`. Without it the command exits 1 with
  `Using --jq requires --output=json (got "text")`. This holds for every glab
  subcommand, `glab issue list` and `glab mr list` included.
- `-F json` cannot be combined with `--live`, `--wait` or `--compact`. glab exits
  1 with `--output json cannot be used with --live, --wait, or --compact flags`.

## `glab ci get` job filters

`--status` filters the **jobs** of the selected pipeline. It does not select a
pipeline by status. `glab ci get --merge-request=42 --status=failed` on a
successful pipeline prints the pipeline and an empty job list, at exit 0. Read it
as "failed jobs of MR 42's head pipeline", never as "the failed pipeline of MR 42".

Add `-d`/`--with-job-details` for job URLs, durations and stages.

## Live flag lists

Claude Code injects these; other agents run the commands.

!`glab ci status --help`

!`glab ci get --help`
