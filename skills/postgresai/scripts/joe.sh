#!/usr/bin/env bash
# Run `postgresai joe <args>` and wait for the result if the CLI's poll budget
# expires first. Usage: joe.sh <joe-subcommand> [args...]
# Env: JOE_WAIT_SECONDS (default 600) total wait; JOE_POLL_MAX_SECONDS (default 15) max sleep.
set -Eeuo pipefail
# Report once: errtrace makes the trap fire in command substitutions too, so only the main shell prints.
trap 'if [ "$BASHPID" = "$$" ]; then echo "joe.sh: failed at line $LINENO" >&2; fi' ERR

wait_limit="${JOE_WAIT_SECONDS:-600}"
max_sleep="${JOE_POLL_MAX_SECONDS:-15}"

for arg in "$@"; do
  if [ "$arg" = "--json" ]; then
    echo "joe.sh is text-only: run 'postgresai joe ... --json' directly and poll 'postgresai joe result <id> --json' (exit 1, \"status\":\"pending\" while running)." >&2
    exit 2
  fi
done

output="$(postgresai joe "$@")"

# Budget expired: "started <id> · pending · budget Ns reached — resume: pgai joe result <id>"
pending_id="$(printf '%s\n' "$output" | sed -nE 's/^started ([0-9]+) .*pending.*/\1/p' | head -n 1)"
if [ -z "$pending_id" ]; then
  printf '%s\n' "$output"
  exit 0
fi

delay=1
waited=0
while [ "$waited" -lt "$wait_limit" ]; do
  sleep "$delay"
  waited=$((waited + delay))
  # `result` exits 1 while the command is still pending.
  if output="$(postgresai joe result "$pending_id" 2>&1)"; then
    printf '%s\n' "$output"
    exit 0
  fi
  # Only the status header on the first line counts; the body may echo SQL errors.
  case "$(printf '%s\n' "$output" | head -n 1)" in
    "command $pending_id · pending"*) ;;
    *) printf '%s\n' "$output" >&2; exit 1 ;;
  esac
  delay=$((delay * 2 > max_sleep ? max_sleep : delay * 2))
done

echo "joe.sh: command $pending_id still pending after ${wait_limit}s; fetch later: postgresai joe result $pending_id" >&2
exit 1
