#!/usr/bin/env bash
# Tests scripts/joe.sh with a stubbed `postgresai` on PATH. No network.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
joe="$here/../scripts/joe.sh"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
failures=0

cat > "$tmp/postgresai" <<'STUB'
#!/usr/bin/env bash
# Behavior driven by STUB_MODE; STUB_STATE counts `result` calls.
echo "$*" >> "$STUB_DIR/calls"
if [ "$2" = "result" ]; then
  n=$(($(cat "$STUB_DIR/state" 2>/dev/null || echo 0) + 1)); echo "$n" > "$STUB_DIR/state"
  if [ "$n" -ge "${STUB_READY_AFTER:-2}" ]; then echo "command 42 · ok"; echo "plan: done"; exit 0; fi
  echo "${STUB_RESULT_ERR:-command 42 · pending — result is not ready}" >&2; exit 1
fi
if [ "$STUB_MODE" = "pending" ]; then
  echo "started 42 · pending · budget 25s reached — resume:  pgai joe result 42"; exit 0
fi
echo "command 41 · ok"; echo "plan: fast"
STUB
chmod +x "$tmp/postgresai"

run() { # name expected_rc expected_output_substring; remaining env set by caller
  local name="$1" want_rc="$2" want_out="$3" out rc=0
  : > "$tmp/calls"; rm -f "$tmp/state"
  out="$(PATH="$tmp:$PATH" STUB_DIR="$tmp" JOE_POLL_MAX_SECONDS=1 "$joe" plan --project x "SELECT 1" 2>/dev/null)" || rc=$?
  if [ "$rc" -eq "$want_rc" ] && [[ "$out" == *"$want_out"* ]]; then echo "ok - $name"
  else echo "FAIL - $name (rc=$rc out=$out)"; failures=$((failures + 1)); fi
}

STUB_MODE=fast run "passes through immediate result" 0 "plan: fast"
if [ "$(grep -c result "$tmp/calls")" -ne 0 ]; then echo "FAIL - fast path polled"; failures=$((failures + 1)); fi
export STUB_MODE=pending
STUB_READY_AFTER=2 run "polls pending until ready" 0 "plan: done"
STUB_READY_AFTER=2 run "prints only the final result" 0 "command 42 · ok"
STUB_READY_AFTER=99 JOE_WAIT_SECONDS=2 run "times out with exit 1" 1 ""
# A non-pending failure from `result` must abort instead of polling until timeout.
STUB_READY_AFTER=99 STUB_RESULT_ERR="Error: unauthorized" JOE_WAIT_SECONDS=30 run "aborts on non-pending error" 1 ""
if [ "$(grep -c result "$tmp/calls")" -ne 1 ]; then echo "FAIL - kept polling after error"; failures=$((failures + 1)); fi
exit "$failures"
