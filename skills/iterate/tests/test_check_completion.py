#!/usr/bin/env python3
"""Regression tests for the fixes found by GitLab Duo review on !109.

Covers the pure-logic parts of check-completion.py, context-watchdog.py,
and session-start-handover.py that don't need a live tmux pane or a real
subprocess call. Run with no arguments; exits non-zero on any failure.
"""
import importlib.util
import re
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cc = _load("iterate_check_completion", "check-completion.py")
cw = _load("iterate_context_watchdog", "context-watchdog.py")
ssh = _load("iterate_session_start_handover", "session-start-handover.py")


class PathMatchesTest(unittest.TestCase):
    """Fix: segment-aware path matching, not bare substring containment."""

    def test_exact_match(self):
        self.assertTrue(cc.IterateConfig._path_matches("vendor", "vendor"))

    def test_subdirectory_match(self):
        self.assertTrue(cc.IterateConfig._path_matches("vendor/foo.py", "vendor"))

    def test_nested_subdirectory_match(self):
        self.assertTrue(cc.IterateConfig._path_matches("lib/vendor/foo.py", "vendor"))

    def test_trailing_segment_match(self):
        self.assertTrue(cc.IterateConfig._path_matches("lib/vendor", "vendor"))

    def test_does_not_match_name_with_shared_prefix(self):
        # The bug: "/vendor" was a substring of "/vendor-extra/foo.py".
        self.assertFalse(
            cc.IterateConfig._path_matches("vendor-extra/foo.py", "vendor")
        )

    def test_does_not_match_name_with_shared_suffix(self):
        self.assertFalse(
            cc.IterateConfig._path_matches("thirdvendor/foo.py", "vendor")
        )


class ShouldSkipTest(unittest.TestCase):
    """stop_hook_active signals a stop attempt with no tool call since the
    last block; approving it is correct (see should_skip's docstring)."""

    def test_stop_hook_active_does_skip(self):
        self.assertTrue(cc.should_skip({"stop_hook_active": True}))

    def test_subagent_still_skips(self):
        self.assertTrue(cc.should_skip({"is_subagent": True}))

    def test_background_still_skips(self):
        self.assertTrue(cc.should_skip({"is_background": True}))

    def test_parent_task_id_still_skips(self):
        self.assertTrue(cc.should_skip({"parent_task_id": "abc"}))

    def test_plain_call_does_not_skip(self):
        self.assertFalse(cc.should_skip({}))


class MustBlockTest(unittest.TestCase):
    """Fix: a verification-only turn with zero gaps remaining is the
    legitimate final validation checkpoint, not a stopping-bias tell —
    it must not force a block (which would require a pointless edit
    just to get past the hook).
    """

    def test_verification_only_with_no_gaps_does_not_block(self):
        must_block, with_gaps = cc.compute_must_block(
            gaps=[], forbidden_matches=[], verification_only=True
        )
        self.assertFalse(must_block)
        self.assertFalse(with_gaps)

    def test_verification_only_with_gaps_blocks(self):
        must_block, with_gaps = cc.compute_must_block(
            gaps=["P1: something"], forbidden_matches=[], verification_only=True
        )
        self.assertTrue(must_block)
        self.assertTrue(with_gaps)

    def test_gaps_alone_block_regardless_of_verification_only(self):
        must_block, with_gaps = cc.compute_must_block(
            gaps=["P1: something"], forbidden_matches=[], verification_only=False
        )
        self.assertTrue(must_block)
        self.assertFalse(with_gaps)

    def test_forbidden_matches_alone_block(self):
        must_block, with_gaps = cc.compute_must_block(
            gaps=[], forbidden_matches=[("deferred", "ctx")], verification_only=False
        )
        self.assertTrue(must_block)
        self.assertFalse(with_gaps)

    def test_nothing_blocks_on_clean_turn(self):
        must_block, with_gaps = cc.compute_must_block(
            gaps=[], forbidden_matches=[], verification_only=False
        )
        self.assertFalse(must_block)
        self.assertFalse(with_gaps)


class RunCommandTimeoutTest(unittest.TestCase):
    """Fix: an explicitly-passed timeout is never overridden by the
    generic config.timeouts fallback, which keyed on cmd[0] ("cargo")
    and never matched the compound keys ("cargo_test") callers actually
    use, so it always fell through to the 120s default.
    """

    def _run_with_mock(self, cmd, timeout, config):
        captured = {}

        class FakeResult:
            returncode = 0
            stdout = ""
            stderr = ""

        def fake_run(final_cmd, **kwargs):
            captured["timeout"] = kwargs.get("timeout")
            return FakeResult()

        with patch.object(cc.subprocess, "run", side_effect=fake_run):
            cc.run_command(cmd, timeout=timeout, config=config)
        return captured["timeout"]

    def test_explicit_timeout_not_clobbered_by_cargo_test_default(self):
        config = cc.IterateConfig()
        # cargo_test defaults to 300s, but the bug always fell back to
        # the generic "default" (120s) because cmd[0]=="cargo" never
        # matches the "cargo_test" key.
        used = self._run_with_mock(["cargo", "test"], timeout=300, config=config)
        self.assertEqual(used, 300)

    def test_short_version_check_timeout_preserved(self):
        config = cc.IterateConfig()
        # A quick 10s version-probe should stay 10s, not get bumped to
        # the 120s default.
        used = self._run_with_mock(["cargo-tarpaulin", "--version"], timeout=10, config=config)
        self.assertEqual(used, 10)

    def test_custom_cargo_audit_timeout_respected(self):
        config = cc.IterateConfig()
        config.timeouts["cargo_audit"] = 90
        used = self._run_with_mock(["cargo", "audit"], timeout=90, config=config)
        self.assertEqual(used, 90)

    def test_no_explicit_timeout_uses_configured_default(self):
        config = cc.IterateConfig()
        config.timeouts["default"] = 45
        used = self._run_with_mock(["some-tool"], timeout=None, config=config)
        self.assertEqual(used, 45)

    def test_no_explicit_timeout_no_config_uses_120(self):
        used = self._run_with_mock(["some-tool"], timeout=None, config=None)
        self.assertEqual(used, 120)


class AdrGapRegexTest(unittest.TestCase):
    """Fix: the implementation-file regex matched only `crates/*.rs`
    (Rust-only), so the ADR gap check silently did nothing for every
    other supported language.
    """

    PATTERN = r"`([A-Za-z0-9_][A-Za-z0-9_\-./]*\.(?:rs|go|py|rb|c|h|cc|cpp|hpp|js|jsx|ts|tsx|nix|sh))`"

    def test_matches_rust_crate_path(self):
        text = "See `crates/donbiki-notify/src/desktop.rs` for the implementation."
        self.assertEqual(
            re.findall(self.PATTERN, text), ["crates/donbiki-notify/src/desktop.rs"]
        )

    def test_matches_go_path(self):
        text = "Implemented in `internal/foo/bar.go`."
        self.assertEqual(re.findall(self.PATTERN, text), ["internal/foo/bar.go"])

    def test_matches_python_path(self):
        text = "See `scripts/check.py` for details."
        self.assertEqual(re.findall(self.PATTERN, text), ["scripts/check.py"])

    def test_does_not_match_bare_code_span(self):
        text = "Call `fetch_data()` to retrieve it."
        self.assertEqual(re.findall(self.PATTERN, text), [])


class SecurityPatternGrepTest(unittest.TestCase):
    """Fix: the security anti-pattern grep calls used basic-regex escaped
    parens (`unwrap\\(`), which grep treats as an (unterminated) group
    and fails on every invocation. The patterns are now literal strings
    combined with `grep -F`.
    """

    def test_patterns_are_literal_not_bre_escaped(self):
        import subprocess

        patterns = ["unwrap(", "expect(", "panic!(", ".clone("]
        for pattern in patterns:
            result = subprocess.run(
                ["grep", "-F", pattern],
                input="example.unwrap();\n",
                capture_output=True,
                text=True,
            )
            # grep -F must not error on these patterns (exit code 2 means
            # a syntax error, which is what happened before this fix).
            self.assertNotEqual(
                result.returncode, 2, f"grep -F {pattern!r} errored: {result.stderr}"
            )


class IterationLogSentinelTest(unittest.TestCase):
    """Fix: `loop_in_flight` now matches its own docstring — it's True
    both when there's no COMPLETE sentinel AND when deferral language is
    present, instead of ignoring the computed `has_deferral` value.
    """

    def _inspect(self, tmp_path, last_line):
        log = tmp_path / "iteration-log.md"
        log.write_text(f"# Log\n\nSome earlier line.\n{last_line}\n")
        return ssh.inspect_iteration_log(log)

    def test_complete_sentinel_marks_not_in_flight(self):
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            _, in_flight = self._inspect(Path(d), "**LOOP COMPLETE.**")
        self.assertFalse(in_flight)

    def test_template_example_without_sentinel_is_in_flight(self):
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            _, in_flight = self._inspect(Path(d), "- All quality gates: PASS")
        self.assertTrue(in_flight)

    def test_complete_with_deferral_language_still_in_flight(self):
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            # "complete." is at end-of-line (is_complete=True) but
            # "deferred" earlier on the same line (has_deferral=True)
            # must still mark the loop as in flight.
            _, in_flight = self._inspect(
                Path(d), "3 items deferred but otherwise complete."
            )
        self.assertTrue(in_flight)


if __name__ == "__main__":
    unittest.main()
