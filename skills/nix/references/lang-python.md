# Python

Load this when you package, build, or set up a dev shell for Python code. The first half covers your own
project (flake, lockfile tooling); the second half covers contributing to nixpkgs, where different rules apply.

**Contents:** [Choosing the approach](#choosing-the-approach) · [In your own flake or project](#in-your-own-flake-or-project) · [In nixpkgs](#in-nixpkgs) · [Checkable rules](#checkable-rules) · [Evidence](#evidence) · [Dated advice to ignore](#dated-advice-to-ignore)

## Choosing the approach

| You're doing | Use | Builder / entry point |
|---|---|---|
| Your own app, uv project (or greenfield) | flake with uv2nix | `workspace.mkPyprojectOverlay` + `pythonSet.mkVirtualEnv` |
| Your own app, existing Poetry project | flake with poetry2nix (unmaintained upstream, see below) | `mkPoetryApplication` |
| Your own small app, every dependency already in nixpkgs | flake, plain nixpkgs builder | `python3Packages.buildPythonApplication` with `pyproject = true` |
| A Python library for nixpkgs | `pkgs/development/python-modules/<name>/default.nix` + entry in `python-packages.nix` | `buildPythonPackage` |
| A Python application for nixpkgs | `pkgs/by-name/<xx>/<name>/package.nix` | `python3Packages.buildPythonApplication` |
| Both library and CLI for nixpkgs | library as above; by-name wrapper | `python3Packages.toPythonApplication python3Packages.<name>` |
| A dev shell | `mkShell` with an interpreter env plus the package manager | `python3.withPackages`, or the uv2nix editable env |

## In your own flake or project

**Default builder:** `uv2nix` (uv projects, greenfield) or `poetry2nix` (existing Poetry projects).
**Lockfile transform:** both read the lockfile (`uv.lock` / `poetry.lock`) at eval time. uv2nix describes itself
as pure Nix code; large lockfiles still cost eval time (see [transforms and IFD](transforms-and-ifd.md)).
**Why:** the developer keeps using `uv` or `poetry` normally; Nix consumes the lockfile and provides
reproducible environments and editable installs for live reload.

### Choosing the tool

| Project state | Use | Notes |
|---|---|---|
| Uses `uv` / greenfield | **uv2nix** (+ pyproject.nix) | By poetry2nix's author, built on pyproject.nix. Consumes `uv.lock`. |
| Uses Poetry | **poetry2nix** | Its README lists it as unmaintained and recommends uv2nix for new projects. API: `mkPoetryApplication` / `mkPoetryEnv` / `mkPoetryEditablePackage`. |
| Plain pip / requirements | migrate to uv, or use `buildPythonApplication` with a manual dependency list | Prefer a lockfile-based tool. |
| Contributing to nixpkgs | see [In nixpkgs](#in-nixpkgs) | Manual dependency lists; IFD isn't allowed there. |

`pip2nix` and `mach-nix` are superseded; don't use them for new work. `dream2nix` is the general
lockfile-to-derivation framework underneath some integrations.

### poetry2nix

```nix
# flake.nix
{ inputs.poetry2nix.url = "github:nix-community/poetry2nix"; }
```

```nix
# package
{ pkgs, poetry2nix, python312 }:
(poetry2nix.lib.mkPoetry2Nix { inherit pkgs; }).mkPoetryApplication {
  projectDir = ../..;
  python = python312;
  # overrides for wheels / native libs go here
}
```

Dev shell with live reload:

```nix
mkPoetryEnv { projectDir = ../..; editablePackageSources = { myapp = ../../src; }; }
```

`mkPoetryEditablePackage` / `editablePackageSources` keep `import myapp` pointing at the working tree, so the
edit-run loop stays the same.

### uv2nix

```nix
# inputs: uv2nix, pyproject-nix, pyproject-build-systems (all follow nixpkgs)
let
  workspace = uv2nix.lib.workspace.loadWorkspace { workspaceRoot = ../..; };
  overlay = workspace.mkPyprojectOverlay { sourcePreference = "wheel"; }; # or "sdist"
  pythonSet =
    (pkgs.callPackage pyproject-nix.build.packages { python = pkgs.python312; }).overrideScope
      (lib.composeManyExtensions [ pyproject-build-systems.overlays.wheel overlay ]);
in
pythonSet.mkVirtualEnv "myapp-env" workspace.deps.default
```

`sourcePreference` controls the perennial wheel-versus-sdist decision. `pyproject-build-systems.overlays.wheel`
supplies build backends as wheels (there's an sdist variant too). uv2nix's override system patches
native-extension packages and binary wheels.

### Binary wheels and C extensions

Packages with compiled extensions (numpy, pydantic-core, psycopg, pillow) are where Python on Nix gets fiddly.
Both tools ship override systems:

- Prefer wheels (`sourcePreference = "wheel"`) for speed; switch specific packages to sdist when a wheel's
  bundled native libraries don't relocate under Nix.
- For sdists that need system libraries, add `buildInputs` (for example `pkgs.postgresql` for psycopg) via an
  override.

### Plain nixpkgs builder in your flake

When every dependency already exists in nixpkgs, skip the lockfile tools. Same attribute set as the nixpkgs
section below, with a local source:

```nix
{ python3Packages }:
python3Packages.buildPythonApplication (finalAttrs: {
  pname = "myapp";
  version = "0.1.0";
  pyproject = true;
  src = ../..;

  build-system = [ python3Packages.hatchling ];
  dependencies = [ python3Packages.click ];

  nativeCheckInputs = [ python3Packages.pytestCheckHook ];
  pythonImportsCheck = [ "myapp" ];

  meta.mainProgram = "myapp";
})
```

### Dev shell

Expose the editable env plus the package manager so the native loop stays intact:

```nix
mkShell { packages = [ pythonEnv pkgs.uv ]; }   # or pkgs.poetry
```

For uv2nix, the upstream template adds `env.UV_NO_SYNC = "1"`, `env.UV_PYTHON = pythonSet.python.interpreter`,
`env.UV_PYTHON_DOWNLOADS = "never"`, and a `shellHook` that unsets `PYTHONPATH` and exports `REPO_ROOT`,
paired with `workspace.mkEditablePyprojectOverlay { root = "$REPO_ROOT"; }`.

`uv sync` / `uv run` / `poetry install` / `poetry run` / `pytest` all behave normally. Dependency changes flow
through the lockfile; Nix re-reads it on the next eval ([transforms and IFD](transforms-and-ifd.md)).
For an interpreter with a few packages and no project, `python3.withPackages (ps: [ ps.requests ])` is enough.
Without uv2nix, `python3Packages.mkPythonEditablePackage` builds an editable pointer to a mutable path outside the store for dev shells.

## In nixpkgs

Verified against `doc/languages-frameworks/python.section.md`, `mk-python-derivation.nix`, and the by-name tree.
Where the manual and review-derived advice disagree, this section follows the manual.

### Where files go

| Kind | Path | Registered in |
|---|---|---|
| Library (import it) | `pkgs/development/python-modules/<pname>/default.nix` | `pkgs/top-level/python-packages.nix`: `name = callPackage ../development/python-modules/name { };`, sorted alphabetically |
| Application (run it) | `pkgs/by-name/<first two letters>/<pname>/package.nix` | picked up automatically |
| Library and application | library as above; by-name file is `{ python3Packages }: python3Packages.toPythonApplication python3Packages.name` | both |

- Attribute names and `pname` match the PyPI name, normalized (lowercase, runs of `.`, `_`, `-` become one `-`).
- Commit titles name the package set: `python3Packages.foo: 1.0 -> 1.1`, not `foo: 1.0 -> 1.1`. The prefix also
  triggers the right CI builds.
- An application needs no Python-version suffix and doesn't go in `python3Packages`.
- A by-name file can't use `python3Packages.callPackage` as its entry point; packages defined that way stay in
  `all-packages.nix`. If you need Python deps as plain arguments, write
  `{ python3 }: python3.pkgs.callPackage ./default.nix { }` in `package.nix` and keep the real expression beside it.

### Library template

```nix
{
  lib,
  buildPythonPackage,
  fetchFromGitHub,

  # build-system
  setuptools,

  # dependencies
  attrs,
  typing-extensions,

  # tests
  pytestCheckHook,
  pytest-cov-stub,
}:

buildPythonPackage (finalAttrs: {
  pname = "example";
  version = "1.2.3";
  pyproject = true;

  src = fetchFromGitHub {
    owner = "example";
    repo = "example";
    tag = "v${finalAttrs.version}";
    hash = lib.fakeHash;
  };

  build-system = [ setuptools ];

  dependencies = [ attrs ];

  optional-dependencies = {
    typing = [ typing-extensions ];
  };

  nativeCheckInputs = [
    pytestCheckHook
    pytest-cov-stub
  ]
  ++ finalAttrs.passthru.optional-dependencies.typing;

  pythonImportsCheck = [ "example" ];

  disabledTests = [
    # needs network access
    "test_download"
  ];

  meta = {
    description = "Short, concrete description of what it does";
    homepage = "https://github.com/example/example";
    changelog = "https://github.com/example/example/blob/${finalAttrs.src.tag}/CHANGELOG.md";
    license = lib.licenses.mit;
    maintainers = with lib.maintainers; [ ];
  };
})
```

Replace `lib.fakeHash` after the first build reports the real one. Group arguments with the
`# build-system` / `# dependencies` / `# tests` comments as the manual's example does.

### Application template (`pkgs/by-name/ex/example-cli/package.nix`)

```nix
{
  lib,
  python3Packages,
  fetchFromGitHub,
  versionCheckHook,
}:

python3Packages.buildPythonApplication (finalAttrs: {
  pname = "example-cli";
  version = "1.2.3";
  pyproject = true;

  src = fetchFromGitHub {
    owner = "example";
    repo = "example-cli";
    tag = "v${finalAttrs.version}";
    hash = lib.fakeHash;
  };

  build-system = with python3Packages; [ hatchling ];

  dependencies = with python3Packages; [
    click
    rich
  ];

  nativeCheckInputs = [
    python3Packages.pytestCheckHook
    versionCheckHook
  ];

  pythonImportsCheck = [ "example_cli" ];

  meta = {
    description = "Short, concrete description of what it does";
    homepage = "https://github.com/example/example-cli";
    license = lib.licenses.mit;
    mainProgram = "example-cli";
    maintainers = with lib.maintainers; [ ];
  };
})
```

`doInstallCheck` already defaults to on for Python builders, and the Python `checkPhase` runs in the install-check
phase, so `versionCheckHook` goes in `nativeCheckInputs` (or `nativeInstallCheckInputs`) without extra flags.
`buildPythonPackage` also adds `passthru.updateScript = nix-update-script { }` by default.

### Attribute rules

| Instead of | Do | Why |
|---|---|---|
| `format = "setuptools"`, `format = "pyproject"`, or neither | `pyproject = true;` plus `build-system = [ ... ]` | The builder throws when neither `pyproject` nor `format` is set. `pyproject = true` also covers packages that only have `setup.py` (falls back to setuptools). |
| `nativeBuildInputs = [ setuptools wheel ]` for the build backend | `build-system = [ setuptools ];` | `build-system` is for Python build requirements (`setup_requires`, `[build-system].requires`). Keep `nativeBuildInputs` for non-Python tools (cmake, `sphinxHook`, pkg-config). |
| `propagatedBuildInputs = [ ... ]` | `dependencies = [ ... ];` | PEP 621 name; the builder injects them into wrappers and `PYTHONPATH`. `propagatedBuildInputs` still works (1,400+ files in the tree) but new code uses `dependencies`. |
| extras as extra function arguments | `optional-dependencies = { name = [ ... ]; };` | Arguments create package variants that collide in one environment. Only list groups the upstream metadata declares. |
| a hand-written `checkPhase` running pytest | `nativeCheckInputs = [ pytestCheckHook ];` | Hooks give structured `enabledTests`, `disabledTests`, `disabledTestPaths`, `disabledTestMarks`, `pytestFlags`. |
| `pytestFlagsArray = [ ... ]` | `pytestFlags = [ ... ];` | `pytestFlagsArray` now throws when non-empty. |
| `pytest-cov` in `nativeCheckInputs` | `pytest-cov-stub` | The tests only need to pass; coverage, formatting and type checking aren't tested. |
| `export HOME=$(mktemp -d)` in `preCheck` | `writableTmpDirAsHomeHook` in `nativeCheckInputs` | Documented fix for tests that write to `$HOME`. |
| patching `setup.py`/`pyproject.toml` to loosen pins | `pythonRelaxDeps = [ "pkg" ];` (or `= true`), `pythonRemoveDeps = [ "pkg" ];` | The builder adds `pythonRelaxDepsHook` automatically when either is set. Prefer relax over remove: remove turns build errors into runtime errors. It doesn't touch `build-system`; use `substituteInPlace` in `postPatch` for those pins. |
| `#!/usr/bin/python` or a hard-coded interpreter | `${python.interpreter}` / `${python3.interpreter}`, or entry points | Keeps cross-compilation and interpreter versions correct. |
| `propagatedBuildInputs = [ ffmpeg ]` for a runtime binary | `makeWrapperArgs = [ "--prefix" "PATH" ":" (lib.makeBinPath [ ffmpeg ]) ];` or `substituteInPlace` | Non-Python runtime deps are wrapped or patched in, not propagated, to keep `$PATH` clean. |
| `overridePythonAttrs` on another package inside nixpkgs | change that package, or add an explicit flag and use `.override` | `pkgs/README.md` asks you not to add new `overrideAttrs`/`overridePythonAttrs` uses in nixpkgs. |

`makeWrapperArgs` entries with spaces need `__structuredAttrs = true;` (the manual calls this out); reviewers
commonly ask for `__structuredAttrs = true;` on new Python packages, and about 1,200 module files set it.

### Tests

- `pytestCheckHook` is the default. Use `unittestCheckHook` (`unittestFlags`) only if pytest can't run the suite.
- Run as much as possible. Disable individual tests, not the suite, and put a comment on every entry that says
  why the failure is safe to ignore (network, sandbox, flaky, platform-specific). If you do set
  `doCheck = false;`, say why in a comment.
- Tests for compiled extensions can import from the source tree instead of the installed package. The manual's
  recipe for Cython modules is `pytestCheckHook` plus `preCheck = "cd $out";`.
- `pythonImportsCheck` should list top-level import names (they often differ from the PyPI name), and it runs
  even when `doCheck = false`. Set it on every package, including ones that run tests.
- `disabledTests` and friends can be conditional: `++ lib.optionals stdenv.hostPlatform.isDarwin [ "socket" ]`.
- Tests that write to `$HOME` need `writableTmpDirAsHomeHook`; tests that import coverage plugins need `pytest-cov-stub`.

### Python versions

- Libraries must build on every packaged interpreter; the tree currently packages 3.11 through 3.16 and
  `python3` points at one of them (check `python3 =` in `all-packages.nix`; the manual's prose lags behind).
- To exclude an interpreter, write `disabled = pythonAtLeast "3.14";` with a comment (or set
  `meta.problems.unsupportedPython` for a custom message and URLs). Don't read `finalAttrs.disabled` or
  `<pkg>.disabled`; the manual says that's deprecated in favour of `<pkg> ? meta.problems.unsupportedPython`.
- Gate conditional dependencies with `pythonOlder "3.13"` / `pythonAtLeast`, not string comparison of
  `python.version`. Checks for versions below 3.11 are dead code now; delete them.
- Don't hard-code `python312`; use the package set you were given.

### Sources

- Prefer `fetchFromGitHub` / `fetchFromGitLab` with `tag = "v${finalAttrs.version}"`. The manual says to fetch from
  the repository unless there's a clear technical reason to use PyPI (sdists often omit tests). This contradicts
  the review-derived rule "use `fetchPypi` as the standard fetcher"; follow the manual.
- Use `fetchPypi { inherit (finalAttrs) pname version; hash = "..."; }` when the repository has no tags, or the
  sdist carries generated files you can't rebuild. If `pname` differs from the PyPI name, pass `pname` to
  `fetchPypi` explicitly.
- `fetchPypi` has its own `format` argument (`"setuptools"` for sdists, `"wheel"` for wheels, with `dist`,
  `python`, `abi`, `platform`) and an `extension` argument for non-`tar.gz` sdists. Don't confuse it with the
  builder's `format`. Build from source rather than fetching binary wheels unless nothing else works.
- Use `finalAttrs` rather than `rec` so overrides of `version` propagate to `src` and `meta.changelog`.
  See [fetchers and sources](fetchers-and-sources.md) for hash and tag details.

### Interpreter and arguments

Inside `pkgs/development/python-modules/`, take each dependency as its own function argument. The aliases
`python3Packages`, `python311Packages` and similar are set to `throw` in `python-aliases.nix` for that scope.
In applications (by-name), take `python3Packages` and index into it, or use `with python3Packages;`.

Write `python3Packages.buildPythonApplication`, the form the manual uses. `python3.pkgs.buildPythonApplication`
is accepted (hundreds of by-name files use it), but reviewers commonly ask for the documented spelling.

`dependencies` can only contain unversioned attributes (`pydantic`, not `pydantic_1`), because `PYTHONPATH`
supports one version of each library.

Use `buildPythonApplication` when the package is only used for its executables and `buildPythonPackage` when
anything imports it. Bindings built with `mkDerivation` need `toPythonModule` and a `pythonPackages = self`
argument when they're added to `python-packages.nix`.

### Cross-checking a change

Build the package and its reverse dependencies, run `nixpkgs-review`, and for libraries try at least the default
interpreter plus the newest packaged one (`python3Packages.foo`, `python313Packages.foo`, ...). See
[testing](testing.md) and [versioning and updates](versioning-and-updates.md).

## Checkable rules

- A `buildPythonPackage` / `buildPythonApplication` call sets exactly one of `pyproject` or `format`; new code uses `pyproject = true`.
- New code has a `build-system` list; it doesn't put Python build backends in `nativeBuildInputs`.
- New code uses `dependencies` (not `propagatedBuildInputs`) and `optional-dependencies` for extras.
- Test tooling lives in `nativeCheckInputs`; there's no hand-written `checkPhase` that only runs pytest; `pytestFlagsArray` is absent.
- `pytestCheckHook` is used with `disabledTests` / `disabledTestPaths`, and each entry has a nearby comment.
- `pythonImportsCheck` is a non-empty list of import names.
- `src` uses a fetcher with `tag =` and `hash =` (not `sha256 =`).
- The package uses `finalAttrs` (no `rec`) and `finalAttrs.version` in `src` and `meta.changelog`.
- `disabled` conditions use `pythonAtLeast`/`pythonOlder`, carry a comment, and don't test versions older than 3.11 or `isPy3k`.
- Inside `python-modules/`, no argument is named `python3Packages`; applications take `python3Packages` or `python3`.
- Library files live under `pkgs/development/python-modules/<pname>/default.nix` and are registered alphabetically in `python-packages.nix`; applications live in `pkgs/by-name`.
- `pname` matches the PyPI name normalized per PEP 503.
- No `overridePythonAttrs` on another package in new nixpkgs code.
- `meta` has `description`, `homepage`, `license`, `maintainers`, and `mainProgram` for applications; `changelog` where upstream has one ([meta and licensing](meta-and-licensing.md)).

## Evidence

Counts from `find-rules.py --category language-ecosystems` (support = PRs, cr = formal changes-requested):

| Rule | support / cr |
|---|---|
| `pytestCheckHook` in `nativeCheckInputs`, not manual `checkPhase` | 214 / 53 |
| Libraries go under `pkgs/development/python-modules/` | 95 / 43 |
| Declare `build-system` explicitly | 76 / 31 |
| `buildPythonApplication` for CLIs, `buildPythonPackage` for libraries | 74 / 30 |
| `pythonOlder` / `pythonAtLeast` instead of version string checks | 169 / 23 |
| `python3Packages` instead of `python3.pkgs` | 31 / 12 |
| `__structuredAttrs = true` for Python packages | 43 / 13 |
| `pythonRelaxDeps` instead of patching version pins | 56 / 6 |

## Dated advice to ignore

- `format = "pyproject"` / `format = "setuptools"` (still in over a thousand files): superseded by `pyproject = true` plus `build-system`.
- "Put build backends in `nativeBuildInputs`" and "put runtime deps in `propagatedBuildInputs`": use `build-system` and `dependencies`.
- "`fetchPypi` is the standard fetcher for Python packages": the manual prefers fetching from the repository.
- `disabled = pythonOlder "3.9"`, `disabled = !isPy3k`, `isPy27`: the oldest packaged interpreter is 3.11; remove these.
- `pytestFlagsArray`: throws now; use `pytestFlags` or the `enabled*`/`disabled*` attributes.
- Adding `pythonRelaxDepsHook` to `nativeBuildInputs` by hand: the builder adds it when `pythonRelaxDeps`/`pythonRemoveDeps` is set.
- `python3.pkgs` versus `python3Packages` as a splicing fix: both spellings exist in the tree; the manual uses `python3Packages`.
- Referencing `finalAttrs.disabled` / `pkg.disabled`: deprecated in favour of `meta.problems.unsupportedPython`.
- Manual text that says `python3Packages` points at 3.13: read `python3` in `pkgs/top-level/all-packages.nix`.
- poetry2nix as the default for Poetry projects: upstream marks it unmaintained.
