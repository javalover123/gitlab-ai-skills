"""Tests for scripts/antipatterns.py (stdlib unittest; run: python3 -m unittest discover tests)."""
import contextlib
import importlib.util
import io
import json
import tempfile
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("antipatterns", HERE.parent / "scripts" / "antipatterns.py")
ap = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = ap
SPEC.loader.exec_module(ap)

# rule id -> (snippet that must trigger it, snippet that must NOT trigger it)
CASES = {
    "NL01": ("stdenv.mkDerivation rec {\n  pname = \"x\";\n}", "stdenv.mkDerivation (finalAttrs: {\n  pname = \"x\";\n})"),
    "NL02": ("with lib; mkIf true {}", "meta.maintainers = with lib.maintainers; [ a ];"),
    "NL03": ("buildInputs = with pkgs; [ zlib ];", "buildInputs = [ zlib ];"),
    "NL04": ("import <nixpkgs> {}", "import nixpkgs {}"),
    "NL05": ("sys = builtins.currentSystem;", "sys = stdenv.hostPlatform.system;"),
    "NL06": ("x = lib.optionals stdenv.isDarwin [ a ];", "x = lib.optionals stdenv.hostPlatform.isDarwin [ a ];"),
    "NL07": ("inherit (stdenv.lib) licenses;", "inherit (lib) licenses;"),
    "NL08": ("description = lib.mdDoc \"x\";", "description = \"x\";"),
    "NL09": ("x = if c then [ a ] else [ ];", "x = lib.optional c a;"),
    "NL10": ("postPatch = ''\n  sed -i 's/a/b/' f\n'';", "postPatch = ''\n  substituteInPlace f --replace-fail a b\n'';"),
    "NL11": ("substituteInPlace f --replace a b", "substituteInPlace f --replace-fail a b"),
    "NL12": ("src = substituteAll { src = ./a; };", "src = replaceVars ./a { };"),
    "NL13": ("tag = \"${version}\";", "tag = version;"),
    "NL15": ("src = ./.;", "src = lib.fileset.toSource { root = ./.; fileset = ./src; };"),
    "NL16": ("hash = lib.fakeHash;", "hash = \"sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=\";"),
    "NL17": ("x = builtins.readFile \"${drv}/out\";", "x = builtins.readFile ./local.txt;"),
    "NL18": ("exec = \"${foo}/bin/foo\";", "exec = lib.getExe foo;"),
    "NL19": ("formatter = pkgs.nixfmt-rfc-style;", "formatter = pkgs.nixfmt;"),
    "NL20": ("homepage = https://example.org;", "homepage = \"https://example.org\";"),
    "NL21": ("buildPhase = ''\n  make\n'';", "buildPhase = ''\n  runHook preBuild\n  make\n  runHook postBuild\n'';"),
    "TS01": ("doCheck = false;", "# needs network\ndoCheck = false;"),
    "TS02": ("python3Packages.buildPythonPackage { }", "buildPythonPackage { pythonImportsCheck = [ \"x\" ]; }"),
    "TS03": ("checkInputs = [ pytestCheckHook ];", "nativeCheckInputs = [ pytestCheckHook ];"),
    "TS04": ("nativeBuildInputs = [ versionCheckHook ];", "nativeInstallCheckInputs = [ versionCheckHook ];"),
    "TS05": ("nativeInstallCheckInputs = [ versionCheckHook ];", "doInstallCheck = true;\nnativeInstallCheckInputs = [ versionCheckHook ];"),
    "TS06": ("pytestFlagsArray = [ \"-x\" ];", "pytestFlags = [ \"-x\" ];"),
    "TS07": ("t = pkgs.nixosTest { };", "t = pkgs.testers.runNixOSTest { };"),
    "TS08": ("skipLint = true;", "skipLint = false;"),
    "TS09": ("installCheckPhase = ''\n  $out/bin/x --version\n'';", "doInstallCheck = true;\nnativeInstallCheckInputs = [ versionCheckHook ];"),
    "TS10": ("platformDontCheck = true;", "doCheck = !stdenv.hostPlatform.isDarwin;"),
    "TS11": ("checks.x = pkgs.foo.passthru.tests;", "checks.x = pkgs.foo.passthru.tests.basic;"),
    "FS01": ("src = fetchurl { url = \"u\"; sha256 = \"abc\"; };", "src = fetchurl { url = \"u\"; hash = \"sha256-abc\"; };"),
    "FS02": ("src = fetchFromGitHub { rev = version; };", "src = fetchFromGitHub { tag = version; };"),
    "FS03": ("url = \"http://example.org/x.tar.gz\";", "url = \"https://example.org/x.tar.gz\";"),
    "FS04": ("src = builtins.fetchTarball \"https://x\";", "src = fetchzip { url = \"https://x\"; };"),
    "MT01": ("license = lib.licenses.gpl3;", "license = lib.licenses.gpl3Plus;"),
    "MT02": ("license = lib.licenses.MIT;", "license = lib.licenses.mit;"),
    "MT03": ("description = \"A tool for things.\";", "description = \"Tool for things\";"),
    "MT04": ("list = \"maintainers/maintainers-list.nix\";", "list = \"maintainers/maintainer-list.nix\";"),
    "MT05": ("changelog = \"https://github.com/o/r/blob/master/CHANGELOG.md\";", "changelog = \"https://github.com/o/r/releases/tag/v${version}\";"),
    "DV01": ("name = \"${pname}-${version}\";", "pname = \"x\";\nversion = \"1\";"),
    "DV03": ("phases = [ \"installPhase\" ];", "dontUnpack = true;"),
    "DV04": ("patchPhase = ''\n  runHook prePatch\n  runHook postPatch\n'';", "postPatch = \"true\";"),
    "DV05": ("version = \"unstable-2024-01-01\";", "version = \"0-unstable-2024-01-01\";"),
    "DV07": ("buildInputs = [ darwin.apple_sdk.frameworks.Cocoa ];", "buildInputs = [ zlib ];"),
    "PY01": ("buildPythonPackage { format = \"pyproject\"; }", "buildPythonPackage { pyproject = true; }"),
    "PY02": ("buildPythonPackage { propagatedBuildInputs = [ requests ]; }", "buildPythonPackage { dependencies = [ requests ]; }"),
    "RS01": ("cargoSha256 = \"abc\";", "cargoHash = \"sha256-abc\";"),
    "GO01": ("vendorSha256 = \"abc\";", "vendorHash = \"sha256-abc\";"),
    "SC01": ("fetchurl { curlOpts = \"--insecure\"; }", "fetchurl { curlOpts = \"--retry 3\"; }"),
    "MOD01": ("description = \"see <link xlink:href=\\\"u\\\"/>\";", "description = \"see [u](u)\";"),
    "MOD02": ("users.users.foo.uid = 1234;", "users.users.foo.isSystemUser = true;"),
    "MOD03": ("preStart = ''\n  mkdir -p /var/lib/x\n'';", "serviceConfig.StateDirectory = \"x\";"),
    "BP01": ("sys = pkgs.system;", "sys = pkgs.stdenv.hostPlatform.system;"),
}


class RuleCases(unittest.TestCase):
    def test_every_rule_has_a_case_and_every_case_a_rule(self):
        ids = {r.id for r in ap.RULES}
        untested = ids - set(CASES) - {"NL14"}  # NL14 has its own tests below
        self.assertFalse(untested, f"rules without a test case: {sorted(untested)}")
        self.assertFalse(set(CASES) - ids, "cases for rules that don't exist")

    def test_bad_snippets_trigger_and_good_do_not(self):
        for rid, (bad, good) in CASES.items():
            with self.subTest(rule=rid, kind="bad"):
                self.assertIn(rid, {f.rule for f in ap.check_text(bad, "x.nix")}, f"{rid} did not fire on bad snippet")
            with self.subTest(rule=rid, kind="good"):
                self.assertNotIn(rid, {f.rule for f in ap.check_text(good, "x.nix")}, f"{rid} fired on good snippet")


class Behaviour(unittest.TestCase):
    def test_nl14_flags_package_ellipsis_but_not_modules(self):
        pkg = "{\n  lib,\n  stdenv,\n  ...\n}:\nstdenv.mkDerivation { }"
        module = "{\n  config,\n  lib,\n  ...\n}:\n{ options = { }; config = { }; }"
        self.assertIn("NL14", {f.rule for f in ap.check_text(pkg, "x.nix")})
        self.assertNotIn("NL14", {f.rule for f in ap.check_text(module, "x.nix")})

    def test_findings_carry_line_numbers(self):
        text = "a = 1;\nb = with lib; x;\n"
        f = [x for x in ap.check_text(text, "x.nix") if x.rule == "NL02"][0]
        self.assertEqual(f.line, 2)

    def test_inline_suppression_same_line_and_previous_line(self):
        same = "x = with lib; y; # antipatterns: ignore NL02"
        prev = "# antipatterns: ignore NL02\nx = with lib; y;"
        other = "# antipatterns: ignore NL03\nx = with lib; y;"
        self.assertNotIn("NL02", {f.rule for f in ap.check_text(same, "x.nix")})
        self.assertNotIn("NL02", {f.rule for f in ap.check_text(prev, "x.nix")})
        self.assertIn("NL02", {f.rule for f in ap.check_text(other, "x.nix")})

    def test_comment_only_lines_do_not_trigger_line_rules(self):
        text = "# we used to write with lib; here\nx = 1;"
        self.assertNotIn("NL02", {f.rule for f in ap.check_text(text, "x.nix")})

    def test_phase_with_runhook_through_either_hook_is_clean(self):
        text = "installPhase = ''\n  runHook preInstall\n  install -Dm755 a $out/bin/a\n  runHook postInstall\n'';"
        self.assertNotIn("NL21", {f.rule for f in ap.check_text(text, "x.nix")})

    def test_clean_modern_package_has_no_findings(self):
        text = (
            "{ lib, stdenv, fetchFromGitHub, versionCheckHook }:\n"
            "stdenv.mkDerivation (finalAttrs: {\n"
            "  pname = \"example\";\n  version = \"1.2.3\";\n"
            "  src = fetchFromGitHub {\n    owner = \"o\";\n    repo = \"r\";\n    tag = \"v${finalAttrs.version}\";\n"
            "    hash = \"sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=\";\n  };\n"
            "  strictDeps = true;\n  doInstallCheck = true;\n  nativeInstallCheckInputs = [ versionCheckHook ];\n"
            "  meta = {\n    description = \"Example tool\";\n    license = lib.licenses.mit;\n"
            "    maintainers = with lib.maintainers; [ ];\n  };\n})\n"
        )
        self.assertEqual([f.rule for f in ap.check_text(text, "package.nix")], [])


class Cli(unittest.TestCase):
    def run_cli(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = ap.main(argv)
        return rc, out.getvalue(), err.getvalue()

    def test_exit_codes_and_output(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "bad.nix").write_text("stdenv.mkDerivation rec { }\n")
            (root / "warn.nix").write_text("x = with lib; y;\n")
            (root / "good.nix").write_text("{ }\n")
            (root / "notes.txt").write_text("stdenv.mkDerivation rec {")
            rc, out, _ = self.run_cli([str(root)])
            self.assertEqual(rc, 1)
            self.assertIn("NL01", out)
            self.assertIn("bad.nix:1", out)
            self.assertNotIn("notes.txt", out)
            rc, _, _ = self.run_cli([str(root / "warn.nix")])
            self.assertEqual(rc, 0)  # warnings alone don't fail
            rc, _, _ = self.run_cli(["--strict", str(root / "warn.nix")])
            self.assertEqual(rc, 1)
            rc, out, _ = self.run_cli([str(root / "good.nix")])
            self.assertEqual(rc, 0)

    def test_json_output(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "a.nix"
            f.write_text("x = with lib; y;\n")
            rc, out, _ = self.run_cli(["--json", str(f)])
            data = json.loads(out)
            self.assertEqual(data[0]["rule"], "NL02")
            self.assertEqual(data[0]["severity"], "warn")
            self.assertIn("reference", data[0])

    def test_generated_files_are_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "gemset.nix").write_text("{ x = { sha256 = \"abc\"; }; }\n")
            (root / "lock.nix").write_text("# This file is generated by tool\n{ x = { sha256 = \"abc\"; }; }\n")
            (root / "real.nix").write_text("{ x = { sha256 = \"abc\"; }; }\n")
            rc, out, _ = self.run_cli([str(root)])
            self.assertIn("real.nix", out)
            self.assertNotIn("gemset.nix", out)
            self.assertNotIn("lock.nix", out)

    def test_missing_path_is_usage_error(self):
        rc, _, err = self.run_cli(["/nonexistent/path.nix"])
        self.assertEqual(rc, 2)
        self.assertIn("not found", err)

    def test_list_rules(self):
        rc, out, _ = self.run_cli(["--list-rules"])
        self.assertEqual(rc, 0)
        self.assertIn("NL01", out)
        self.assertIn("nix-language-style.md", out)

    def test_ignore_flag(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "a.nix"
            f.write_text("x = with lib; y;\n")
            rc, out, _ = self.run_cli(["--strict", "--ignore", "NL02", str(f)])
            self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
