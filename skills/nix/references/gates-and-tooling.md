# Quality gates and tooling

Load this before you say any Nix work is finished. It lists the gates to run, the exact commands, what each gate catches, and what to do when a tool isn't installed. It covers three contexts and says which gates apply to each. Verified against nixpkgs master (26.11 development, Oct 2026) and Nix 2.34.

Contexts used throughout:

| Tag | Context |
|-----|---------|
| P | a project of your own, flake or non-flake |
| N | a nixpkgs checkout (package or module change headed for a PR) |
| S | a NixOS system configuration (a flake's `nixosConfigurations`, or a `configuration.nix`) |

**Contents:** [The completion rule](#the-completion-rule) · [Gate ladder](#gate-ladder) · [Formatting and diagnostics](#formatting-and-diagnostics) · [Evaluation gates](#evaluation-gates) · [Purity and sandbox gates](#purity-and-sandbox-gates) · [Build gates](#build-gates) · [Test gates](#test-gates) · [nixpkgs-specific gates](#nixpkgs-specific-gates) · [NixOS system gates (context S)](#nixos-system-gates-context-s) · [When a tool is missing](#when-a-tool-is-missing) · [Checkable rules](#checkable-rules) · [Evidence](#evidence) · [Dated advice to ignore](#dated-advice-to-ignore)

## The completion rule

Never claim done without having run the gates that apply to your context. In your final message, list which gates you ran, with the result, and which you couldn't run and why. "Couldn't run" is an acceptable answer ("no aarch64 builder available"); silence is not.

```
Gates run:   parse OK, treefmt 0 changed, nix build x86_64-linux OK, passthru.tests OK
Not run:     aarch64-darwin build (no builder), nixpkgs-review (no GitHub token)
```

A gate you skipped because it was slow is "not run", not "passed". A build that succeeded only because the result was already in a cache you didn't inspect is still a pass for that gate, but say so if you suspect the change didn't rebuild anything (`nix build` printing no `building '...'` lines).

## Gate ladder

Run top to bottom. Stop and fix at the first failure; later gates assume earlier ones pass.

| # | Gate | Command | Ctx | Passes when | On failure |
|---|------|---------|-----|-------------|------------|
| 1 | Parse | `git ls-files '*.nix' \| xargs -n1 nix-instantiate --parse >/dev/null` | P N S | exit 0, nothing on stderr | Fix syntax. nixpkgs CI (`ci/parse.nix`) also fails on any `warning` in stderr. |
| 2 | Format | P: `nix fmt` or `nixfmt --check $(git ls-files '*.nix')`. N: `nix fmt` or `nix-shell --run treefmt`. | P N S | formatter reports 0 changed / exit 0 | Run the formatter without `--check` and commit its output. Don't hand-format. |
| 3 | Diagnostics | N: included in step 2 (`nixf-diagnose`). P: `statix check .` and `deadnix --fail .` | P N S | no findings | Fix or justify each finding; `deadnix` and `statix` are advisory outside your own repo. |
| 4 | Eval | P flake: `nix flake check --no-build --all-systems`. P non-flake: `nix-instantiate --show-trace -A <attr> default.nix`. N: `nix-instantiate -A <pkg>`. S: `nix eval .#nixosConfigurations.<host>.config.system.build.toplevel.drvPath` | P N S | prints a `.drv` path, no errors | Re-run with `--show-trace`, read the innermost frame. |
| 5 | Purity | P flake: eval above already runs pure. P non-flake: `NIX_PATH= nix-instantiate ...`. N: `nix-instantiate -A <pkg> --arg config '{ allowAliases = false; }'` | P N | same result as step 4 | Replace `<nixpkgs>` lookups and `builtins.currentSystem`; stop using aliases. |
| 6 | Build, sandboxed | P flake: `nix build -L .#<pkg>`. Non-flake / N: `nix-build -A <pkg>` | P N S | exit 0, output contains the expected files | Read the log (`nix log`, or `-K` to keep the failed build dir). Add the missing input rather than disabling a phase. |
| 7 | Run the result | `./result/bin/<main-program> --version` and one real invocation | P N | the program starts and does something | Missing runtime deps; wrap or patch rather than relying on your user environment. |
| 8 | Tests | see [Test gates](#test-gates) | P N S | all derivations build | Fix the code or test; don't delete the test. |
| 9 | Closure | `nix path-info -Sh ./result` | P N | size plausible for the package | `nix why-depends` to find the unexpected dependency. |
| 10 | Meta | `nix-instantiate --eval --strict --json -A <pkg>.meta` | N | license, description, platforms, mainProgram present and sane | See [meta-and-licensing](meta-and-licensing.md). |
| 11 | by-name vet | `./ci/nixpkgs-vet.sh master` | N | exit 0 | Move or restructure files as the tool reports. |
| 12 | Dependents | `nixpkgs-review wip` | N | all rebuilt dependents build | Fix or mark broken explicitly; report which ones fail on base too. |
| 13 | Platforms | build for each platform you claim in `meta.platforms` | P N | build or documented "couldn't run" | Narrow `meta.platforms`/`badPlatforms`, or fix. |
| 14 | System build | `nixos-rebuild build --flake .#<host>` (or `dry-build`) | S | exit 0 | Don't `switch` or `test` unless the user asked you to. |

Context cheat sheet: P runs 1-9 and 13. N runs 1-13, with 8 meaning `passthru.tests` and `nixosTests`. S runs 1-4, 8 (its `checks`), and 14.

## Formatting and diagnostics

### What nixpkgs runs

`ci/treefmt.nix` configures treefmt. The formatters that touch Nix and docs:

- `nixfmt` (the official formatter, RFC 166) for `*.nix`.
- `nixf-diagnose` for `*.nix`, run with `--auto-fix` and at `priority = -1` so `nixfmt` cleans up after it. It ignores the `sema-unused-def-*` rules (unused let bindings, lambda arguments, formals) and a few primop rules, each with a TODO to remove the ignore.
- `keep-sorted` for any file, honouring `keep-sorted start`/`end` markers.
- `editorconfig-checker` for any file.
- `markdown-code-runner`, which formats fenced `nix` blocks in `*.md` with `nixfmt`.
- `yamlfmt`, `biome` (JS/TS/CSS), `actionlint`, and `zizmor` for the non-Nix files in the tree.

`statix` and `deadnix` are **not** in `ci/treefmt.nix`, and nothing under `ci/`, `.github/`, `doc/` or `CONTRIBUTING.md` references them. They're third-party tools. Use them in your own projects; don't cite them as nixpkgs requirements. Because nixpkgs ignores the unused-binding diagnostics, unused arguments and bindings are caught by reviewers, not by CI; run `deadnix -L` on your diff yourself (`-L` skips lambda pattern names, which would otherwise flag every unused `callPackage` argument you intentionally keep).

`nixf-diagnose --auto-fix` rewrites files. After running treefmt in nixpkgs, read `git diff` to see what it changed beyond whitespace.

### Commands

```bash
# nixpkgs checkout (from the repo root); all three are documented in CONTRIBUTING.md
nix fmt
nix develop --command treefmt
nix-shell --run treefmt

# one file (treefmt accepts paths)
nix-shell --run 'treefmt pkgs/by-name/fo/foo/package.nix'

# what CI runs; builds a check derivation, fails if anything would change
nix-build ci -A fmt.check

# your own project
nix fmt                                   # needs a `formatter.<system>` output
nixfmt --check $(git ls-files '*.nix')    # no flake formatter defined
statix check .
deadnix --fail .
```

`nix fmt` runs the flake's `formatter.<system>` output. If your flake has none, `nix fmt` errors; add one.

### Wiring a formatter into your own flake

The least ceremony is `nixfmt-tree`, a treefmt wrapper preconfigured with `nixfmt`:

```nix
{
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  outputs =
    { nixpkgs, ... }:
    {
      formatter.x86_64-linux = nixpkgs.legacyPackages.x86_64-linux.nixfmt-tree;
    };
}
```

To add more formatters and a `checks` entry that fails when files are unformatted, use nixpkgs' own `treefmt.withConfig` (the same function `ci/default.nix` uses):

```nix
{
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  outputs =
    { self, nixpkgs }:
    let
      pkgs = nixpkgs.legacyPackages.x86_64-linux;
      treefmt = pkgs.treefmt.withConfig {
        runtimeInputs = [ pkgs.nixfmt ];
        settings.formatter.nixfmt = {
          command = "nixfmt";
          includes = [ "*.nix" ];
        };
      };
    in
    {
      formatter.x86_64-linux = treefmt;
      checks.x86_64-linux.formatting = treefmt.check self;
    };
}
```

The external `treefmt-nix` flake is the other common route (the nixpkgs manual's treefmt section names it as an alternative); follow its README for the wiring.

## Evaluation gates

| Command | What it catches |
|---------|-----------------|
| `nix-instantiate --parse FILE >/dev/null` | Syntax errors only; fast enough to run on every file. |
| `nix-instantiate --eval --strict -E 'EXPR'` | Forces the value deeply; surfaces errors hidden in lazy attributes. Use `--json` for structured output. |
| `nix-instantiate -A <attr> [file]` | Evaluates a derivation and writes its `.drv`; the cheapest "does this evaluate" check for one package. Add `--add-root` or ignore the GC-root warning. |
| `nix eval .#<attr>` / `nix eval --raw .#<attr>.name` | Same for flakes; `--apply builtins.attrNames` lists children. |
| `nix flake check --no-build` | Evaluates every output and checks its shape (`packages`, `checks`, `devShells`, `apps`, `nixosConfigurations.*.config.system.build.toplevel`, templates, `overlays`, `nixosModules`). It never builds `packages`; without `--no-build` it builds `checks` only. |
| `nix flake check --all-systems` | Evaluates outputs for every system, not just yours. Combine with `--no-build` unless you have builders for each system. |
| `--show-trace` | Add to any failing eval; the error message alone usually names the wrong frame. |
| `nix-env -qaP -f . --show-trace` | In nixpkgs, evaluates the whole attribute set. `pkgs/README.md` asks for it after removing a package or adding an alias. |

Flake gotchas that look like eval failures:

- A new file that isn't `git add`ed doesn't exist as far as flake evaluation is concerned. Stage new files before evaluating.
- `nix flake check` doesn't evaluate `legacyPackages`, so anything exposed only there isn't covered. Evaluate those attributes explicitly with `nix eval`.

### nixpkgs-wide evaluation

`ci/eval` is what the `eval` workflow runs, and you can run it locally (16 GB RAM is the recommended minimum):

```bash
nix-build ci -A eval.baseline --out-link baseline          # on the base commit
nix-build ci -A eval.full --arg baseline ./baseline        # on your commit; report in result/step-summary.md
# quick iteration: one chunk, current system only
nix-build ci -A eval.baseline --arg quickTest true
```

Use `--arg evalSystems '["x86_64-linux" "aarch64-darwin"]'` to narrow the systems. Other `ci/default.nix` entry points: `lib-tests` (library changes), `manual-nixpkgs` and `manual-nixos` (doc changes), `parse`, `nixpkgs-vet`, `shell`, `tarball`.

## Purity and sandbox gates

These catch code that works on your machine and nowhere else.

| Check | How |
|-------|-----|
| Sandbox on | Linux has it on by default (`nix config show sandbox` prints `true`). On macOS add `sandbox = true` to `/etc/nix/nix.conf` before building, as CONTRIBUTING.md asks. Hydra builds sandboxed, so a package that only builds unsandboxed fails there. |
| No network in build phases | The sandbox enforces it; only fixed-output derivations (`fetch*`) reach the network. A build that needs a download during `buildPhase` has to move that into a fetcher or vendored dependency. |
| Pure evaluation (flakes) | Flake evaluation is pure by default. Never "fix" a failure with `--impure` in a gate; fix the impurity (`builtins.getEnv`, `builtins.currentSystem`, unlocked fetches). |
| `--pure-eval` outside flakes | Not useful for a plain `default.nix`: Nix rejects the local path itself ("access to absolute path ... is forbidden in pure evaluation mode"). Use the next two rows instead. |
| No lookup paths | `NIX_PATH= nix-build ...`. Any `<nixpkgs>` reference fails with "file 'nixpkgs' was not found in the Nix search path". Use a pinned input (npins, niv, or a flake). nix.dev's best-practices guide recommends this. |
| No ambient config | Import nixpkgs with `{ config = { }; overlays = [ ]; }` so `~/.config/nixpkgs` doesn't leak in. |
| No aliases (nixpkgs) | `nix-instantiate -A <pkg> --arg config '{ allowAliases = false; }'`. CI imports nixpkgs this way "because we want to ensure they are not load-bearing". A deprecated alias that works for you can be absent in CI. |
| nixpkgs doesn't refer to itself by lookup path | `ci/nixpkgs-vet.nix` fails any `pkgs/**/*.nix` with `<nixpkgs/` outside a comment. |

## Build gates

```bash
# flakes
nix build -L .#foo                          # -L prints build logs as they run
nix build --no-link --print-out-paths .#foo # path only, no ./result symlink
nix log .#foo                               # log of the last build

# non-flake and nixpkgs
nix-build -A foo                            # ./result symlink; prints the out path
nix-build -A foo --no-out-link
nix-build -A foo -K                         # keep the failed build directory

# closure
nix path-info -Sh ./result                  # closure size, human-readable
nix path-info -rS ./result | sort -nk2      # every path in the closure with its closure size, largest last
nix why-depends .#foo .#libbar              # flake: why does foo reference libbar? (nixpkgs: nix why-depends -f . foo libbar)
nix why-depends --all .#foo .#libbar        # every path, not just the shortest
nix-store --query --requisites ./result     # every path in the runtime closure
nix-store --query --requisites $(nix-instantiate -A foo)   # build-time closure (.drv inputs)
```

What each one tells you: `path-info -S` flags a closure that ballooned (a stray `dev` output, a compiler reference, an accidentally-included toolchain). `why-depends` answers "why is this in my closure"; run it whenever the size surprises you. `--requisites` on the `.drv` shows build-time inputs, which is where a misplaced `buildInputs` entry (versus `nativeBuildInputs`) shows up. Details on reference removal are in [build-closure-and-platforms](build-closure-and-platforms.md).

Check an output's runtime references directly when something shouldn't be there: `nix-store --query --references ./result`.

## Test gates

Authoring tests is covered in [testing](testing.md). At gate level:

| What | Command | Notes |
|------|---------|-------|
| Package tests (nixpkgs) | `nix-build -A foo.tests` | Builds every `passthru.tests` entry. Documented in `pkgs/README.md`. |
| One package test | `nix-build -A foo.tests.simple-execution` | Faster while iterating. |
| NixOS test (nixpkgs) | `nix-build -A nixosTests.foo` | Boots a QEMU VM; needs `kvm` in `system-features`. Read the log with `nix-store --read-log result`. |
| Debug a NixOS test | `nix-build -A nixosTests.foo.driverInteractive && ./result/bin/nixos-test-driver` | Interactive Python shell for the VMs. |
| Flake checks | `nix flake check` | Builds `checks.<system>.*` for your system, VM tests included. |
| One flake check | `nix build -L .#checks.x86_64-linux.foo` | |
| Library changes | `nix-build ci -A lib-tests`, or from `lib/`: `nix-instantiate --eval --strict tests/misc.nix` | Empty list means all passed. |
| Test outside nixpkgs | `pkgs.testers.runNixOSTest { ... }` | Returns a derivation; put it in `checks`. |

Other `pkgs.testers` that are gate material: `testVersion` (a `passthru.tests` entry that runs the program and looks for the version string), `testBuildFailure` (assert that a build fails), `shellcheck`/`shfmt` (lint scripts as derivations), `hasPkgConfigModules`, `lycheeLinkCheck`. In-build alternatives: `versionCheckHook` in `nativeInstallCheckInputs` with `doInstallCheck = true` fails the build itself if `${version}` isn't in the `--version` output; `testers.testVersion` only fails the test derivation.

Make sure a passing test can fail: for a new test, break the thing under test once and confirm the test goes red. For VM tests, the log should show the test script's assertions executing.

NixOS tests need KVM. On macOS, a Linux builder is required (`nix.linux-builder.enable` with nix-darwin). Remote builders must advertise `kvm` in `supportedFeatures`. If none of that exists, report the VM test as not run and say what you ran instead (evaluation of `nixosTests.foo`, with `nix-instantiate -A nixosTests.foo`).

## nixpkgs-specific gates

### nixpkgs-review

`nixpkgs-review` evaluates your change against its base, builds every package whose derivation changed (including dependents), and drops you into a shell with the results. The nixpkgs docs show three entry points:

```bash
nix run nixpkgs#nixpkgs-review -- wip          # uncommitted and staged changes
nix run nixpkgs#nixpkgs-review -- rev HEAD     # the last commit
nix run nixpkgs#nixpkgs-review -- pr 12345     # an existing PR
```

Useful flags (checked against `nixpkgs-review pr --help`, version 4.0.0; `wip` shares most of them): `--systems "x86_64-linux aarch64-linux"` or `--systems all`; `-p PACKAGE` / `--package-regex RE` to build only some of the changed packages; `-P` to skip some; `--tests` to also build `passthru.tests`; `--pkgs pkgsStatic` (or `pkgsCross.aarch64-multiplatform`) to test an alternative package set; `--no-shell` to just build and report; `--run 'CMD'` to execute a command in the review shell instead of an interactive one; `--build-args` to pass through to `nix`; `--sandbox` to wrap the review shell in bubblewrap.

Pass criterion: no package fails that built on the base. A failure that also fails on base (`--checkout base`) isn't yours, but record it in the PR. Reviewers commonly ask for this run; see [Evidence](#evidence).

### nixpkgs-vet (by-name checks)

CI runs `nixpkgs-vet` against `pkgs/by-name`. It enforces the directory structure (`pkgs/by-name/<2-letter-prefix>/<name>/package.nix`), that by-name packages don't reach outside their directory, that new top-level `callPackage` packages go through by-name, and ratchet rules against the base. Locally:

```bash
./ci/nixpkgs-vet.sh master              # or release-YY.MM for backports
```

The script wraps `nix-build ci -A nixpkgs-vet --arg base ... --arg head ...` and makes temporary git worktrees of your HEAD merged with the fetched base branch, so it checks committed changes: commit first. The CI derivation also fails files that refer to `<nixpkgs/...>` and paths that differ only by case.

### Meta checks

```bash
nix-instantiate --eval --strict --json -A foo.meta     # full meta, including `available`
nix-instantiate --eval -A foo.meta.available
nix-env -f . -qaP -A foo --meta --json                 # same data via nix-env
NIXPKGS_ALLOW_UNFREE=1 nix-build -A foo                # unfree package
NIXPKGS_ALLOW_BROKEN=1 nix-build -A foo                # to try a package marked broken
NIXPKGS_ALLOW_INSECURE=1 nix-build -A foo
nix-instantiate -A foo --arg config '{ checkMeta = true; }'   # validate meta at eval time
```

`config.checkMeta` is documented as "check that the `meta` attribute of derivations are correct during evaluation time" and defaults to `false`; turn it on for a meta-only change. Review what `meta.platforms` evaluates to, since a wrong value silently removes a package from a platform's channel. The environment variables are the documented one-shot way to allow unfree, broken, insecure, or unsupported-system packages (`NIXPKGS_ALLOW_UNSUPPORTED_SYSTEM`); they're for testing your build, never a fix for a package that should be marked unfree or broken.

### Update gates

For version bumps, run the package's own update path and then the normal ladder:

```bash
nix-update foo --build --test            # nix-update; --build builds it, --test runs passthru.tests
nix-update foo --version=unstable        # track a branch; also --version=skip, --version-regex RE
nix-shell maintainers/scripts/update.nix --argstr package foo   # run the declared passthru.updateScript
```

`--argstr package foo` is how `maintainers/scripts/update.nix` selects a package (it also takes `maintainer`, `path`, `predicate`, plus `--arg commit true` to commit). When a package declares `passthru.updateScript = nix-update-script { };`, running `update.nix` for it should leave a diff that builds. If the update script produces a diff you wouldn't write by hand (changed `hash` without a `version` change, reformatted attributes), fix the script before relying on it. See [versioning-and-updates](versioning-and-updates.md).

### Rebuild count

CI computes rebuild counts per kernel (linux, darwin) from the eval diff and applies labels named `10.rebuild-linux: N-M` and `10.rebuild-darwin: N-M`, with buckets 1-10, 11-100, 101-500, 501-1000, 1001-2500, 2501-5000, and 5001+. The count is the number of packages (Hydra jobs) whose derivation changed. `CONTRIBUTING.md` gives the rule of thumb: at 500 or more, consider targeting `staging` instead of `master`; at 1000 or more it's a mass rebuild and belongs on `staging`. A change that rebuilds all NixOS tests gets `10.rebuild-nixos-tests` and goes to `staging-nixos`.

Estimating before you push:

| Method | Cost | Accuracy |
|--------|------|----------|
| Judge by position in the graph: a leaf application changes only itself; a widely used library, a setup hook, `stdenv`, or a compiler changes thousands. | none | coarse, good enough to rule out the extreme |
| `git grep -l -w libfoo -- pkgs \| wc -l` | cheap | rough: counts direct references, not transitive dependents |
| `maintainers/scripts/rebuild-amount.sh HEAD^` (add `--print` to list them) | evaluates `release.nix` for x86_64-linux and aarch64-darwin by default | counts changed Hydra jobs for a commit range; needs a git checkout |
| `nix-build ci -A eval.baseline` then `-A eval.full` | local copy of the CI eval | same numbers CI will label with |
| `nixpkgs-review wip --no-shell` | evaluates and builds | the exact set that would be rebuilt |

`nix-store --query --referrers-closure` only sees paths already in your local store, so it undercounts and isn't an estimate.

### Cross-platform verification

The PR template asks you to tick the platforms you built on. On master the supported systems (`pkgs/top-level/release-supported-systems.json`) are `x86_64-linux`, `aarch64-linux`, and `aarch64-darwin`. CONTRIBUTING.md says it's not practical to test every platform and not required for a merge, but you must be honest about which you tested.

What you can do, in decreasing strength:

- Build natively on the platform, or on a remote builder: `nix build --system aarch64-linux .#foo --builders 'ssh://builder aarch64-linux'`, or `nix-build -A foo --argstr system aarch64-linux`. NixOS can run foreign builds under QEMU with `boot.binfmt.emulatedSystems`; it's slow but a real build.
- Cross-build from your own machine, e.g. `nix-build -A pkgsCross.aarch64-multiplatform.foo`. This shows the cross build works; it says little about native behaviour or the test suite on the target.
- Evaluate for the platform without building: `nix-instantiate -A foo --argstr system aarch64-darwin` or `nix build --system aarch64-darwin --dry-run .#foo`. This catches `meta.platforms` mistakes and eval errors, not build or test failures.
- Rely on CI: say that you did, and leave `meta.platforms`/`meta.badPlatforms` as the evidence allows. CONTRIBUTING.md suggests setting `meta.broken`, `meta.badPlatforms`, or `meta.platforms` when CI shows a failure on a platform you can't reach.

State which of these you did per platform. Don't write `meta.platforms = lib.platforms.all` because evaluation passed.

### CI map (what runs on a PR)

| Workflow / entry | Local equivalent |
|------------------|------------------|
| `lint.yml` treefmt job | `nix-build ci -A fmt.check` or `nix fmt` |
| `lint.yml` parse job (several Nix and Lix versions) | `nix-build ci -A parse --keep-going` |
| `lint.yml` nixpkgs-vet job | `./ci/nixpkgs-vet.sh master` |
| `eval.yml` (rebuild labels, eval diff) | `nix-build ci -A eval.full ...` |
| `build.yml` (shell, manuals, lib tests, tarball) | `nix-build ci -A shell`, `manual-nixos`, `manual-nixpkgs`, `lib-tests`, `tarball` |

CI doesn't build your package for you in the way `nixpkgs-review` does. CONTRIBUTING.md still mentions ofborg for builds on a PR; its builds can stall (Darwin especially), and reviewers will say when to ignore that.

## NixOS system gates (context S)

```bash
nix eval .#nixosConfigurations.host.config.system.build.toplevel.drvPath   # evaluates, builds nothing
nixos-rebuild build --flake .#host        # builds the toplevel, makes ./result, activates nothing
nixos-rebuild dry-build --flake .#host    # shows what would build
nixos-rebuild build-vm --flake .#host && ./result/bin/run-*-vm   # boot it in QEMU
nix store diff-closures /run/current-system ./result              # what changed versus the running system
```

`nix flake check` also evaluates every `nixosConfigurations.<name>.config.system.build.toplevel` (no build). `nixos-rebuild test` and `switch` change the running machine; don't run them unless the user told you to. Before telling a user a configuration "works", the minimum is a successful `build` of the toplevel, not just `eval`: some failures (a missing file, a bad systemd unit, an assertion in a derivation) only appear when building.

For a NixOS module change inside nixpkgs, add `nix-build -A nixosTests.<module>` and, when you touched option docs, `nix-build ci -A manual-nixos`. `nixos/README.md` documents testing a module on a live system with `sudo nixos-rebuild test -I nixpkgs=<path to your checkout> --fast`; again, only on a machine you were told to change.

## When a tool is missing

First try to run it ad hoc; every tool below is in nixpkgs.

| Tool | Ad hoc |
|------|--------|
| `nixfmt` | `nix run nixpkgs#nixfmt -- --check FILE` |
| `treefmt` (in nixpkgs) | `nix-shell --run treefmt` from the repo root, or `nix-build ci -A fmt.pkg` and run `result/bin/treefmt PATHS` |
| `nixf-diagnose` | `nix run nixpkgs#nixf-diagnose -- FILE` (no `--auto-fix` unless you want edits) |
| `statix` | `nix run nixpkgs#statix -- check .` |
| `deadnix` | `nix run nixpkgs#deadnix -- --fail .` |
| `nixpkgs-review` | `nix run nixpkgs#nixpkgs-review -- wip` or `nix-shell -p nixpkgs-review --run "nixpkgs-review wip"` |
| `nix-update` | `nix run nixpkgs#nix-update -- foo --build --test` |
| `nixpkgs-vet` | `./ci/nixpkgs-vet.sh master` (fetches its own tool), or `nix run nixpkgs#nixpkgs-vet -- --base BASE_CHECKOUT .` |
| `nixpkgs-hammering` | `nix run nixpkgs#nixpkgs-hammering -- foo` from a checkout (community lint for package expressions; not run by CI) |

`nixpkgs` in `nix run nixpkgs#...` comes from the flake registry, which is an unlocked lookup. That's fine for a throwaway lint tool and wrong for anything that ends up in a derivation or CI file. If experimental features aren't enabled, add `--extra-experimental-features 'nix-command flakes'` to the `nix` command, or use the `nix-shell -p` form.

If a tool can't be fetched (no network, no cache), report that gate as not run. Don't substitute a weaker check and call it the same gate; say "ran `nix-instantiate --parse` instead of treefmt".

## Checkable rules

- Every changed `.nix` file passes `nix-instantiate --parse` with no stderr output.
- In nixpkgs, `nix fmt` / treefmt reports 0 changed files after your edit, and `nixf-diagnose`'s auto-fixes (if any) are in your commit.
- `nix flake check --no-build --all-systems` exits 0 for a flake project; `nix flake check` exits 0 when the project defines `checks`.
- A new file in a flake repo is tracked by git before evaluation.
- No `<nixpkgs>` or other `<...>` lookup path in code you add; `NIX_PATH= nix-build ...` still works.
- `import nixpkgs { }` in your own code passes `config` and `overlays` explicitly.
- In nixpkgs, `nix-instantiate -A foo --arg config '{ allowAliases = false; }'` succeeds.
- `nix-build -A foo.tests` (nixpkgs) or `nix flake check` (project) builds every test you added.
- New package files live at `pkgs/by-name/<xx>/<name>/package.nix` and `./ci/nixpkgs-vet.sh master` exits 0.
- The final report names each gate as run (with result) or not run (with reason).
- A platform appears in a PR description's "built on" list only if a build ran there.

## Evidence

Counts are from `find-rules.py` (support = PRs backing the rule, cr = PRs with a formal changes-requested review). Support is how often reviewers raise a rule; cr is closer to how hard they enforce it.

| Rule (paraphrased) | support | cr |
|--------------------|---------|----|
| Format Nix code with the official formatter before review | 590 | 165 |
| Include test phases/checks so the packaged software is shown to work | 523 | 88 |
| Remove unused code, bindings, and attributes | 578 | 86 |
| Test all affected packages and their dependents | 1384 | 57 |
| Verify the package builds on all supported platforms | 1980 | 56 |
| Test across the target platforms (x86_64-linux, aarch64-linux, Darwin) | 3042 | 43 |
| Enable upstream tests; if you can't, say why and set `doCheck = false` | 174 | 30 |
| Run `nixpkgs-review` across multiple architectures | 3512 | 19 |
| Use sandboxed builds to reveal missing build dependencies | 62 | 10 |

The pattern: platform and dependents verification is raised constantly but rarely blocks a merge on its own; formatting and unused-code cleanup are raised less often and get changes-requested more. Run both kinds.

## Dated advice to ignore

- "Format with `nixfmt-rfc-style`": that attribute is now a `warnAlias` for `nixfmt` (`pkgs/top-level/aliases.nix`), and `nixfmt-classic` is a `throw`. Use `nixfmt`. `nixpkgs-fmt` was the pre-RFC-166 formatter; CI doesn't run it.
- "Tick x86_64-darwin in the platforms-built list": on master the supported systems are `x86_64-linux`, `aarch64-linux`, and `aarch64-darwin`; 26.05 was the last release supporting `x86_64-darwin` and the PR template no longer lists it.
- "Run `statix`/`deadnix` because nixpkgs CI does": it doesn't. CI formats with `nixfmt`, runs `nixf-diagnose` with the unused-definition rules ignored, and leaves unused-code review to humans.
- "Check `nix-env -qa` for the whole tree before every PR": `pkgs/README.md` documents it for the package-removal procedure only. For a normal package PR, `nixpkgs-review` and the `eval` CI run cover it.
- "Wait for ofborg to build it": old PRs lean on ofborg builds. Formatting, parsing, vetting, evaluation, and rebuild labels now come from GitHub Actions workflows that call `ci/`; CONTRIBUTING.md notes ofborg builds can hang and reviewers will tell you when to disregard them.
- "`--pure-eval` is the purity gate for every project": it only works for flake evaluation. For non-flake code, use empty `NIX_PATH` plus an explicit `config`/`overlays`.

`scripts/gates.sh` runs the applicable subset: `scripts/gates.sh [--context auto|project|nixpkgs|nixos] [--paths ...]`.
