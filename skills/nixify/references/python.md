# Python — nixify playbook

**Default builder:** `uv2nix` (for uv projects / greenfield) or `poetry2nix`
(for existing Poetry projects).
**Lockfile transform:** both parse the lockfile (`uv.lock` / `poetry.lock`)
on the fly (IFD-ish).
**Why:** the developer keeps using `uv` / `poetry` normally; Nix consumes the
lockfile and provides reproducible envs and editable installs for live reload.

## Choosing the tool

| Project state | Use | Notes |
|---|---|---|
| Uses `uv` / greenfield | **uv2nix** (+ pyproject.nix) | By poetry2nix's author; positioned as "next generation replacing Poetry & poetry2nix". Consumes `uv.lock`. |
| Uses Poetry | **poetry2nix** | Mature; `mkPoetryApplication` / `mkPoetryEnv` / `mkPoetryEditablePackage`. |
| Uses plain pip / requirements | migrate to uv, or use `buildPythonApplication` with manual deps | Prefer migrating to a lockfile-based tool. |
| Contributing to nixpkgs | `buildPythonPackage` / `buildPythonApplication` | Manual dep lists; IFD disallowed in nixpkgs. |

`pip2nix` and `mach-nix` are effectively superseded — do not use for new work.
`dream2nix` is the general lockfile→derivation framework underneath some
integrations.

## poetry2nix

```nix
# flake input
inputs.poetry2nix.url = "github:nix-community/poetry2nix";

# package
{ poetry2nix, python312, pkgs }:
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

`mkPoetryEditablePackage` / `editablePackageSources` keep `import myapp`
pointing at the working tree so the edit-run loop is unchanged.

## uv2nix

```nix
# inputs: uv2nix, pyproject-nix, pyproject-build-systems (follow nixpkgs)
let
  workspace = uv2nix.lib.workspace.loadWorkspace { workspaceRoot = ../..; };
  overlay = workspace.mkPyprojectOverlay { sourcePreference = "wheel"; };  # or "sdist"
  pythonSet = (pkgs.callPackage pyproject-nix.build.packages { python = pkgs.python312; })
    .overrideScope (lib.composeManyExtensions [ pyproject-build-systems.overlays.default overlay ]);
in pythonSet.mkVirtualEnv "myapp-env" workspace.deps.default
```

`sourcePreference` controls the perennial wheel-vs-sdist decision; uv2nix's
override system patches native-extension packages and binary wheels.

## Binary wheels & C extensions (the hard part)

Packages with compiled extensions (numpy, pydantic-core, psycopg, pillow, …)
are where Python-on-Nix gets fiddly. Both tools ship override systems:

- Prefer wheels (`sourcePreference = "wheel"`) for speed; switch specific
  packages to sdist when a wheel's bundled native libs don't relocate under Nix.
- For sdists needing system libs, add `buildInputs` (e.g. `pkgs.postgresql` for
  psycopg) via an override.

## Dev shell

Expose the editable env plus the package manager so the native loop is intact:

```nix
mkShell { packages = [ pythonEnv pkgs.uv ]; }   # or pkgs.poetry
```

`uv sync` / `uv run` / `poetry install` / `poetry run` / `pytest` all behave
normally. Dependency changes flow through the lockfile; Nix re-reads it on the
next eval (IFD cost applies — see `references/transforms-and-ifd.md`).
