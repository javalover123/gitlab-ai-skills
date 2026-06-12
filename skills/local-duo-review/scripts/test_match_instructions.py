#!/usr/bin/env python3
"""Unit tests for match-instructions.py glob/filter semantics.

Pure-stdlib (``unittest``) — no third-party dependencies. Run with:

    python3 skills/local-duo-review/scripts/test_match_instructions.py

These lock the doublestar-style glob behavior the skill relies on, so the
"trust the script, don't hand-match" contract in SKILL.md stays honest.
"""

import importlib.util
import os
import subprocess
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_SPEC = importlib.util.spec_from_file_location(
    "match_instructions", os.path.join(_HERE, "match-instructions.py")
)
mi = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mi)


class TestExpandBraces(unittest.TestCase):
    def test_no_braces(self):
        self.assertEqual(mi.expand_braces("a/b.rb"), ["a/b.rb"])

    def test_simple_union(self):
        self.assertEqual(sorted(mi.expand_braces("*.{js,jsx}")), ["*.js", "*.jsx"])

    def test_nested_union(self):
        self.assertEqual(
            sorted(mi.expand_braces("{a,{b,c}}.rb")),
            ["a.rb", "b.rb", "c.rb"],
        )

    def test_unbalanced_is_literal(self):
        self.assertEqual(mi.expand_braces("a{b.rb"), ["a{b.rb"])

    def test_blowup_guard_bounds_output(self):
        # Deeply nested/repeated braces would explode combinatorially
        # (2**20 here); the guard keeps the result bounded instead of OOMing,
        # falling back to literal sub-patterns once the cap is exceeded.
        pattern = "{a,b}" * 20  # 2**20 alternatives without the guard
        result = mi.expand_braces(pattern)
        self.assertLessEqual(len(result), mi.MAX_BRACE_EXPANSIONS + 1)
        self.assertGreaterEqual(len(result), 1)


class TestGlobMatching(unittest.TestCase):
    def matches(self, pattern, path):
        return mi.any_match(path, [pattern])

    def test_single_star_is_root_anchored_only(self):
        self.assertTrue(self.matches("*.rb", "foo.rb"))
        self.assertFalse(self.matches("*.rb", "lib/foo.rb"))

    def test_doublestar_slash_matches_any_depth(self):
        self.assertTrue(self.matches("**/*.rb", "foo.rb"))
        self.assertTrue(self.matches("**/*.rb", "lib/foo.rb"))
        self.assertTrue(self.matches("**/*.rb", "a/b/c/foo.rb"))

    def test_trailing_doublestar_matches_subtree(self):
        self.assertTrue(self.matches("src/**", "src/a/b.rb"))
        self.assertFalse(self.matches("src/**", "lib/a.rb"))

    def test_non_segment_doublestar_does_not_cross_dirs(self):
        # ``a**b`` is NOT its own path segment, so it behaves like a single ``*``
        # confined to one segment (doublestar semantics), not ``.*``.
        self.assertTrue(self.matches("a**b", "axxb"))
        self.assertFalse(self.matches("a**b", "a/x/b"))

    def test_dir_prefix_doublestar(self):
        self.assertTrue(self.matches("app/**/*.js", "app/x.js"))
        self.assertTrue(self.matches("app/**/*.js", "app/a/b/x.js"))
        self.assertFalse(self.matches("app/**/*.js", "lib/x.js"))

    def test_question_mark_single_char_no_slash(self):
        self.assertTrue(self.matches("a?c", "abc"))
        self.assertFalse(self.matches("a?c", "a/c"))

    def test_brace_in_path(self):
        self.assertTrue(self.matches("src/{a,b}.rb", "src/a.rb"))
        self.assertTrue(self.matches("src/{a,b}.rb", "src/b.rb"))
        self.assertFalse(self.matches("src/{a,b}.rb", "src/c.rb"))


class TestFileMatches(unittest.TestCase):
    def test_empty_filters_match_everything(self):
        self.assertTrue(mi.file_matches("anything.py", []))

    def test_positive_required(self):
        self.assertTrue(mi.file_matches("foo.rb", ["**/*.rb"]))
        self.assertFalse(mi.file_matches("foo.py", ["**/*.rb"]))

    def test_exclusion(self):
        filters = ["**/*.rb", "!spec/**"]
        self.assertTrue(mi.file_matches("lib/foo.rb", filters))
        self.assertFalse(mi.file_matches("spec/foo.rb", filters))

    def test_only_negatives_match_everything_except_exclusions(self):
        filters = ["!vendor/**"]
        self.assertTrue(mi.file_matches("lib/foo.rb", filters))
        self.assertFalse(mi.file_matches("vendor/x.rb", filters))

    def test_blank_filters_ignored(self):
        self.assertTrue(mi.file_matches("foo.rb", ["", "  ", "**/*.rb"]))


def _git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _write(repo, rel, content, mode="w"):
    with open(os.path.join(repo, rel), mode, encoding="utf-8") as fh:
        fh.write(content)


class GitRepoTestCase(unittest.TestCase):
    """Base for tests needing a throwaway git repo: a temp repo on ``main`` with
    a local identity and commit signing disabled. Run callables inside the repo
    via ``_in_repo``; the temp dir is removed automatically on teardown."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = self.tmp.name
        _git(self.repo, "init", "-q", "-b", "main")
        _git(self.repo, "config", "user.email", "t@e.st")
        _git(self.repo, "config", "user.name", "Test")
        _git(self.repo, "config", "commit.gpgsign", "false")

    def _in_repo(self, fn):
        cwd = os.getcwd()
        os.chdir(self.repo)
        try:
            return fn()
        finally:
            os.chdir(cwd)


class TestBaseResolution(GitRepoTestCase):
    """Fork-point / target resolution must be purely local and match how an MR
    diff is computed (merge-base with the target), never a stale remote pointer."""

    def setUp(self):
        super().setUp()
        _write(self.repo, "base.txt", "base\n")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-qm", "base")
        # Branch off main and add a feature commit.
        _git(self.repo, "checkout", "-q", "-b", "feature")
        _write(self.repo, "feat.txt", "feat\n")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-qm", "feat")
        # Advance main beyond the fork point so merge-base != tip-of-main.
        _git(self.repo, "checkout", "-q", "main")
        _write(self.repo, "base.txt", "more\n", mode="a")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-qm", "main moves on")
        self.main_tip = subprocess.run(
            ["git", "rev-parse", "main"],
            cwd=self.repo,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        _git(self.repo, "checkout", "-q", "feature")
        self.fork = subprocess.run(
            ["git", "merge-base", "main", "HEAD"],
            cwd=self.repo,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

    def test_prefers_local_default_branch(self):
        target, auto = self._in_repo(lambda: mi.detect_target(None))
        self.assertEqual(target, "main")
        self.assertTrue(auto)

    def test_fork_point_is_merge_base_not_tip(self):
        base = self._in_repo(lambda: mi.fork_point("main"))
        self.assertEqual(base, self.fork)
        self.assertNotEqual(base, self.main_tip)

    def test_explicit_target_not_autodetected(self):
        target, auto = mi.detect_target("some-branch")
        self.assertEqual(target, "some-branch")
        self.assertFalse(auto)


class TestFileDiffStagedRevert(GitRepoTestCase):
    """file_diff must stay consistent with changed_files. A file staged then
    reverted in the worktree to match the base still differs from ref in the
    index, so changed_files reports it; file_diff must then yield a non-empty
    diff (falling back to the index-vs-ref diff) rather than silence."""

    def setUp(self):
        super().setUp()
        self.path = "f.txt"
        _write(self.repo, self.path, "base\n")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-qm", "base")
        # Stage a change, then revert the worktree copy back to base WITHOUT
        # unstaging: index != HEAD, but worktree == HEAD.
        _write(self.repo, self.path, "changed\n")
        _git(self.repo, "add", self.path)
        _write(self.repo, self.path, "base\n")

    def test_changed_files_reports_it(self):
        tracked, _ = self._in_repo(lambda: mi.changed_files(None, False))
        self.assertIn(self.path, tracked)

    def test_file_diff_falls_back_to_staged(self):
        diff = self._in_repo(lambda: mi.file_diff(self.path, None, set()))
        self.assertTrue(
            diff.strip(),
            "a staged-then-reverted file must not yield an empty diff",
        )
        self.assertIn("changed", diff)


if __name__ == "__main__":
    unittest.main()
