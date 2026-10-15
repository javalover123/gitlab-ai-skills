"""Tests for scripts/find-rules.py (stdlib unittest; run: python3 -m unittest discover tests)."""
import importlib.util
import io
import contextlib
import tempfile
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("find_rules", HERE.parent / "scripts" / "find-rules.py")
find_rules = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = find_rules
SPEC.loader.exec_module(find_rules)

TSV = (
    "category\tsupport\tmerged_pct\tchanges_requested\tmaintainer_reviewed\trule\n"
    "derivation-structure\t40\t90\t12\t30\tPut build-time tools in nativeBuildInputs, not buildInputs.\n"
    "fetchers-and-sources\t25\t88\t9\t20\tUse tag = version with fetchFromGitHub instead of rev.\n"
    "fetchers-and-sources\t6\t40\t1\t3\tAvoid fetchSubmodules unless submodules are required.\n"
    "nixos-modules\t18\t70\t7\t10\tUse the settings pattern instead of many individual options.\n"
)


class FindRulesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "rules.tsv"
        self.path.write_text(TSV)
        self.rules = find_rules.load_rules(self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_load_parses_numbers(self):
        self.assertEqual(len(self.rules), 4)
        self.assertEqual(self.rules[0]["support"], 40)
        self.assertEqual(self.rules[0]["category"], "derivation-structure")

    def test_all_keywords_must_match_case_insensitively(self):
        hits = find_rules.search(self.rules, ["FETCHFROMGITHUB", "tag"])
        self.assertEqual([r["support"] for r in hits], [25])

    def test_category_and_min_support_filters(self):
        hits = find_rules.search(self.rules, [], category="fetchers-and-sources", min_support=10)
        self.assertEqual([r["support"] for r in hits], [25])

    def test_default_sort_is_support_descending(self):
        hits = find_rules.search(self.rules, [])
        self.assertEqual([r["support"] for r in hits], [40, 25, 18, 6])

    def test_sort_by_enforcement(self):
        hits = find_rules.search(self.rules, [], sort="enforced")
        self.assertEqual([r["changes_requested"] for r in hits], [12, 9, 7, 1])

    def test_limit(self):
        self.assertEqual(len(find_rules.search(self.rules, [], limit=2)), 2)

    def test_format_line_contains_evidence(self):
        line = find_rules.format_rule(self.rules[0])
        self.assertIn("derivation-structure", line)
        self.assertIn("support 40", line)
        self.assertIn("90% merged", line)
        self.assertIn("nativeBuildInputs", line)

    def test_main_lists_categories(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = find_rules.main(["--rules", str(self.path), "--list-categories"])
        self.assertEqual(rc, 0)
        self.assertIn("fetchers-and-sources", out.getvalue())
        self.assertIn("2", out.getvalue())

    def test_main_no_match_returns_1(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = find_rules.main(["--rules", str(self.path), "zzzzz-nothing"])
        self.assertEqual(rc, 1)

    def test_missing_file_is_a_clear_error(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            rc = find_rules.main(["--rules", str(self.path) + ".missing", "x"])
        self.assertEqual(rc, 2)
        self.assertIn("not found", err.getvalue())


if __name__ == "__main__":
    unittest.main()
