#!/usr/bin/env python3
"""Offline tests for the gitlab-retry-until-merged helper scripts.

A fake `glab` on PATH serves fixtures from a temp directory and logs every
call, so a case can assert that a refused retry never reached a POST. The
property that matters most: retry.py writes nothing unless every
precondition holds. The status page is served from a file:// URL.

Run: python3 skills/gitlab-retry-until-merged/tests/test_scripts.py
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, "..", "scripts")

MR_URL = "https://gitlab.com/grp/sub/proj/-/merge_requests/42"
SHA = "aaaa1111"
MERGE_REF = "refs/merge-requests/42/merge"
TRAIN_REF = "refs/merge-requests/42/train"

# Logs "<METHOD> <path>" and serves the fixture named after the endpoint.
FAKE_GLAB = r'''#!/usr/bin/env python3
import os, re, sys
mock = os.environ["MOCK_DIR"]
args = sys.argv[1:]
method = args[args.index("--method") + 1] if "--method" in args else "GET"
path = next(a for a in args if a.startswith("projects/"))
with open(os.path.join(mock, "calls.log"), "a") as log:
    log.write(f"{method} {path}\n")
if os.path.exists(os.path.join(mock, "api_down")):
    sys.stderr.write("glab: 503 Service Unavailable\n")
    sys.exit(1)
route = path.split("?")[0]
rules = [
    (r"^POST .*/pipelines/\d+/retry$", "retry_response"),
    (r"^POST .*/merge_requests/\d+/pipelines$", "new_pipeline_response"),
    (r"/merge_requests/\d+/pipelines$", "mr_pipelines"),
    (r"/merge_requests/\d+/diffs$", "diffs"),
    (r"/merge_requests/\d+$", "mr"),
    (r"/pipelines/\d+/jobs$", "jobs"),
    (r"/pipelines/\d+/bridges$", "bridges"),
    (r"/jobs/\d+/trace$", "trace"),
    (r"/jobs/\d+$", "job"),
    (r"production/issues$", "production"),
    (r"master-broken-incidents/issues$", "master_broken"),
]
name = next((f for pattern, f in rules if re.search(pattern, f"{method} {route}")), None)
fixture = os.path.join(mock, name) if name else ""
sys.stdout.write(open(fixture).read() if os.path.exists(fixture) else "[]")
'''


def job(id, retried=False, allow_failure=False, name="rspec"):
    return {"id": id, "name": name, "stage": "test", "status": "failed", "failure_reason": "script_failure",
            "web_url": f"u{id}", "allow_failure": allow_failure, "retried": retried}


class ScriptTestCase(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.work)
        self.mock = os.path.join(self.work, "mock")
        bindir = os.path.join(self.work, "bin")
        os.makedirs(self.mock)
        os.makedirs(bindir)
        glab = os.path.join(bindir, "glab")
        with open(glab, "w") as f:
            f.write(FAKE_GLAB.replace("#!/usr/bin/env python3", f"#!{sys.executable}", 1))
        os.chmod(glab, 0o755)
        self.env = dict(os.environ, MOCK_DIR=self.mock, PATH=bindir + os.pathsep + os.environ["PATH"],
                        GITLAB_STATUS_URL="file://" + os.path.join(self.mock, "status_page"))
        self.mr()

    # --- fixtures ----------------------------------------------------------
    def fixture(self, name, data):
        with open(os.path.join(self.mock, name), "w") as f:
            f.write(data if isinstance(data, str) else json.dumps(data))

    def mr(self, state="opened", auto_merge=True, sha=SHA, status="failed", ref=MERGE_REF):
        self.fixture("mr", {"iid": 42, "web_url": MR_URL, "title": "T", "author": {"username": "someone"},
                            "target_branch": "master", "state": state, "sha": sha,
                            "merge_when_pipeline_succeeds": auto_merge, "merge_user": {"username": "me"},
                            "detailed_merge_status": "ci_still_running", "merge_error": None})
        self.fixture("mr_pipelines", [{"id": 900, "status": status, "ref": ref, "sha": "merge999",
                                       "web_url": "https://example.com/p/900", "source": "merge_request_event"}])
        self.fixture("retry_response", {"id": 900, "status": "running", "web_url": "https://example.com/p/900"})
        self.fixture("new_pipeline_response", {"id": 901, "status": "created", "web_url": "https://example.com/p/901"})

    # --- running -----------------------------------------------------------
    def run_script(self, script, *args):
        return subprocess.run([sys.executable, os.path.join(SCRIPTS, script), *args], env=self.env,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)

    def json_of(self, script, *args):
        proc = self.run_script(script, *args)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)

    def calls(self):
        path = os.path.join(self.mock, "calls.log")
        return open(path).read().splitlines() if os.path.exists(path) else []

    def posts(self):
        return [c for c in self.calls() if c.startswith("POST ")]

    def assertNothingWritten(self):
        self.assertEqual(self.posts(), [])


class MrStateTest(ScriptTestCase):
    def test_snapshot(self):
        self.fixture("jobs", [job(1), job(2, retried=True), job(3, allow_failure=True, name="danger")])
        self.fixture("bridges", [dict(job(7, name="e2e:trigger"), failure_reason="downstream_pipeline_failure",
                                      downstream_pipeline={"id": 77, "project_id": 5, "web_url": "d77"})])
        self.fixture("diffs", [{"new_path": "app/a.rb", "old_path": "app/a.rb"},
                               {"new_path": "lib/new.rb", "old_path": "lib/old.rb"}])
        out = self.json_of("mr_state.py", "--files", MR_URL)
        self.assertEqual(out["project"], "grp/sub/proj")
        self.assertEqual(out["project_encoded"], "grp%2Fsub%2Fproj")
        self.assertEqual(out["pipeline"]["kind"], "merged_result")
        self.assertEqual([j["id"] for j in out["failed_jobs"]], [1], "only current, blocking failed jobs")
        self.assertEqual(out["failed_bridges"][0]["downstream_pipeline_id"], 77)
        self.assertEqual(out["blocking_failure_count"], 2)
        self.assertIs(out["auto_merge"], True)
        self.assertEqual(out["target_branch"], "master")
        self.assertEqual(out["changed_files"], ["app/a.rb", "lib/new.rb", "lib/old.rb"])
        self.assertIn("GET projects/grp%2Fsub%2Fproj/pipelines/900/jobs?scope[]=failed&per_page=100", self.calls())
        self.assertNothingWritten()

    def test_paginated_pages_are_merged(self):
        self.fixture("jobs", json.dumps([job(1)]) + "\n" + json.dumps([job(2)]))
        out = self.json_of("mr_state.py", MR_URL)
        self.assertEqual([j["id"] for j in out["failed_jobs"]], [1, 2])

    def test_merge_train_kind(self):
        self.mr(ref=TRAIN_REF)
        self.assertEqual(self.json_of("mr_state.py", MR_URL)["pipeline"]["kind"], "merge_train")

    def test_no_pipeline(self):
        self.fixture("mr_pipelines", [])
        self.assertIsNone(self.json_of("mr_state.py", MR_URL)["pipeline"])

    def test_rejects_non_mr_url(self):
        self.assertEqual(self.run_script("mr_state.py", "https://example.com/x").returncode, 2)

    def test_api_failure_exits_nonzero(self):
        self.fixture("api_down", "")
        proc = self.run_script("mr_state.py", MR_URL)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("503", proc.stderr)


class RetryTest(ScriptTestCase):
    def test_retries_pipeline(self):
        out = self.json_of("retry.py", "--expect-sha", SHA, MR_URL, "pipeline", "900")
        self.assertIs(out["retried"], True)
        self.assertEqual(self.posts(), ["POST projects/grp%2Fsub%2Fproj/pipelines/900/retry"])

    def test_new_pipeline(self):
        out = self.json_of("retry.py", "--expect-sha", SHA, MR_URL, "new-pipeline")
        self.assertEqual(out["pipeline_id"], 901)
        self.assertEqual(self.posts(), ["POST projects/grp%2Fsub%2Fproj/merge_requests/42/pipelines"])

    def assertRefused(self, fragment, *args):
        proc = self.run_script("retry.py", *args)
        self.assertEqual(proc.returncode, 3, proc.stdout + proc.stderr)
        out = json.loads(proc.stdout)
        self.assertIs(out["retried"], False)
        self.assertIn(fragment, out["reason"])
        self.assertNothingWritten()

    def test_refuses_after_new_commits(self):
        self.mr(sha="bbbb2222")
        self.assertRefused("head moved", "--expect-sha", SHA, MR_URL, "pipeline", "900")

    def test_refuses_when_auto_merge_canceled(self):
        self.mr(auto_merge=False)
        self.assertRefused("auto-merge", "--expect-sha", SHA, MR_URL, "pipeline", "900")

    def test_refuses_when_merged(self):
        self.mr(state="merged", status="success")
        self.assertRefused("merged", "--expect-sha", SHA, MR_URL, "new-pipeline")

    def test_refuses_merge_train_pipeline(self):
        self.mr(ref=TRAIN_REF)
        self.assertRefused("merge train", "--expect-sha", SHA, MR_URL, "pipeline", "900")

    def test_refuses_pipeline_of_another_mr(self):
        self.assertRefused("not a pipeline of this MR", "--expect-sha", SHA, MR_URL, "pipeline", "123")

    def test_usage_errors_write_nothing(self):
        for args in (
            [MR_URL, "pipeline", "900"],                          # no --expect-sha
            ["--expect-sha", SHA, MR_URL, "rebase"],              # unknown mode
            ["--expect-sha", SHA, MR_URL, "pipeline"],            # missing pipeline ID
            ["--expect-sha", SHA, MR_URL, "new-pipeline", "900"],  # stray pipeline ID
            [MR_URL, "new-pipeline", "--expect-sha"],             # flag without a value
        ):
            with self.subTest(args=args):
                self.assertEqual(self.run_script("retry.py", *args).returncode, 2)
        self.assertNothingWritten()

    def test_api_failure_is_exit_1(self):
        self.fixture("api_down", "")
        self.assertEqual(self.run_script("retry.py", "--expect-sha", SHA, MR_URL, "new-pipeline").returncode, 1)


class WatchTest(ScriptTestCase):
    def event(self, *args):
        return self.json_of("watch_mr.py", "--interval", "0", "--timeout", "0", *args, MR_URL)["event"]

    def test_events(self):
        cases = [
            (dict(state="merged", auto_merge=False, status="success"), [], "MERGED"),
            (dict(state="closed", auto_merge=False), [], "CLOSED"),
            (dict(auto_merge=False, sha="bbbb2222", status="running"), [], "SHA_CHANGED"),
            (dict(auto_merge=False, status="running"), [], "AUTO_MERGE_OFF"),
            (dict(status="failed"), [], "PIPELINE_FAILED"),
            (dict(status="canceled"), [], "PIPELINE_CANCELED"),
            (dict(status="failed"), ["--grace", "60"], "TIMEOUT"),
            (dict(status="success"), [], "TIMEOUT"),
            (dict(status="failed"), ["--mr-only"], "TIMEOUT"),
            (dict(sha="bbbb2222", status="failed"), ["--mr-only"], "SHA_CHANGED"),
        ]
        for mr, args, expected in cases:
            with self.subTest(mr=mr, args=args):
                self.mr(**mr)
                self.assertEqual(self.event("--expect-sha", SHA, *args), expected)
        self.assertNothingWritten()

    def test_early_failure(self):
        self.mr(status="running")
        self.fixture("jobs", [job(5)])
        self.assertEqual(self.event("--expect-sha", SHA), "NEW_FAILURE")
        self.assertEqual(self.event("--expect-sha", SHA, "--seen", "4,5"), "TIMEOUT")

    def test_no_pipeline(self):
        self.fixture("mr_pipelines", [])
        self.assertEqual(self.event("--expect-sha", SHA), "NO_PIPELINE")

    def test_api_outage_is_an_event_not_a_crash(self):
        self.fixture("api_down", "")
        out = self.json_of("watch_mr.py", "--interval", "0", "--timeout", "0", "--expect-sha", SHA, MR_URL)
        self.assertEqual(out["event"], "API_ERROR")
        self.assertIn("503", out["api_error"])

    def test_usage_errors(self):
        self.assertEqual(self.run_script("watch_mr.py", MR_URL).returncode, 2)
        self.assertEqual(self.run_script("watch_mr.py", MR_URL, "--expect-sha").returncode, 2)
        self.assertEqual(self.run_script("watch_mr.py", "--expect-sha", SHA, "--grace", "-1", MR_URL).returncode, 2)


class IncidentStatusTest(ScriptTestCase):
    def setUp(self):
        super().setUp()
        self.fixture("status_page", {"result": {
            "status_overall": {"status": "Partial Service Disruption", "status_code": 400},
            "status": [{"name": "Website", "status": "Operational", "status_code": 100},
                       {"name": "CI/CD - Hosted runners on Linux", "status": "Degraded Performance",
                        "status_code": 300}],
            "incidents": [{"name": "Slow CI jobs", "_id": "abc"}]}})
        self.fixture("production", [
            {"iid": 1, "title": "S1", "labels": ["incident", "Incident::Active", "severity::1", "Service::CI Runners"],
             "created_at": "t", "web_url": "p1"},
            {"iid": 2, "title": "S3", "labels": ["incident", "Incident::Active", "severity::3"],
             "created_at": "t", "web_url": "p2"}])
        self.fixture("master_broken", [
            {"iid": 9, "title": "broken master with rspec", "created_at": "t", "web_url": "m9",
             "labels": ["master:broken", "master-broken::gitlab-com-overloaded", "missed::SLA"]}])

    def test_signals(self):
        out = self.json_of("incident_status.py")
        page = out["status_page"]
        self.assertIs(page["operational"], False)
        self.assertEqual([c["name"] for c in page["degraded_components"]], ["CI/CD - Hosted runners on Linux"])
        self.assertEqual(page["active_incidents"][0]["url"],
                         "https://status.gitlab.com/pages/incident/5b36dc6502d06804c08349f7/abc")
        self.assertEqual([i["iid"] for i in out["production_incidents"]], [1])
        self.assertEqual(out["production_incidents"][0]["severity"], "1")
        self.assertEqual(out["production_incidents"][0]["labels"], ["Service::CI Runners"])
        self.assertEqual(out["master_broken_incidents"][0]["labels"],
                         ["master:broken", "master-broken::gitlab-com-overloaded"])
        mb_call = next(c for c in self.calls() if "master-broken-incidents" in c)
        self.assertIn("created_after=" + out["master_broken_since"].replace(":", "%3A"), mb_call)
        self.assertNothingWritten()

    def test_all_severities(self):
        out = self.json_of("incident_status.py", "--all-severities")
        self.assertEqual([i["iid"] for i in out["production_incidents"]], [1, 2])

    def test_unreachable_signals_degrade_to_error_fields(self):
        os.remove(os.path.join(self.mock, "status_page"))
        out = self.json_of("incident_status.py")
        self.assertIn("error", out["status_page"])
        self.assertEqual(len(out["production_incidents"]), 1, "other signals still reported")
        self.fixture("api_down", "")
        out = self.json_of("incident_status.py")
        self.assertIn("error", out["production_incidents"])
        self.assertIn("error", out["master_broken_incidents"])

    def test_bad_hours(self):
        self.assertEqual(self.run_script("incident_status.py", "--hours", "soon").returncode, 2)


class JobLogTailTest(ScriptTestCase):
    def test_cleans_timestamped_trace(self):
        self.fixture("job", {"id": 5, "name": "rspec", "runner": {"description": "r1"}})
        trace = (
            "2026-09-24T17:23:52.844727Z 00O section_start:1790270633:step_script\r\x1b[0K"
            "\x1b[0K\x1b[36;1mExecuting step_script\x1b[0;m\n"
            "2026-09-24T17:23:52.851799Z 01O $ bundle exec rspec\n"
            "2026-09-24T17:23:52.851800Z 01O \n"
            "2026-09-24T17:23:53.692264Z 01O \x1b[31mFailure/Error: expect(x).to eq(1)\x1b[0m\r\n"
            "2026-09-24T17:23:53.869094Z 00O section_end:1790270633:step_script\r\x1b[0K\n"
            "2026-09-24T17:23:54.530118Z 00O+\x1b[31;1mERROR: Job failed: exit code 1\x1b[0;m\n"
        )
        self.fixture("trace", trace)

        proc = self.run_script("job_log_tail.py", "grp%2Fproj", "5", "10")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        log = proc.stdout.split("=== JOB LOG (last 10 lines) ===\n", 1)[1].splitlines()
        self.assertEqual(log, ["Executing step_script", "$ bundle exec rspec",
                               "Failure/Error: expect(x).to eq(1)", "ERROR: Job failed: exit code 1"])
        self.assertIn('"runner": "r1"', proc.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
