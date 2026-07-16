# Python harness builder

Genesis-side orchestration package for Python projects.

## Package layout

```
<project>_genesis/
├── pyproject.toml
├── README.md
└── src/<project>_genesis/
    ├── __init__.py
    ├── __main__.py                  # python -m <project>_genesis
    ├── cli.py                       # outer loop + CLI
    ├── state.py                     # .iteratotron/state.json IO + atomic-rename
    ├── bootstrap.py                 # Phase 0
    ├── gap_analysis.py              # Phase 1
    ├── plan.py                      # Phase 2
    ├── inner_loop.py                # Phase 3 dispatcher state machine
    ├── constitution_check.py        # gates each iteratotron dispatch
    ├── streaming.py                 # claude -p stream-json consumer (asyncio)
    ├── adversarial_review.py        # Phase 7 cold-context reviewer
    ├── harness_runner.py            # Tier-1/2/3 invocation
    │                                #  ↳ flake.nix present ⇒ gates via
    │                                #    `nix develop --command` (pinned
    │                                #    interpreter + ruff/mypy/pytest). See
    │                                #    implementation-nix.md
    │                                #    § "Gate-execution contract".
    ├── done_predicate.py            # Phase 4 evaluator
    └── slsa.py                      # in-toto + cosign attestation
```

## pyproject.toml essentials

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "<project>-genesis"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "anyio>=4.0",
    "click>=8.1",
    "structlog>=24.4",
    "pydantic>=2.9",
    "claude-agent-sdk>=0.2.0",       # canonical Python SDK; supports include_partial_messages
]

[project.scripts]
<project>-genesis = "<project>_genesis.cli:main"

[tool.ruff]
target-version = "py311"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "S", "ASYNC", "T20"]

[tool.mypy]
strict = true
```

## cli.py — outer loop

```python
import asyncio
import sys
from pathlib import Path

import click
import structlog

from . import bootstrap, gap_analysis, plan, inner_loop, done_predicate, state

log = structlog.get_logger()

@click.command()
@click.option("--parallel", default=2, help="outer iteratotron parallelism")
@click.option("--inner", default=3, help="inner iterate parallelism")
@click.option("--time", "time_secs", default=604_800, help="wall-clock budget seconds (default 7 days; a converging build/E2E run takes days — size to the workload, see SKILL.md 'Size the deadlines to the workload', drop to 28_800/8h only for fast-feedback projects)")
@click.option("--budget-usd", default=100.0, help="cost budget USD")
@click.option("--resume", default=None, help="resume session by ID")
@click.option("--dry-run", is_flag=True, help="emit plan and exit")
def main(parallel: int, inner: int, time_secs: int, budget_usd: float,
         resume: str | None, dry_run: bool) -> None:
    asyncio.run(_run(parallel, inner, time_secs, budget_usd, resume, dry_run))

async def _run(parallel, inner, time_secs, budget_usd, resume, dry_run):
    if resume:
        s = state.resume(resume)
    else:
        s = state.new_session(parallel, inner, time_secs, budget_usd)
        await bootstrap.run(s)
        await gap_analysis.run(s)
        await plan.run(s)

    if dry_run:
        log.info("dry_run", msg="plan written, no dispatch")
        return

    await inner_loop.run(s)
    await done_predicate.evaluate_and_attest(s)
```

## streaming.py — claude_agent_sdk consumer

Python is the rare case where the canonical pattern is the SDK, not raw
subprocess parsing — `claude_agent_sdk` already wraps the stream-json
schema and exposes typed messages. Nono wrapping goes through a custom
`Transport` subclass (the SDK's supported extension point). See
`references/nono-integration.md` for the full sandbox contract.

**SDK version note**: the `NonoTransport` below subclasses an internal
module (`_internal.transport.subprocess_cli`). Pin `claude-agent-sdk`
to the version you tested against and re-test after bumps.

```python
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, ResultMessage
# NonoTransport subclasses the internal subprocess transport.
# Pin claude-agent-sdk version; this is an _internal module.
from claude_agent_sdk._internal.transport.subprocess_cli import SubprocessCLITransport


@dataclass
class SandboxVerdict:
    """Result of the preflight check. Thread through to every dispatch call."""
    nono_version: str = ""
    network_profile: str | None = None       # "claude-code" or None
    permission_mode: str = "acceptEdits"     # "bypassPermissions" when sandboxed

    @property
    def sandboxed(self) -> bool:
        return self.permission_mode == "bypassPermissions"


async def check_sandbox(allow_unsandboxed: bool = False) -> SandboxVerdict:
    """Run once at harness startup. Returns the SandboxVerdict to thread
    through every dispatch call."""
    verdict = SandboxVerdict()

    # Step 1 — probe nono
    result = await asyncio.to_thread(
        subprocess.run, ["nono", "--version"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        if allow_unsandboxed:
            import logging
            logging.warning(
                "\n┌─────────────────────────────────────────────────────┐\n"
                "│  RUNNING UNSANDBOXED — nono not found on PATH       │\n"
                "│  permission_mode = acceptEdits (NOT bypassPerms)    │\n"
                "│  Install: brew install nono                         │\n"
                "│           nix shell nixpkgs#nono                    │\n"
                "│           .deb from github.com releases             │\n"
                "└─────────────────────────────────────────────────────┘"
            )
            return verdict  # acceptEdits, no sandbox
        raise RuntimeError(
            "nono is required but not found on PATH.\n"
            "Install: brew install nono  |  nix shell nixpkgs#nono\n"
            "         or .deb from github.com releases\n"
            "Pass --allow-unsandboxed to proceed without the sandbox\n"
            "(keeps permission_mode=acceptEdits; not recommended for\n"
            "unattended loops)."
        )

    verdict.nono_version = result.stdout.strip()

    # Step 2 — check Landlock ABI for network-profile support
    setup = await asyncio.to_thread(
        subprocess.run, ["nono", "setup", "--check-only"],
        capture_output=True, text=True,
    )
    # Landlock ABI v4+ required for --network-profile (Linux 6.7+)
    if "landlock_abi: 4" in setup.stdout or "landlock_abi: 5" in setup.stdout:
        verdict.network_profile = "claude-code"
    else:
        import logging
        logging.warning("[sandbox] Landlock ABI < 4 — dropping --network-profile claude-code")

    verdict.permission_mode = "bypassPermissions"
    return verdict


class NonoTransport(SubprocessCLITransport):
    """Wraps claude in `nono run --silent` via the SDK's transport hook.

    See references/nono-integration.md for the --add-dir ↔ --allow invariant.
    Both lists come from the same `allow_dirs` parameter so they can't drift.
    """

    def __init__(
        self,
        *,
        allow_dirs: list[str],
        read_dirs: list[str],
        network_profile: str | None,
        **kw,
    ) -> None:
        super().__init__(**kw)
        self._allow_dirs = allow_dirs
        self._read_dirs = read_dirs
        self._network_profile = network_profile

    def _build_command(self) -> list[str]:
        base = super()._build_command()  # the claude argv built by the SDK
        prefix = ["nono", "run", "--silent"]
        if self._network_profile:
            prefix += ["--network-profile", self._network_profile]
        for d in self._allow_dirs:
            prefix += ["--allow", d]
        for d in self._read_dirs:
            prefix += ["--read", d]
        prefix.append("--")
        return prefix + base


@dataclass
class SubagentResult:
    log_path: Path
    total_cost_usd: float
    subtype: str
    duration_ms: int


async def dispatch(
    prompt: str,
    log_dir: Path,
    model: str,
    add_dirs: list[str],
    disallowed_tools: list[str],
    verdict: SandboxVerdict,
    max_turns: int = 80,
    max_budget_usd: float = 20.0,
) -> SubagentResult:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{int(time.time())}.jsonl"
    options = ClaudeAgentOptions(
        model=model,
        permission_mode=verdict.permission_mode,
        max_turns=max_turns,
        max_budget_usd=max_budget_usd,
        add_dirs=add_dirs,
        disallowed_tools=disallowed_tools,
        include_partial_messages=True,
    )

    # Derive --allow from the same source as add_dirs (+ shared dotfile dirs).
    # The --add-dir ↔ --allow invariant: nono-integration.md.
    transport = None
    if verdict.sandboxed:
        allow_dirs = list(add_dirs) + [
            ".bug-burndown", ".test-effectiveness", ".iteratotron",
        ]
        read_dirs = [
            os.path.expanduser("~/.pyenv/shims"),
            os.path.expanduser("~/.local/bin"),
        ]
        transport = NonoTransport(
            allow_dirs=allow_dirs,
            read_dirs=read_dirs,
            network_profile=verdict.network_profile,
        )

    cost = 0.0
    subtype = "unknown"
    duration_ms = 0

    # The SDK's __aexit__ handles the watchdog — no SIGTERM/SIGKILL loop needed.
    # nono passes stdout straight through; the SDK sees the same NDJSON as before.
    async with ClaudeSDKClient(options, transport=transport) as client:
        with log_path.open("w") as log:
            async for msg in client.query(prompt):
                # tee raw message to disk BEFORE filtering
                log.write(json.dumps(msg.dict() if hasattr(msg, "dict") else msg) + "\n")
                log.flush()
                if isinstance(msg, ResultMessage):
                    cost = msg.total_cost_usd
                    subtype = msg.subtype
                    duration_ms = msg.duration_ms

    return SubagentResult(log_path=log_path, total_cost_usd=cost,
                          subtype=subtype, duration_ms=duration_ms)
```

The SDK handles the watchdog via `__aexit__` of the `ClaudeSDKClient`
context manager. (When subprocess-shelling out instead of using the SDK,
follow the Rust / Go watchdog pattern.)

Set `os.environ.setdefault("CLAUDE_BWRAP_TTY", "0")` once in `main()`
before constructing any `ClaudeSDKClient` — this forces `--pipe` mode in
any `claude-bwrap` wrapper on PATH even if it regressed to `--pty`. nono
preserves the parent env, so this env var survives the sandbox wrap.

## inner_loop.py (pseudocode)

```python
import anyio
import asyncio

from . import state, streaming, adversarial_review, constitution_check, harness_runner

async def run(s: state.SessionState) -> None:
    while not s.is_terminal() and not s.budget_exhausted():
        dispatchable = s.select_dispatchable(s.budgets.parallel_outer)

        async with anyio.create_task_group() as tg:
            for scope in dispatchable:
                check = await constitution_check.run(scope)
                if not check.pass_:
                    s.park_for_human(scope, check.violations)
                    continue

                worktree = await s.create_worktree(scope)
                prompt = _render_iteratotron_prompt(scope, s)
                tg.start_soon(
                    _dispatch_and_review, s, scope, worktree, prompt)

        if s.bug_queue:
            await _dispatch_burndown(s)
        s.fsync()

async def _dispatch_and_review(s, scope, worktree, prompt):
    result = await streaming.dispatch(
        prompt, worktree.log_dir, "haiku",
        s.add_dirs(), ["WebSearch"], max_turns=80, max_budget_usd=20.0,
    )
    s.record_cost(scope.id, "iteratotron", result)
    verdict = await adversarial_review.run(scope, worktree)
    match verdict.kind:
        case "approved":
            await s.merge_worktree(scope, worktree)
        case "insufficient":
            s.requeue_scope(scope, verdict.lessons)
        case "needs_human":
            s.park_for_human(scope, verdict.reason)
    await harness_runner.run_applicable_tiers(scope, s.harness_vector)
```

## Composes with the runtime harness Python variant (when applicable)

When harness-builder has scaffolded a Python runtime harness for
the same project, both packages live in the same `pyproject.toml`
optional-dependency group. Genesis's `<project>-genesis` and harness's
`<project>-harness` share the `.bug-burndown/` and
`.test-effectiveness/` directories.
