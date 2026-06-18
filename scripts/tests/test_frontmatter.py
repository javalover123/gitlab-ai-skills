#!/usr/bin/env python3
"""Tests for lib/frontmatter — especially edge cases around ``---`` handling
and the strict YAML validation added to validate_frontmatter.py.

Run:  python3 scripts/tests/test_frontmatter.py
"""

import os
import sys
import tempfile
import unittest

# Allow imports from the scripts/ directory.
SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCRIPTS_DIR)

from lib.frontmatter import extract_raw_frontmatter, parse_frontmatter  # noqa: E402

try:
    import yaml

    HAS_YAML = True
except ImportError:
    HAS_YAML = False


def _write_temp(content):
    """Write *content* to a temporary file and return the path."""
    fd, path = tempfile.mkstemp(suffix=".md")
    with os.fdopen(fd, "w") as f:
        f.write(content)
    return path


class TestExtractRawFrontmatter(unittest.TestCase):
    """Regression tests for ``extract_raw_frontmatter``."""

    def test_simple(self):
        path = _write_temp("---\nname: foo\n---\n# body\n")
        try:
            raw = extract_raw_frontmatter(path)
            self.assertIsNotNone(raw)
            self.assertIn("name: foo", raw)
        finally:
            os.unlink(path)

    def test_no_frontmatter(self):
        path = _write_temp("# Just a heading\n")
        try:
            self.assertIsNone(extract_raw_frontmatter(path))
        finally:
            os.unlink(path)

    def test_no_closing_delimiter(self):
        path = _write_temp("---\nname: foo\n")
        try:
            self.assertIsNone(extract_raw_frontmatter(path))
        finally:
            os.unlink(path)

    def test_dashes_inside_quoted_value(self):
        """Regression: ``---`` inside a quoted value must NOT close the block.

        This was the BLOCKER-1 bug — ``content.split('---', 2)`` truncated
        values containing ``---``.
        """
        content = (
            '---\n'
            'name: foo\n'
            'description: "Use this --- it is great"\n'
            'version: 1.0.0\n'
            'license: MIT\n'
            '---\n'
            '# body\n'
        )
        path = _write_temp(content)
        try:
            raw = extract_raw_frontmatter(path)
            self.assertIsNotNone(raw)
            # The full description line must be present, not truncated at ---.
            self.assertIn('description: "Use this --- it is great"', raw)
            # The raw block should include all frontmatter fields.
            self.assertIn("name: foo", raw)
            self.assertIn("version: 1.0.0", raw)
        finally:
            os.unlink(path)

    def test_dashes_inside_quoted_value_parses_as_yaml(self):
        """When PyYAML is available, the extracted block must parse cleanly."""
        if not HAS_YAML:
            self.skipTest("PyYAML not installed")

        content = (
            '---\n'
            'name: foo\n'
            'description: "Use this --- it is great"\n'
            'version: 1.0.0\n'
            'license: MIT\n'
            '---\n'
        )
        path = _write_temp(content)
        try:
            raw = extract_raw_frontmatter(path)
            result = yaml.safe_load(raw)
            self.assertEqual(result["description"], "Use this --- it is great")
        finally:
            os.unlink(path)


class TestStrictYamlDetectsUnquotedColon(unittest.TestCase):
    """The motivating bug: an unquoted value containing ``: `` is invalid YAML."""

    @unittest.skipUnless(HAS_YAML, "PyYAML not installed")
    def test_unquoted_colon_in_value_is_rejected(self):
        content = (
            '---\n'
            'name: foo\n'
            'description: MUST USE before ... Triggers: review, plan\n'
            'version: 1.0.0\n'
            'license: MIT\n'
            '---\n'
        )
        path = _write_temp(content)
        try:
            raw = extract_raw_frontmatter(path)
            with self.assertRaises(yaml.YAMLError):
                yaml.safe_load(raw)
        finally:
            os.unlink(path)

    @unittest.skipUnless(HAS_YAML, "PyYAML not installed")
    def test_quoted_colon_in_value_is_accepted(self):
        content = (
            '---\n'
            'name: foo\n'
            'description: "MUST USE before ... Triggers: review, plan"\n'
            'version: 1.0.0\n'
            'license: MIT\n'
            '---\n'
        )
        path = _write_temp(content)
        try:
            raw = extract_raw_frontmatter(path)
            result = yaml.safe_load(raw)
            self.assertIn("Triggers:", result["description"])
        finally:
            os.unlink(path)

    @unittest.skipUnless(HAS_YAML, "PyYAML not installed")
    def test_strict_yaml_check_includes_line_and_column(self):
        """The error message must include line/column for actionability."""
        from validate_frontmatter import strict_yaml_check

        content = (
            '---\n'
            'name: foo\n'
            'description: MUST USE before ... Triggers: review, plan\n'
            'version: 1.0.0\n'
            'license: MIT\n'
            '---\n'
        )
        path = _write_temp(content)
        try:
            err = strict_yaml_check(path)
            self.assertIsNotNone(err)
            self.assertIn("not valid YAML", err)
            # Must include line/column context from problem_mark.
            self.assertRegex(err, r"line \d+, column \d+")
        finally:
            os.unlink(path)


class TestMissingClosingDelimiter(unittest.TestCase):
    """A file that opens with ``---`` but never closes must be caught."""

    def test_unclosed_frontmatter_returns_none(self):
        """extract_raw_frontmatter returns None for an unclosed block."""
        content = (
            '---\n'
            'name: badskill\n'
            'description: MUST USE. Triggers: a, b\n'
            'version: 1.0.0\n'
            'license: MIT\n'
        )
        path = _write_temp(content)
        try:
            self.assertIsNone(extract_raw_frontmatter(path))
        finally:
            os.unlink(path)

    def test_unclosed_frontmatter_detected_by_validator(self):
        """The validator must surface an explicit error, not silently pass."""
        # Import the check function from validate_frontmatter
        sys.path.insert(0, SCRIPTS_DIR)
        from validate_frontmatter import check_frontmatter_delimiters

        content = (
            '---\n'
            'name: badskill\n'
            'description: MUST USE. Triggers: a, b\n'
            'version: 1.0.0\n'
            'license: MIT\n'
        )
        path = _write_temp(content)
        try:
            err = check_frontmatter_delimiters(path)
            self.assertIsNotNone(err)
            self.assertIn("missing closing frontmatter delimiter", err)
        finally:
            os.unlink(path)

    def test_closed_frontmatter_no_delimiter_error(self):
        """A properly closed block must not trigger the delimiter error."""
        sys.path.insert(0, SCRIPTS_DIR)
        from validate_frontmatter import check_frontmatter_delimiters

        content = (
            '---\n'
            'name: goodskill\n'
            'description: A valid skill\n'
            'version: 1.0.0\n'
            'license: MIT\n'
            '---\n'
        )
        path = _write_temp(content)
        try:
            err = check_frontmatter_delimiters(path)
            self.assertIsNone(err)
        finally:
            os.unlink(path)


class TestParseFrontmatterBackcompat(unittest.TestCase):
    """The lenient parser must keep working for existing callers."""

    def test_basic_fields(self):
        content = (
            '---\n'
            'name: my-skill\n'
            'description: A test skill\n'
            'version: 1.0.0\n'
            'license: MIT\n'
            '---\n'
        )
        path = _write_temp(content)
        try:
            fields = parse_frontmatter(path)
            self.assertEqual(fields["name"], "my-skill")
            self.assertEqual(fields["description"], "A test skill")
            self.assertEqual(fields["version"], "1.0.0")
        finally:
            os.unlink(path)

    def test_multiline_folded(self):
        content = (
            '---\n'
            'name: my-skill\n'
            'description: >\n'
            '  First line\n'
            '  second line\n'
            'version: 1.0.0\n'
            'license: MIT\n'
            '---\n'
        )
        path = _write_temp(content)
        try:
            fields = parse_frontmatter(path)
            self.assertEqual(fields["description"], "First line second line")
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
