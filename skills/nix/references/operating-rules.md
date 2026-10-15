# Operating rules

Load this at the start of any Nix task. These eleven rules hold in every context (a
nixpkgs package, a NixOS module, your own flake). Each links to the reference that holds
the detail and the evidence.

**Contents:** [1 Current docs](#1-use-what-the-tree-and-docs-say-today-not-what-you-remember) · [2 Reuse](#2-reuse-before-you-write) · [3 Minimal derivations](#3-minimal-derivations) · [4 Pin and hash](#4-pin-and-hash-everything) · [5 Tests](#5-every-change-ships-with-a-test) · [6 Platforms](#6-platform-and-cross-correctness) · [7 Metadata](#7-complete-metadata) · [8 Secrets and impurity](#8-no-secrets-in-the-store-no-impurity) · [9 Workflow](#9-dont-change-a-projects-workflow-uninvited) · [10 Reporting](#10-never-claim-what-you-didnt-run) · [11 Names](#11-dont-invent-names)


## 1. Use what the tree and docs say today, not what you remember

Nix conventions moved fast (`stdenv.isDarwin`, `lib.mdDoc`, `substituteAll`, `cargoSha256`, `format = "pyproject"` are all dead or deprecated). Old PRs and blog posts still show them. When unsure, grep the nixpkgs checkout or manual; each reference ends with a `Dated advice to ignore` list.

## 2. Reuse before you write

Search nixpkgs and `lib` for an existing package, builder, hook, or helper before adding code. Don't copy a package to tweak it; use `override`/`overrideAttrs`.

```nix
# BAD: hand-rolled path and sed
postPatch = ''sed -i 's|/bin/foo|${foo}/bin/foo|' Makefile'';
# GOOD: helper that fails the build when the pattern goes stale
postPatch = ''substituteInPlace Makefile --replace-fail "/bin/foo" "${lib.getExe foo}"'';
```

## 3. Minimal derivations

Start from the smallest expression and add only what a failing build demands. Remove unused inputs, patches, and arguments. Prefer a builder or hook over a custom phase; if you write a phase, call `runHook`.

```nix
# BAD: rec, hand-built name, build tool in buildInputs
stdenv.mkDerivation rec { name = "foo-${version}"; version = "1.0"; buildInputs = [ cmake ]; }
# GOOD: finalAttrs, pname/version, tools in nativeBuildInputs, strictDeps
stdenv.mkDerivation (finalAttrs: {
  pname = "foo"; version = "1.0"; strictDeps = true; nativeBuildInputs = [ cmake ];
})
```

## 4. Pin and hash everything

Fetchers take an SRI `hash`, and a release is `tag`, not `rev = version`. No mutable URLs, no `builtins.fetch*` in nixpkgs, no network in build phases.

```nix
# BAD: legacy hash, ambiguous ref
src = fetchFromGitHub { owner = "o"; repo = "r"; rev = version; sha256 = "0abc..."; };
# GOOD
src = fetchFromGitHub { owner = "o"; repo = "r"; tag = "v${version}"; hash = "sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="; };
```

## 5. Every change ships with a test

`passthru.tests`, `versionCheckHook`, `pythonImportsCheck`, a flake `check`, or a NixOS VM test. Don't set `doCheck = false` without a comment saying why; disable named tests instead.

## 6. Platform and cross correctness

Build tools in `nativeBuildInputs`, libraries in `buildInputs`, conditions on `stdenv.hostPlatform`, and honest `meta.platforms`. In a NixOS module, where there's no `stdenv` argument, that's `pkgs.stdenv.hostPlatform`.

```nix
# BAD: deprecated attribute
lib.optionals stdenv.isDarwin [ libiconv ]
# GOOD (package file)            (NixOS module)
lib.optionals stdenv.hostPlatform.isDarwin [ libiconv ]
lib.optionals pkgs.stdenv.hostPlatform.isDarwin [ pkgs.libiconv ]
```

## 7. Complete metadata

`description` (no leading article, no trailing period), a real `lib.licenses.*` value, `maintainers`, `mainProgram`, `platforms`, and `sourceProvenance` for binary repackages. Check the `meta` evaluates with `config.checkMeta = true`.

## 8. No secrets in the store, no impurity

Secrets arrive through `*File` options and `LoadCredential`. No `<nixpkgs>` lookups, `builtins.currentSystem`, or `--impure` in code you ship. Avoid import-from-derivation.

## 9. Don't change a project's workflow uninvited

For a new project with no convention, use flakes with the layout in [flake-layout](flake-layout.md). For an existing project, keep its native commands (`cargo`, `npm`, `bundle`) working inside the dev shell and keep non-flake setups non-flake unless asked.

## 10. Never claim what you didn't run

A gate counts as run only if you executed it and saw the result; describing a command isn't running it. Report the gates you ran with their results and the ones you couldn't run. "Couldn't run" is fine; silence isn't. When asked "is this ready?", lead with what's established and what's open. Opening a PR with some platforms or checks unchecked is normal if the description says which (the PR template's boxes are information, not requirements); saying a change is tested, or builds on a platform you didn't build, is not.

## 11. Don't invent names

Don't use an option, function, attribute, or flag you haven't seen in the tree, the docs, or a reference. If you can't find it, say so and use what you can verify.
