# Nix harness toolchain and adversarial checklist

The driver layer for a Pattern 3 Nix harness (Nix-as-the-deliverable —
see `implementation-nix.md`). Shell out to `nix` and a fixed toolchain
with `--json`; parse into typed Rust results; do **not** embed an
evaluator.

- [Driver invocations](#driver-invocations)
- [Don't embed tvix yet](#dont-embed-tvix-yet)
- [Parsing and editing Nix source](#parsing-and-editing-nix-source)
- [Pure-Nix and module unit testing](#pure-nix-and-module-unit-testing)
- [Adversarial review checklist](#adversarial-review-checklist)
- [Reproducer construction](#reproducer-construction)
- [Observability](#observability)
- [Staged rollout](#staged-rollout)
- [Caveats](#caveats)

## Driver invocations

Typed wrappers over the `nix` CLI, all with `--json` where available.
Every long-running call gets the liveness heartbeat (a `nix build` of a
heavy closure goes silent for minutes — indistinguishable from a hang
without it).

| Invocation | Purpose | Feeds |
|---|---|---|
| `nix flake show --json` | enumerate outputs (packages, checks, nixosConfigurations) | the triage target queue |
| `nix flake check --no-build` | fast eval-only validation of all outputs | eval-error bucket |
| `nix flake check -L` | run all checks with full logs | test/build buckets |
| `nix eval --json .#<attr>` | structured values (`meta`, option defaults) | requirement checks |
| `nix-eval-jobs --flake '.#checks.<sys>'` | streamable per-job JSON, memory-bounded parallel eval | enumerate + classify before building |
| `nix build --json .#<attr>` | build + output paths | build bucket |
| `nix build --rebuild` / `--check --keep-failed` | reproducibility | reproducibility bucket |
| `nix derivation show <drv>` | `.drv` graph JSON (inputs, outputs, env) | dependency/closure analysis |
| `nix log <drv>` / `nix-store --read-log` | build logs | failure classification |
| `nix store diff-closures A B` | closure delta between revisions | size/observability |
| `nix path-info -S` / `--closure-size` | closure sizes | observability |

Static analysis and review tools (all emit parseable output):

- `statix check` — antipattern linter (Rust, on rnix-parser): `with pkgs;`
  in module scope, `rec` sets, unnecessary `let`. `statix fix` autofixes.
- `deadnix` — dead code / unused bindings.
- `nixfmt-rfc-style --check` — canonical formatter (RFC 166). The old
  style is the unmaintained `nixfmt-classic`. `alejandra` is an alternative.
- `nixpkgs-hammering` — nit-picky nixpkgs-PR rules.
- `nixpkgs-review` — fetch a PR (or local `wip`/`rev`), build affected
  packages + reverse deps in isolated **git worktrees** under `.review/`,
  optionally `--post-result`. Matches the harness worktree-isolation rule.
- `nixpkgs-check-by-name` — validate the `pkgs/by-name` structure.
- `nix-fast-build --skip-cached` — incremental check re-runs in the inner
  loop; pipe through `nom` (`nix-output-monitor`) for visible progress.

Supply-chain tools (acceptance gate for image/hardened builds):
`sbomnix` (Nix-native SBOM + SLSA provenance), `slsa-verifier`, `cosign`,
`syft`, `grype`, `sbomqs`, `vexctl`, `vulnix`/`trivy`.

## Don't embed tvix yet

The tvix README states verbatim that it "is not ready for use in
production" and "None of our current APIs should be considered stable in
any way." Its fork `snix` is fast-moving. So:

- **Evaluate by shelling out to `nix`** — it's resilient,
  forward-compatible, and emits structured output. This is what
  Hydra-style CI does at scale.
- **The one reusable tvix crate is `nix-compat`** — store-path math,
  hashing schemes, `.drv` and NAR parsing — usable to compute and assert
  store-path invariants *without* spawning Nix.
- **`tvix-eval`/`snix-eval` are feature-gated, best-effort only** — embed
  later for fast lint-time eval of small expressions if subprocess
  overhead bites, never as the primary evaluator.

> **Naming footgun:** the `nix` crate on crates.io is **POSIX/Unix
> syscalls, NOT the Nix package manager.** Don't add it expecting a Nix
> API — it won't give you one. Drive the `nix` *binary* via
> `tokio::process` instead.

## Parsing and editing Nix source

Use `rnix-parser` (rowan-based, lossless CST — printing the AST
reproduces the original source exactly, preserving spans and comments).
It backs `nil`/`nixd`/`statix`. The harness uses it to:

- implement custom adversarial lints beyond statix (IFD patterns, missing
  `meta`, `with`-scope leaks);
- make safe automated edits — add `passthru.tests`, fix `meta.maintainers`
  — without destroying formatting.

It's community-maintained (`nix-community/rnix-parser`); watch for lag
against new language features.

Process orchestration: `tokio::process::Command` with piped stdout/stderr
read line-by-line via `BufReader` + `AsyncBufReadExt::lines()`, wrapped in
`tokio::time::timeout` with `kill_on_drop(true)`. `tokio-process-tools`
packages streaming inspection, readiness-by-log-line, and graceful
SIGINT→SIGTERM→kill escalation — well matched to watching `nix build`.

## Pure-Nix and module unit testing

For NixOS modules, overlays, and Nix-only logic, test without a VM where
you can — it's orders of magnitude cheaper than `runNixOSTest`, and you
don't need KVM for any of it:

- `lib.evalModules` — unit-test option definitions, defaults, and
  `assertions` in pure eval.
- `nix-unit` — per-test failures even on eval errors; `expr` / `expected`
  / `expectedError` (regex); integrates with `nix flake check`. `lix-unit`
  is the Lix fork.
- `pkgs.lib.runTests` — built-in `test*` attrs with `expr`/`expected`.
- `namaka` — snapshot testing on haumea (`namaka check`/`review`),
  conceptually identical to Rust's `insta`; ideal for asserting stable
  eval output of module configs.

Derivation testers in `pkgs.testers.*`: `testVersion` (runs `<pkg>
--version`, greps for the version), `testBuildFailure` (asserts a build
fails; captures `.log`/`.exit`), `testEqualContents`, `testEqualDerivation`,
`invalidateFetcherByDrvHash` (force FOD re-fetch in tests),
`hasPkgConfigModules`, `runNixOSTest`/`nixosTest`, `lycheeLinkCheck`.

## Adversarial review checklist

Here's what the reviewer hunts for (walk the rnix CST + run
`nixpkgs-hammering`):

- **IFD / import-from-derivation** — banned in nixpkgs; serializes eval on
  a build (stalls). Detect `import <drv-output>`, `builtins.readFile
  <drv>`, crane/cabal2nix-style patterns. For nixpkgs targets, **reject**
  and propose committed-generated-code alternatives. For non-nixpkgs
  flakes (crane-based Rust), IFD is acceptable but flag the cost.
- **Impurities** — `builtins.currentTime`, unpinned `fetchTarball`/
  `fetchGit` without hash, `<nixpkgs>`/`NIX_PATH` reliance, network in
  build, `__noChroot`, reading env at eval.
- **Missing / incorrect `meta`** — no `description`, `license`,
  `maintainers`, `platforms`; missing `mainProgram` (needed for
  `testVersion` / `nix run`).
- **Missing tests** — no `passthru.tests`, no `nixosTests` wiring for a
  service, no `testVersion`. An untested derivation output is a gap.
- **Cross-compilation breakage** — wrong `nativeBuildInputs` vs
  `buildInputs` split, `buildPackages` misuse, hardcoded `stdenv.system`.
- **FOD hash issues** — stale/wrong `hash`/`cargoHash`/`vendorHash`; use
  `invalidateFetcherByDrvHash` to force re-fetch in tests.
- **Overlay / override correctness** — `passthru.tests` not using
  `finalAttrs.finalPackage`; `overrideAttrs` vs `override` confusion;
  `rec` self-reference fragility.
- **Module regressions** — removed/renamed options without
  `mkRenamedOptionModule`/`mkRemovedOptionModule`; missing `assertions`;
  silent default changes (the GitLab PostgreSQL≥16 assertion, the
  15.7 weak-password silent root-user failure).
- **Reproducibility** — timestamp/locale/ordering non-determinism; archive
  formats (ZIP/JAR). Discipline: `SOURCE_DATE_EPOCH` / `outputTimestamp`.
- **Eval failures under specific systems/configs** — test with
  `--all-systems`, `checkMeta = true`, and multiple `nixpkgs.config`
  permutations.

The authoritative process references are the nixpkgs `CONTRIBUTING.md`,
the manual's "Reviewing contributions" section, and `pkgs/README.md`
(the three test types). ofborg encodes the machine checks (eval validity,
`meta` presence, maintainer-list membership, platform builds); note it
may omit packages with `hydraPlatforms = []`, so supplement with local
`nixpkgs-review --eval local`.

## Reproducer construction

- **Runtime failures** (not caught at build/eval) — write a
  `runNixOSTest` that reproduces the failing scenario, confirm it fails on
  the unfixed tree in a worktree, fix, confirm green. Reproducer-first.
- **Eval/build failures** — a minimal `nix eval` / `nix build` invocation
  captured as a `checks` entry or a `nix-unit` case.

## Observability

Emit one structured JSON record per phase/derivation (mirror the
`streaming.*` convention so the agent reacts and humans get a report):

- **build logs** — streamed `nix log` output, error lines classified;
- **timings** — wall-clock per derivation/check, eval vs build split
  (nix-eval-jobs surfaces eval cost);
- **cache hit rate** — `nix-eval-jobs --check-cache-status` (`cacheStatus`
  field), `nix path-info` substituter queries;
- **closure sizes** — `nix path-info -S`, `nix store diff-closures`;
- **test results** — parse the nixos-test-driver output and nix-unit/
  namaka JSON; emit JUnit for dashboards;
- **supply-chain status** — pass/fail per artifact (provenance, SBOM
  score, VEX validity, signatures, reproducibility).

## Staged rollout

1. **Foundations (no VMs)** — driver + rnix inspection; wire `nix flake
   check --no-build`, `nix-eval-jobs`, `statix`, `deadnix`, `nixfmt
   --check`, `nixpkgs-hammering`, `nix derivation show --json`; add
   `nix-unit`/`namaka`/`evalModules`. *Advance when* triage classifies
   eval/lint failures and the reviewer produces a prioritized gap list.
2. **Derivation & build** — `nix build --json`, `passthru.tests`/
   `testVersion` enumeration + execution, reproducibility checks,
   `nixpkgs-review`. *Advance when* the harness can add a missing
   `passthru.tests` and prove it passes, and fix a build/eval bug
   reproducer-first.
3. **E2E (KVM-gated)** — `runNixOSTest` orchestration via
   `nixos-test-driver`, the GitLab example, container build/run. *Advance
   when* the built app/image boots and passes its smoke test E2E.
4. **Supply chain** — `sbomnix`, `slsa-verifier`, `cosign`, `syft`/
   `grype`/`sbomqs`, `vexctl`. *Advance when* the build fails if any
   provenance/SBOM/VEX/signature/reproducibility check fails.
5. **Full autonomy** — agent dispatch under nono consuming the telemetry,
   gated by `cargo-mutants` (zero survivors on changed lines), fuzzing,
   and coverage on the harness's own Rust.

## Caveats

- **tvix/snix immaturity** — not production-ready per the maintainers;
  APIs unstable. Use `nix-compat` only, prefer shelling out.
- **nixosTest cost & CI** — needs KVM, ~4GB+ RAM, minutes per run; GitLab
  CI can't cache the Nix store outside the project dir. Plan a binary
  cache + `/dev/kvm` passthrough; keep heavy E2E in a nightly-gated tier.
- **IFD** — banned in nixpkgs, stalls eval; reject for nixpkgs targets,
  flag for crane-based flakes.
- **GitLab test path moved** to `nixos/tests/gitlab/default.nix` — resolve
  the attr via `nix flake show`/`nixosTests`, never a hardcoded path.
- **SLSA L3** — needs a trusted isolated builder; the harness verifies,
  the build system generates.
- **rnix-parser** — community-maintained; watch for lag against new Nix
  language features.
- **Fast-moving** — `nixfmt-rfc-style` (RFC 166), dynamic derivations (a
  future IFD replacement), and the snix/tvix split are all evolving. Pin
  tool versions and re-validate periodically.
