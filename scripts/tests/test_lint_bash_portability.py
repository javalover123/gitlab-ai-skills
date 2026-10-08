"""Tests for scripts/lint_bash_portability.sh using throwaway skill trees."""

import os
import subprocess
import tempfile
import unittest

SCRIPT = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "lint_bash_portability.sh")

# One offending line per rule.
VIOLATIONS = {
    "BASHPID": 'echo "$BASHPID"',
    "mapfile": "mapfile -t lines < f",
    "readarray": "readarray -t lines < f",
    "declare -A": "declare -A m",
    "local -A": "local -A m",
    "lowercase": 'x="${v,,}"',
    "uppercase": 'x="${v^^}"',
    "negative index": 'x="${a[-1]}"',
    "@Q": 'x="${v@Q}"',
    "printf time": "printf '%(%s)T\\n' -1",
    "wait -n": "wait -n",
    "EPOCHSECONDS": 'now="$EPOCHSECONDS"',
    "sed -i": "sed -i 's/a/b/' f",
    "sed -i empty suffix": "sed -i '' 's/a/b/' f",
    "date -d": "date -d '1 day ago' +%s",
    "readlink -f": 'p="$(readlink -f "$0")"',
    "grep -P": "grep -P '\\d+' f",
    "stat -c": "stat -c %s f",
    "mktemp --suffix": "mktemp --suffix=.x",
    "find -printf": "find . -printf '%p\\n'",
    "cp --parents": "cp --parents a b",
}

CLEAN = [
    "sed -i.bak 's/a/b/' f && rm f.bak",
    "date +%s",
    "grep -E 'a+' f",
    "wc -c < f",
    'x="${a[${#a[@]}-1]}"',
    "echo mapfiles and mywait -n",
]


class LintBashPortabilityTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = self.tmp.name

    def write(self, rel, *lines):
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write("#!/usr/bin/env bash\n" + "\n".join(lines) + "\n")

    def run_lint(self):
        env = dict(os.environ, PORTABILITY_ROOT=self.root)
        return subprocess.run(["bash", SCRIPT], env=env, capture_output=True, text=True)

    def test_each_rule_fires_with_file_and_line(self):
        for name, line in VIOLATIONS.items():
            with self.subTest(rule=name):
                self.write("skills/demo/scripts/a.sh", line)
                result = self.run_lint()
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("skills/demo/scripts/a.sh:2:", result.stdout)

    def test_portable_code_passes(self):
        self.write("skills/demo/scripts/a.sh", *CLEAN)
        result = self.run_lint()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_comment_lines_are_ignored(self):
        self.write("skills/demo/scripts/a.sh", "# do not use $BASHPID or mapfile", "  # declare -A")
        self.assertEqual(self.run_lint().returncode, 0)

    def test_portability_ok_opts_out_one_line(self):
        self.write("skills/demo/scripts/a.sh", 'a="$BASHPID" # portability-ok: guarded')
        self.assertEqual(self.run_lint().returncode, 0)
        self.write("skills/demo/scripts/a.sh", 'a="$BASHPID" # portability-ok', 'b="$BASHPID"')
        result = self.run_lint()
        self.assertEqual(result.returncode, 1)
        self.assertIn("a.sh:3:", result.stdout)
        self.assertNotIn("a.sh:2:", result.stdout)

    def test_synced_skills_are_excluded(self):
        with open(os.path.join(self.root, "synced-skills.yml"), "w") as f:
            f.write("# c\nskills:\n  synced:\n    source_project: x/y\n    mode: mr\n")
        self.write("skills/synced/scripts/a.sh", 'echo "$BASHPID"')
        self.assertEqual(self.run_lint().returncode, 0)
        self.write("skills/other/scripts/a.sh", 'echo "$BASHPID"')
        self.assertEqual(self.run_lint().returncode, 1)

    def test_repo_scripts_dir_is_out_of_scope(self):
        self.write("scripts/tool.sh", 'echo "$BASHPID"')
        self.write("skills/demo/scripts/a.sh", "true")
        self.assertEqual(self.run_lint().returncode, 0)


if __name__ == "__main__":
    unittest.main()
