---
name: nix
description: "Write, review, and fix Nix so it is minimal, tested, and upstreamable: flakes, dev shells, nixpkgs packages, NixOS modules and system configs, language builders, and nixpkgs PRs. Use when editing flake.nix, shell.nix, default.nix, package.nix, an overlay, or a NixOS module; packaging software with mkDerivation, buildGoModule, buildPythonPackage, or buildRustPackage; reviewing or preparing a nixpkgs PR; fixing a Nix eval or build failure; or when asked to nixify a project, add reproducible builds, or set up nix develop and direnv. Not for installing Nix or general shell questions."
version: 0.1.0
license: MIT
category: Development Workflow
compatibility: opencode
metadata:
  audience: developers
  workflow: nix
---

# Nix

Produce Nix a nixpkgs maintainer would merge: small, correct on the first build, tested,
built from existing helpers. Load one or two references per task from the map below, not
all of them. Before you report Nix work done, run `scripts/gates.sh` and the checklist in
the workflow, and say what ran and what didn't. Rules with examples:
[operating-rules](references/operating-rules.md).

## When to use

Any task that creates, changes, reviews, or debugs Nix: your own flake or dev shell, a
nixpkgs package, a NixOS module or system, or a nixpkgs PR. Existing projects keep their
native workflow; converting one to Nix is a nixify task ([nixify-workflow](references/nixify-workflow.md)).

## Gotchas (what agents get wrong by default)

Conventions here changed quickly and old PRs still show the dead forms. Check the
nixpkgs tree or manual when unsure; each reference ends with a "Dated advice" list.

- `stdenv.isDarwin` and friends: use `stdenv.hostPlatform.isDarwin` (`pkgs.stdenv.hostPlatform` in a module).
- `lib.mdDoc`, `substituteAll`, `cargoSha256`, `vendorSha256`, `nixfmt-rfc-style`, and `substituteInPlace --replace` are gone or deprecated: write plain markdown, `replaceVars`, `cargoHash`, `vendorHash`, `nixfmt`, `--replace-fail`.
- Build tools go in `nativeBuildInputs`, not `buildInputs`; use `finalAttrs`, not `rec`; `pname` plus `version`, not a hand-built `name`.
- `fetchFromGitHub` takes `tag = ...` (not `rev = version`) and an SRI `hash`, never `sha256`.
- `runNixOSTest` is `testers.runNixOSTest`, not a top-level `pkgs` attribute.
- `lib.packagesFromDirectoryRecursive` gets `callPackage` only; adding `newScope` returns a scope and breaks `nix flake check`.
- Don't invent options, functions, or flags. If you can't find it in the tree or a reference, say so.
- Describing a command is not running it, and a green build is not readiness. Report gates you ran and gates you couldn't (other platforms, `nixpkgs-review`, tests); don't call work tested or platform-verified beyond what you built.

## Workflow

```
- [ ] 1. scripts/detect.sh <dir>: what you're in (nixpkgs checkout, NixOS config, flake, plain Nix, none)
- [ ] 2. Load the reference for the task (map below); don't write from memory
- [ ] 3. Reuse: search nixpkgs and lib first; scripts/find-rules.py <keywords> for review evidence
- [ ] 4. Write the least Nix that works, plus its test
- [ ] 5. scripts/gates.sh [--context auto|project|nixpkgs|nixos] [--no-build]; fix the first failure
- [ ] 6. Walk references/upstreamable-checklist.md; run the manual gates it names
- [ ] 7. Report: gates run, gates not run, unchecked boxes with reasons
```

Defaults: new project with no convention gets flakes ([flake-layout](references/flake-layout.md));
`scripts/antipatterns.py` gives a fast scan with rule ids. State a short plan, then write the
code in the same turn: take the docs' default, and stop to ask only for a decision they can't
settle (CI's tolerance for IFD, container target, a downstream consumer contract). Paths are
relative to the skill root.

`find-rules.py` queries a catalog of review-derived rules with support, merged share,
and changes-requested counts. Treat them as hints, not law: [review-evidence](references/review-evidence.md).

## Reference map

| Task | Load |
|---|---|
| Track choice, CI, ad hoc vs dev shell vs flake | [choosing-a-track](references/choosing-a-track.md), [dev-shells-and-ergonomics](references/dev-shells-and-ergonomics.md) |
| New flake or restructure | [flake-layout](references/flake-layout.md), [flake-frameworks](references/flake-frameworks.md), [scoped-outputs](references/scoped-outputs.md) |
| Nixify a project or replace a build system | [nixify-workflow](references/nixify-workflow.md), [worked-example-gitlab-toolchain](references/worked-example-gitlab-toolchain.md), [worked-example-gkg-orbit](references/worked-example-gkg-orbit.md) |
| Containers, VM tests, IFD, cross builds | [containers](references/containers.md), [vm-tests](references/vm-tests.md), [transforms-and-ifd](references/transforms-and-ifd.md), [native-vs-cross](references/native-vs-cross.md) |
| Package any software | [derivation-authoring](references/derivation-authoring.md), [fetchers-and-sources](references/fetchers-and-sources.md), [meta-and-licensing](references/meta-and-licensing.md) |
| Python, Go, Rust | [lang-python](references/lang-python.md), [lang-go](references/lang-go.md), [lang-rust](references/lang-rust.md) |
| Node, Ruby, C/C++, other ecosystems | [lang-nodejs](references/lang-nodejs.md), [lang-ruby](references/lang-ruby.md), [lang-c-cpp](references/lang-c-cpp.md), [lang-other-ecosystems](references/lang-other-ecosystems.md) |
| Patches, overrides, version bumps, removals | [patches-and-overrides](references/patches-and-overrides.md), [versioning-and-updates](references/versioning-and-updates.md) |
| Platforms, Darwin, closure size | [build-closure-and-platforms](references/build-closure-and-platforms.md) |
| Code style and anti-patterns | [nix-language-style](references/nix-language-style.md), [code-patterns](references/code-patterns.md), [common-mistakes](references/common-mistakes.md), [nix-linting-tools](references/nix-linting-tools.md) |
| Tests | [testing](references/testing.md) |
| NixOS module | [nixos-modules](references/nixos-modules.md), [module-design](references/module-design.md), [rfc-summary](references/rfc-summary.md) |
| NixOS system config | [nixos-systems](references/nixos-systems.md) |
| Security | [security](references/security.md), [security-hardening](references/security-hardening.md) |
| nixpkgs PR, backport, final pass | [upstreaming-and-prs](references/upstreaming-and-prs.md), [upstreamable-checklist](references/upstreamable-checklist.md), [gates-and-tooling](references/gates-and-tooling.md) |
| Judging a review rule, examples | [review-evidence](references/review-evidence.md), [review-real-examples](references/review-real-examples.md) |

## Contributing Improvements

This skill is maintained in [`gitlab-org/ai/skills`](https://gitlab.com/gitlab-org/ai/skills).
If you discover that any guidance here is **inaccurate or outdated** (a command that no
longer works, a wrong flag, an incorrect API behavior), confirm with the user and open an
MR against that repository with the fix. Keep changes focused: one fix per MR.
