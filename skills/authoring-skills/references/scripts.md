# Scripts, tools, and dependencies

Applies to anything under `scripts/` and to skills that drive CLIs or MCP tools.
Follow the target project's shell conventions if any. Baseline for bash helpers:
start with `set -Eeuo pipefail`; pass untrusted input as a field value, not
interpolated into a command string; never `[ -f glob* ]` (`[ ]` doesn't glob; use
a `for` loop or `compgen -G`); run `shellcheck`.

## When to ship a script

Ship one when a step is deterministic, error-prone to regenerate, or checked
repeatedly. A pre-made script is more reliable than regenerated code, costs no
context tokens for its body (only its output), and behaves the same every run.
Prefer a validator script over prose for critical checks.

## Run or read?

Say which in the instructions:

- Run: "Run `scripts/analyze.sh input > fields.json` to extract fields."
- Read: "See `scripts/analyze.sh` for the extraction algorithm."

Document usage, flags, and output format next to the command. Paths are
relative to the skill root.

## Solve, don't defer

Handle expected errors in the script (missing file, bad permission, empty
input) with a clear message or a sane fallback instead of crashing and leaving
the agent to guess. Make validators verbose and specific so the agent can fix
the cause on the next loop.

## Justify constants

No unexplained magic numbers. If a timeout, retry count, or threshold exists,
comment why that value. If you can't justify it, the agent can't tune it.

## Verifiable output

For batch or high-stakes operations, have the script emit an intermediate plan
file, validate it, then apply (see *Workflows and feedback loops* in
`body-patterns.md`). Where inputs can be rendered as images, a render step lets
a vision-capable agent inspect layout.

## Dependencies and tools

- Never assume a package or CLI is installed: name it and give the install
  command, or say how to detect it.
- Some runtimes have no network or package installation *(Claude API sandbox)*;
  state such requirements in a body "Prerequisites" line (see `compatibility` in
  [frontmatter.md](frontmatter.md); gitlab-org/ai/skills convention in
  [gitlab-skills-repo.md](gitlab-skills-repo.md)).
- Reference MCP tools by fully qualified name, `ServerName:tool_name`
  *(Claude-specific syntax)*; in other agents use that agent's naming. Unqualified
  names fail when several servers are connected.
- Check tool-name casing against the server docs.

## Portability: Linux and macOS

Skill scripts run on whatever machine the agent's user has, and macOS is common.
It ships **bash 3.2** (the last GPLv2 release) and **BSD** userland, so a script
that passes on a Linux CI box can fail on a laptop. Target bash 3.2 plus POSIX
tools unless the skill states a newer requirement.

- Start with `#!/usr/bin/env bash`, not `#!/bin/bash`: the latter pins the
  system bash, which is 3.2 on macOS even when a newer one is installed.
- Don't send stderr to `/dev/null` in tests; see *Testing portability* below.

### Bash 3.2 traps

Checked against `bash:3.2` and `bash:5` Docker images:

| Don't use | Bash 3.2 does | Use instead |
|---|---|---|
| `$BASHPID` (4.0+) | Unset: fatal under `set -u` (`BASHPID: unbound variable`) | `$$` for the main shell PID. `${BASHPID:-$$}` avoids the crash, but on 3.2 it is always the main PID, so it can't tell a subshell from the main shell: don't build traps (e.g. an `ERR` dedupe guard) on it; accept duplicate messages. Dropping `-E` also stops the `ERR` trap firing inside functions, and `set -Eeuo pipefail` is the baseline |
| `declare -A` (4.0+) | Prints `invalid option` and returns 2. Under `set -e` the script stops there; without it, `m[key]=...` silently treats `m` as an indexed array (every string key is index 0) | Parallel arrays, or a `case` lookup |
| `mapfile` / `readarray` (4.0+) | `command not found` | `while IFS= read -r line; do arr+=("$line"); done < <(cmd)` |
| `${v,,}` / `${v^^}` (4.0+) | `bad substitution` | `tr '[:upper:]' '[:lower:]'` |
| `wait -n` (4.3+) | `invalid option` | `wait` on each PID, or poll with `kill -0` |
| `${a[-1]}` (not in 3.2) | `bad array subscript`, expands empty | `${a[${#a[@]}-1]}` |
| `\|&`, `&>>`, `;&` in `case` (4.0+) | Syntax error | `2>&1 \|`, `>> f 2>&1`, `;;` with duplicated bodies |
| `printf '%(%s)T'` (4.2+) | `invalid format character` (also on 4.0 and 4.1) | `date +%s` |
| `${v@Q}` (4.4+) | `bad substitution` (also on 4.3) | `printf '%q' "$v"` |
| `$EPOCHSECONDS` (5.0+) | Unset: fatal under `set -u` (also on 4.3 and 4.4) | `date +%s` |
| `"${arr[@]}"` on an empty array under `set -u` (fixed in 4.4) | `arr[@]: unbound variable` | `${arr[@]+"${arr[@]}"}`, or check `${#arr[@]}` first |

The empty-array failure also reproduces on bash 4.3, so it can bite Linux
distros that ship older bash too. Beware that a `trap` body is only evaluated
when it fires: an unsupported variable inside it can pass every happy-path test.

### BSD vs GNU tools

macOS tools differ from GNU. These are well-known differences (not reproduced
here, since the Docker images are Linux): check on a Mac when in doubt.

- `sed -i`: BSD requires a suffix argument. `sed -i.bak 's/a/b/' f && rm f.bak`
  works on both.
- `date -d '1 day ago'`: GNU only. BSD uses `date -v-1d`. Avoid date arithmetic
  in shell; use `python3` or accept epoch seconds from the caller.
- `readlink -f`: missing on older macOS; current macOS documents it, but check
  the minimum version you need. For the script's directory use
  `script_dir=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)`
  (empty `CDPATH` stops `cd` printing the path); it does not follow a symlinked
  script.
- `grep -P`: not available on macOS grep (and busybox). Use `grep -E`.
- `stat`: flags differ (`-c` vs `-f`). Avoid; use `wc -c < file` for size, but BSD `wc` pads the
  number with spaces: compare with `-eq` or normalise with `$(( $(wc -c < f) ))`.
- `mktemp`: `mktemp -d` works on both; GNU-only options such as `--suffix` do not.
  Pass an explicit template: `mktemp "${TMPDIR:-/tmp}/name.XXXXXX"`.
- `timeout` (and `gtimeout`) is not installed on macOS by default. Detect it
  with `command -v` and fall back, or document the dependency.
- `xargs -r`: keep it. GNU xargs runs the command once on empty input without
  it (verified); BSD xargs accepts `-r` and already skips empty input.
- `cp --parents` and `find -printf` are GNU extensions; use POSIX flags.

### Other script types

- **POSIX `sh`** (`#!/bin/sh`): no arrays, `[[ ]]`, `local` guarantees, or
  `<(...)`. Run `shellcheck -s sh` and test under `dash` or busybox.
- **Python**: use `#!/usr/bin/env python3`; macOS has no `python` command by
  default. Stick to the stdlib and say which minimum version you need.

### Testing portability

- Run the script under old and current bash:
  `docker run --rm -v "$PWD:/w:ro" -w /w bash:3.2 bash path/to/script.sh`
  and again with `bash:5`. Add `bash:4.3` if empty-array expansion matters.
- Keep stderr visible in tests: assert it is empty, or capture and print it.
  Discarding it (`2>/dev/null`) hid a `BASHPID: unbound variable` on every poll
  of a real helper, so the suite passed while the script was broken on macOS.
- Exercise cleanup paths (`trap`, error exits), not just the happy path.
- The Docker bash images use busybox tools, so they cover the bash language
  but not BSD tool behaviour; BSD flags need a real macOS run.
