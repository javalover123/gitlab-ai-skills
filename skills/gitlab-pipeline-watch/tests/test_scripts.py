#!/usr/bin/env python3
"""Offline tests for the gitlab-pipeline-watch MR scripts.

A fake `glab` on PATH serves fixtures from a temp directory and logs every
call, so a case can assert that the read-only scripts never POST.

Run: python3 skills/gitlab-pipeline-watch/tests/test_scripts.py
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
if "--hostname" not in args or args[args.index("--hostname") + 1] != "gitlab.com":
    sys.stderr.write("fake glab: call not pinned to --hostname gitlab.com\n")
    sys.exit(9)
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
    (r"/pipelines/\d+/trigger_jobs$", "bridges"),
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


class WatchTest(ScriptTestCase):
    def event(self, *args):
        return self.json_of("watch_mr.py", "--interval", "0", "--timeout", "0", *args, MR_URL)["event"]

    def test_events(self):
        cases = [
            (dict(state="merged", auto_merge=False, status="success"), [], "MERGED"),
            (dict(state="closed", auto_merge=False), [], "CLOSED"),
            (dict(auto_merge=False, sha="bbbb2222", status="running"), ["--expect-sha", SHA, "--auto-merge"],
             "SHA_CHANGED"),
            (dict(sha="bbbb2222", status="running"), [], "TIMEOUT"),  # pushes ignored without --expect-sha
            (dict(auto_merge=False, status="running"), ["--auto-merge"], "AUTO_MERGE_OFF"),
            (dict(auto_merge=False, status="running"), [], "TIMEOUT"),  # auto-merge ignored without --auto-merge
            (dict(status="failed"), [], "PIPELINE_FAILED"),
            (dict(status="canceled"), [], "PIPELINE_CANCELED"),
            (dict(status="failed"), ["--grace", "60"], "TIMEOUT"),
            (dict(status="success"), [], "PIPELINE_SUCCESS"),
            (dict(status="success"), ["--auto-merge"], "TIMEOUT"),  # green: keep waiting for MERGED
            (dict(status="failed"), ["--mr-only"], "TIMEOUT"),
            (dict(sha="bbbb2222", status="failed"), ["--mr-only", "--expect-sha", SHA], "SHA_CHANGED"),
            (dict(status="failed"), ["--newer-than", "900"], "NO_NEW_PIPELINE"),
            (dict(status="failed"), ["--newer-than", "899"], "PIPELINE_FAILED"),
        ]
        for mr, args, expected in cases:
            with self.subTest(mr=mr, args=args):
                self.mr(**mr)
                self.assertEqual(self.event(*args), expected)
        self.assertNothingWritten()

    def test_early_failure(self):
        self.mr(status="running")
        self.fixture("jobs", [job(5)])
        self.assertEqual(self.event(), "NEW_FAILURE")
        self.assertEqual(self.event("--seen", "4,5"), "TIMEOUT")

    def test_no_pipeline(self):
        self.fixture("mr_pipelines", [])
        self.assertEqual(self.event(), "NO_PIPELINE")
        self.assertEqual(self.event("--newer-than", "900"), "NO_NEW_PIPELINE")

    def test_api_outage_is_an_event_not_a_crash(self):
        self.fixture("api_down", "")
        out = self.json_of("watch_mr.py", "--interval", "0", "--timeout", "0", MR_URL)
        self.assertEqual(out["event"], "API_ERROR")
        self.assertIn("503", out["api_error"])

    def test_usage_errors(self):
        self.assertEqual(self.run_script("watch_mr.py").returncode, 2)
        self.assertEqual(self.run_script("watch_mr.py", MR_URL, "--expect-sha").returncode, 2)
        self.assertEqual(self.run_script("watch_mr.py", "--grace", "-1", MR_URL).returncode, 2)
        self.assertEqual(self.run_script("watch_mr.py", "https://example.com/x").returncode, 2)


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
