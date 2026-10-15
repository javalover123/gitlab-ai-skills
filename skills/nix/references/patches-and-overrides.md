# Patches and overrides

Load this when you're changing upstream source (patches, `substituteInPlace`, `postPatch`) or changing an existing package without rewriting it (`override`, `overrideAttrs`, overlays, `overrideScope`). It also covers where a change belongs: in your flake, or upstream in nixpkgs. Version bumps are in [versioning-and-updates](versioning-and-updates.md); fetcher arguments are in [fetchers-and-sources](fetchers-and-sources.md).

Everything here was checked against nixpkgs master (Oct 2026). Where the review-derived advice and the manual disagree, the manual wins and the section says so.

**Contents:** [Where does the change belong?](#where-does-the-change-belong) · [Patch hygiene](#patch-hygiene) · [`substituteInPlace` and friends](#substituteinplace-and-friends) · [`postPatch`, not `patchPhase`](#postpatch-not-patchphase) · [Prefer upstreaming, prefer unbundling](#prefer-upstreaming-prefer-unbundling) · [Overrides](#overrides) · [In-flake overlay or nixpkgs-wide patch?](#in-flake-overlay-or-nixpkgs-wide-patch) · [Checkable rules](#checkable-rules) · [Evidence](#evidence) · [Dated advice to ignore](#dated-advice-to-ignore)

## Where does the change belong?

| Situation | Do this |
|---|---|
| The package needs a source fix that anyone building it would want | Patch it in nixpkgs (or send it upstream first), with a comment naming the upstream status |
| You need a build option the package already exposes | `pkg.override { enableFoo = true; }` at the `callPackage` site or in an overlay |
| The package doesn't expose the option you need, and you're editing nixpkgs | Add an explicit argument to the package and use `override`; don't reach in with `overrideAttrs` |
| You need a fix or version in your own flake, and nixpkgs hasn't taken it yet | `overrideAttrs` in an overlay, with a comment giving the removal condition |
| You need a different dependency for many packages at once | Overlay with `final: prev:`, taking dependencies from `final` |
| You need a different version of a library inside one language package set | `pythonPackages.overrideScope`-style scope override, or the set's `packageOverrides` |
| The change only matters for one dev shell or one consumer | Do it at the point of use, not in a global overlay |

A package copied out of nixpkgs into your repo drifts: it misses security bumps, hardening changes, and fixes to its dependencies. Override it instead, so the diff against nixpkgs stays visible and small. The exception is a package nixpkgs doesn't have at all; write that one with [derivation-authoring](derivation-authoring.md) and keep it in your `pkgs/` directory.

## Patch hygiene

### Declaring patches

Use the `patches` list. It's applied during the patch phase, before `postPatch`.

```nix
{
  patches = [
    # Fix build with newer compilers (missing include). Upstream commit,
    # merged for 2.4.1; drop this when the version moves past it.
    (fetchpatch2 {
      name = "fix-missing-include.patch";
      url = "https://example.org/foo/commit/0123456789abcdef0123456789abcdef01234567.patch?full_index=1";
      hash = "sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=";
    })

    # Packaging-specific: look up plugins relative to $out instead of /usr.
    ./plugin-dir-from-prefix.patch
  ];
}
```

Rules that reviewers and the manual both enforce:

- Say why. A comment, a descriptive `name`, or a descriptive filename must explain the patch's intent, and ideally its upstream link, its status (merged, proposed, rejected, won't-upstream), and the condition for removing it. "Patch for gcc15 build" tells the next maintainer when to delete it; `fix.patch` doesn't.
- One patch, one fix. Keep each patch small and separate, so a single upstream release can obsolete one patch without touching the others.
- Don't bump `version` just because you added a patch. Declarative installs don't depend on it.
- Delete patches that landed upstream when you bump the version. One that no longer applies fails the build, but one that applies harmlessly lingers, so check each patch against the release notes during every bump.
- Patch the source, not the build output. A fix applied to installed files is usually the wrong layer.
- Pin remote patches to a commit. Pull requests and branches change under you, and forges garbage-collect unreachable commits.

### Fetch or vendor?

| Patch is... | Use |
|---|---|
| Already merged upstream (a commit URL on a forge) | `fetchpatch2` with the commit URL and a `hash` |
| An open pull request, a mutable branch, or a URL that could vanish after a rebase | Vendor a `.patch` file next to the package |
| A packaging fix upstream would never want (paths, Nix-specific behaviour) | Vendor a `.patch` file |
| Hard to fetch, or needs edits to apply | Vendor it |

Both fetching and vendoring show up in the review corpus with contradictory wording ("always fetch" and "always vendor"). The manual resolves it: fetch what's stable and already published, vendor what's packaging-specific or unstable.

`fetchpatch2` is the current default. The manual says to use plain `fetchpatch` only when the patch contains short commit hashes in its `index` lines (for example `index 0c97fcc35..f533e464a`); the manual links a tracking issue for that limitation. GitHub accepts `?full_index=1` on `.patch` URLs, which expands the hashes and makes `fetchpatch2` usable.

Both fetchers normalize the patch before hashing, so changing `relative`, `stripLen`, `extraPrefix`, `includes`, `excludes`, `hunks`, or `revert` has no effect unless you also change `hash`. Use `revert = true` to undo an upstream commit, and `includes`/`excludes` to drop hunks that touch files you don't have (tests, docs). You can't pass `includes` and `excludes` together.

```nix
{
  patches = [
    (fetchpatch2 {
      name = "revert-bad-change.patch";
      url = "https://example.org/foo/commit/fedcba9876543210fedcba9876543210fedcba98.patch?full_index=1";
      revert = true;
      excludes = [ "tests/*" ];
      hash = "sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=";
    })
  ];
}
```

To make a vendored patch, `git init && git add -A` in an unpacked source tree, edit, then `git diff -a > pkgs/by-name/fo/foo/0001-short-description.patch`. Name it for the intent. Mail-formatted patches (with a header, as `git format-patch` writes) use `.patch`; bare diffs commonly use `.diff`.

### Conditional and version-scoped patches

Patch unconditionally unless a platform or version genuinely differs. Reviewers commonly request an explanation for any conditional patch.

```nix
{
  patches =
    lib.optionals stdenv.hostPlatform.isDarwin [ ./darwin-dylib-name.patch ]
    ++ lib.optionals (lib.versionOlder finalAttrs.version "2.0") [ ./legacy-only.patch ];
}
```

Prefer `lib.optionals` (list) or `lib.optional` (single item) to `if ... then [ ... ] else [ ]`. Version-scoped patches are a sign you're carrying several versions; consider whether the old version should still exist (see [versioning-and-updates](versioning-and-updates.md)).

### Patch or substitute?

| Change | Tool |
|---|---|
| Replace a fixed string (a hardcoded path, a version check, a flag) | `substituteInPlace` in `postPatch` |
| Multi-line or structural code change | A `.patch` file |
| Pull in a path to another package inside a patch | `replaceVars ./foo.patch { inherit libbar; }` |
| Many unrelated one-line changes in one file | A patch, because ten `--replace-fail` lines obscure intent |

The corpus has both "use `substituteInPlace` for in-place modifications" (386 PRs) and "consolidate edits into patch files rather than many `substituteInPlace` calls" (102 PRs). They don't conflict: the first covers string swaps, the second covers sprawl.

## `substituteInPlace` and friends

In current nixpkgs, `substitute`, `substituteInPlace`, and `substituteStream` take these arguments:

| Flag | Behaviour when the pattern isn't found |
|---|---|
| `--replace-fail OLD NEW` | Build fails (use this by default) |
| `--replace-warn OLD NEW` | Prints a warning, continues |
| `--replace-quiet OLD NEW` | Does nothing, silently |
| `--subst-var NAME` | Replaces `@NAME@` with the shell variable `$NAME`; errors if the variable is unset or isn't a valid bash name |
| `--subst-var-by NAME VALUE` | Replaces `@NAME@` with `VALUE` |

The plain `--replace` flag is deprecated (since late 2023). It still works, but behaves like `--replace-warn` and prints a deprecation warning. Don't write new uses; migrate old ones to `--replace-fail`.

```nix
{
  postPatch = ''
    substituteInPlace src/config.c \
      --replace-fail "/usr/share/foo" "$out/share/foo" \
      --replace-fail "/bin/sh" "${runtimeShell}"
  '';
}
```

Why `--replace-fail`: a silent no-op after a version bump is the usual way a hardcoded path ends up unpatched. Use `--replace-quiet` only for substitutions that legitimately don't match on every platform, and say so in a comment.

Related helpers:

- `replaceVars src { name = value; ... }` (a Nix function) substitutes `@name@` in a file or patch. Every `@name@` left in the file must be listed in the attribute set; set `name = null` to leave one untouched on purpose. `replaceVarsWith` adds options such as `dir`, `isExecutable`, and `meta`.
- The shell function `substituteAll` (for a file with `@var@` markers, using environment variables) still exists in stdenv. The Nix functions `pkgs.substituteAll` and `pkgs.substituteAllFiles` were removed in 2025; use `replaceVars`.
- Hardcoded paths to other packages should be store paths from the package that provides them: `${lib.getExe foo}` or `${lib.getBin foo}/bin/foo`, not a `PATH` lookup.
- For a tool the program should find at run time, use a wrapper instead (see [build-closure-and-platforms](build-closure-and-platforms.md)).

## `postPatch`, not `patchPhase`

Don't override `patchPhase` (or `phases`). Doing so drops the `patches` list and the hooks callers add. Use `prePatch` and `postPatch`, which compose with everything else.

When you extend an existing derivation's `postPatch`, concatenate:

```nix
{
  postPatch = (previousAttrs.postPatch or "") + ''
    substituteInPlace Makefile --replace-fail "-Werror" ""
  '';
}
```

If you must override a phase like `installPhase`, start it with `runHook preInstall` and end it with `runHook postInstall`. This is a review checklist item in the manual.

### Shebangs

The fixup phase runs `patchShebangs` over installed scripts automatically. You need to call it yourself only for scripts that run during the build:

```nix
{
  postPatch = ''
    patchShebangs --build scripts/generate.sh tools/
  '';
}
```

`--build` resolves interpreters from the build-time `PATH` (so the interpreter must be in `nativeBuildInputs`); `--host` resolves from the runtime closure. Scripts need the executable bit, or they're skipped. Set `dontPatchShebangs = true` only when a script's interpreter line must stay as written.

## Prefer upstreaming, prefer unbundling

- If the problem is upstream's, file or find the issue and link it in the patch comment. Write the comment so it holds whether or not upstream replies: what the patch does, the link, and what makes it removable.
- Fix a bug in the library that causes it, not in each of its consumers.
- Prefer building against the library already in nixpkgs over a vendored copy. If upstream bundles a dependency, look for a CMake/Meson/configure switch to use the system one; if there's none, a patch that does so is usually acceptable and shrinks the closure. Reviewers commonly ask for this on bundled libraries, and rarely accept new bundled copies of widely packaged ones.
- Don't hide a build failure by disabling the failing check without a comment that says why and when it can come back.

## Overrides

### Which function?

| Function | Changes | Use for |
|---|---|---|
| `pkg.override { ... }` | Arguments of the package function (dependencies, feature flags) | Swapping a dependency, toggling a feature the package exposes |
| `pkg.overrideAttrs (finalAttrs: previousAttrs: { ... })` | Attributes passed to `stdenv.mkDerivation` | Patches, `version`/`src`, flags, phases, `meta` |
| `pythonPkg.overridePythonAttrs` | Arguments of `buildPythonPackage` / `buildPythonApplication` | `dependencies`, `build-system`, `optional-dependencies`, `pyproject`, `format`, `disabled` |
| `goPkg.overrideModAttrs` | The vendoring derivation behind `buildGoModule` | Hooks or `vendorHash`-affecting changes of the module fetch |
| overlay (`final: prev: { ... }`) | The package set | Applying one of the above everywhere a package is consumed |
| `scope.overrideScope (final: prev: { ... })` | One scoped package set (Python, Haskell, Lua, ...) | Changing a package for everything else in that set |
| `overrideDerivation` | The raw derivation, after evaluation | Almost never; it breaks `mkDerivation` processing |

`override` and `overrideAttrs` are different layers. `override` re-calls the package function with new arguments (`pkg.override { libbar = libbar_2; }`). `overrideAttrs` changes what goes into `mkDerivation`. A dependency passed via `override` is wired into `buildInputs` by the package itself; changing `buildInputs` with `overrideAttrs` replaces the list and can drop other inputs unless you append.

```nix
{
  # Different dependency: override
  fooWithBar2 = foo.override { libbar = libbar_2; };

  # Add a patch and keep the existing ones: overrideAttrs, append
  fooPatched = foo.overrideAttrs (
    finalAttrs: previousAttrs: {
      patches = (previousAttrs.patches or [ ]) ++ [ ./fix-startup.patch ];
    }
  );

  # Python: overridePythonAttrs for dependencies
  pyFoo = pythonPackages.foo.overridePythonAttrs (old: {
    dependencies = old.dependencies ++ [ pythonPackages.extra ];
  });
}
```

A one-argument function passed to `overrideAttrs` receives `previousAttrs`. Name the arguments `finalAttrs` and `previousAttrs`; old code uses `self`/`super` or `old`.

### Overriding a version

Change every attribute that is derived from the version, and every hash that depends on it. With a package written using `finalAttrs`, `src` reads `finalAttrs.version`, so override `version` and the source hash together:

```nix
{
  foo_2_5 = foo.overrideAttrs (
    finalAttrs: previousAttrs: {
      version = "2.5.0";
      src = fetchFromGitHub {
        inherit (previousAttrs.src) owner repo;
        tag = "v${finalAttrs.version}";
        hash = "sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=";
      };
      # buildGoModule: the vendored-dependency hash changes too
      vendorHash = "sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=";
      # patches written for the old version may not apply
      patches = [ ];
    }
  );
}
```

Set the new hashes to `lib.fakeHash` first, build, and copy the hash from the mismatch error. Language builders add their own derived hashes (`cargoHash`, `npmDepsHash`, `vendorHash`, pnpm and yarn offline-cache hashes); see the `lang-*` references and [versioning-and-updates](versioning-and-updates.md). `buildRustPackage` and `buildGoModule` read these through `finalAttrs`, so `overrideAttrs` on `version`, `src`, and the dependency hash works. Overriding `version` without `src` builds the old source under a new name, unless `src` reads `finalAttrs.version` (and even then the hash is stale). Current nixpkgs warns at evaluation ("was overridden with `version` but not `src`") whenever you do it. Set `__intentionallyOverridingVersion = true` in the same `overrideAttrs` call only when you mean it.

### Why `finalAttrs` matters for overridability

A package written with `rec` freezes its self-references: `rec { version = "1"; src = fetchurl { url = ".../${version}.tar.gz"; }; }` still fetches 1 after someone overrides `version`. Write `mkDerivation (finalAttrs: { ... finalAttrs.version ... })` so overrides propagate. It's also the way to refer to the final package from `passthru.tests` (`finalAttrs.finalPackage`). See [nix-language-style](nix-language-style.md) for the `rec` rules.

### In nixpkgs itself

The nixpkgs manual says not to introduce new `overrideAttrs` or `overridePythonAttrs` uses inside nixpkgs. Overrides there are easy to duplicate, invisible to the overridden package's maintainers, easy to forget, and they pull two versions of a package into one closure. Instead:

- keep every instance of a package next to each other and keep the count low;
- if you need a patch in a dependency, ask its maintainer to apply it to the main package;
- if you need a different version, first try making your package work with the version nixpkgs has; failing that, factor the package so one expression builds several versions;
- if you need to toggle optional functionality, add an explicit argument to the dependency and use `override`.

When a package needs a specific version of a dependency, take that version as the function argument (`{ libbar_2, ... }`) rather than overriding `libbar` in `all-packages.nix`. The requirement stays visible in the package's own interface, and a downstream override of the argument fails loudly if the requirement changes.

Corpus note: "prefer `overrideAttrs` over `overridePythonAttrs`" (20 PRs, 9 cr) conflicts with the manual in two ways. Inside nixpkgs, neither should be added. Outside nixpkgs, `overridePythonAttrs` is still the documented way to change `dependencies`, `build-system`, and similar arguments, because those reach `mkDerivation` through `passthru`; `overrideAttrs` can change them only with the `passthru = previousAttrs.passthru // { ... }` pattern.

### Overlays

```nix
final: prev: {
  foo = prev.foo.override { barSupport = true; };
  mytool = final.callPackage ./pkgs/mytool { };
}
```

- `prev` is the set before this overlay: use it for the thing you're overriding and for functions like `callPackage`. `final` is the result after all overlays: use it for every dependency, so later overlays take effect.
- Don't read `final.foo` to build `foo`; that's infinite recursion. Read `prev.foo`.
- Overriding something near the root (`stdenv`, a compiler, `openssl`, `zlib`) rebuilds everything downstream and misses the binary cache. Prefer overriding leaves, or scope the change to one package set.
- `pkgs.extend` and `pkgs.appendOverlays` recompute the package fixpoint, which is expensive; pass `overlays` to `import nixpkgs { ... }` once instead. The manual says not to use either approach inside nixpkgs.
- Set a flake's overlay in `overlays.default` (see [scoped-outputs](scoped-outputs.md) and [flake-layout](flake-layout.md)), and apply it when you instantiate `pkgs` for your outputs.
- Keep overlay functions small and named by purpose; one overlay per concern composes better than one large `final: prev:` that nobody can partly remove.

### Scoped sets and `overrideScope`

Package sets built with `lib.makeScope` (Python, Haskell, Lua, ...) expose `overrideScope (final: prev: { ... })`. It re-evaluates the whole set with your change, so every package in the set sees the new version:

```nix
{
  pythonPackages = python3Packages.overrideScope (
    final: prev: {
      blas = final.toPythonModule (prev.blas.override { blasProvider = final.mkl; });
    }
  );
}
```

Use it instead of overriding a single member when other members depend on it. A single `scipy.override { blas = ...; }` leaves `numpy` on the old BLAS and breaks.

### Build options through `callPackage`

When you call a package from your own tree, pass overrides at the call site:

```nix
{
  mytool = callPackage ./mytool.nix {
    libbar = libbar.override { withNetwork = false; };
  };
}
```

Not every combination of options is tested. The manual says maintainers aren't expected to fix arbitrary option combinations; if an override breaks, send a fix with a regression test, or take over maintenance.

## In-flake overlay or nixpkgs-wide patch?

| Question | If yes |
|---|---|
| Would every user of this package benefit? | Send the patch to nixpkgs. Carry an `overrideAttrs` overlay in your flake meanwhile, with the PR link in a comment |
| Does the fix depend on your flake's inputs or configuration? | Keep it in your flake's overlay |
| Is it a security fix nixpkgs hasn't shipped? | Overlay now, upstream the same change, remove the overlay once your `nixpkgs` input contains it |
| Does your overlay patch a package that rebuilds thousands of others? | Reconsider; cache misses cost more than the patch saves |
| Will you update `nixpkgs` regularly? | Put a removal condition in the overlay and check it when you run `nix flake update` |

Every flake-local override needs three things in its comment: what it fixes, why nixpkgs doesn't have it yet, and what makes it removable ("drop when nixpkgs includes #NNNN" or "drop once foo >= 2.5"). Without those, it stays forever.

## Checkable rules

- Every entry in `patches` has an adjacent comment, a descriptive `name`, or a descriptive filename that states intent.
- Remote patches use `fetchpatch2` (or `fetchpatch` where the patch has short index hashes) with a `hash`, and the URL points at a commit, not a PR or branch.
- Local patches live beside the package and end in `.patch` (mail-formatted) or `.diff`.
- No `patchPhase =` or `phases =` override; `prePatch`/`postPatch` only.
- Any overridden phase starts with `runHook pre<Phase>` and ends with `runHook post<Phase>`.
- `substituteInPlace` calls use `--replace-fail` (or `--replace-warn`/`--replace-quiet` with a reason); no bare `--replace`.
- No `pkgs.substituteAll`; use `replaceVars`.
- Platform-specific patches or substitutions are gated with `lib.optionals`/`lib.optionalString` and `stdenv.hostPlatform`.
- `overrideAttrs` extensions to `patches`, `postPatch`, `buildInputs` append to `previousAttrs` instead of replacing them.
- No new `overrideAttrs`/`overridePythonAttrs` inside nixpkgs.
- Overlays use `final` for dependencies and `prev` for the overridden package.

## Evidence

From `find-rules.py --category patches-and-overrides` (support = PRs, cr = PRs with changes requested):

| Rule | support | cr |
|---|---|---|
| `postPatch` with `substituteInPlace` for in-place edits | 386 | 94 |
| Document patches: upstream link, purpose, status | 455 | 65 |
| Prefer root-cause and upstream fixes to local workarounds | 283 | 41 |
| Gate platform patches with `lib.optionals` | 157 | 36 |
| Prefer fetching merged upstream patches with a hash, and `revert = true` for reversions | 189 | 31 |
| Keep patches minimal; remove once upstream has them | 197 | 26 |
| Patch hardcoded paths to store paths | 132 | 26 |
| `postPatch`, not `patchPhase` | 76 | 20 |
| Use `patchShebangs` | 67 | 18 |
| `--replace-fail` over `--replace` | 22 | 3 |

## Dated advice to ignore

- `substituteAll` / `substituteAllFiles` as Nix functions: removed in 2025 (the aliases now throw). Use `replaceVars` or `replaceVarsWith`.
- Plain `substituteInPlace --replace`: deprecated since 2023, warns. Use `--replace-fail`.
- "Always use `fetchpatch`": `fetchpatch2` is the current default, with `fetchpatch` only for short-hash patches.
- "Prefer `overrideAttrs` over `overridePythonAttrs`" and "prefer `overrideAttrs` to `override`": the layers differ, and nixpkgs itself asks you not to add either.
- "Vendor all patches" and "never vendor patches": both appear in the corpus; the manual's rule is fetch stable merged commits, vendor the rest.
- `with` or `rec`-based overlay and package examples in old PRs: use `final: prev:` and `finalAttrs`.
