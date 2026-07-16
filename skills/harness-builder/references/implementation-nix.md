# Nix harness builder

Nix shows up in three shapes, and the harness handles all of them:

1. **Nix-wrapped harness** — the project is in another language but uses
   Nix for build orchestration. The harness binary itself is built via
   Nix and integrates with the project's flake. (Pattern 1.)
2. **Pure-Nix project** — a NixOS module, an overlay, or a Nix-only DSL
   package where the "harness" is a flake.nix check graph rather than a
   binary. (Pattern 2.)
3. **Nix *is* the deliverable** — the Nix itself is the thing under test:
   a nixpkgs derivation, a flake build, an OCI/disk image build, or a
   repackaging of existing software via flakes/modules/derivations. Here
   the harness drives `nix` like an operator, triages every signal
   against nixpkgs standards plus the project's own requirements, and
   burns down gaps and defects in the Nix **and** in the packaged
   software it ships. (Pattern 3 — the focus of "Nix as the deliverable"
   below.)

The Rust harness orchestrates by shelling out to the `nix` CLI with
`--json` and to a fixed toolchain; it does **not** embed an evaluator.
The full toolchain table, the adversarial-review checklist, and the
worked GitLab-image example live in
[nix-harness-toolchain.md](nix-harness-toolchain.md). This file covers
wiring and the loop; that file covers the tools and the gotchas.

## Pattern 1 — Nix-wrapped harness

The harness binary is built by Nix as a package. The flake.nix exposes
it as `packages.<arch>.<project>-genesis`:

```nix
{
  description = "<project> with genesis-driven implementation harness";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-parts.url = "github:hercules-ci/flake-parts";
    crane.url = "github:ipetkov/crane";          # for Rust harnesses
  };

  outputs = inputs@{ flake-parts, ... }:
    flake-parts.lib.mkFlake { inherit inputs; } {
      systems = [ "x86_64-linux" "aarch64-linux" "aarch64-darwin" ];

      perSystem = { config, self', inputs', pkgs, system, ... }: let
        craneLib = inputs.crane.mkLib pkgs;
      in {
        packages.<project>-genesis = craneLib.buildPackage {
          src = craneLib.cleanCargoSource ./<project>-genesis;
          # use cargo-auditable for SLSA-attestable provenance
          cargoBuildCommand = "cargo auditable build --release";
          nativeBuildInputs = [ pkgs.cargo-auditable ];
          # nono is a runtime dep (the harness forks it at each claude call),
          # not a build dep, so it lives in the dev shell below.
        };

        # nono is required at runtime. Pin via flake.lock; it's alpha (0.x)
        # and flags change across minor versions — re-test after bumps.
        # See references/nono-integration.md for the sandbox contract.
        devShells.default = pkgs.mkShell {
          packages = [ pkgs.nono ];
        };

        # Tier-1 checks
        checks = {
          <project>-genesis-tests = craneLib.cargoTest {
            src = craneLib.cleanCargoSource ./<project>-genesis;
          };
          <project>-genesis-clippy = craneLib.cargoClippy {
            src = craneLib.cleanCargoSource ./<project>-genesis;
            cargoClippyExtraArgs = "-- -D warnings";
          };
          <project>-genesis-mutation = pkgs.runCommand "mutation" {
            buildInputs = [ pkgs.cargo-mutants ];
          } ''
            cd ${./.}/<project>-genesis
            cargo mutants --in-diff <(git diff main) > $out/mutants.json
          '';
        };

        # Tier-3 nixosTest topologies (when triggered).
        # nono wrapping applies to the *orchestrator* running outside the VM,
        # not to commands inside the nixosTest script — the VM is already an
        # isolation boundary. Wrapping inside would be double-isolation with
        # no security benefit and extra PATH friction.
        checks.multi-vm-topology = pkgs.testers.runNixOSTest {
          name = "multi-vm-topology";
          nodes = {
            agent1 = { ... };
            agent2 = { ... };
            broker = { ... };
          };
          testScript = ''
            start_all()
            agent1.wait_for_unit("<project>-agent.service")
            agent2.wait_for_unit("<project>-agent.service")
            broker.wait_for_unit("<project>-broker.service")

            # tc-netem injection for chaos
            broker.succeed("tc qdisc add dev eth1 root netem delay 100ms loss 5%")

            agent1.succeed("test-scenario --scenario partition-recovery")
            broker.succeed("tc qdisc del dev eth1 root")
            agent1.wait_until_succeeds("test-status --scenario partition-recovery --expect recovered")
          '';
        };
      };
    };
}
```

Genesis Phase 0 scaffolds this flake.nix when none exists. The harness
binary itself is built per the primary language's reference
(`rust.md`, `go.md`, `python.md`, `ruby.md`). That binary includes
the nono wrapping logic (see `references/nono-integration.md`); its
runtime dependency on `nono` is satisfied by the `devShells.default`
entry above.

## Gate-execution contract (any flake-bearing project)

This applies to **every** project that ships a `flake.nix`, regardless of the
harness's primary language — not just pure-Nix projects. The project flake is
the toolchain boundary: it pins the compiler and the gate tools, so the harness
must run gates inside the devShell, and the devShell must contain those tools.

### Why: gates run outside the devShell produce false failures

A flake-bearing project does not put its toolchain on the bare host PATH. Run a
gate outside `nix develop` and you get spurious failures that an autonomous loop
will misread as real defects and "fix" by thrashing. Observed on vulnmapper
(Go + flake, 2026-06-13) when gates were run on the host instead of the devShell:

| Host-PATH symptom | Reality inside `nix develop` |
|---|---|
| `cgo: C compiler "gcc" not found` on `go vet`/`go build`/`go test` | devShell provides the gcc wrapper; vet/test pass |
| `which: no govulncheck` | resolved (devShell tool or `go run …/govulncheck`) |
| `nix flake show` → `experimental Nix feature 'nix-command' is disabled` | succeeds with `--extra-experimental-features 'nix-command flakes'` |
| `gofmt -l .` lists dozens of files | all under gitignored `.claude/worktrees/` and `.iteratotron/` scratch copies; the real tree is clean |

None were defects. A completion checker then reported P0/P1 gaps that evaporated
once the gates ran in the devShell. The harness must not be able to make this
mistake.

### The rule

When `flake.nix` is present, the harness routes **every** gate subprocess through
the project devShell:

```bash
nix develop --extra-experimental-features 'nix-command flakes' \
  --command bash -lc '<gate command>'
```

- Use `--command bash -lc '…'` so devShell `shellHook` exports (PATH,
  `CGO_ENABLED`, `PKG_CONFIG_PATH`, DB sockets) are in effect.
- Set `--extra-experimental-features 'nix-command flakes'` unconditionally; the
  host `nix.conf` may not enable them.
- Scope gate file-walks to the tracked tree (`git ls-files`); exclude
  `.claude/worktrees/`, `.iteratotron/`, `<project>-harness/`,
  `<project>-genesis/` and other gitignored scratch dirs from `gofmt -l`, lint,
  and coverage walks.

### Preflight: validate the flake and the devShell toolchain

Before scaffolding, and again at each run's preflight, assert:

1. **The flake is properly formed.** `nix flake metadata` **and** `nix flake
   show` exit 0. A flake that won't evaluate is a hard blocker; fix it or report
   it. Never silently fall back to host-PATH gates.
2. **The devShell carries the harness's gate dependencies.** For each gate tool,
   assert it resolves *inside* the shell, e.g.:
   ```bash
   nix develop --command bash -lc 'command -v go cc golangci-lint && go version'
   ```
   Per-language minimum (all must resolve in `devShells.default`):

   | Language | Required in devShell |
   |---|---|
   | Go | pinned `go`, a C compiler (`cc`/`gcc` wrapper) for cgo, `golangci-lint`, govulncheck (packaged or via `go run golang.org/x/vuln/cmd/govulncheck`), coverage tooling |
   | Rust | `cargo`/`rustc` (or the `rust-toolchain`), `clippy`, `rustfmt`, `cargo-nextest`/`cargo-mutants` if used |
   | Python | the pinned interpreter, `ruff`, `mypy`/`pyright`, `pytest`, `pip-audit` if used |
   | Ruby | the pinned `ruby`, `rubocop`, `bundler-audit` if used |
   | Nix | `nix flake check` itself; plus `nixpkgs-fmt`/`alejandra`, `statix`/`deadnix` if gated |

3. **If genesis scaffolded the flake, the harness owns the fix:** add any missing
   gate tool to `devShells.default.packages` and re-assert. If the project owns
   its flake, a missing tool is reported as a gap (with the exact `packages` line
   to add), never silently worked around.
4. **Record the resolved toolchain in the run manifest** (compiler version,
   devShell store path, gate tool versions) so a real gate failure is
   distinguishable from a toolchain mismatch.

### Scaffolded devShell must list gate deps, not just runtime deps

The `devShells.default` in Pattern 1 shows only `pkgs.nono` (the harness
*runtime* dep). When genesis scaffolds or amends a flake for a project whose
gates it will run, the devShell must additionally carry the gate toolchain. For
a Go project, at minimum:

```nix
devShells.default = pkgs.mkShell {
  packages = [
    pkgs.nono            # harness runtime dep (sandbox)
    pkgs.go              # pinned compiler
    pkgs.gcc             # cgo C compiler — without this `go vet`/`test` fail
    pkgs.golangci-lint
    pkgs.govulncheck     # or rely on `go run …/govulncheck`
    pkgs.gotestsum
  ];
};
```

The smoke-test in SKILL.md Step 8 must include one real gate run through
`nix develop --command` to prove the wiring end-to-end before the first loop.

## Pattern 2 — pure-Nix project

For projects that are themselves Nix expressions (a NixOS module, an
overlay, a flake-parts module library), the "harness" is the flake's
check graph plus the genesis-side orchestration is in Python or shell.
Genesis runs from a `nix shell` with `claude-code`, `python3`, and
`nono` available:

```bash
nix shell nixpkgs#claude-code nixpkgs#python3 nixpkgs#nono
```

Every `claude` invocation in the Python or shell genesis layer wraps
through `nono run --silent` exactly as the other language paths do.
See `references/nono-integration.md` for the canonical wrapper command
and the `--add-dir` ↔ `--allow` invariant.

A minimal shell genesis call:

```bash
nono run --silent \
  --network-profile claude-code \
  --allow . --allow .bug-burndown --allow .test-effectiveness \
  -- claude -p "$PROMPT" \
     --output-format stream-json --verbose --include-partial-messages \
     --permission-mode bypassPermissions \
     --model haiku --max-turns 80 --max-budget-usd 20 \
     --add-dir . --disallowed-tools WebSearch
```

```nix
# flake.nix for a pure-Nix project under genesis
{
  outputs = inputs@{ self, nixpkgs, ... }: let
    system = "x86_64-linux";
    pkgs = nixpkgs.legacyPackages.${system};
  in {
    # Tier-1: lint + dead-code + format
    checks.${system} = {
      statix = pkgs.runCommand "statix" {} ''
        ${pkgs.statix}/bin/statix check ${./.}
        touch $out
      '';
      deadnix = pkgs.runCommand "deadnix" {} ''
        ${pkgs.deadnix}/bin/deadnix --no-lambda-arg --no-lambda-pattern-names ${./.}
        touch $out
      '';
      nixfmt-check = pkgs.runCommand "nixfmt-check" {} ''
        ${pkgs.nixfmt-rfc-style}/bin/nixfmt --check ${./.}
        touch $out
      '';
      vulnix = pkgs.runCommand "vulnix" {} ''
        ${pkgs.vulnix}/bin/vulnix -G ${self} > $out
      '';

      # Tier-2: module-level integration tests.
      # nono wrapping is for the orchestrator outside the VM, not commands
      # inside the test script — the VM is already an isolation boundary.
      module-evaluation = pkgs.testers.runNixOSTest {
        name = "module-evaluation";
        nodes.machine = { ... }: {
          imports = [ self.nixosModules.default ];
          # ... module options exercised ...
        };
        testScript = ''
          machine.wait_for_unit("multi-user.target")
          machine.succeed("test-module-installed")
        '';
      };
    };
  };
}
```

Genesis runs `nix flake check --all-systems` as the Tier-1 gate and
specific Tier-2 / Tier-3 topology builds as part of the done predicate.

## Nix as the deliverable (Pattern 3)

When the Nix is the thing being built, tested, and shipped — a nixpkgs
package or PR, a flake that builds an application, an image build, or a
repackaging of existing software — the genesis harness drives `nix` and
the Nix tooling exactly the way the runtime harness drives an HTTP API or
a CLI. The "natural interface" is the `nix` CLI; the "requirements" are
the project's stories/ADRs/specs/threat-model **plus** the nixpkgs
contribution standards; the loop closes gaps in the Nix and in the
software the Nix ships.

### Project sub-shapes and what "done" means for each

| Sub-shape | Drive surface | Done means |
|---|---|---|
| **nixpkgs derivation / PR** | `nixpkgs-review`, `nix build -A <attr>`, `passthru.tests`, `nixpkgs-hammering` | builds on declared platforms; lint + format + hammering clean; `meta` complete; `passthru.tests`/`testVersion` present and green; reverse deps build |
| **Flake application build** | `nix flake check`, `nix build .#<pkg>`, `nix run` | every flake output builds; `checks` green on `--all-systems`; the built app runs and passes its own tests + E2E |
| **Image build (OCI / disk)** | `nix build .#<image>`, load + run, `nix build --rebuild` | image builds reproducibly; the app inside boots and passes the E2E smoke; supply-chain artifacts present + verify |
| **Repackaging existing software** | derivation + NixOS module + `nixosTests` | the repackaged software builds, the module configures it, and the existing upstream tests / E2E scenarios pass against the Nix-built instance |

The recurring rule for **all four**: don't stop at "eval succeeds" or
"the derivation built". Build the derivation **and exercise its output**
through the same tests and E2E scenarios you'd run if you were harnessing
the software directly. A package whose `nix build` is green but whose
binary was never run, or a module whose options eval but whose service
never booted, is an untested output and a gap — never `Clean`.

### The agentic loop, mapped onto Nix

The standard `INSTRUMENT → DRIVE → OBSERVE → TRIAGE → SCHEDULE → BURN
DOWN` cycle maps cleanly:

- **INSTRUMENT** — preflight the flake (`nix flake metadata` + `nix flake
  show --json` both exit 0), resolve the devShell toolchain, load
  requirements + the nixpkgs-standards checklist.
- **DRIVE** — run the gate ladder in order of cost: `nix flake check
  --no-build` (fast eval) → `statix check` / `deadnix` / `nixfmt
  --check` / `nixpkgs-hammering` → `nix-eval-jobs` to enumerate every
  flake output and `check` → `nix build` the changed attrs and their
  reverse deps (`nixpkgs-review`) → run `passthru.tests`/`nixosTests` →
  build images and run E2E → verify supply-chain artifacts.
- **OBSERVE** — parse the `--json` output of every tool into typed
  results; capture `nix log` for failed builds; stream long builds with a
  liveness heartbeat (a `nix build` of a heavy closure goes silent for
  minutes — same heartbeat discipline as mutation testing).
- **TRIAGE** — classify each signal into a bucket: eval error, build
  failure, test failure, lint, format, missing-test gap, IFD/impurity
  hazard, cross-compile breakage, FOD-hash mismatch, reproducibility
  drift, supply-chain gap. The adversarial reviewer walks the rnix CST
  for hazards the gate tools miss.
- **SCHEDULE** — link each reject/gap to its requirement item and assign
  priority. P0 = security/threat-model mitigations + a broken build; P1 =
  a `Draft` story whose acceptance criteria fail (e.g. "the packaged app
  passes its E2E"); P2 = lint/format/meta nits.
- **BURN DOWN** — dispatch in-session agents to add the missing
  `passthru.tests`, wire the `nixosTest`, add module `assertions`, fix
  the build reproducer-first, regenerate the FOD hash, complete `meta`.
  Each agent works in a worktree; merge, re-instrument, continue.

The full toolchain wrappers (which `nix --json` invocation feeds which
typed result) and the adversarial-review checklist (IFD, impurity,
missing tests, cross-compile, FOD hashes, module regressions,
reproducibility) are in
[nix-harness-toolchain.md](nix-harness-toolchain.md).

### The triage gate ladder as flake checks

Express the cheap gates as `checks` so `nix flake check` runs them and
so the harness can build a single one with `nix build .#checks.<sys>.<name>`:

```nix
checks.${system} = {
  statix   = pkgs.runCommand "statix"   {} '' ${pkgs.statix}/bin/statix check ${./.}; touch $out '';
  deadnix  = pkgs.runCommand "deadnix"  {} '' ${pkgs.deadnix}/bin/deadnix --fail ${./.}; touch $out '';
  fmt      = pkgs.runCommand "fmt"      {} '' ${pkgs.nixfmt-rfc-style}/bin/nixfmt --check ${./.}; touch $out '';
  # nixpkgs-hammering for PR-shaped projects; nix-unit / namaka for pure-Nix logic
};
```

`nixfmt-rfc-style` is the canonical formatter (RFC 166); the old style is
the unmaintained `nixfmt-classic`. `statix` and `deadnix` are both Rust
tools that emit machine-readable output the harness parses directly.
`nix-linter` is superseded by `statix` — don't wire it.

### Exercising the packaged software (the part most harnesses skip)

The whole point of Pattern 3 for application/repackaging projects is that
the software shipped via Nix gets exercised by real tests and E2E
scenarios, not just built. Three layers, in increasing cost:

1. **Derivation-level** — `passthru.tests = { version =
   pkgs.testers.testVersion { package = finalAttrs.finalPackage; }; }`.
   Use `finalAttrs.finalPackage` (the fixed-point) so the test follows
   `overrideAttrs` instead of testing the un-overridden package. Run with
   `nix build -A pkgs.<name>.passthru.tests`.
2. **Service / module-level** — a `pkgs.testers.runNixOSTest` that imports
   the project's NixOS module, enables the service, and asserts behaviour
   from a second `client` node over the network. For a repackaging effort,
   **reuse** the upstream `nixosTests.<name>` via `.extendNixOS { module =
   { services.foo.package = finalAttrs.finalPackage; }; }` so the existing
   integration test runs against your build.
3. **E2E acceptance** — build the image, run it, drive the upstream E2E /
   scenario suite against the running instance. For a service this is the
   upstream API smoke (or the project's own E2E RSpec/pytest/etc.) pointed
   at the Nix-built instance in a VM.

`runNixOSTest` boots real QEMU VMs and needs **KVM** (`/dev/kvm`), ~4GB+
RAM, and minutes per run. Gate it on KVM availability; on a macOS host
fall back to the `linux-builder` remote builder or skip with a loud
warning. In CI, the Nix store can't be cached outside the project dir, so
plan a binary cache (Cachix/attic/minio) and `/dev/kvm` passthrough on a
privileged runner. Keep heavy E2E in a nightly-gated tier and rely on
derivation-level + module-eval (`lib.evalModules`) tests in the inner loop.

### Worked example — repackaging GitLab with a hardened image

A repackaging project that ships hardened GitLab container images with
SLSA L3 provenance, CycloneDX SBOMs, and OpenVEX (capabilities Omnibus
doesn't provide) is the canonical Pattern 3 shape. The harness:

1. Builds the OCI image (`nix build .#packages.<sys>.gitlab-image`) via
   `nix2container` or `dockerTools`.
2. Reuses `nixosTests.gitlab` (resolve the attr via `nix flake show` —
   the test file moved to `nixos/tests/gitlab/default.nix`; don't hardcode
   the path) via `extendNixOS` to swap in the hardened
   `services.gitlab.packages.gitlab`, proving the hardened build still
   passes the upstream `/api/v4/` smoke test (create users/projects/
   issues/snippets/commits; the full Puma + Gitaly + Workhorse + Sidekiq +
   PostgreSQL + Redis stack boots under `gitlab.target`).
3. Runs the image and asserts health (`wait_for_open_port`,
   `/api/v4/version`, login).
4. Asserts the supply-chain artifacts (next section).
5. Optionally drives GitLab's own `gitlab-qa` E2E RSpec against the
   running Nix-built instance as a heavier acceptance tier.

GitLab module footguns the adversarial reviewer must catch: a
`databasePasswordFile` given as a Nix path (not a string path) copies the
secret world-readable into the store; and since 15.7 GitLab silently
fails to create the root user from a weak `initialRootPasswordFile`.

### Supply-chain verification as an acceptance gate

For image/hardened-build projects, treat supply-chain artifacts as E2E
acceptance — the build **fails** if any check fails. All are CLI-shellable
from the Rust harness:

- **SLSA provenance** — generate with `sbomnix provenance` (SLSA v1.0 for
  a derivation/closure); verify with `slsa-verifier verify-image …` or by
  checking the in-toto `https://slsa.dev/provenance/v1` predicate. L3
  needs a trusted isolated builder — the harness *verifies* it; the build
  system *generates* it.
- **SBOM** — `sbomnix` (Nix-native CycloneDX + SPDX from the closure) or
  `syft`; score with `sbomqs`; scan with `grype`; verify the attestation
  with `cosign verify-attestation --type cyclonedx`.
- **VEX** — validate OpenVEX docs with `vexctl`; cross-check that `grype`
  findings are addressed or suppressed by the VEX statements.
- **Signatures** — `cosign verify` / `cosign verify-attestation` (keyless
  via Rekor or key-based).
- **Reproducibility** — `nix build --rebuild` on the image derivation;
  diff with `diffoscope`; compare closures with `nix store diff-closures`.

## nix-fast-build for the orchestrator

Genesis uses `nix-fast-build --skip-cached` when re-running checks
during the inner loop to avoid re-evaluating the whole flake graph on
every iteration. Per the nix-fast-build README, on a typical changes-
only diff this drops from minutes to seconds:

```bash
nix-fast-build \
  --skip-cached \
  --flake ".#checks.$(nix eval --raw --impure --expr builtins.currentSystem)" \
  | nom --json
```

`nix-output-monitor` (nom) wraps the output so the operator can see
build progress instead of staring at an unchanging "Evaluating
flake..." line.

## Composing with the runtime-harness Nix integration

When `harness-builder` has also produced a runtime harness for the Nix
project (via the runtime workflow — e.g. a deployment-validator that
exercises a NixOS system), the implementation flake's `checks` reference
the runtime-harness binary as a build input. Both consume the project's
flake.nix's outputs; both write findings to `.bug-burndown/` and
`.test-effectiveness/`.

The microvm.nix integration is the right place to spin up ephemeral
test VMs that exercise the implementation harness without polluting
the developer's host:

```nix
{
  microvm = {
    hypervisor = "qemu";
    vcpu = 4;
    mem = 4096;
    interfaces = [ { type = "tap"; id = "vm-genesis"; mac = "..."; } ];
  };
}
```

`microvm-nix/microvm.nix` (rebranded from astro/microvm.nix in 2024)
supports 8 hypervisors including firecracker, cloud-hypervisor, qemu,
crosvm, and vfkit, with squashfs/erofs read-only root.

## nixos-anywhere `--vm-test` for deployment verification

When the project has deploy-shape (a NixOS configuration intended to
run on a target host), the done-predicate's Tier-2 / Tier-3 includes:

```bash
nixos-anywhere --vm-test --flake .#<target-host> root@dummy
```

This validates the entire deploy inside a VM **without touching the
target**, including the disko disk-layout module. The VM provisions,
boots, applies the configuration, and exits — any failure is a finding
routed to bug-burndown.

## Caveats

- **macOS hosts.** The NixOS test driver assumes Linux x86_64 / aarch64.
  macOS hosts must use the linux-builder remote builder pattern; otherwise
  Tier-2 / Tier-3 nixosTest builds are skipped with a warning.
- **vulnix's NVD coverage lag** is 24–48 hours behind publication. For
  high-severity Nix CVEs, supplement with Trivy on the same closure
  during the done predicate's supply-chain check.
- **crane vs naersk vs crate2nix.** Crane is the 2025–2026 recommended
  Rust-via-Nix builder (Tweag's blog + the nixpkgs community lean
  this way). devenv made crate2nix the default for `languages.rust.import`
  in August 2025. For genesis-built harnesses, **crane** is the right
  choice because of its composable derivations (separate clippy /
  build / test / coverage steps).
- **nix flake check** is non-incremental by default; the
  `--keep-going` flag plus `nix-fast-build`'s caching are what make
  the inner loop's check phase tolerable on a multi-crate project.
