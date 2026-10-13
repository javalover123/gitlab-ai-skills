# Per-ecosystem completion gate tooling

This reference is loaded on demand from `iterate` Step 6 (stopping criteria)
and Step 5 (validation). It tells you which tools to reach for per language
when you're checking that "implemented" really means implemented — not just
"compiles and one test passed".

The premise comes from the SWE-ABS adversarial benchmark study (arXiv
2603.00520, March 2026): re-evaluating top SWE-Bench-Verified agents under
strengthened test suites rejected 19.78% of patches that the original suites
accepted. The top agent dropped from 78.80% → 62.20%. Coverage alone is not
a gate. Mutation survival on changed lines, CRAP score on complete modules,
fuzzing or property tests where the spec demands them, and supply-chain
attestation are what separate a confident success report from one that
survives contact with a real harness.

## Companion skill — harness-builder (runtime mode)

When the project's been through a runtime-harness session (built via `harness-builder`),
`.test-effectiveness/baseline.json` and `iter-NNN/delta.json` already
contain workspace-wide mutation/CRAP/coverage findings with Pass 3
Haiku verdicts attached. **Read those first** — they're cheaper and
more accurate than re-running the scans per-scope. The schema is in
`harness-builder/references/runtime-test-effectiveness-baseline.md`.

## The matrix

Pick the row that matches the language of the scope you're closing.
Genesis mode (within `iteratotron`) reads this matrix to compose its
per-language harness vector; iterate consults it directly when no
genesis run is in flight.

### Rust

| Concern | Tool | Invocation | Gate |
|---|---|---|---|
| Tests | cargo-nextest | `cargo nextest run -p <pkg>` | All pass, no `#[ignore]` on Implemented-marked code |
| Coverage | cargo-llvm-cov | `cargo llvm-cov --lcov --output-path lcov.info` | ≥ 80% lines, ≥ 70% branches on changed files |
| Mutation | cargo-mutants | `cargo mutants --in-diff <(git diff origin/main)` | Zero surviving mutants on changed lines |
| Complexity × coverage | cargo-crap | `cargo crap --lcov lcov.info --fail-above --threshold 30` | CRAP ≤ 30 on every module marked complete |
| Property tests | proptest + bolero | `cargo bolero test <harness>` | Spec mentions parsing/codec → required |
| Symbolic verification | Kani (via bolero) | `cargo bolero test <harness> --engine kani` | Spec mentions safety invariant → required |
| Concurrency (sync prims) | loom | `RUSTFLAGS="--cfg loom" cargo test --release` | Hand-rolled sync primitives → required |
| Concurrency (Tokio) | shuttle | `cargo test --features shuttle -- --test-threads=1` | Multi-task async code → required |
| Snapshot | insta | `cargo insta test --review` | No unreviewed snapshots |
| Supply chain | cargo-deny | `cargo deny check advisories bans licenses sources` | Zero unmitigated High+ advisories |
| SBOM + provenance | cargo-cyclonedx + cargo-auditable + cosign | `cargo cyclonedx && cosign attest` | SBOM exists, attestation valid |
| Dead code | cargo-machete (+ cargo-shear) | `cargo machete` | Zero unused deps |
| Static analysis | clippy (pedantic + deny clippy::unwrap_used) | `cargo clippy -p <pkg> -- -D warnings` | Zero violations |

The bolero+Kani integration matters more than it looks — it lets the same
`check!` harness run as `cargo test`, as a libFuzzer fuzzer, or as a Kani
proof. One harness, three engines, scaled to the property's complexity.

### Go

| Concern | Tool | Invocation | Gate |
|---|---|---|---|
| Tests | native + gotestsum | `go test -race ./...` | All pass |
| Coverage | built-in | `go test -coverprofile=cover.out` | ≥ 80% lines |
| Mutation | Gremlins | `gremlins unleash --tags fast ./...` | Zero surviving on changed lines (v0.6.0+ recommended) |
| Complexity × coverage | cyclop + gocover-cobertura | `golangci-lint run --enable=cyclop` | cyclop max-complexity ≤ 12 |
| Property tests | rapid | `go test ./... -run TestRapid` | Hypothesis-style, state machines built in |
| Fuzzing | native `testing.F` | `go test -fuzz=Fuzz -fuzztime=60s ./...` | User-input parsing required |
| Supply chain | govulncheck | `govulncheck ./...` | Zero reachable High+ advisories |
| SBOM | cyclonedx-gomod | `cyclonedx-gomod mod -licenses -json -output sbom.json` | SBOM exists |
| Dead code | `golang.org/x/tools/cmd/deadcode` + staticcheck U-codes | `deadcode ./...` | Zero on exported symbols |
| Static analysis | golangci-lint v2 | `golangci-lint run` | Zero violations |
| BDD | godog | `godog ./features` | One scenario per acceptance criterion |

golangci-lint v2 (March 2025) bundles staticcheck, gosec, govet, errcheck,
revive, gocyclo, modernize, copyloopvar, and ~100 others. Pin
`linters.default: standard` plus security additions; avoid `all` outside
exploratory passes.

### Python

| Concern | Tool | Invocation | Gate |
|---|---|---|---|
| Tests | pytest + pytest-xdist | `pytest -n auto` | All pass |
| Coverage | coverage.py + pytest-cov | `pytest --cov --cov-fail-under=80` | ≥ 80% lines, ≥ 70% branches (`--branch`) |
| Mutation | Mutmut (or Cosmic Ray for custom ops) | `mutmut run --paths-to-mutate=src/` | Zero survivors on diff scope |
| Complexity × coverage | radon + wily | `radon cc -nC --total-average src/` + `wily build` | Wily delta non-regressing |
| Property tests | Hypothesis | `pytest` (auto-detects strategies) | RuleBasedStateMachine for stateful APIs |
| API contract | Schemathesis | `schemathesis run --checks=all openapi.yaml` | OpenAPI link metadata → state machine |
| Fuzzing | atheris | `atheris fuzz_target.py` | User-input parsing required (Python 3.11–3.13) |
| Supply chain | pip-audit | `pip-audit --strict` | Zero High+ advisories |
| SBOM | cyclonedx-py | `cyclonedx-py environment -o sbom.json` | SBOM exists |
| Dead code | vulture (+ ruff F401/F841) | `vulture --min-confidence 80 src/` | Zero on exported symbols |
| Static analysis | ruff + mypy/pyright | `ruff check && mypy --strict` | Zero violations |
| Snapshot | syrupy | `pytest --snapshot-update` (review only) | No unreviewed snapshots |
| BDD | behave or pytest-bdd | `behave features/` | One scenario per acceptance criterion |
| Docstring coverage | interrogate | `interrogate -f 90 src/` | ≥ 90% |

For multi-agent Python work, Hypothesis's `RuleBasedStateMachine`
shows documented performance degradation with many dynamic rules (open issue
#4465, July 2025). Prefer one state machine per agent class, not one mega-machine.

### Ruby

| Concern | Tool | Invocation | Gate |
|---|---|---|---|
| Tests | RSpec + rspec-parallel | `bundle exec rspec` | All pass |
| Coverage | simplecov | (configured in spec_helper) | ≥ 80% lines |
| Mutation | Mutant (Markus Schirp) | `bundle exec mutant run --use rspec` | Zero survivors per subject |
| Complexity × coverage | rubycritic (+ skunk for CRAP-style) | `rubycritic --mode-ci` | A-B rating, skunk score under threshold |
| Property tests | rantly + rspec-prop | `bundle exec rspec` | Weaker ecosystem; use project-specific metamorphic relations where it matters |
| Supply chain | bundler-audit | `bundle audit check --update` | Zero advisories |
| SBOM | cyclonedx-ruby-gem | `cyclonedx-ruby -p . -f json -s 1.7` | SBOM exists |
| Dead code | debride (`--rails`-aware) | `debride lib/` | Zero on exported symbols |
| Static analysis | rubocop + brakeman (Rails SAST) | `bundle exec rubocop && bundle exec brakeman` | Zero violations |
| Type checking | Sorbet OR RBS+Steep | `bundle exec srb tc` | All strict files type-check |
| BDD | cucumber-ruby | `bundle exec cucumber` | The original Cucumber; one scenario per criterion |

Mutant requires a commercial license for non-OSS use. Confirm license
compatibility before integrating into bug-burndown for a closed-source
Ruby subproject. `mutant-rspec` / `mutant-minitest` are separate gems —
mutant alone won't run.

### Nix

| Concern | Tool | Invocation | Gate |
|---|---|---|---|
| Build correctness | `nix flake check` | `nix flake check --no-build` (eval-only) or `--all-systems` | Zero failures |
| Parallel evaluation | nix-fast-build | `nix-fast-build --skip-cached` | Replaces nix-build-uncached |
| Build observability | nix-output-monitor | `nix build --log-format internal-json -v \|& nom --json` | Visible progress |
| Linting | statix | `statix check .` | Zero violations |
| Dead code | deadnix | `deadnix . --no-lambda-arg --no-lambda-pattern-names` | Zero on top-level bindings |
| Formatting | nixfmt-rfc-style (RFC 166) | `nixfmt --check .` | All files conforming |
| Supply chain | vulnix | `vulnix -G -j` | Zero CVE-affected derivations (or CVE-in-patch justified) |
| Integration tests | nixosTest + microvm.nix | `nix build .#checks.<arch>.<test>` | All multi-VM topologies green |
| Deployment verify | nixos-anywhere `--vm-test` | `nixos-anywhere --vm-test --flake .#host root@dummy` | VM converges without touching target |
| OCI image | nix2container | `nix build .#oci-image` | Image builds; cosign attestation present |
| Rust-via-Nix | crane | `nix build .#default` | Cargo incremental cache hits |
| Store hygiene | `nix store verify --all` | run weekly | No corruption |

Mutation testing is not applicable to Nix expressions — they're declarative
and non-Turing-complete for derivation evaluation. The equivalent gap
analysis is captured via `nix flake check` + Hercules CI / Hydra rebuild
counts on input changes.

## Differential and Wycheproof for crypto / parsers

Cross-language tooling for code that touches cryptography, parsing, or
protocol handling — the surface where "looks right" most often hides
real bugs:

- **Wycheproof** (C2SP/wycheproof, transferred from google/wycheproof):
  known-attack JSON test vectors for AEAD, DSA, ECDSA, EdDSA, ECDH,
  RSA-PKCS#1v1.5 / PSS, HKDF, X25519/X448. Integrated by `pyca/cryptography`,
  Go's `crypto/internal/wycheproof`, and Rust's `wycheproof` crate. Pin
  C2SP/wycheproof as a submodule under `tests/wycheproof/` and auto-run
  vectors at every commit for any crypto code path.
- **csmith / YARPGen** for compiler / lowering correctness work — UB-free
  random-program generation; YARPGen (PLDI 2023 for loops) found 260+ bugs
  in gcc / clang / ispc / dpc++.
- **SQLsmith** for SQL-emitting code — found 100+ bugs in PostgreSQL /
  SQLite / MonetDB since 2015.
- **Metamorphic testing** for round-tripping invariants (`decrypt(encrypt(P, K), K)
  == P`, `sort(X) == sort(sort(X))`). The Python `metamorphic-test` package
  exists but project-specific relations per system tend to work better.

## OSS-Fuzz / ClusterFuzzLite

For self-hosted continuous fuzzing inside GitLab CI, ClusterFuzzLite covers
C / C++ / Rust / Go / Python / Java / JS / Lua. EO 14028 and FedRAMP Rev. 5
both list "automated security testing" as a control; OSS-Fuzz output
satisfies NIST SSDF PS.3 / PW.7 / PW.8 evidence requirements. Wire any
user-input-parsing crate (transport parser, command interpreter, query
layer) into ClusterFuzzLite before declaring it complete.

## What this matrix gates

The completion-ready gate set per ecosystem (referenced from `iterate`'s
Step 6 stopping criteria):

| Gate | Rust | Go | Python | Ruby | Nix |
|---|---|---|---|---|---|
| Tests pass | nextest | go test -race | pytest | rspec | flake check |
| Coverage ≥ branch threshold | cargo llvm-cov | go test -cover | coverage.py | simplecov | (host lang) |
| CRAP ≤ 30 on changed lines | cargo crap | cyclop + cobertura | radon + wily | rubycritic + skunk | n/a |
| Mutation survival = 0 on changed lines | cargo mutants | gremlins | mutmut | mutant | n/a |
| Property / fuzz for risk classes | bolero + Kani | rapid + testing.F | hypothesis + atheris | rantly | n/a |
| Doc / docstring coverage | `#[deny(missing_docs)]` | dlc | interrogate ≥ 90% | yard | option doc completeness |
| No advisory ≥ High | cargo deny | govulncheck | pip-audit | bundle audit | vulnix |
| SBOM + cosign attestation | cargo cyclonedx + cosign | cyclonedx-gomod + cosign | cyclonedx-py + cosign | cyclonedx-ruby + cosign | nix2container + cosign |
| Snapshot review clean | insta | cupaloy | syrupy | rspec-snapshot | (host lang) |

When a scope passes every applicable cell in its language column,
implementation is *credibly* complete — not just compilable. When it
doesn't, the specific cell that failed is the next gap to close.

## Risk-triggered Tier-3 escalation

Tier-1 (unit + coverage + mutation) runs every iteration. Tier-2
(integration + contract) runs at story-completion. Tier-3 (chaos /
deterministic-simulation / multi-VM) only runs when the scope's spec
or threat model mentions one of these triggers — Tier-3 is expensive
and shouldn't run by default.

| Trigger phrase in spec / threat model | Tier-3 tool |
|---|---|
| "leader election", "consensus", "transaction commit protocol" | TLA+ / P + `tlc` model check |
| "concurrent", "parallel", "race", "atomic" (Rust hand-rolled prims) | loom (exhaustive C11) |
| "Tokio task", "async fn", "tokio::spawn" in multi-agent path | shuttle (randomized PCT) |
| "distributed", "ZMQ DEALER/ROUTER", "message bus", "saga" | madsim deterministic simulation |
| "multi-host", "VLAN", "BitTorrent topology", "deploy verification" | nixosTest multi-VM with tc-netem in guests |
| "network partition", "latency injection", "packet loss" | Toxiproxy in front of sockets |
| "FIPS", "AEAD", "signature scheme", "key exchange" | Wycheproof vectors + differential against ring / RustCrypto / openssl-sys |
| "OpenAPI", "REST contract", "GraphQL schema" | schemathesis conformance fuzz |

When none of those triggers fire, Tier-3 is genuinely not needed for the
scope. When one fires, sampling 10–50 seeds at scope-completion is the
right budget; full sweeps (≥ 1000 seeds) only at project-complete or
pre-merge.

## Recurrence patterns to feed `iteratotron`

These signals come from tool output and feed iteratotron's stop-bias
catalogue across sessions:

| Recurring pattern across sessions | Recurrence family |
|---|---|
| Same `(file, fn, mutation_op)` survives in mutation output | test-effectiveness regression |
| Same `(file, fn)` CRAP score rising | complexity creep |
| Same `(ecosystem, package, advisory_id)` in supply-chain output | supply-chain debt |
| Same `(file, snapshot)` flipping state across iterations | snapshot churn / nondeterminism |
| bolero / Kani proof time growing > 50% session-over-session | verification time regression |
| Same orphan symbol surviving dead-code passes | orphan scaffolding plateau |

iteratotron's recurrence detector (`references/stop-bias-patterns.md`)
treats three hits as a STOP-PAT escalation — the soft signal needs to
fire repeatedly before it becomes the human's problem.

## Caveats from the field

- **cargo-crap is new (2025)** and built by a single maintainer (minikin).
  The formula is correct and well-architected but not battle-tested at
  scale. Pin v0.2.0 and validate LCOV parsing on your own repo before
  relying on it as a hard gate. Hand-computed fallback (cyclomatic from
  clippy + LCOV from `cargo llvm-cov`) is documented in
  `.claude/rules/static-analysis.md`.
- **TestGen-LLM caveat** (Alshahwan et al., Meta, ESEC/FSE 2024): 75% of
  generated tests built correctly, 57% passed reliably, only 25% measurably
  increased coverage. An LLM agent that generates tests will produce a
  majority that compile and pass but don't catch new behaviour. This is
  the empirical reason `iterate` requires mutation testing as a gate
  downstream of any LLM-generated test.
- **Mutation-testing benchmark figures vary widely.** The "~1200 mutants/min,
  88.5% detection" Mutmut number from a johal.in blog is unreviewed; the
  peer-reviewed UT Dallas 2024 IEEE comparison emphasises that no Python
  mutation tool dominates and operator coverage matters more than
  throughput. Treat per-tool benchmarks as directional, not absolute.
- **Hypothesis stateful performance** degrades with many dynamic rules
  (open issue #4465, July 2025) — split mega-machines per agent class.
- **vulnix's NVD coverage** lags 24–48 hours behind publication; for
  high-severity Nix CVEs, supplement with Trivy on the same closure.
