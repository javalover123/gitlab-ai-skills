# Per-language harness vector composition

The harness vector is the iteratotron-computed mapping of language → tool
list per tier, plus the risk-triggered Tier-3 additions per scope. It's
written to `.iteratotron/state.json#harness_vector` during Phase 0 and
consumed by iteratotron + iterate transitively.

The base matrix lives in `iterate/references/ecosystem-tooling.md` —
this file is iteratotron-specific composition logic that adapts the base
matrix to the project's detected languages and risk profile.

## Composition algorithm

1. **Detect languages.** Scan the repo for manifest files:
   - `Cargo.toml` → Rust
   - `go.mod` → Go
   - `pyproject.toml`, `setup.py`, `requirements.txt` → Python
   - `Gemfile` → Ruby
   - `flake.nix`, `default.nix`, `shell.nix` → Nix
   - `package.json` → JavaScript / TypeScript
   - `Makefile`, `CMakeLists.txt`, `configure.ac` → C / C++
2. **Per language, pull the base tier matrix** from the ecosystem
   tooling reference. That's the always-on Tier-1 set.
3. **Tier-2 add-ons** by detection:
   - `.feature` files present → cucumber (cucumber-rs / godog /
     pytest-bdd / cucumber-ruby)
   - `openapi.yaml` / `openapi.json` present → schemathesis (any
     language) or language-native equivalent
   - `proto/` directory → gRPC contract tests
   - `Dockerfile` / `docker-compose.yml` → testcontainers
4. **Tier-3 triggers** by spec-content scan (see
   `references/tier3-triggers.md`):
   - Trigger phrase present in any spec / ADR / threat model →
     add the corresponding Tier-3 tool with `sample_seeds: 50` as the
     scope-completion budget.
5. **Cross-cutting** (always-on regardless of tier):
   - SBOM emitter per language
   - Supply-chain scanner per language
   - cosign attestation (one config, all artefacts)

## The composed vector schema

```json
{
  "languages": ["rust", "nix"],
  "rust": {
    "tier1": {
      "tests": "cargo nextest run",
      "coverage": "cargo llvm-cov --lcov",
      "mutation": "cargo mutants --in-diff",
      "crap": "cargo crap --lcov lcov.info --fail-above --threshold 30",
      "lint": "cargo clippy -- -D warnings",
      "fmt": "cargo fmt --check",
      "dead_code": "cargo machete",
      "supply_chain": "cargo deny check",
      "sbom": "cargo cyclonedx"
    },
    "tier2": {
      "cucumber": "cargo test --test cucumber",
      "contracts": "schemathesis run --checks=all openapi.yaml",
      "containers": "cargo nextest run --features testcontainers"
    },
    "tier3": {
      "bolero_kani": {
        "trigger": "spec mentions parsing / codec / safety invariant",
        "command": "cargo bolero test <harness> --engine kani",
        "sample_seeds": 50,
        "full_seeds": 10000
      },
      "loom": {
        "trigger": "hand-rolled sync primitive in scope",
        "command": "RUSTFLAGS=\"--cfg loom\" cargo test --release",
        "sample_seeds": 1,
        "full_seeds": 1
      },
      "shuttle": {
        "trigger": "tokio::spawn or async fn in multi-agent path",
        "command": "cargo test --features shuttle",
        "sample_seeds": 50,
        "full_seeds": 1000
      },
      "madsim": {
        "trigger": "distributed / ZMQ / message bus / saga",
        "command": "cargo test --features madsim -- --test-threads=1",
        "sample_seeds": 50,
        "full_seeds": 1000
      },
      "wycheproof": {
        "trigger": "FIPS / AEAD / signature / key exchange",
        "command": "cargo test --features wycheproof",
        "vectors": "tests/wycheproof/"
      }
    }
  },
  "nix": {
    "tier1": {
      "flake_check": "nix flake check",
      "fast_build": "nix-fast-build --skip-cached",
      "lint": "statix check .",
      "dead_code": "deadnix .",
      "format": "nixfmt --check .",
      "supply_chain": "vulnix -G"
    },
    "tier2": {
      "nixos_test": "nix build .#checks.<arch>.<test>"
    },
    "tier3": {
      "multi_vm": {
        "trigger": "multi-host / VLAN / deploy verification",
        "command": "nix build .#checks.<arch>.<topology-test>"
      }
    }
  },
  "global_attestation": {
    "sbom_format": "CycloneDX 1.6",
    "cosign_keyless": true,
    "in_toto_layout": ".iteratotron/in-toto/layout.json"
  }
}
```

## Budget partitioning

The harness vector also includes per-scope cost / time budgets so the
orchestrator knows when to stop a Tier-3 sweep:

| Tier | Wall-clock budget per scope | USD budget per scope |
|---|---|---|
| Tier-1 | 5 min | $0.20 |
| Tier-2 | 15 min | $0.50 |
| Tier-3 sample (50 seeds) | 30 min | $1.50 |
| Tier-3 full (≥1000 seeds, at Phase 4) | up to 4h | $20 |

When a Tier-3 sample blows past its budget without finding a defect,
iteratotron records the time growth (Family 12 — verification-time
regression, see iteratotron's stop-bias-pattern catalogue) and the
operator gets a one-line warning. The sample doesn't get re-run; the
finding is what matters.

## Why composition, not "run everything"

The temptation is to always run every Tier-3 tool — "to be thorough".
That's the wrong economics:

- A full madsim sweep of a 17-agent ZMQ topology can run for hours.
- Wycheproof vectors against non-crypto code are pure waste.
- nixosTest multi-VM topology on a project that has no deploy concern
  consumes minutes per check for no signal.

Genesis composes the vector to match the project's actual risk surface
— what the spec says could break, plus what the codebase actually
contains. Tier-3 fires *only* when the trigger and the code are both
present. This is the canonical risk-triggered-not-always-on pattern
from `docs/genesis.md` § Part 6 (per-language harness stack).

## Updating the vector mid-session

The vector is **immutable per session** once written. Mid-session
discovery of a new risk (e.g. an in-flight scope adds a `tokio::spawn`
call that triggers shuttle) goes into the `bug_queue` as a
`harness-vector-extension` finding; iteratotron updates the vector and
re-dispatches at the next round.

This prevents the worker from "expanding the scope" by deliberately
adding triggers it doesn't need; harness-vector expansion is an
orchestrator-level decision, not a worker decision.
