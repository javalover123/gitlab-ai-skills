#!/usr/bin/env python3
"""Regression tests for the fixes found by GitLab Duo review on !111.

Covers the pure-logic parts of check-completion.py that don't need a live
tmux pane or a real subprocess call. Run with no arguments; exits non-zero
on any failure.
"""
import importlib.util
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cc = _load("iteratotron_check_completion", "check-completion.py")


class ShouldSkipTest(unittest.TestCase):
    """Fix: stop_hook_active must not cause an unconditional skip, or the
    orchestration loop ends after exactly one block regardless of how
    much of the scope queue is still undrained. Same bug and fix as
    iterate's should_skip().
    """

    def test_stop_hook_active_alone_does_not_skip(self):
        self.assertFalse(cc.should_skip({"stop_hook_active": True}))

    def test_subagent_still_skips(self):
        self.assertTrue(cc.should_skip({"is_subagent": True}))

    def test_parent_task_id_still_skips(self):
        self.assertTrue(cc.should_skip({"parent_task_id": "abc"}))

    def test_agent_type_still_skips(self):
        self.assertTrue(cc.should_skip({"agent_type": "something"}))

    def test_plain_call_does_not_skip(self):
        self.assertFalse(cc.should_skip({}))


class SessionFixture(unittest.TestCase):
    """Base class that builds a `.iteratotron/<session>/` tree in a temp
    cwd and restores the real cwd on teardown.
    """

    def setUp(self):
        self._orig_cwd = os.getcwd()
        self._tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self._tmpdir.name)
        (self.root / ".iteratotron").mkdir()
        (self.root / ".iteratotron" / "CURRENT").write_text("sess1")
        self.session_dir = self.root / ".iteratotron" / "sess1"
        self.session_dir.mkdir()
        os.chdir(self.root)

    def tearDown(self):
        os.chdir(self._orig_cwd)
        self._tmpdir.cleanup()

    def write_queue(self, *entries):
        lines = [json.dumps(e) for e in entries]
        (self.session_dir / "scope_queue.jsonl").write_text("\n".join(lines) + "\n")

    def write_state(self, started_at=None, time_budget_seconds=None):
        state = {}
        if started_at is not None:
            state["started_at"] = started_at
        if time_budget_seconds is not None:
            state["budgets"] = {"time_budget_seconds": time_budget_seconds}
        (self.session_dir / "state.json").write_text(json.dumps(state))


class ScopeQueueDedupeTest(SessionFixture):
    """Fix: scope_queue.jsonl is append-only with "latest wins" per id
    (orchestration.md), but entries were counted per-line without
    deduping, so a scope that went queued -> complete left its stale
    "queued" line still counted as non-terminal work forever.
    """

    def test_stale_queued_line_does_not_count_after_complete(self):
        self.write_queue(
            {"id": "SCOPE-1", "status": "queued"},
            {"id": "SCOPE-1", "status": "complete"},
        )
        _, queue_entries, _ = cc.load_session_state()
        self.assertEqual(len(queue_entries), 1)
        self.assertEqual(queue_entries[0]["status"], "complete")

    def test_distinct_ids_both_kept(self):
        self.write_queue(
            {"id": "SCOPE-1", "status": "complete"},
            {"id": "SCOPE-2", "status": "queued"},
        )
        _, queue_entries, _ = cc.load_session_state()
        self.assertEqual(len(queue_entries), 2)

    def test_counts_reflect_latest_status_only(self):
        self.write_queue(
            {"id": "SCOPE-1", "status": "queued"},
            {"id": "SCOPE-1", "status": "in_flight"},
            {"id": "SCOPE-1", "status": "complete"},
        )
        _, queue_entries, _ = cc.load_session_state()
        counts, _ = cc.count_by_status(queue_entries)
        self.assertEqual(counts["terminal"], 1)
        self.assertEqual(counts["non_terminal"], 0)

    def test_entries_without_id_are_each_counted(self):
        # Entries missing `id` can't be deduped against each other; they
        # should still each be counted rather than silently collapsing.
        self.write_queue({"status": "queued"}, {"status": "queued"})
        _, queue_entries, _ = cc.load_session_state()
        self.assertEqual(len(queue_entries), 2)


class TimeBudgetFromStateJsonTest(SessionFixture):
    """Fix: the hook read a manifest.yaml that nothing in the skill ever
    writes (the documented file is state.json, with top-level
    `started_at` and nested `budgets.time_budget_seconds`), so the
    time-budget exit never fired.
    """

    def test_manifest_reads_state_json_fields(self):
        self.write_queue({"id": "SCOPE-1", "status": "queued"})
        self.write_state(started_at="2026-05-25T15:22:17Z", time_budget_seconds=28800)
        _, _, manifest = cc.load_session_state()
        self.assertEqual(manifest["start_time"], "2026-05-25T15:22:17Z")
        self.assertEqual(manifest["time_budget_seconds"], 28800)

    def test_budget_exhausted_when_elapsed_exceeds_budget(self):
        self.write_queue({"id": "SCOPE-1", "status": "queued"})
        started = (datetime.now(timezone.utc) - timedelta(hours=9)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        self.write_state(started_at=started, time_budget_seconds=28800)  # 8h
        _, _, manifest = cc.load_session_state()
        self.assertTrue(cc.time_budget_exhausted(manifest))

    def test_budget_not_exhausted_when_within_budget(self):
        self.write_queue({"id": "SCOPE-1", "status": "queued"})
        started = (datetime.now(timezone.utc) - timedelta(hours=1)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        self.write_state(started_at=started, time_budget_seconds=28800)  # 8h
        _, _, manifest = cc.load_session_state()
        self.assertFalse(cc.time_budget_exhausted(manifest))

    def test_no_state_json_means_no_budget_info(self):
        self.write_queue({"id": "SCOPE-1", "status": "queued"})
        _, _, manifest = cc.load_session_state()
        self.assertEqual(manifest, {})
        self.assertFalse(cc.time_budget_exhausted(manifest))


if __name__ == "__main__":
    unittest.main()
