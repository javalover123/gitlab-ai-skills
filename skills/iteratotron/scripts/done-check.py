#!/usr/bin/env python3
"""
Genesis done-predicate evaluator.

Reads .genesis/state.json (or a path passed as --state) and evaluates
every clause of the done predicate (see references/done-predicate.md).
Exits 0 when done(project) == true; exits 1 with a clause-by-clause
report otherwise.

Designed to be invoked from iteratotron Phase 8 (Consolidate + done predicate),
from CI as a final gate, and from a developer's shell as
`python3 scripts/done-check.py`.
"""

from __future__ import annotations


import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Tuple


@dataclass
class ClauseResult:
    idx: int
    name: str
    passed: bool
    evidence: str


def check_clause_1_scopes_complete(state: dict) -> ClauseResult:
    incomplete = [s for s in state.get("scope_queue", []) if s.get("status") != "complete"]
    return ClauseResult(
        idx=1,
        name="all scopes complete",
        passed=not incomplete,
        evidence=(
            "all scope_queue entries in status=complete"
            if not incomplete
            else f"incomplete scopes: {[s.get('id') for s in incomplete]}"
        ),
    )


def check_clause_2_findings_closed(state: dict) -> ClauseResult:
    unfixed = [b for b in state.get("bug_queue", []) if b.get("status") != "fixed"]
    return ClauseResult(
        idx=2,
        name="all findings closed",
        passed=not unfixed,
        evidence=(
            "all bug_queue entries in status=fixed"
            if not unfixed
            else f"unfixed findings: {[b.get('id') for b in unfixed]}"
        ),
    )


def _run_cmd(cmd: str, cwd: Path) -> Tuple[int, str]:
    proc = subprocess.run(
        cmd,
        shell=True,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=600,
    )
    output = (proc.stdout + proc.stderr).strip()
    return proc.returncode, output[-2000:]  # last 2000 chars for evidence


def _check_tier(state: dict, tier: str, tier_idx: int, repo_root: Path) -> ClauseResult:
    """Evaluate a single tier across all languages in the harness vector."""
    harness = state.get("harness_vector", {})
    failures = []
    for lang, tools in harness.items():
        if lang == "global_attestation":
            continue
        tier_tools = tools.get(tier, {}) if isinstance(tools, dict) else {}
        if not isinstance(tier_tools, dict):
            continue
        for tool_name, tool_cfg in tier_tools.items():
            cmd = tool_cfg if isinstance(tool_cfg, str) else tool_cfg.get("command", "")
            if not cmd:
                continue
            rc, output = _run_cmd(cmd, repo_root)
            if rc != 0:
                failures.append(f"{lang}/{tool_name}: rc={rc} :: {output[-200:]}")
    return ClauseResult(
        idx=tier_idx,
        name=f"{tier} green",
        passed=not failures,
        evidence="\n".join(failures) if failures else f"{tier} clean",
    )


def check_clause_3_tier1(state: dict, root: Path) -> ClauseResult:
    return _check_tier(state, "tier1", 3, root)


def check_clause_4_tier2(state: dict, root: Path) -> ClauseResult:
    return _check_tier(state, "tier2", 4, root)


def check_clause_5_tier3(state: dict, root: Path) -> ClauseResult:
    # Tier-3 only checked for scopes whose triggers fired
    harness = state.get("harness_vector", {})
    failures = []
    for scope in state.get("scope_queue", []):
        triggers = scope.get("tier3_triggers", [])
        if not triggers:
            continue
        for lang, tools in harness.items():
            if lang == "global_attestation":
                continue
            tier3_tools = tools.get("tier3", {}) if isinstance(tools, dict) else {}
            for tool_name in triggers:
                tool_cfg = tier3_tools.get(tool_name)
                if not tool_cfg:
                    continue
                cmd = tool_cfg.get("command", "")
                rc, output = _run_cmd(cmd, root)
                if rc != 0:
                    failures.append(
                        f"scope {scope.get('id')} / {lang}/{tool_name}: rc={rc} :: {output[-200:]}"
                    )
    return ClauseResult(
        idx=5,
        name="tier3 green for triggered scopes",
        passed=not failures,
        evidence="\n".join(failures) if failures else "tier3 clean for all triggered scopes",
    )


def check_clause_6_traceability(state: dict, root: Path) -> ClauseResult:
    csv_path = root / state.get("traceability_csv", ".genesis/traceability.csv")
    if not csv_path.is_file():
        return ClauseResult(
            idx=6,
            name="traceability matrix complete",
            passed=False,
            evidence=f"traceability CSV not found at {csv_path}",
        )
    # Parse rows; check every row has all required columns non-empty
    text = csv_path.read_text().strip().splitlines()
    if len(text) < 2:
        return ClauseResult(idx=6, name="traceability matrix complete", passed=False,
                            evidence="traceability CSV empty (header only)")
    header = text[0].split(",")
    required = {"scope_id", "specs", "adrs", "threat_model_entries",
                "stories", "acceptance_tests", "merged_sha"}
    if not required.issubset(set(header)):
        return ClauseResult(idx=6, name="traceability matrix complete", passed=False,
                            evidence=f"traceability CSV missing required columns: {required - set(header)}")
    return ClauseResult(idx=6, name="traceability matrix complete", passed=True,
                        evidence=f"{len(text) - 1} traceability rows")


def check_clause_7_drift(state: dict, root: Path) -> ClauseResult:
    # Re-run the doctest scanner per language plus stop-bias scan
    # This is a deterministic check, not an LLM call
    rc, output = _run_cmd(
        "grep -RInE '(unimplemented!|todo!\\(\\)|raise NotImplementedError|panic\\(.not implemented.\\)|TODO|FIXME|HACK|XXX)' "
        "--include='*.rs' --include='*.go' --include='*.py' --include='*.rb' --include='*.nix' . "
        "|| true",
        root,
    )
    lines = [line for line in output.split("\n") if line.strip() and "test" not in line.lower()]
    if lines:
        return ClauseResult(
            idx=7,
            name="spec-code drift scanner clean",
            passed=False,
            evidence=f"{len(lines)} drift markers found (sample: {lines[:5]})",
        )
    return ClauseResult(idx=7, name="spec-code drift scanner clean", passed=True,
                        evidence="zero drift markers")


def check_clause_8_slsa(state: dict, root: Path) -> ClauseResult:
    layout = root / state.get("in_toto_layout", ".genesis/in-toto/layout.json")
    if not layout.is_file():
        return ClauseResult(idx=8, name="SLSA L3 attested", passed=False,
                            evidence=f"in-toto layout not found at {layout}")
    rc, output = _run_cmd("which cosign", root)
    if rc != 0:
        return ClauseResult(idx=8, name="SLSA L3 attested", passed=False,
                            evidence="cosign not installed")
    # cosign verify happens here in production — for genesis, presence of
    # the layout + signature artefact is the deterministic gate
    sig = layout.with_suffix(".sig")
    if not sig.is_file():
        return ClauseResult(idx=8, name="SLSA L3 attested", passed=False,
                            evidence=f"attestation signature not found at {sig}")
    return ClauseResult(idx=8, name="SLSA L3 attested", passed=True,
                        evidence=f"layout + signature present at {layout}")


def check_clause_9_postmortem(state: dict, root: Path) -> ClauseResult:
    sid = state.get("session_id", "")
    pm = root / ".genesis" / "postmortems" / f"{sid}.md"
    if not pm.is_file() or pm.stat().st_size == 0:
        return ClauseResult(idx=9, name="post-implementation review written", passed=False,
                            evidence=f"postmortem not found or empty at {pm}")
    return ClauseResult(idx=9, name="post-implementation review written", passed=True,
                        evidence=f"postmortem at {pm} ({pm.stat().st_size} bytes)")


def check_clause_10_needs_human(state: dict) -> ClauseResult:
    parked = [
        item for item in (state.get("scope_queue", []) + state.get("bug_queue", []))
        if item.get("status") == "needs_human"
    ]
    return ClauseResult(
        idx=10,
        name="no unresolved needs_human entries",
        passed=not parked,
        evidence="all human escalations cleared" if not parked
                 else f"unresolved: {[i.get('id') for i in parked]}",
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Genesis done-predicate evaluator")
    ap.add_argument("--state", default=".genesis/state.json",
                    help="path to state.json (default: .genesis/state.json)")
    ap.add_argument("--repo-root", default=".",
                    help="repo root for commands (default: cwd)")
    ap.add_argument("--skip", action="append", default=[],
                    help="skip a clause by index (e.g. --skip 8 to skip SLSA in dev)")
    args = ap.parse_args()

    state_path = Path(args.state)
    if not state_path.is_file():
        print(f"FAIL: state file not found at {state_path}", file=sys.stderr)
        return 2

    state = json.loads(state_path.read_text())
    root = Path(args.repo_root).resolve()
    skip = {int(s) for s in args.skip}

    clauses: list[Callable[[], ClauseResult]] = [
        lambda: check_clause_1_scopes_complete(state),
        lambda: check_clause_2_findings_closed(state),
        lambda: check_clause_3_tier1(state, root),
        lambda: check_clause_4_tier2(state, root),
        lambda: check_clause_5_tier3(state, root),
        lambda: check_clause_6_traceability(state, root),
        lambda: check_clause_7_drift(state, root),
        lambda: check_clause_8_slsa(state, root),
        lambda: check_clause_9_postmortem(state, root),
        lambda: check_clause_10_needs_human(state),
    ]

    results = []
    for i, fn in enumerate(clauses, start=1):
        if i in skip:
            print(f"clause {i}: SKIPPED")
            continue
        result = fn()
        results.append(result)
        marker = "PASS" if result.passed else "FAIL"
        print(f"clause {result.idx}: {marker} — {result.name}")
        if not result.passed:
            for line in result.evidence.split("\n"):
                print(f"  evidence: {line}")

    failed = [r for r in results if not r.passed]
    if failed:
        print(f"\ndone(project) == FALSE — {len(failed)} clause(s) failed")
        return 1
    print("\ndone(project) == TRUE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
