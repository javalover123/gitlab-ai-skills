"""Tests for scripts/gates.sh using stub tools on an isolated PATH.

The stubs record every invocation so the tests can assert which gates ran for each
context, and that a failing tool fails the run. Run: python3 -m unittest discover tests
"""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
GATES = HERE.parent / "scripts" / "gates.sh"
# NO_GIT=1 hides git from the isolated PATH, to reproduce CI images that don't ship it.
HAVE_GIT = bool(shutil.which("git")) and not os.environ.get("NO_GIT")
CORE = ["bash", "sh", "git", "python3", "grep", "sed", "tr", "mktemp", "cat", "head", "tail", "find", "sort",
        "dirname", "basename", "wc", "rm", "mkdir", "env", "uniq", "xargs", "cut", "printf", "tee", "awk", "ls", "test", "timeout", "sleep"]


class GatesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.log = self.root / "calls.log"
        self.log.write_text("")
        for name in CORE:
            real = shutil.which(name)
            if real and not (name == "git" and not HAVE_GIT):
                (self.bin / name).symlink_to(real)
        self.proj = self.root / "proj"
        self.proj.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def stub(self, name, rc=0, out="", to_stderr=False):
        path = self.bin / name
        redirect = " >&2" if to_stderr else ""
        path.write_text(f'#!/bin/sh\necho "{name} $*" >> "{self.log}"\n[ -n "{out}" ] && echo "{out}"{redirect}\nexit {rc}\n')
        path.chmod(0o755)

    def run_gates(self, *args, cwd=None):
        env = {"PATH": str(self.bin), "HOME": str(self.root), "GIT_CONFIG_GLOBAL": "/dev/null"}
        return subprocess.run(["bash", str(GATES), *args], cwd=cwd or self.proj, env=env,
                              capture_output=True, text=True)

    def calls(self):
        return self.log.read_text()

    def git_init(self, files):
        """Write files; make it a git repo too when git is available (gates.sh falls back to find)."""
        for rel, content in files.items():
            p = self.proj / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
        if not HAVE_GIT:
            return
        subprocess.run(["git", "init", "-q"], cwd=self.proj, env={"PATH": str(self.bin), "HOME": str(self.root)})
        subprocess.run(["git", "add", "-A"], cwd=self.proj, env={"PATH": str(self.bin), "HOME": str(self.root)})

    def test_flake_project_runs_parse_format_eval_and_reports_summary(self):
        for tool in ("nix-instantiate", "nixfmt", "nix"):
            self.stub(tool)
        self.git_init({"flake.nix": "{ outputs = _: { }; }\n", "pkg.nix": "{ }\n"})
        r = self.run_gates("--context", "project", "--no-build")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("PASS parse", r.stdout)
        self.assertIn("PASS format", r.stdout)
        self.assertIn("PASS eval", r.stdout)
        self.assertIn("nix flake check --no-build", self.calls())
        self.assertIn("nixfmt --check", self.calls())
        self.assertIn("Gates run:", r.stdout)
        self.assertIn("Not run:", r.stdout)

    def test_missing_tools_are_skipped_not_failed(self):
        self.git_init({"pkg.nix": "{ }\n"})
        r = self.run_gates("--context", "project", "--no-build")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("SKIP parse", r.stdout)
        self.assertIn("SKIP format", r.stdout)
        self.assertIn("nixfmt", r.stdout)  # tells you what to install

    def test_failing_tool_fails_the_run_and_shows_output(self):
        self.stub("nix-instantiate", rc=1, out="error: syntax error, unexpected '}'", to_stderr=True)
        self.git_init({"pkg.nix": "{ \n"})
        r = self.run_gates("--context", "project", "--no-build")
        self.assertEqual(r.returncode, 1)
        self.assertIn("FAIL parse", r.stdout)
        self.assertIn("syntax error", r.stdout)
        # A failing gate is recorded and the run continues to the summary (set -e must not abort it).
        self.assertIn("Gates run:", r.stdout)
        self.assertIn("parse FAIL", r.stdout)

    def test_antipattern_errors_fail_and_warnings_do_not(self):
        self.git_init({"bad.nix": "stdenv.mkDerivation rec { }\n"})
        r = self.run_gates("--context", "project", "--no-build")
        self.assertEqual(r.returncode, 1)
        self.assertIn("FAIL antipatterns", r.stdout)
        shutil.rmtree(self.proj)
        self.proj.mkdir()
        self.git_init({"warn.nix": "x = with lib; y;\n"})
        r = self.run_gates("--context", "project", "--no-build")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("PASS antipatterns", r.stdout)

    @unittest.skipUnless(HAVE_GIT, "changed-file detection needs git")
    def test_nixpkgs_context_checks_changed_packages_only(self):
        for tool in ("nix-instantiate", "nix-build", "nixfmt"):
            self.stub(tool)
        self.git_init({
            "lib/default.nix": "{ }\n",
            "pkgs/by-name/fo/foo/package.nix": "{ }\n",
            "pkgs/by-name/ba/bar/package.nix": "{ }\n",
            "ci/nixpkgs-vet.sh": "#!/bin/sh\necho vet \"$@\" >> " + str(self.log) + "\n",
        })
        os.chmod(self.proj / "ci/nixpkgs-vet.sh", 0o755)
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "base"], cwd=self.proj,
                       env={"PATH": str(self.bin), "HOME": str(self.root)})
        (self.proj / "pkgs/by-name/fo/foo/package.nix").write_text("{ x = 1; }\n")
        r = self.run_gates("--context", "nixpkgs")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        calls = self.calls()
        self.assertIn("nix-instantiate -A foo", calls)
        self.assertNotIn("-A bar", calls)
        self.assertIn("nix-build -A foo", calls)
        self.assertIn("vet master", calls)
        self.assertIn("PASS by-name vet", r.stdout)
        self.assertIn("nixpkgs-review", r.stdout)  # reminder of manual gates

    def test_nixpkgs_no_build_skips_the_build_gate(self):
        for tool in ("nix-instantiate", "nix-build"):
            self.stub(tool)
        self.git_init({"lib/default.nix": "{ }\n", "pkgs/by-name/fo/foo/package.nix": "{ }\n"})
        r = self.run_gates("--context", "nixpkgs", "--no-build", "--paths", "pkgs/by-name/fo/foo/package.nix")
        self.assertNotIn("nix-build", self.calls())
        self.assertIn("SKIP build", r.stdout)

    def test_auto_detects_context(self):
        self.git_init({"lib/default.nix": "{ }\n", "pkgs/by-name/fo/foo/package.nix": "{ }\n"})
        r = self.run_gates("--no-build", "--paths", "pkgs/by-name/fo/foo/package.nix")
        self.assertIn("context: nixpkgs", r.stdout)
        shutil.rmtree(self.proj)
        self.proj.mkdir()
        self.git_init({"flake.nix": "{ outputs = _: { nixosConfigurations.box = {}; }; }\n"})
        r = self.run_gates("--no-build")
        self.assertIn("context: nixos", r.stdout)
        shutil.rmtree(self.proj)
        self.proj.mkdir()
        self.git_init({"shell.nix": "{ }\n"})
        r = self.run_gates("--no-build")
        self.assertIn("context: project", r.stdout)

    def test_nixos_context_evaluates_each_host(self):
        self.stub("nix-instantiate")
        self.stub("nix", out="[\"box\"]")
        self.git_init({"flake.nix": "{ outputs = _: { nixosConfigurations.box = {}; }; }\n"})
        r = self.run_gates("--context", "nixos", "--no-build")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("nixosConfigurations.box.config.system.build.toplevel.drvPath", self.calls())

    def test_vet_is_skipped_under_no_build_because_it_needs_network_and_builds(self):
        self.stub("nix-instantiate")
        self.git_init({"lib/default.nix": "{ }\n", "pkgs/by-name/fo/foo/package.nix": "{ }\n",
                       "ci/nixpkgs-vet.sh": "#!/bin/sh\necho vet >> " + str(self.log) + "\n"})
        os.chmod(self.proj / "ci/nixpkgs-vet.sh", 0o755)
        r = self.run_gates("--context", "nixpkgs", "--no-build", "--paths", "pkgs/by-name/fo/foo/package.nix")
        self.assertNotIn("vet", self.calls())
        self.assertIn("SKIP by-name vet", r.stdout)

    def test_a_hung_gate_times_out_and_fails_instead_of_blocking(self):
        slow = self.bin / "nix-instantiate"
        slow.write_text("#!/bin/sh\nsleep 30\n")
        slow.chmod(0o755)
        self.git_init({"pkg.nix": "{ }\n"})
        env = {"PATH": str(self.bin), "HOME": str(self.root), "GIT_CONFIG_GLOBAL": "/dev/null", "GATE_TIMEOUT": "1"}
        r = subprocess.run(["bash", str(GATES), "--context", "project", "--no-build"], cwd=self.proj, env=env,
                           capture_output=True, text=True, timeout=20)
        self.assertEqual(r.returncode, 1)
        self.assertIn("FAIL parse", r.stdout)
        self.assertIn("timed out after 1s", r.stdout)

    def test_bad_context_is_a_usage_error(self):
        r = self.run_gates("--context", "bogus")
        self.assertEqual(r.returncode, 2)
        self.assertIn("usage", (r.stdout + r.stderr).lower())

    def test_no_nix_files_is_a_clean_noop(self):
        self.git_init({"README.md": "hi\n"})
        r = self.run_gates("--context", "project", "--no-build")
        self.assertEqual(r.returncode, 0)
        self.assertIn("no .nix files", r.stdout)


if __name__ == "__main__":
    unittest.main()
