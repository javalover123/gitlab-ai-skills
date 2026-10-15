"""Tests for scripts/check_version_bump.py using throwaway git repos."""

import os
import subprocess
import sys
import tempfile
import unittest

SCRIPT = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "check_version_bump.py")

def isolated_env(**extra):
    """Environment without inherited git/CI state (e.g. GIT_DIR from a worktree hook)."""
    env = {k: v for k, v in os.environ.items() if not k.startswith(("GIT_", "CI_"))}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
    env.update(extra)
    return env


GIT_ENV = {
    "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com",
}


class CheckVersionBumpTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = os.path.join(self.tmp.name, "repo")
        os.makedirs(os.path.join(self.repo, "scripts"))
        # The script resolves the repo root relative to its own location.
        with open(SCRIPT) as f, open(os.path.join(self.repo, "scripts", "check_version_bump.py"), "w") as g:
            g.write(f.read())
        self.git("init", "-q", "-b", "main")
        self.write_skill("alpha", "1.2.0")
        self.commit("base")
        # Stand-in for the remote: origin/main tracks local main via update-ref.
        self.sync_origin()

    def git(self, *args):
        return subprocess.run(
            ["git", *args], cwd=self.repo, check=True, capture_output=True, text=True,
            env=isolated_env(**GIT_ENV),
        ).stdout.strip()

    def write_skill(self, name, version, body="x"):
        path = os.path.join(self.repo, "skills", name)
        os.makedirs(path, exist_ok=True)
        with open(os.path.join(path, "SKILL.md"), "w") as f:
            f.write(f"---\nname: {name}\nversion: {version}\n---\n{body}\n")

    def commit(self, msg):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", msg)
        return self.git("rev-parse", "HEAD")

    def sync_origin(self):
        self.git("update-ref", "refs/remotes/origin/main", "main")

    def run_check(self, **env):
        proc = subprocess.run(
            [sys.executable, os.path.join(self.repo, "scripts", "check_version_bump.py"), "--ci"],
            cwd=self.repo, capture_output=True, text=True, env=isolated_env(**env),
        )
        return proc.returncode, proc.stdout + proc.stderr

    def feature_branch(self):
        self.git("checkout", "-q", "-b", "feature")

    def test_bump_passes(self):
        self.feature_branch()
        self.write_skill("alpha", "1.3.0", "changed")
        self.commit("bump")
        code, out = self.run_check()
        self.assertEqual(code, 0, out)

    def test_missing_bump_fails(self):
        self.feature_branch()
        self.write_skill("alpha", "1.2.0", "changed")
        self.commit("no bump")
        code, out = self.run_check()
        self.assertEqual(code, 1, out)
        self.assertIn("version unchanged", out)

    def test_new_skill_passes(self):
        self.feature_branch()
        self.write_skill("beta", "0.1.0")
        self.commit("new skill")
        code, out = self.run_check()
        self.assertEqual(code, 0, out)

    def test_deleted_skill_passes(self):
        """Removing a whole skill has no version to bump, so the gate must not fail it."""
        self.feature_branch()
        self.git("rm", "-r", "-q", "skills/alpha")
        self.commit("remove skill")
        code, out = self.run_check()
        self.assertEqual(code, 0, out)
        self.assertIn("alpha", out)
        self.assertIn("removed", out)

    def test_deleting_one_skill_does_not_hide_another_skills_missing_bump(self):
        self.write_skill("beta", "0.4.0")
        self.commit("add beta")
        self.sync_origin()
        self.feature_branch()
        self.git("rm", "-r", "-q", "skills/alpha")
        self.write_skill("beta", "0.4.0", "changed without a bump")
        self.commit("remove alpha, edit beta")
        code, out = self.run_check()
        self.assertEqual(code, 1, out)
        self.assertIn("beta", out)
        self.assertIn("version unchanged", out)

    def test_replacing_a_skill_with_a_new_one_passes(self):
        """The nixify -> nix shape: one skill removed, a differently named one added."""
        self.feature_branch()
        self.git("rm", "-r", "-q", "skills/alpha")
        self.write_skill("omega", "0.1.0")
        self.commit("replace alpha with omega")
        code, out = self.run_check()
        self.assertEqual(code, 0, out)
        self.assertIn("removed", out)
        self.assertIn("new", out)

    def test_merged_results_ignores_target_drift(self):
        base = self.git("rev-parse", "HEAD")
        self.feature_branch()
        self.write_skill("gamma", "0.1.0")
        self.commit("mr change")
        self.git("checkout", "-q", "main")
        self.write_skill("alpha", "1.2.0", "drift without bump")
        tip = self.commit("target drift")
        self.sync_origin()
        self.git("checkout", "-q", "-b", "merged", tip)
        self.git("merge", "-q", "--no-ff", "-m", "merge", "feature")
        code, out = self.run_check(
            CI_MERGE_REQUEST_EVENT_TYPE="merged_result",
            CI_MERGE_REQUEST_TARGET_BRANCH_SHA=tip,
            CI_MERGE_REQUEST_DIFF_BASE_SHA=base,
        )
        self.assertEqual(code, 0, out)
        self.assertNotIn("alpha", out)

    def test_merged_results_without_target_sha_uses_first_parent(self):
        self.feature_branch()
        self.write_skill("gamma", "0.1.0")
        self.commit("mr change")
        self.git("checkout", "-q", "main")
        self.write_skill("alpha", "1.2.0", "drift without bump")
        tip = self.commit("target drift")
        self.git("checkout", "-q", "-b", "merged", tip)
        self.git("merge", "-q", "--no-ff", "-m", "merge", "feature")
        code, out = self.run_check(CI_MERGE_REQUEST_EVENT_TYPE="merged_result")
        self.assertEqual(code, 0, out)

    def test_local_run_without_origin_fails_loudly(self):
        self.git("update-ref", "-d", "refs/remotes/origin/main")
        self.feature_branch()
        self.write_skill("alpha", "1.3.0", "changed")
        self.commit("bump")
        code, out = self.run_check()
        self.assertEqual(code, 2, out)

    def test_detached_collision_with_target_tip_fails(self):
        base = self.git("rev-parse", "HEAD")
        self.feature_branch()
        self.write_skill("alpha", "1.3.0", "mine")
        self.commit("my bump")
        self.git("checkout", "-q", "main")
        self.write_skill("alpha", "1.3.0", "theirs")
        self.commit("other bump")
        self.sync_origin()
        self.git("checkout", "-q", "feature")
        code, out = self.run_check(CI_MERGE_REQUEST_DIFF_BASE_SHA=base)
        self.assertEqual(code, 1, out)
        self.assertIn("already on the target branch", out)

    def test_detached_ignores_target_drift_in_other_skills(self):
        base = self.git("rev-parse", "HEAD")
        self.feature_branch()
        self.write_skill("beta", "0.1.0")
        self.commit("mine")
        self.git("checkout", "-q", "main")
        self.write_skill("alpha", "1.3.0", "drift")
        self.commit("drift")
        self.sync_origin()
        self.git("checkout", "-q", "feature")
        code, out = self.run_check(CI_MERGE_REQUEST_DIFF_BASE_SHA=base)
        self.assertEqual(code, 0, out)

    def test_unreadable_baseline_fails_loudly(self):
        self.feature_branch()
        self.write_skill("alpha", "1.2.0", "changed")
        self.commit("no bump")
        code, out = self.run_check(CI_MERGE_REQUEST_DIFF_BASE_SHA="0" * 40)
        self.assertEqual(code, 2, out)
        self.assertIn("cannot compute baseline", out)


if __name__ == "__main__":
    unittest.main()
