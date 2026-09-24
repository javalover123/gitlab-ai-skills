#!/usr/bin/env bash
# Offline test suite for the gitlab-retry-until-merged helper scripts.
#
# Stub `glab` and `curl` binaries on PATH serve fixtures from $MOCK_DIR and
# append every call to $MOCK_DIR/calls.log, so a case can assert that a
# refused retry never reached a POST. The property that matters most: retry.sh
# writes nothing unless every precondition holds.
#
# Usage: bash skills/gitlab-retry-until-merged/tests/test_scripts.sh
set -uo pipefail

here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
scripts="$here/../scripts"

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
export MOCK_DIR="$work/mock"
mkdir -p "$work/bin" "$MOCK_DIR"

# --- stubs -----------------------------------------------------------------
# glab: log "<METHOD> <path>", then serve the fixture whose name matches the
# endpoint. A missing fixture is an empty JSON array.
cat >"$work/bin/glab" <<'STUB'
#!/usr/bin/env bash
method=GET
path=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --method|-X) method="$2"; shift 2 ;;
    -f|--raw-field|-F|--field) shift 2 ;;
    projects/*) path="$1"; shift ;;
    *) shift ;;
  esac
done
echo "$method $path" >>"$MOCK_DIR/calls.log"
if [[ -f "$MOCK_DIR/api_down" ]]; then
  echo "glab: 503 Service Unavailable" >&2
  exit 1
fi
case "$method $path" in
  "POST "*/retry) f=retry_response ;;
  "POST "*/merge_requests/*/pipelines) f=new_pipeline_response ;;
  *"/merge_requests/"*/pipelines*) f=mr_pipelines ;;
  *"/merge_requests/"*/diffs*) f=diffs ;;
  *"/merge_requests/"*) f=mr ;;
  *"/pipelines/"*/jobs*) f=jobs ;;
  *"/pipelines/"*/bridges*) f=bridges ;;
  *production/issues*) f=production ;;
  *master-broken-incidents/issues*) f=master_broken ;;
  *) f=unknown ;;
esac
if [[ -f "$MOCK_DIR/$f" ]]; then cat "$MOCK_DIR/$f"; else echo '[]'; fi
STUB

cat >"$work/bin/curl" <<'STUB'
#!/usr/bin/env bash
echo "CURL $*" >>"$MOCK_DIR/calls.log"
[[ -f "$MOCK_DIR/status_page" ]] || exit 22
cat "$MOCK_DIR/status_page"
STUB
chmod +x "$work/bin/glab" "$work/bin/curl"
export PATH="$work/bin:$PATH"

MR_URL="https://gitlab.com/grp/sub/proj/-/merge_requests/42"
SHA="aaaa1111"

pass=0
fail=0
ok() { pass=$((pass + 1)); printf '  ok   %s\n' "$1"; }
bad() { fail=$((fail + 1)); printf '  FAIL %s\n     %s\n' "$1" "$2"; }
check() { if [[ "$2" == "$3" ]]; then ok "$1"; else bad "$1" "expected [$2] got [$3]"; fi; }
posted() { if grep -q '^POST' "$MOCK_DIR/calls.log" 2>/dev/null; then ok "$1"; else bad "$1" "no POST was made"; fi; }
not_posted() { if grep -q '^POST' "$MOCK_DIR/calls.log" 2>/dev/null; then bad "$1" "a POST WAS made"; else ok "$1"; fi; }

# reset <mr_state> <auto_merge> <sha> <pipeline_status> <ref>
reset() {
  rm -f "$MOCK_DIR"/*
  printf '{"iid":42,"web_url":"%s","title":"T","author":{"username":"someone"},"target_branch":"master","state":"%s","sha":"%s","merge_when_pipeline_succeeds":%s,"merge_user":{"username":"me"},"detailed_merge_status":"ci_still_running","merge_error":null}' \
    "$MR_URL" "$1" "$3" "$2" >"$MOCK_DIR/mr"
  printf '[{"id":900,"status":"%s","ref":"%s","sha":"merge999","web_url":"https://example.com/p/900","source":"merge_request_event"}]' \
    "$4" "$5" >"$MOCK_DIR/mr_pipelines"
  echo '{"id":900,"status":"running","web_url":"https://example.com/p/900"}' >"$MOCK_DIR/retry_response"
  echo '{"id":901,"status":"created","web_url":"https://example.com/p/901"}' >"$MOCK_DIR/new_pipeline_response"
}

MERGE_REF="refs/merge-requests/42/merge"
TRAIN_REF="refs/merge-requests/42/train"

# --- mr_state.sh -------------------------------------------------------------
echo "== mr_state.sh =="
reset opened true "$SHA" failed "$MERGE_REF"
cat >"$MOCK_DIR/jobs" <<'EOF'
[{"id":1,"name":"rspec 1/2","stage":"test","status":"failed","failure_reason":"script_failure","web_url":"u1","allow_failure":false,"retried":false},
 {"id":2,"name":"rspec 1/2","stage":"test","status":"failed","failure_reason":"script_failure","web_url":"u2","allow_failure":false,"retried":true},
 {"id":3,"name":"danger","stage":"test","status":"failed","failure_reason":"script_failure","web_url":"u3","allow_failure":true,"retried":false}]
EOF
echo '[{"id":7,"name":"e2e:trigger","stage":"qa","status":"failed","failure_reason":"downstream_pipeline_failure","allow_failure":false,"retried":false,"downstream_pipeline":{"id":77,"project_id":5,"web_url":"d77"}}]' >"$MOCK_DIR/bridges"
echo '[{"new_path":"app/a.rb","old_path":"app/a.rb"},{"new_path":"lib/new.rb","old_path":"lib/old.rb"}]' >"$MOCK_DIR/diffs"
out=$(bash "$scripts/mr_state.sh" --files "$MR_URL")
check "parses nested project path" "grp/sub/proj" "$(jq -r .project <<<"$out")"
check "encodes project path" "grp%2Fsub%2Fproj" "$(jq -r .project_encoded <<<"$out")"
check "classifies merged-results pipeline" "merged_result" "$(jq -r .pipeline.kind <<<"$out")"
check "keeps only current blocking failed jobs" "1" "$(jq -c '[.failed_jobs[].id] | join(",")' -r <<<"$out")"
check "surfaces failed bridge downstream pipeline" "77" "$(jq -r '.failed_bridges[0].downstream_pipeline_id' <<<"$out")"
check "counts jobs and bridges as blocking" "2" "$(jq -r .blocking_failure_count <<<"$out")"
check "auto_merge is a boolean" "true" "$(jq -r .auto_merge <<<"$out")"
check "reports the target branch" "master" "$(jq -r .target_branch <<<"$out")"
check "changed files include renames both ways" "app/a.rb,lib/new.rb,lib/old.rb" "$(jq -r '.changed_files | join(",")' <<<"$out")"

reset opened true "$SHA" failed "$TRAIN_REF"
check "classifies merge train pipeline" "merge_train" "$(bash "$scripts/mr_state.sh" "$MR_URL" | jq -r .pipeline.kind)"

reset opened true "$SHA" failed "$MERGE_REF"
echo '[]' >"$MOCK_DIR/mr_pipelines"
out=$(bash "$scripts/mr_state.sh" "$MR_URL")
check "no pipeline yields null" "null" "$(jq -r .pipeline <<<"$out")"
not_posted "mr_state.sh never POSTs"

# --- retry.sh ----------------------------------------------------------------
echo "== retry.sh =="
reset opened true "$SHA" failed "$MERGE_REF"
out=$(bash "$scripts/retry.sh" --expect-sha "$SHA" "$MR_URL" pipeline 900)
check "retries a failed MR pipeline" "0" "$?"
check "reports retried" "true" "$(jq -r .retried <<<"$out")"
posted "POSTs pipeline retry"
check "POST hits the retry endpoint" "POST projects/grp%2Fsub%2Fproj/pipelines/900/retry" "$(grep '^POST' "$MOCK_DIR/calls.log")"

reset opened true "$SHA" failed "$MERGE_REF"
out=$(bash "$scripts/retry.sh" --expect-sha "$SHA" "$MR_URL" new-pipeline)
check "new-pipeline reports the new pipeline id" "901" "$(jq -r .pipeline_id <<<"$out")"
check "POST hits the MR pipelines endpoint" "POST projects/grp%2Fsub%2Fproj/merge_requests/42/pipelines" "$(grep '^POST' "$MOCK_DIR/calls.log")"

refused() { # <label> <expected reason fragment> <args...>
  local label="$1" frag="$2"
  shift 2
  out=$(bash "$scripts/retry.sh" "$@")
  local rc=$?
  check "$label: exit 3" "3" "$rc"
  if grep -q "$frag" <<<"$out"; then ok "$label: says why"; else bad "$label: says why" "no [$frag] in $out"; fi
  not_posted "$label: nothing written"
}

reset opened true "bbbb2222" failed "$MERGE_REF"
refused "new commits pushed" "head moved" --expect-sha "$SHA" "$MR_URL" pipeline 900

reset opened false "$SHA" failed "$MERGE_REF"
refused "auto-merge canceled" "auto-merge" --expect-sha "$SHA" "$MR_URL" pipeline 900

reset merged true "$SHA" success "$MERGE_REF"
refused "already merged" "merged" --expect-sha "$SHA" "$MR_URL" new-pipeline

reset opened true "$SHA" failed "$TRAIN_REF"
refused "merge train pipeline" "merge train" --expect-sha "$SHA" "$MR_URL" pipeline 900

reset opened true "$SHA" failed "$MERGE_REF"
refused "pipeline from another MR" "not a pipeline of this MR" --expect-sha "$SHA" "$MR_URL" pipeline 123

reset opened true "$SHA" failed "$MERGE_REF"
bash "$scripts/retry.sh" "$MR_URL" pipeline 900 >/dev/null 2>&1
check "missing --expect-sha is a usage error" "2" "$?"
bash "$scripts/retry.sh" --expect-sha "$SHA" "$MR_URL" rebase >/dev/null 2>&1
check "unknown mode is a usage error" "2" "$?"
bash "$scripts/retry.sh" "$MR_URL" new-pipeline --expect-sha >/dev/null 2>&1
check "trailing --expect-sha without a value is a usage error" "2" "$?"
not_posted "usage errors write nothing"

# --- watch_mr.sh -------------------------------------------------------------
echo "== watch_mr.sh =="
watch() { bash "$scripts/watch_mr.sh" --interval 0 --timeout 0 "$@" "$MR_URL" | jq -r .event; }

reset merged false "$SHA" success "$MERGE_REF"
check "merged MR" "MERGED" "$(watch --expect-sha "$SHA")"

reset closed false "$SHA" failed "$MERGE_REF"
check "closed MR" "CLOSED" "$(watch --expect-sha "$SHA")"

reset opened false "bbbb2222" running "$MERGE_REF"
check "new push wins over auto-merge off" "SHA_CHANGED" "$(watch --expect-sha "$SHA")"

reset opened false "$SHA" running "$MERGE_REF"
check "auto-merge canceled" "AUTO_MERGE_OFF" "$(watch --expect-sha "$SHA")"

reset opened true "$SHA" failed "$MERGE_REF"
check "failed pipeline" "PIPELINE_FAILED" "$(watch --expect-sha "$SHA")"

reset opened true "$SHA" failed "$MERGE_REF"
check "grace period hides a stale failed status" "TIMEOUT" "$(watch --expect-sha "$SHA" --grace 60)"

reset opened true "$SHA" running "$MERGE_REF"
echo '[{"id":5,"name":"rspec","stage":"test","status":"failed","failure_reason":"script_failure","web_url":"u","allow_failure":false,"retried":false}]' >"$MOCK_DIR/jobs"
check "early blocking failure" "NEW_FAILURE" "$(watch --expect-sha "$SHA")"
check "already-triaged failure is ignored" "TIMEOUT" "$(watch --expect-sha "$SHA" --seen 4,5)"

reset opened true "$SHA" success "$MERGE_REF"
check "green but not merged yet keeps waiting" "TIMEOUT" "$(watch --expect-sha "$SHA")"

reset opened true "$SHA" running "$MERGE_REF"
echo '[]' >"$MOCK_DIR/mr_pipelines"
check "no pipeline" "NO_PIPELINE" "$(watch --expect-sha "$SHA")"

reset opened true "$SHA" failed "$MERGE_REF"
check "--mr-only ignores a failed pipeline" "TIMEOUT" "$(watch --expect-sha "$SHA" --mr-only)"
reset opened true "bbbb2222" failed "$MERGE_REF"
check "--mr-only still catches a push" "SHA_CHANGED" "$(watch --expect-sha "$SHA" --mr-only)"

reset opened true "$SHA" running "$MERGE_REF"
touch "$MOCK_DIR/api_down"
out=$(bash "$scripts/watch_mr.sh" --interval 0 --timeout 0 --expect-sha "$SHA" "$MR_URL")
check "API outage exits 0 with an event" "0" "$?"
check "API outage is API_ERROR, not a crash" "API_ERROR" "$(jq -r .event <<<"$out")"
rm -f "$MOCK_DIR/api_down"

bash "$scripts/watch_mr.sh" "$MR_URL" --expect-sha >/dev/null 2>&1
check "trailing flag without a value is a usage error" "2" "$?"
not_posted "watch_mr.sh never POSTs"

# --- incident_status.sh ------------------------------------------------------
echo "== incident_status.sh =="
reset opened true "$SHA" running "$MERGE_REF"
cat >"$MOCK_DIR/status_page" <<'EOF'
{"result":{"status_overall":{"status":"Partial Service Disruption","status_code":400},
 "status":[{"name":"Website","status":"Operational","status_code":100},
           {"name":"CI/CD - Hosted runners on Linux","status":"Degraded Performance","status_code":300}],
 "incidents":[{"name":"Slow CI jobs","_id":"abc"}]}}
EOF
cat >"$MOCK_DIR/production" <<'EOF'
[{"iid":1,"title":"S1 thing","labels":["incident","Incident::Active","severity::1","Service::CI Runners"],"created_at":"t","web_url":"p1"},
 {"iid":2,"title":"S3 thing","labels":["incident","Incident::Active","severity::3"],"created_at":"t","web_url":"p2"}]
EOF
echo '[{"iid":9,"title":"broken master with rspec","labels":["master:broken","master-broken::gitlab-com-overloaded","missed::SLA"],"created_at":"t","web_url":"m9"}]' >"$MOCK_DIR/master_broken"
out=$(bash "$scripts/incident_status.sh")
check "status page not operational" "false" "$(jq -r .status_page.operational <<<"$out")"
check "lists only degraded components" "CI/CD - Hosted runners on Linux" "$(jq -r '.status_page.degraded_components | map(.name) | join(",")' <<<"$out")"
check "links the status page incident" "https://status.gitlab.com/pages/incident/5b36dc6502d06804c08349f7/abc" "$(jq -r '.status_page.active_incidents[0].url' <<<"$out")"
check "keeps S1/S2 production incidents only" "1" "$(jq -r '[.production_incidents[].iid] | join(",")' <<<"$out")"
check "extracts severity" "1" "$(jq -r '.production_incidents[0].severity' <<<"$out")"
check "keeps master-broken triage labels" "master:broken,master-broken::gitlab-com-overloaded" "$(jq -r '.master_broken_incidents[0].labels | join(",")' <<<"$out")"
check "all severities on request" "1,2" "$(bash "$scripts/incident_status.sh" --all-severities | jq -r '[.production_incidents[].iid] | join(",")')"

rm -f "$MOCK_DIR/status_page"
out=$(bash "$scripts/incident_status.sh")
check "unreachable status page degrades to an error field" "true" "$(jq -r '.status_page | has("error")' <<<"$out")"
check "other signals still reported" "1" "$(jq -r '.production_incidents | length' <<<"$out")"
bash "$scripts/incident_status.sh" --hours soon >/dev/null 2>&1
check "non-numeric --hours is a usage error" "2" "$?"
not_posted "incident_status.sh never POSTs"

echo
echo "passed: $pass  failed: $fail"
[[ $fail -eq 0 ]]
