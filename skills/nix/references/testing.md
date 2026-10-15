# Testing Nix work

Load this when you add or change a package, module, library function, flake, or dev shell and need to decide what to test, how to wire the test in, and what evidence to show a reviewer. NixOS VM test mechanics are in [vm tests](vm-tests.md); PR evidence formatting is in [review evidence](review-evidence.md); the tools themselves are in [nix linting tools](nix-linting-tools.md).

**Contents:** [Pick the tests by change type](#pick-the-tests-by-change-type) · [Build-time unit tests](#build-time-unit-tests) · [Install checks and `versionCheckHook`](#install-checks-and-versioncheckhook) · [`pythonImportsCheck`](#pythonimportscheck) · [`passthru.tests`](#passthrutests) · [NixOS VM tests](#nixos-vm-tests) · [Flake checks](#flake-checks) · [Evaluation-level tests](#evaluation-level-tests) · [Reproducibility and no-op checks](#reproducibility-and-no-op-checks) · [What reviewers expect as evidence](#what-reviewers-expect-as-evidence) · [Checkable rules](#checkable-rules) · [Evidence](#evidence) · [Dated advice to ignore](#dated-advice-to-ignore)

## Pick the tests by change type

Run the "minimum" column before you open the PR. The right-hand column is what reviewers tend to ask for next.

| Change | Minimum | Usually also |
|---|---|---|
| Version bump, upstream has tests | Package builds with its check phase on; run the main binary; `nixpkgs-review wip` | `versionCheckHook` if absent |
| Version bump, upstream has no tests | `versionCheckHook` (or `pythonImportsCheck`); run every binary | a `passthru.tests` smoke test for non-trivial tools |
| New CLI or application package | Build; check phase if upstream ships tests; `versionCheckHook`; run every binary in `result/bin` | `passthru.tests` smoke test; `nixpkgs-review wip` |
| New Python library | `pythonImportsCheck`; `pytestCheckHook` when upstream has tests | build against every Python version it supports |
| New C or C++ library | Upstream tests; `testers.hasPkgConfigModules` / `hasCmakeConfigModules` if it installs those files | reverse-dependency build |
| Change to a package with many dependents | `nixpkgs-review` across the dependents; build on the platforms you claim | check the rebuild count: `CONTRIBUTING.md` suggests `staging` from about 500 rebuilds and requires it from 1000 |
| Package that backs a NixOS service | Link the module's `nixosTests.<name>` in `passthru.tests` and run it | `.extendNixOS` so the test uses your package |
| New NixOS module | A `nixos/tests/<name>.nix` module test, registered in `all-tests.nix` | assertion eval tests |
| Changed module option or behaviour | Run the existing test; extend it to cover the change | eval-level test for new assertions |
| Change to a `lib` function | A case in `lib/tests/misc.nix` (or the matching test file) | run `lib/tests/release.nix` |
| Change to a build helper, hook, or tester | A test under `pkgs/test/` run with `nix-build -A tests.<name>` | `passthru.tests` on one real consumer |
| Flake outside nixpkgs | `nix flake check`; build each `packages.<system>` you declare | VM test or `runCommand` check wired into `checks` |
| Overlay or Nix function in your own repo | `lib.debug.runTests` or `nix-unit` cases | a check that evaluates them |
| Refactor meant to change nothing | Same `drvPath` before and after (see below) | `testers.testEqualDerivation` |
| Dev shell | `nix develop --command true`, then each tool's `--version` | a flake check that builds the shell |

## Build-time unit tests

The check phase runs upstream's tests after the build. `stdenv.mkDerivation` skips it unless `doCheck = true;`; the language builders for Rust and Go run it by default. Cross-compiled builds never run tests, whatever `doCheck` says.

- Test-only tools that must be on `PATH` go in `nativeCheckInputs` (`pytestCheckHook`, `ctest`). Libraries linked into test executables go in `checkInputs`. Both are injected only when `doCheck` is on.
- `checkTarget` and `checkFlags` tune the default `make` invocation. Prefer these and the ecosystem hooks to a hand-written `checkPhase`.
- If you do override `checkPhase`, call `runHook preCheck` first and `runHook postCheck` last.
- Don't write `doCheck = false;` to get a failing build through. The Rust chapter allows it in two cases: no tests exist, or the tests are highly impure (network). Everywhere else, disable the failing subset and say why in a comment. The review checklist in `pkgs/README.md` lists "checks partially or fully disabled" as something that must be documented.
- Before you disable anything, find out whether the failure exists on the base branch. A test that fails the same way without your change isn't your regression, and `nixpkgs-review pr --checkout base` builds the base for comparison.
- Tests that need network access can't pass in the sandbox. Disable them by name.
- Tests that need a writable `HOME` take `writableTmpDirAsHomeHook` in `nativeCheckInputs`.

Selective disabling, per ecosystem:

```nix
# Python: pytestCheckHook
{
  nativeCheckInputs = [ pytestCheckHook ];

  disabledTests = [
    # needs network
    "test_download"
  ]
  ++ lib.optionals stdenv.hostPlatform.isDarwin [
    # sandbox forbids binding the socket
    "test_socket"
  ];

  disabledTestPaths = [
    # integration suite needs a running database
    "tests/integration"
  ];
}
```

```nix
# Go: -skip takes a regular expression
{
  checkFlags =
    let
      skippedTests = [
        # needs network
        "TestNetwork"
        "TestDatabase/with_mysql"
      ];
    in
    [ "-skip=^${builtins.concatStringsSep "$|^" skippedTests}$" ];
}
```

```nix
# Rust: flags after `--` reach the test binary
{
  checkFlags = [
    # reason for disabling the test
    "--skip=example::tests::example_test"
  ];
}
```

`pytestCheckHook` also has `enabledTestPaths`, `enabledTests`, `enabledTestMarks`, `disabledTestMarks`, and `pytestFlags`. The older `pytestFlagsArray` is obsolete (the hook keeps a compatibility shim). Items with spaces, or `"Foo and bar"` sub-expressions, need `__structuredAttrs = true;`.

## Install checks and `versionCheckHook`

`doInstallCheck` runs `installCheckPhase` after install, against the installed outputs. The current form for a version check is a hook plus `nativeInstallCheckInputs`:

```nix
stdenv.mkDerivation (finalAttrs: {
  pname = "foo";
  version = "1.2.3";
  # ...

  doInstallCheck = true;
  nativeInstallCheckInputs = [ versionCheckHook ];

  meta.mainProgram = "foo";
})
```

- The hook runs `meta.mainProgram` (falling back to `pname`) with `--version`, then `--help`, in a clean environment, and fails the build if `${version}` isn't in stdout or stderr.
- Controls: `versionCheckProgramArg` (for `-V`, `version`), `versionCheckProgram` (a full path; use `placeholder "out"`, not `$out`), `versionCheckKeepEnvironment = [ "HOME" ];` (or `"*"`), `dontVersionCheck`, and `preVersionCheck` / `postVersionCheck`.
- `buildPythonPackage` and `buildPythonApplication` enable `doInstallCheck` by default.
- The hook needs a hermetic binary. If the program wants `PATH`, `HOME`, or a config file to print its version, use `testers.testVersion` in `passthru.tests` instead.
- It's a failure users see when they build the package, which is the point: a binary that builds but can't start is caught on the next update, not in a user's profile. `testVersion` only surfaces when someone builds `passthru.tests`.
- The hello package also uses `postInstallCheck` for an extra assertion; the phase hooks `preInstallCheck` and `postInstallCheck` exist for this.
- If you write `installCheckPhase = ''$out/bin/foo --version'';` by hand, replace it with the hook.

## `pythonImportsCheck`

```nix
{
  pythonImportsCheck = [
    "foo"
    "foo.cli"
  ];
}
```

It imports each module in its own phase, and it runs whether or not `doCheck` is on. List the package's public top-level module plus any submodule that pulls in an optional dependency, since a missing dependency shows up as an `ImportError` there. Add it even when you also have `pytestCheckHook`; it takes seconds and catches a broken closure. Use the importable name, not the distribution name.

## `passthru.tests`

`passthru.tests` is an attribute set of derivations that build when the test passes. They don't change the package's own derivation, they exercise it as a consumer would, and you can rerun them without rebuilding the package. Run them with:

```bash
nix-build -A foo.tests
```

Who builds them: Hydra and `nixpkgs-review` skip them by default (`nixpkgs-review pr --tests` adds them), and ofborg builds them for packages your commits touch directly. If a test matters, build it yourself and say so.

```nix
stdenv.mkDerivation (finalAttrs: {
  pname = "foo";
  version = "1.2.3";
  # ...

  passthru.tests = {
    version = testers.testVersion { package = finalAttrs.finalPackage; };
    pkg-config = testers.hasPkgConfigModules { package = finalAttrs.finalPackage; };
    run = callPackage ./test.nix { foo = finalAttrs.finalPackage; };
    service = nixosTests.foo.extendNixOS {
      module = {
        services.foo.package = finalAttrs.finalPackage;
      };
    };
  };

  meta.pkgConfigModules = [ "libfoo" ];
})
```

with `test.nix` beside it:

```nix
{ runCommand, foo }:
runCommand "foo-test-run" { nativeBuildInputs = [ foo ]; } ''
  foo --help > /dev/null
  echo 'input' | foo process > actual
  diff -u ${./expected} actual
  touch $out
''
```

| Tool | Use it for |
|---|---|
| `testers.testVersion { package; command ? ...; version ? ... }` | Version check for a binary the hook can't run hermetically. Matches the version as a whole word. |
| `runCommand` smoke test (`callPackage ./test.nix { foo = finalAttrs.finalPackage; }`) | Run the program on a tiny input and compare output. End with `touch $out`. |
| `testers.hasPkgConfigModules`, `testers.hasCmakeConfigModules` | A library installs the `.pc` or `*config.cmake` files it should. Reads `meta.pkgConfigModules` / `meta.cmakeConfigModules` when `moduleNames` is omitted. |
| `testers.testEqualContents { assertion; expected; actual; }` | Two outputs must match byte for byte, for example a generated file against a golden copy. |
| `testers.testEqualDerivation message a b` | Two package variants must have identical build instructions, such as an overlay that must not cause a rebuild. |
| `testers.testBuildFailure`, `testBuildFailure'` | A build must fail, with an expected exit code and log line; useful for testing testers. |
| `testers.shellcheck`, `testers.shfmt` | Lint a set of shell scripts you ship; pass a `lib.fileset`-selected `src`. |
| `nixosTests.<name>` | A VM test that already exercises the package inside a module. |

- Always pass `finalAttrs.finalPackage` (not the package's own attribute name) so `overrideAttrs` flows into the test.
- A `passthru.tests` derivation is a derivation like any other: it needs `nativeBuildInputs` for the tools it calls, and it must write `$out`.
- Give each entry a short name (`version`, `run`, `service`); `foo.tests.<name>` then builds just that one.
- Keep slow tests here and out of `checkPhase`; the check phase runs on every build of the package for every user who builds from source.

## NixOS VM tests

`nixosTests.<name>` and `passthru.tests` link a module test to the package. The mechanics (nodes, `testScript` API, interactive driver, multi-node, KVM requirements) are in [vm tests](vm-tests.md); what follows is the nixpkgs-specific part.

- In nixpkgs, a test is a module file `nixos/tests/<name>.nix` with `name`, `nodes` (or `containers`), `testScript`, and `meta.maintainers`. Register it in `nixos/tests/all-tests.nix` as `foo = runTest ./foo.nix;`, then run `nix-build -A nixosTests.foo`.
- Outside nixpkgs, call `pkgs.testers.runNixOSTest`. It returns a derivation that runs the test.
- Don't use `testers.nixosTest` for new work; the manual describes it as primarily for external use.
- The test script is linted with Pyflakes and type-checked with Mypy when the test evaluates, so a typo fails evaluation. `skipLint = true;` and `skipTypeCheck = true;` exist for local debugging only; don't commit them.
- `nix-store --read-log result` prints the log of a finished run. `nix-build -A nixosTests.foo.driverInteractive` then `./result/bin/nixos-test-driver` opens a Python prompt where `start_all()` and `test_script()` work. `enableDebugHook = true;` pauses on the first failure.
- VM tests need KVM (or `apple-virt` on macOS, plus a Linux builder). Say which platform you ran on.

```nix
{
  name = "foo";
  meta.maintainers = [ ];

  nodes.machine =
    { pkgs, ... }:
    {
      services.foo.enable = true;
      environment.systemPackages = [ pkgs.curl ];
    };

  testScript = ''
    machine.wait_for_unit("foo.service")
    machine.wait_for_open_port(8080)
    machine.succeed("curl --fail http://localhost:8080/health")
  '';
}
```

Fill `meta.maintainers` with `lib.maintainers` entries (take `lib` as an argument) rather than leaving it empty.

## Flake checks

`checks.<system>.<name>` must be a derivation; `nix flake check` builds each one. It doesn't accept a nested attribute set, so you can't point a check at `passthru.tests` directly. Flatten it:

```nix
{
  checks = forAllSystems (
    system:
    let
      pkgs = nixpkgs.legacyPackages.${system};
      foo = self.packages.${system}.foo;
    in
    {
      inherit foo;
      integration = pkgs.testers.runNixOSTest ./checks/foo-integration.nix;
    }
    // lib.mapAttrs' (name: test: lib.nameValuePair "foo-${name}" test) (foo.passthru.tests or { })
  );
}
```

- `nix flake check --no-build` evaluates everything without building, which is the cheap pre-push gate. `--all-systems` evaluates systems other than yours. Don't claim a system you evaluated but didn't build.
- Keep each check small and independent; they run in the sandbox like any build.
- VM checks need a builder with KVM, so gate them on Linux (`lib.optionalAttrs pkgs.stdenv.hostPlatform.isLinux`). The flattening above also pulls in a package's VM tests, so filter those out for other platforms.
- Build checks from `self.packages`, so they test what you ship.

## Evaluation-level tests

When the thing under test is Nix code (a module's assertions, an overlay, a helper function) you can test it without building anything.

`lib.debug.runTests` takes attributes whose names start with `test`, each `{ expr; expected; }`, and returns the failures as a list (empty means pass). `lib.debug.throwTestFailures` turns a non-empty list into a readable error. `lib/tests/misc.nix` is written this way, and its harness checks that evaluation returns `[ ]`.

```nix
{ lib }:
let
  fooModule =
    { lib, ... }:
    {
      options.services.foo = {
        enable = lib.mkEnableOption "foo";
        port = lib.mkOption {
          type = lib.types.port;
          default = 8080;
        };
      };
    };

  evalFoo = cfg: lib.evalModules { modules = [ fooModule cfg ]; };

  tests = {
    testDefaultPort = {
      expr = (evalFoo { }).config.services.foo.port;
      expected = 8080;
    };
    testPortOverride = {
      expr = (evalFoo { services.foo.port = 9000; }).config.services.foo.port;
      expected = 9000;
    };
    testWrongTypeFails = {
      expr = (builtins.tryEval (evalFoo { services.foo.port = "http"; }).config.services.foo.port).success;
      expected = false;
    };
  };
in
lib.debug.throwTestFailures { failures = lib.debug.runTests tests; }
```

Evaluate it with `nix-instantiate --eval --strict tests.nix --arg lib 'import /path/to/nixpkgs/lib'` (or pass the `lib` from your pinned nixpkgs). It prints `null` on success and throws with the expected and actual values on failure.

- For a NixOS module, evaluate with the real module list (`nixpkgs.lib.nixosSystem` or `pkgs.nixos`) and assert on `config.assertions` or `config.system.build.toplevel.drvPath`. `nix eval --raw .#nixosConfigurations.<name>.config.system.build.toplevel.drvPath` is a fast "does it still evaluate" check for a host configuration.
- `nix-unit` is in nixpkgs (`pkgs.nix-unit`, used by `lib/tests/nix-unit.nix`) and takes the same `expr` / `expected` shape, plus `expectedError` for tests that must throw. Run it on a file: `nix-unit ./tests.nix`. Inside a build, nixpkgs's own wrapper sets `HOME=$TMPDIR` and passes `--eval-store "$HOME"` to it (`lib/tests/nix-unit.nix`); copy that when you run it in a derivation.
- Keep one behaviour per test attribute; `runTests` reports failures by attribute name, so the name should say what broke.
- Library changes in nixpkgs go in `lib/tests/` and run with `nix-build lib/tests/release.nix`; module-system changes use `lib/tests/modules.sh`.

## Reproducibility and no-op checks

- `nix build --rebuild .#foo` (or `nix-build --check -A foo`) rebuilds a package that's already in the store and compares the result with it. A differing result fails; `nix-build` reports exit status 104 for "not deterministic". Add `-K` to keep the failed build directory. Run it when you touch anything that embeds timestamps, paths, or random data.
- Build with the sandbox on. It's the default on Linux; elsewhere set `sandbox = true` in `nix.conf` before you build, because Hydra builds sandboxed (`CONTRIBUTING.md`).
- A source-hash or fixed-output change should fail on the old hash and pass on the new one. Build once with the placeholder hash to read the real value, then rebuild to confirm.
- A test that passes once and fails once is a finding, not noise. Report it with both logs.

A refactor that claims to change nothing has to produce the same derivation. Compare the `drvPath` before and after:

```bash
nix eval --raw .#foo.drvPath > before
# make the change
nix eval --raw .#foo.drvPath > after
diff before after && echo same derivation
```

Equal paths mean no rebuild for anyone. If they differ, `nix-diff` (or `testers.testEqualDerivation`) shows why. This is the quickest proof that a formatting, ordering, or `finalAttrs` conversion didn't alter the build.

## What reviewers expect as evidence

The nixpkgs PR template asks for:

- a change that follows `CONTRIBUTING.md`, `pkgs/README.md`, and the automation policy;
- the platforms you built on (`x86_64-linux`, `aarch64-linux`, `aarch64-darwin`), ticking only the ones you ran;
- basic functionality of the binaries in `result/bin`;
- a `nixpkgs-review` run;
- `passthru.tests`, NixOS tests, and `lib/tests` or `pkgs/test` results, as applicable;
- release-note entries for major package changes and new or changed modules.

How to produce each:

- `nixpkgs-review pr NUMBER` reviews a PR, `nixpkgs-review wip` your uncommitted changes, `nixpkgs-review rev HEAD` your last commit. Add `--systems "x86_64-linux aarch64-linux"` (or `all`) to choose platforms; `--system` is deprecated. `--tests` also builds `passthru.tests`, and `--post-result` comments the summary on the PR.
- Test on the platforms your meta claims. If you can't build a platform, say so; CI covers the rest, and the contributing guide says testing every platform isn't required.
- Paste the check results and the command you ran, not an assertion that it "works". Name any test you disabled and why, and say whether the failure also occurs on the base branch.
- A test that was already failing, a flaky build, or a resource-limited builder is a different statement from a regression; label it as such and show the evidence.

Counts from the review corpus: running `nixpkgs-review` and validating the build on several architectures are the most-repeated testing requests by a wide margin, and "include check phases or `pythonImportsCheck`/`doInstallCheck`" has the most formal changes-requested reviews among the top testing rules (523 PRs, 88 with one).

## Checkable rules

- A package with upstream tests has `doCheck` on (explicitly, or by its language builder's default), and any `doCheck = false;` has a comment giving the reason.
- Disabled tests are listed by name (`disabledTests`, `--skip=`, `-skip=`), each with a comment.
- A package with an installed main program has `versionCheckHook` in `nativeInstallCheckInputs` with `doInstallCheck = true;`, or a `testVersion` entry in `passthru.tests`.
- A Python library sets `pythonImportsCheck`.
- `pytestCheckHook` and `versionCheckHook` sit in `nativeCheckInputs` / `nativeInstallCheckInputs`, never in `checkInputs`, `buildInputs`, or `nativeBuildInputs`.
- `passthru.tests` entries refer to `finalAttrs.finalPackage`, and `meta.mainProgram` is set when a version-check hook is used.
- Every overridden phase calls `runHook` for its pre and post hooks.
- A module has a `nixos/tests` entry; a package that backs a module links it as `nixosTests.<name>`.
- A flake's `checks.<system>.<name>` values are derivations.
- No `skipLint` or `skipTypeCheck` is committed in a test.

### Grep-able

- `TS01` (warn) `doCheck\s*=\s*false` with no `#` comment on the same or previous line: say why tests are off.
- `TS02` (warn, file-level) file contains `buildPythonPackage` and not `pythonImportsCheck`.
- `TS03` (error) `(?s)\bcheckInputs\s*=\s*\[[^\]]*(pytestCheckHook|unittestCheckHook|versionCheckHook)`: move to `nativeCheckInputs` (`nativeInstallCheckInputs` for `versionCheckHook`).
- `TS04` (error) `(?s)\bnativeBuildInputs\s*=\s*\[[^\]]*versionCheckHook`: use `nativeInstallCheckInputs` with `doInstallCheck = true;`.
- `TS05` (warn, file-level) file contains `versionCheckHook` and not `doInstallCheck` (Python builders enable it by default; ignore those).
- `TS06` (warn) `\bpytestFlagsArray\b`: obsolete; use `pytestFlags`.
- `TS07` (warn) `\bnixosTest\s*\{|\btesters\.nixosTest\b`: use `nixosTests.<name>` or `runNixOSTest`.
- `TS08` (error) `\b(skipLint|skipTypeCheck)\s*=\s*true`: debugging only.
- `TS09` (warn) `installCheckPhase\s*=\s*''[^']*--version`: a hand-written version check; use `versionCheckHook`.
- `TS10` (warn) `\bplatformDontCheck\b`: not defined anywhere in nixpkgs; use `doCheck = !stdenv.hostPlatform.isX;` or disable named tests.
- `TS11` (warn) `\bchecks\b[^;]*\.(passthru\.)?tests\s*(or\s*\{\s*\})?\s*;`: flake checks must be derivations, not an attribute set.

## Evidence

From `find-rules.py`; support is PRs behind the rule, cr is PRs with a formal changes-requested review.

| Rule | Support | cr |
|---|---|---|
| Include check phases, `pythonImportsCheck`, or `doInstallCheck` | 523 | 88 |
| Disable platform-specific failing tests, don't delete the suite | 339 | 43 |
| `pythonImportsCheck` in Python packages | 143 | 31 |
| Use `doCheck` / `doInstallCheck` to control tests | 98 | 22 |
| `passthru.tests` for CI-run test suites | 91 | 10 |
| `versionCheckHook` with `doInstallCheck` | 51 | 16 |
| Investigate test failures before disabling | 400 | 19 |
| Run `nixpkgs-review` across architectures (expected hygiene) | 3512 | 19 |

Most of the testing corpus is "run `nixpkgs-review` and build on several platforms" at counts in the thousands, with few formal change requests; treat that as expected hygiene rather than a gate you can argue around.

## Dated advice to ignore

- `platformDontCheck` as the way to disable tests per platform: the name isn't defined in the current tree. Use named `disabledTests` or `doCheck = !stdenv.hostPlatform.isDarwin;`.
- Hand-written `installCheckPhase` that runs `--version`: `versionCheckHook` replaces it.
- `testers.nixosTest` and `nixosTest { ... }` in `passthru.tests` or in a module's `config` (seen in [code patterns](code-patterns.md) and [common mistakes](common-mistakes.md)): link `nixosTests.<name>` for in-tree tests, `runNixOSTest` elsewhere; a `passthru` attribute inside a NixOS module's `config` doesn't exist.
- `checks = { package-test = pkg.tests or { }; }` (the flake in [code patterns](code-patterns.md)): `checks` values must be derivations, so an attribute set fails `nix flake check`.
- `pytestFlagsArray`: obsolete alias for `pytestFlags`.
- `nixpkgs-review ... --system x86_64-linux`: deprecated for `--systems`.
- `nix-build -A tests.nixpkgs-vet` as the local vet command ([nix linting tools](nix-linting-tools.md)): the attribute isn't in `pkgs/test`; CI runs `ci/nixpkgs-vet.sh BASE_BRANCH`.
- `nix-flake-tests` as a lightweight unit-test runner ([vm tests](vm-tests.md)): no package by that name exists in the tree; `lib.debug.runTests` and `nix-unit` (`pkgs.nix-unit`) are the verified options.
- "Merge-rate" claims for testing rules (for example that adding `nixpkgs-review` output makes a PR merge): the counts are correlation, not cause.
