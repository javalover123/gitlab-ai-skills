"""Tests for scripts/check_synced_skills_untouched.sh using throwaway git repos."""

import os
import shutil
import subprocess
import tempfile
import unittest

SCRIPT = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "check_synced_skills_untouched.sh")
MANIFEST = "skills:\n  synced:\n    source_project: x/y\n"


def hermetic_env(**extra):
    """Environment without hook-exported GIT_* or user/system git config."""
    env = {k: v for k, v in os.environ.items() if not k.startswith(("GIT_", "CI_", "GITLAB_"))}
    env.update(GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_NOSYSTEM="1")
    env.update(extra)
    return env


def git(cwd, *args):
    env = hermetic_env(GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
    return subprocess.run(["git", *args], cwd=cwd, env=env, check=True, capture_output=True, text=True).stdout.strip()


def commit_file(cwd, path, content="x\n"):
    full = os.path.join(cwd, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w") as f:
        f.write(content)
    git(cwd, "add", "-A")
    git(cwd, "commit", "-qm", f"edit {path}")
    return git(cwd, "rev-parse", "HEAD")


class GuardSyncedSkillsTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)
        os.makedirs(os.path.join(self.dir, "scripts"))
        shutil.copy(SCRIPT, os.path.join(self.dir, "scripts"))
        git(self.dir, "init", "-q", "-b", "main")
        with open(os.path.join(self.dir, "synced-skills.yml"), "w") as f:
            f.write(MANIFEST)
        self.base = commit_file(self.dir, "skills/own/SKILL.md")

    def run_guard(self, **env):
        clean = hermetic_env(**env)
        return subprocess.run(["bash", os.path.join(self.dir, "scripts", SCRIPT.rsplit("/", 1)[1])],
                              cwd=self.dir, env=clean, capture_output=True, text=True)

    def merged_results(self):
        """MR edits an unrelated skill; main then gains a synced-skill commit; HEAD merges both."""
        git(self.dir, "checkout", "-q", "-b", "mr")
        commit_file(self.dir, "skills/own/SKILL.md", "mr\n")
        git(self.dir, "checkout", "-q", "main")
        target = commit_file(self.dir, "skills/synced/SKILL.md", "sync\n")
        git(self.dir, "checkout", "-q", "-b", "merged")
        git(self.dir, "merge", "-q", "--no-ff", "-m", "merge", "mr")
        return target

    def test_merged_results_ignores_target_commits(self):
        target = self.merged_results()
        result = self.run_guard(CI_MERGE_REQUEST_DIFF_BASE_SHA=self.base, CI_MERGE_REQUEST_TARGET_BRANCH_SHA=target)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_old_diff_base_alone_blames_mr(self):
        self.merged_results()
        result = self.run_guard(CI_MERGE_REQUEST_DIFF_BASE_SHA=self.base)
        self.assertEqual(result.returncode, 1)

    def test_mr_editing_synced_skill_fails(self):
        git(self.dir, "checkout", "-q", "-b", "mr")
        commit_file(self.dir, "skills/synced/SKILL.md", "edit\n")
        result = self.run_guard(CI_MERGE_REQUEST_DIFF_BASE_SHA=self.base, CI_MERGE_REQUEST_TARGET_BRANCH_SHA=self.base)
        self.assertEqual(result.returncode, 1)
        self.assertIn("skills/synced/SKILL.md", result.stderr)

    def linear_mr_editing_synced_first(self):
        """Linear MR: first commit edits a synced skill, last commit only an own skill."""
        git(self.dir, "checkout", "-q", "--detach")
        commit_file(self.dir, "skills/synced/SKILL.md", "edit\n")
        commit_file(self.dir, "skills/own/SKILL.md", "later\n")

    def test_linear_train_detects_earlier_commit(self):
        # HEAD^1 would only see the last commit and false-pass.
        self.linear_mr_editing_synced_first()
        result = self.run_guard(CI_MERGE_REQUEST_TARGET_BRANCH_SHA=self.base)
        self.assertEqual(result.returncode, 1)
        self.assertIn("skills/synced/SKILL.md", result.stderr)

    def test_detached_mr_pipeline_uses_diff_base_when_target_sha_unset_or_empty(self):
        self.linear_mr_editing_synced_first()
        for env in ({}, {"CI_MERGE_REQUEST_TARGET_BRANCH_SHA": ""}):
            with self.subTest(env=env):
                result = self.run_guard(CI_MERGE_REQUEST_DIFF_BASE_SHA=self.base, **env)
                self.assertEqual(result.returncode, 1)
                self.assertIn("CI_MERGE_REQUEST_DIFF_BASE_SHA", result.stdout)

    def test_merge_train_ignores_target_and_earlier_train_commits(self):
        git(self.dir, "checkout", "-q", "-b", "prev")
        commit_file(self.dir, "skills/own/prev.md")
        git(self.dir, "checkout", "-q", "main")
        target = commit_file(self.dir, "skills/synced/SKILL.md", "sync\n")
        git(self.dir, "checkout", "-q", "-b", "train", target)
        git(self.dir, "merge", "-q", "--no-ff", "-m", "prev", "prev")
        git(self.dir, "checkout", "-q", "-b", "mr", self.base)
        commit_file(self.dir, "skills/own/mr.md")
        git(self.dir, "checkout", "-q", "train")
        git(self.dir, "merge", "-q", "--no-ff", "-m", "mr", "mr")
        result = self.run_guard(CI_MERGE_REQUEST_DIFF_BASE_SHA=self.base, CI_MERGE_REQUEST_TARGET_BRANCH_SHA=target)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_merge_train_detects_this_mr_edit(self):
        git(self.dir, "checkout", "-q", "-b", "prev")
        commit_file(self.dir, "skills/own/prev.md")
        git(self.dir, "checkout", "-q", "-b", "mr", self.base)
        commit_file(self.dir, "skills/synced/SKILL.md", "edit\n")
        git(self.dir, "checkout", "-q", "prev")
        git(self.dir, "merge", "-q", "--no-ff", "-m", "mr", "mr")
        result = self.run_guard(CI_MERGE_REQUEST_TARGET_BRANCH_SHA=self.base)
        self.assertEqual(result.returncode, 1)

    def test_logs_base_source(self):
        result = self.run_guard(CI_MERGE_REQUEST_TARGET_BRANCH_SHA=self.base)
        self.assertIn(f"Diffing against {self.base} (CI_MERGE_REQUEST_TARGET_BRANCH_SHA)", result.stdout)

    def test_sync_branch_exempt(self):
        commit_file(self.dir, "skills/synced/SKILL.md", "edit\n")
        result = self.run_guard(CI_COMMIT_REF_NAME="sync/foo", CI_MERGE_REQUEST_TARGET_BRANCH_SHA=self.base)
        self.assertEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
