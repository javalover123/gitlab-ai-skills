# The done predicate

`done(project) == true` is the conjunction of every clause below. The
done predicate is the deterministic gate at Phase 4 — a Python script
that enumerates each clause and reports pass/fail with cited evidence.
Genesis cannot declare done without all clauses passing.

This reference documents every clause, the per-language command(s)
that evaluate it, and the failure-handling pattern.

## The clause list

1. **All scopes complete.** Every `scope_queue.jsonl` entry has
   `status: complete` AND `adversarial_review.verdict == "APPROVED"`.
2. **All findings closed.** Every `bug_queue.jsonl` entry has
   `status: fixed` AND has a `fixed_in_commit` SHA that survives
   re-run.
3. **Tier-1 green at HEAD on the integration branch.** See § Tier-1
   commands below.
4. **Tier-2 green at HEAD.** See § Tier-2 commands below.
5. **Tier-3 full sweep green for every scope whose triggers fired.**
   See § Tier-3 commands below.
6. **Traceability matrix complete.** `/traceability-matrix-build`
   reports zero unlinked stories, specs, ADRs, threat-model entries.
7. **Spec ↔ code drift scanner clean.** Doctest runners (per-language
   `--doc-tests`) plus the iteratotron stop-bias scan return zero
   findings on HEAD.
8. **SLSA L3 provenance attested.** in-toto attestation generated and
   signed via cosign keyless; the `.intoto.jsonl` file exists in
   `.iteratotron/in-toto/`; cosign-verify returns 0.
9. **Post-implementation review written.** `.iteratotron/postmortems/<session_id>.md`
   exists and is non-empty.
10. **No unresolved `needs_human` entries.** All escalations have been
    cleared via `/human-review`.

## Tier-1 commands per language

Failures here re-enter Phase 3's iteratotron loop, not bug-burndown —
Tier-1 failures are usually a wrong-scope-boundary issue, not a
specific bug.

```bash
# Rust
cargo nextest run --workspace --no-fail-fast
cargo llvm-cov --lcov --output-path lcov.info --workspace
cargo crap --lcov lcov.info --fail-above --threshold 30
cargo mutants --in-diff <(git diff "$BASELINE_SHA"..HEAD)
cargo clippy --workspace -- -D warnings
cargo fmt --check
cargo machete
cargo deny check advisories bans licenses sources

# Go
go test -race ./...
go test -coverprofile=cover.out ./...
gremlins unleash --tags fast ./...
golangci-lint run
govulncheck ./...
deadcode ./...

# Python
pytest --cov --cov-fail-under=80 -n auto
mutmut run --paths-to-mutate=src/
ruff check && mypy --strict src/
pip-audit --strict
vulture --min-confidence 80 src/

# Ruby
bundle exec rspec
bundle exec mutant run --use rspec --usage opensource '<Subject>'
bundle exec rubocop && bundle exec brakeman
bundle audit check --update
debride lib/

# Nix
nix flake check
statix check . && deadnix .
nixfmt --check .
vulnix -G
```

## Tier-2 commands per language

Failures here become structured bug-burndown findings (which scenario
failed, which contract was violated). Don't re-enter iteratotron;
route to bug-burndown's queue.

```bash
# Rust (cucumber-rs)
cargo test --test cucumber -- --tags '@implemented'

# Go (godog)
godog ./features

# Python (behave or pytest-bdd)
behave features/         # or pytest --bdd

# Ruby (cucumber-ruby)
bundle exec cucumber

# Cross-language (schemathesis for OpenAPI/GraphQL)
schemathesis run --checks=all openapi.yaml

# Testcontainers integration (when present)
# Rust: cargo nextest run --features testcontainers
# Go: go test -tags testcontainers ./...
# Python: pytest -m testcontainers

# Nix (multi-VM tests)
nix build .#checks.<arch>.<integration-test>
```

## Tier-3 commands per language

The full sweep — only for scopes whose triggers fired. Per
`references/tier3-triggers.md`, sample density at scope-completion is
much lower (typically 50 seeds); full density is what runs here.

```bash
# Rust — shuttle (Tokio multi-task)
cargo test --features shuttle -- --test-threads=1     # CI configures SHUTTLE_RANDOM_SEED partitioning for 1000 seeds

# Rust — madsim (deterministic distributed simulation)
cargo test --features madsim -- --test-threads=1       # CI configures MADSIM_SEED partitioning for 1000 seeds

# Rust — loom (exhaustive C11 — no sampling, one run is authoritative)
RUSTFLAGS="--cfg loom" cargo test --release --test 'loom_*'

# Rust — bolero + Kani (proofs)
cargo bolero test <harness> --engine kani --release

# Rust + cross-language — Wycheproof vectors
cargo test --features wycheproof --release           # or per-language equivalent

# TLA+ — when consensus / commit protocol is in scope
tlc -workers $(nproc) -tool spec.tla

# Nix — multi-VM topology with tc-netem
nix build .#checks.<arch>.<topology-test-with-chaos>

# Toxiproxy — when network partition / latency triggered
make tier3-toxiproxy-suite      # project-specific harness
```

## SLSA L3 attestation

The attestation is the difference between "ship-ready" and
"FedRAMP-track-ready". Generation:

```bash
# Generate the in-toto layout
slsa-generator generate \
  --source-uri "$REPO_URI" \
  --source-digest "$(git rev-parse HEAD)" \
  --builder-id "github.com/<org>/<repo>/.github/workflows/build.yml@refs/heads/main" \
  --build-type "https://slsa.dev/build/v1.0" \
  --output .iteratotron/in-toto/layout.json

# Sign with cosign keyless (OIDC-bound)
cosign attest \
  --predicate .iteratotron/in-toto/layout.json \
  --type slsaprovenance \
  --yes \
  "$ARTIFACT_REF"

# Verify (the done predicate re-verifies)
cosign verify-attestation \
  --certificate-identity-regexp "^https://github\\.com/<org>/" \
  --certificate-oidc-issuer "https://token.actions.githubusercontent.com" \
  --type slsaprovenance \
  "$ARTIFACT_REF"
```

The done predicate script runs `cosign verify-attestation` and expects
exit 0. Any other exit blocks `done == true`.

cargo-auditable + cargo-cyclonedx (and per-language equivalents) provide
the SBOM inside the attestation. Microsoft, Alpine Linux, NixOS,
openSUSE, Void Linux, Chimera Linux, and Wolfi OS all use this pattern
for production Rust packaging, so the toolchain is well-trodden.

## The done-predicate script

`scripts/done-check.py` evaluates every clause:

```python
import json
import subprocess
import sys
from pathlib import Path

def check_clause_1_scopes_complete(state):
    incomplete = [s for s in state["scope_queue"] if s["status"] != "complete"]
    return (not incomplete, f"incomplete scopes: {[s['id'] for s in incomplete]}")

def check_clause_2_findings_closed(state):
    unfixed = [b for b in state["bug_queue"] if b["status"] != "fixed"]
    return (not unfixed, f"unfixed findings: {[b['id'] for b in unfixed]}")

def check_clause_3_tier1_green(harness_vector):
    for lang, tools in harness_vector.items():
        if lang == "global_attestation":
            continue
        for tool_name, cmd in tools.get("tier1", {}).items():
            rc = subprocess.run(cmd, shell=True, capture_output=True).returncode
            if rc != 0:
                return (False, f"tier1 failed: {lang}/{tool_name}")
    return (True, "tier1 green")

# ... clauses 4-10 follow the same pattern ...

def main():
    state = json.loads(Path(".iteratotron/state.json").read_text())
    clauses = [
        check_clause_1_scopes_complete(state),
        check_clause_2_findings_closed(state),
        check_clause_3_tier1_green(state["harness_vector"]),
        # ...
    ]
    failed = [(i + 1, msg) for i, (ok, msg) in enumerate(clauses) if not ok]
    if failed:
        print("done(project) == FALSE")
        for idx, msg in failed:
            print(f"  clause {idx}: {msg}")
        sys.exit(1)
    print("done(project) == TRUE")
    sys.exit(0)

if __name__ == "__main__":
    main()
```

Implementation in `scripts/done-check.py`. Genesis invokes it at
Phase 4; failure means re-enter Phase 3 with the failing clause as a
finding.

## Budget-capped done

When wall-clock or USD budget is exhausted before `done == true`,
iteratotron emits a partial-completion report:

```
GENESIS PARTIAL — budget exhausted

Clauses passed: <list>
Clauses failed: <list>

Remaining work (re-invoke `/iteratotron resume:<id>` after extending budget):
- scope <id>: <status>
- finding <id>: <status>

SLSA attestation generated: <yes/no>
Recommended next: <"raise budget", "split into two iteratotron runs in genesis mode", ...>
```

The session ends with `stop_reason: "time_budget_exhausted"` or
`"cost_budget_exhausted"`. The session is resumable.

## "Production-ready" is the done predicate, not a vibe

The done predicate is the **only** thing iteratotron uses to claim
project completion. The phrasing matters:

- ❌ "Project is production-ready."
- ✅ "done(project) == true: clauses 1-10 passed, attestation
  verified at $(git rev-parse HEAD)."

This is the discipline decision from `docs/genesis.md` § Part 10H —
the multi-tier harness is the source of truth, not the model's
confidence. Without the predicate, "ship-ready" is just another
prompt the model can hallucinate over.
