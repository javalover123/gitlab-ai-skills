#!/usr/bin/env python3
"""Tests for validate_content_quality — link resolution, teaching-line
exemptions, compound-word handling, and structural cues.

Run:  python3 scripts/tests/test_content_quality.py
"""

import os
import sys
import tempfile
import unittest

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SCRIPTS_DIR)

import validate_content_quality as vcq  # noqa: E402


class TempSkill:
    """Context manager that builds a throwaway skill dir with a SKILL.md."""

    def __init__(self, body, refs=None):
        self.body = body
        self.refs = refs or {}

    def __enter__(self):
        self.dir = tempfile.mkdtemp()
        self.skill_md = os.path.join(self.dir, "SKILL.md")
        with open(self.skill_md, "w") as f:
            f.write(self.body)
        if self.refs:
            ref_dir = os.path.join(self.dir, "references")
            os.makedirs(ref_dir, exist_ok=True)
            for name, content in self.refs.items():
                with open(os.path.join(ref_dir, name), "w") as f:
                    f.write(content)
        return self

    def __exit__(self, *a):
        import shutil

        shutil.rmtree(self.dir, ignore_errors=True)


class TestLinks(unittest.TestCase):
    def test_resolving_link_passes(self):
        with TempSkill("[ref](references/a.md)\n", refs={"a.md": "# a"}) as s:
            self.assertEqual(vcq.check_links(s.skill_md), [])

    def test_broken_link_flagged(self):
        with TempSkill("[ref](references/missing.md)\n") as s:
            errs = vcq.check_links(s.skill_md)
            self.assertEqual(len(errs), 1)
            self.assertIn("missing.md", errs[0])

    def test_external_and_anchor_ignored(self):
        body = "[web](https://x.y) [top](#heading) [mail](mailto:a@b.c)\n"
        with TempSkill(body) as s:
            self.assertEqual(vcq.check_links(s.skill_md), [])

    def test_link_in_code_span_ignored(self):
        with TempSkill("`[x](references/nope.md)`\n") as s:
            self.assertEqual(vcq.check_links(s.skill_md), [])

    def test_anchor_stripped_before_resolving(self):
        with TempSkill("[ref](references/a.md#sec)\n", refs={"a.md": "# a"}) as s:
            self.assertEqual(vcq.check_links(s.skill_md), [])


class TestVoice(unittest.TestCase):
    def test_standalone_banned_word_flagged(self):
        with TempSkill("This will utilize the cache.\n") as s:
            warns = vcq.check_voice(s.skill_md)
            self.assertTrue(any("utilize" in w for w in warns))

    def test_hyphenated_compound_not_flagged(self):
        with TempSkill("The highest-leverage change here.\n") as s:
            self.assertEqual(vcq.check_voice(s.skill_md), [])

    def test_teaching_line_exempt(self):
        with TempSkill("Never use: utilize, leverage, robust.\n") as s:
            self.assertEqual(vcq.check_voice(s.skill_md), [])

    def test_frontmatter_not_scanned(self):
        body = "---\nname: x\ndescription: robust thing\n---\n# body\n"
        with TempSkill(body) as s:
            self.assertEqual(vcq.check_voice(s.skill_md), [])


class TestStructure(unittest.TestCase):
    def test_use_when_cue_satisfies(self):
        with TempSkill("# S\n\nUse when you need X.\n") as s:
            warns = vcq.check_structure(s.skill_md)
            self.assertFalse(any("When to Use" in w for w in warns))

    def test_missing_cue_warns(self):
        with TempSkill("# S\n\nJust does a thing.\n") as s:
            warns = vcq.check_structure(s.skill_md)
            self.assertTrue(any("When to Use" in w for w in warns))

    def test_stray_todo_warns(self):
        with TempSkill("# S\n\nUse when X. TODO wire this up.\n") as s:
            warns = vcq.check_structure(s.skill_md)
            self.assertTrue(any("TODO" in w for w in warns))

    def test_todo_in_code_span_ignored(self):
        with TempSkill("# S\n\nUse when X. See `TODO.md`.\n") as s:
            warns = vcq.check_structure(s.skill_md)
            self.assertFalse(any("stray TODO" in w for w in warns))


if __name__ == "__main__":
    unittest.main()
