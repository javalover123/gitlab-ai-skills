# Nix language style

Load this when you write or review Nix expressions: packages, modules, flakes, dev shells, overlays. It covers formatting, scoping, conditionals, strings, naming, comments, and which library helper to reach for before you hand-roll something. Package attribute ordering and `meta` live in [derivation authoring](derivation-authoring.md) and [meta and licensing](meta-and-licensing.md); module option design lives in [module design](module-design.md).

**Contents:** [What's written down and what's custom](#whats-written-down-and-whats-custom) · [Formatting](#formatting) · [Function arguments](#function-arguments) · [`finalAttrs`, not `rec`](#finalattrs-not-rec) · [`let`, `inherit`, and `with`](#let-inherit-and-with) · [Impurity and lookup paths](#impurity-and-lookup-paths) · [Local sources](#local-sources) · [Avoiding import from derivation](#avoiding-import-from-derivation) · [Conditionals](#conditionals) · [Strings](#strings) · [Naming](#naming) · [Layout and ordering](#layout-and-ordering) · [Comments](#comments) · [Reuse before you reimplement](#reuse-before-you-reimplement) · [Checkable rules](#checkable-rules) · [Evidence](#evidence) · [Dated advice to ignore](#dated-advice-to-ignore)

## What's written down and what's custom

nixpkgs has a short list of written code rules. Everything else is reviewer custom, and the contributing guide tells reviewers not to comment on unwritten style preferences. Knowing which tier a rule sits in tells you how hard to argue for it.

| Tier | Source | Rules |
|---|---|---|
| Written, enforced by CI | `ci/treefmt.nix`, `.editorconfig` | nixfmt layout, 2-space indent, final newline |
| Written, enforced by review | `CONTRIBUTING.md`, `pkgs/README.md` | kebab-case file names, `lowerCamelCase` variables, precise function arguments (no `...`), `lib.optional(s)` over `if ... else null`, no needless `"${x}"`, `version` starts with a digit, `pname` lowercase, `meta` last, no IFD, `runHook` in overridden phases |
| Documented practice | `doc/` manual | `finalAttrs` instead of `rec`, `--replace-fail`, `with lib.maintainers`, `lib.getExe`, `lib.fileset` |
| Reviewer custom | review corpus | no `with lib;`, sorted dependency lists, remove dead code, comment pins and patches |

`with lib;` is not banned by the written conventions, but reviewers ask for the change often enough (see Evidence) that you should treat it as a rule in new code.

## Formatting

nixpkgs formats every `.nix` file with `nixfmt` (the package is `pkgs.nixfmt`; `ci/treefmt.nix` runs it through treefmt). Format with:

```bash
nix fmt
nix develop --command treefmt
```

Rules that follow from that:

- Don't hand-format. If the formatter disagrees with you, the formatter wins.
- Two-space indent, LF line endings, final newline, no trailing whitespace (`.editorconfig` is checked too).
- Function arguments go one per line with trailing commas, as in the examples below.
- Put pure formatting changes in their own commit, away from the functional change. Reviewers ask for this (69 PRs) and it keeps `git blame` usable.
- CI also runs `nixf-diagnose --auto-fix` and `keep-sorted`. Honour any `# keep-sorted start` / `# keep-sorted end` markers you find; they mean the block is sorted mechanically.
- `nixfmt-rfc-style` is now a warning alias for `nixfmt`, `nixfmt-classic` has been removed, and `nixpkgs-fmt` is a different formatter that nixpkgs doesn't use. Name `nixfmt` in new devShells and CI. RFC 166 background is in [rfc summary](rfc-summary.md); tool setup is in [nix linting tools](nix-linting-tools.md).

## Function arguments

List exactly what the file uses. No `...` in a package file, and never `args: with args;`.

```nix
# GOOD
{
  stdenv,
  fetchurl,
  perl,
}:
stdenv.mkDerivation {
  pname = "example";
  version = "1.0";
  src = fetchurl {
    url = "https://example.org/example-1.0.tar.gz";
    hash = "sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=";
  };
  nativeBuildInputs = [ perl ];
}
```

```nix
# BAD: ellipsis hides typos and unused arguments
{
  stdenv,
  fetchurl,
  perl,
  ...
}:
stdenv.mkDerivation { }
```

Use the `@`-pattern only for a function that's truly generic over its arguments and has a few required ones:

```nix
{
  stdenv,
  doCoverageAnalysis ? false,
  ...
}@args:
stdenv.mkDerivation (args // { foo = if doCoverageAnalysis then "bla" else ""; })
```

- NixOS modules are the exception: `{ config, lib, pkgs, ... }:` keeps the ellipsis because the module system passes more arguments than any one module uses.
- Take `lib` as an argument and write `lib.optionals`, not `with lib;`.
- Delete arguments you don't use. CI's `nixf-diagnose` currently ignores the unused-argument and unused-binding diagnostics (`ci/treefmt.nix`), so nothing fails the build; reviewers still ask for the cleanup (578 PRs).
- Order is loose convention, not a rule: `lib` and `stdenv` first, fetchers next, then the dependencies, one per line.

## `finalAttrs`, not `rec`

`rec` binds names when the set is defined and never sees later overrides. A fixed-point function gets the final values, so `overrideAttrs` stays consistent (`doc/stdenv/stdenv.chapter.md`, `doc/build-helpers/fixed-point-arguments.chapter.md`).

```nix
# BAD: overrideAttrs { version = "2"; } leaves src pointing at 1.0
stdenv.mkDerivation rec {
  pname = "example";
  version = "1.0";
  src = fetchurl { url = "https://example.org/${pname}-${version}.tar.gz"; };
}
```

```nix
# GOOD
stdenv.mkDerivation (finalAttrs: {
  pname = "example";
  version = "1.0";
  src = fetchurl {
    url = "https://example.org/${finalAttrs.pname}-${finalAttrs.version}.tar.gz";
    hash = "sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=";
  };
  passthru.tests.run = callPackage ./test.nix { example = finalAttrs.finalPackage; };
  meta.changelog = "https://example.org/NEWS#v${finalAttrs.version}";
})
```

- `finalAttrs.finalPackage` is the built package with overrides applied. Use it in `passthru.tests`, not a bare reference to the package's own name.
- Outside derivations, avoid `rec` as well. nix.dev's best-practices page warns about `infinite recursion` when a name is shadowed. Use `let ... in`, or name the set (`let argset = { a = 1; b = argset.a + 2; }; in argset`).
- The `pkgs/README.md` still shows `buildGoModule rec {` in one example. The manual's own fixed-point chapter and the hello package use `finalAttrs`; follow those.
- The helper must accept fixed-point arguments. `stdenv.mkDerivation` and the language builders documented with `finalAttrs` examples do; check the language chapter before assuming.

## `let`, `inherit`, and `with`

- Bind a value once in `let` when you use it more than once. Don't bind something you use once.
- `inherit x;` instead of `x = x;`. `inherit (set) a b;` instead of `a = set.a; b = set.b;`.
- `inherit (finalAttrs) pname version;` is a common way to pass package fields into a helper call.
- Don't shadow names in `let`; it hides which `lib` or `pkgs` you mean.

`with` policy:

| Use | Verdict |
|---|---|
| `with import <nixpkgs> { };` or `with pkgs;` at file scope | Never. Static analysis can't resolve names, and nested `with` hides origin. |
| `buildInputs = with pkgs; [ a b ];` in package code | Avoid; list the arguments instead. |
| `meta = with lib; { ... }` | Avoid; write `lib.licenses.mit`, `lib.platforms.linux`. |
| `maintainers = with lib.maintainers; [ alice bob ];` | Accepted. The meta chapter prescribes this exact form. |
| `meta.teams = with lib.teams; [ ... ];` | Accepted, same chapter. |
| `license = with lib.licenses; [ asl20 ofl ];` | Accepted for a list of licenses. A single license is `lib.licenses.mit`. |
| `environment.systemPackages = with pkgs; [ ... ];` in a user's own NixOS config | Fine; the nixpkgs manual's configuration chapter does it. Don't copy it into nixpkgs modules. |

The accepted forms narrow `with` to a lookup table (`lib.maintainers`) where every name comes from one place. If you want no `with` at all, `builtins.attrValues { inherit (pkgs) curl jq; }` builds the same list.

## Impurity and lookup paths

- No `<nixpkgs>` or any `<...>` lookup path in code you ship. It reads `$NIX_PATH`, so two machines evaluate two different things. Pin with a flake input or `npins`; minimal throwaway examples may use it. When you do import nixpkgs, pass `config = { }; overlays = [ ];` so the evaluation doesn't read `~/.config/nixpkgs`.
- `builtins.currentSystem`, `builtins.getEnv`, `builtins.currentTime`, and reading absolute paths are impure. In flake outputs and library code they're a bug. The one accepted use is a default argument on a non-flake entry point (`{ system ? builtins.currentSystem }:` in a `default.nix`), which nix.dev's tutorials and nixpkgs' own `lib/tests/release.nix` both use.
- Quote URLs (RFC 45). `url = "https://example.org/x.tar.gz";`, never bare.
- In nixpkgs, fetch with the nixpkgs fetchers (`fetchFromGitHub`, `fetchurl`), not `builtins.fetchTarball` or `builtins.fetchGit`, which fetch at evaluation time and are impure without a hash. See [fetchers and sources](fetchers-and-sources.md).

## Local sources

`src = ./.;` copies the whole directory (including `.git`, build output, and secrets) and ties the store path to the directory name. Select files with `lib.fileset`:

```nix
{
  src = lib.fileset.toSource {
    root = ./.;
    fileset = lib.fileset.unions [
      ./Cargo.toml
      ./Cargo.lock
      ./src
    ];
  };
}
```

- `lib.fileset.fileFilter` selects by predicate (`(file: file.hasExt "c")`), `difference` removes files, and `gitTracked ./.` takes tracked files only.
- A path passed to any fileset function is coerced to the set of every file beneath it, so `./src` above includes its subdirectories.
- Inside a flake, a local directory is copied in full unless it's a Git repository (nix.dev warns about this). `lib.fileset.trace` prints what a set contains, so check it before you build.
- Older code uses `lib.sources.cleanSource` or `lib.sources.sourceByRegex`. They work; prefer `fileset` for new code. If you must use `builtins.path`, set `name` so the store path doesn't depend on the checkout directory.

## Avoiding import from derivation

IFD means evaluation has to build something before it can continue: `import "${drv}/default.nix"`, `builtins.readFile "${src}/Cargo.lock"` where `src` is a fetcher result, or `builtins.fromJSON (builtins.readFile someDerivation)`. nixpkgs forbids it (`pkgs/README.md`) because Hydra evaluates the whole package set and every IFD serialises a build into evaluation. Outside nixpkgs it's allowed but slows `nix flake check` and stalls evaluators that don't support it; the trade-offs are in [transforms and IFD](transforms-and-ifd.md).

What to do instead:

| You wanted | Use |
|---|---|
| Rust dependencies from `Cargo.lock` | `cargoHash`, or `cargoLock.lockFile = ./Cargo.lock;` with the lock file committed beside the package. A lock file read out of `src` is IFD; commit a copy, or pass `lockFileContents`. |
| Go, Node dependencies | `vendorHash`, `npmDepsHash`: a fixed-output hash of the dependency fetch |
| Generated Nix or JSON from a tool | Run the tool, commit the output, read it with `lib.importJSON ./deps.json` or `import ./deps.nix`, and wire a `passthru.updateScript` to regenerate it |
| Version or metadata read from the source tree | Write it in the expression, or have the update script rewrite it |
| Configuration file for a module | `pkgs.formats.<fmt>.generate`, which builds the file at build time and only interpolates its path |

`nixpkgs-review` disables IFD by default (`--allow ifd` turns it back on); don't rely on that flag.

## Conditionals

`CONTRIBUTING.md` prescribes `lib.optional(s)` for lists. The same idea applies to strings and attribute sets.

| Result type | Write | Not |
|---|---|---|
| list, one element | `lib.optional stdenv.hostPlatform.isDarwin libiconv` | `if isDarwin then [ libiconv ] else [ ]` |
| list, several | `lib.optionals cond [ a b ]` | `if cond then [ a b ] else null` |
| string | `lib.optionalString cond "--flag"` | `if cond then "--flag" else ""` |
| attribute set | `lib.optionalAttrs cond { NIX_LDFLAGS = "-liconv"; }` | `if cond then { ... } else { }` |
| module config | `lib.mkIf cfg.enable { ... }`, `lib.mkMerge [ ... ]` | `lib.optionalAttrs` on `config` (forces the condition early; infinite recursion when it reads `config`) |
| scalar | `if cond then a else b` | a helper |

- Use `stdenv.hostPlatform.isDarwin` and `stdenv.hostPlatform.isLinux`. The bare `stdenv.isDarwin` form is gone from nixpkgs (zero uses in the tree).
- Emit a build-system flag with the typed helper instead of formatting the string by hand: `lib.cmakeBool "FOO" cond`, `lib.cmakeFeature "BAR" "x"`, `lib.mesonBool`, `lib.mesonEnable`, `lib.mesonOption`, `lib.enableFeature`, `lib.withFeature`.
- Don't use `lib.mkIf` in package code; it only means something inside a module's `config`.
- The one sanctioned `if ... then [ ... ] else null`: fixing an important bug without triggering a mass rebuild. `CONTRIBUTING.md` asks for a follow-up PR that converts it to `lib.optional(s)`.

## Strings

Indented strings (`'' ... ''`) for every multi-line value, including phases and `postPatch`. Don't build phases by concatenating quoted strings.

```nix
{
  postPatch = ''
    substituteInPlace Makefile \
      --replace-fail "/usr/local" "$out"
  ''
  + lib.optionalString stdenv.hostPlatform.isDarwin ''
    chmod +x ./configure
  '';
}
```

Escapes inside `'' ... ''` (verified by evaluating them):

| You want in the shell text | Write |
|---|---|
| `${HOME}` | `''${HOME}` |
| `''` | `'''` |
| a tab | `''\t` |
| `$HOME`, `$out` | as is; only `${` starts interpolation |

- Interpolating a value into shell text needs quoting: `lib.escapeShellArg value` for one argument, `lib.escapeShellArgs [ ... ]` for a list. Don't wrap interpolations in your own quotes.
- Tool paths: `${lib.getExe pkg}` uses `meta.mainProgram` (and warns if it's missing); `${lib.getExe' pkg "name"}` names the binary. Write `PATH` extensions as `lib.makeBinPath [ a b ]`.
- Skip needless conversions: `tag = version;`, not `tag = "${version}";` (`CONTRIBUTING.md`).
- Text edits go through `substituteInPlace file --replace-fail old new`. Bare `--replace` prints a deprecation warning in `stdenv`; `--replace-warn` and `--replace-quiet` exist for the cases where a miss is acceptable. Template files with `@name@` markers use `replaceVars ./file { name = ...; }`; `substituteAll` has been removed.
- A custom phase must call the hooks: `runHook preInstall` first and `runHook postInstall` last, and don't override `phases` (the new-package review checklist in `pkgs/README.md` lists both).
- Put explanatory comments in Nix (`# ...`), outside the string. A `#` line inside `'' ... ''` is part of the script, so editing the comment changes the derivation hash and rebuilds the package (83 PRs; reviewers do ask).

## Naming

| Thing | Rule |
|---|---|
| Nix variables, function arguments, attribute names you define | `lowerCamelCase`. `UpperCamelCase` is out. |
| `pname` | Same as upstream, lowercase, hyphenated: `"mplayer"`, `"foo-bar"`. |
| Package attribute / `by-name` directory | Equals `pname`; don't convert hyphens to camelCase. A leading digit gets a `_` prefix (`_0ad`). |
| `version` | Starts with a digit. Unreleased commits: `"2.2-unstable-2022-03-15"`, or `"0-unstable-2022-03-15"` with no release. |
| Files and directories | lowercase with dashes: `all-packages.nix`. |
| Multiple versions of one package | `json-c_0_9`, plus a plain `json-c` alias to the default. |

## Layout and ordering

Written rules: `meta` is the last attribute, and `passthru` (and any other meta-like set) comes before it. Dependency lists are one item per line.

By convention (the hello package in `pkgs/by-name/he/hello/package.nix` follows it): `pname`, `version`, `__structuredAttrs`, `strictDeps`, `src`, `patches`, `env`, `nativeBuildInputs`, `buildInputs`, flags, phases, checks, `passthru`, `meta`. Keep each dependency list sorted alphabetically; reviewers ask for it (172 PRs) but no written rule says so, so don't reorder a list someone else left unsorted in a drive-by change.

New top-level packages must set `__structuredAttrs = true`; pass environment variables through `env = { ... };` (`doc/stdenv/stdenv.chapter.md`).

## Comments

- Explain why, not what. The reader can see `substituteInPlace`; they can't see which upstream bug forced it.
- Document every deliberate deviation. The review checklists in `pkgs/README.md` name four: a pinned version (and when to unpin), a patch or `substituteInPlace` that isn't obvious, a non-default build flag, and disabled or partial checks.
- Link the upstream issue or commit when the workaround depends on one. Patches carry either an upstream URL or the reason they weren't upstreamed.
- Delete code you replace. Commented-out blocks, unused `let` bindings, stale patches, and arguments nothing reads all count as dead code (578 PRs). Don't leave `TODO` markers or stub bodies either: finish the step, or leave it out and say so in the PR.

## Reuse before you reimplement

If you're about to write the left column, check for the right column first. Every helper below exists in the current tree.

| About to hand-write | Use |
|---|---|
| `if c then [ x ] else [ ]` | `lib.optional c x`, `lib.optionals c [ ... ]` |
| `if c then "text" else ""` | `lib.optionalString c "text"` |
| `if c then { ... } else { }` | `lib.optionalAttrs c { ... }` |
| `"${pkg}/bin/name"` | `lib.getExe pkg`, `lib.getExe' pkg "name"` |
| `concatStringsSep ":" (map (p: "${p}/bin") ps)` | `lib.makeBinPath ps`, `lib.makeLibraryPath ps`, `lib.makeSearchPath "share" ps` |
| `"-DX=${if c then "ON" else "OFF"}"` | `lib.cmakeBool "X" c`, `lib.cmakeFeature`, `lib.mesonBool`, `lib.mesonEnable`, `lib.mesonOption`, `lib.enableFeature`, `lib.withFeature` |
| Hand-quoted shell arguments | `lib.escapeShellArg`, `lib.escapeShellArgs` |
| `concatStringsSep sep (map f xs)` | `lib.concatMapStringsSep sep f xs` |
| `listToAttrs (map (n: { name = n; value = f n; }) names)` | `lib.genAttrs names f` |
| `map (n: f n attrs.${n}) (attrNames attrs)` | `lib.mapAttrsToList f attrs`, `lib.mapAttrs`, `lib.attrValues` |
| `foldl' (a: b: a // b) { } sets` | `lib.mergeAttrsList sets`; nested merge: `lib.recursiveUpdate` |
| `fromJSON (readFile ./x.json)` | `lib.importJSON ./x.json`, `lib.importTOML ./x.toml` |
| `builtins.compareVersions a b >= 0` | `lib.versionAtLeast a b`, `lib.versionOlder a b`, `lib.versions.majorMinor v` |
| Nested function application `f (g (h x))` | `lib.pipe x [ h g f ]` |
| `sed -i` in a phase | `substituteInPlace --replace-fail` |
| `@var@` template fill | `replaceVars ./file { var = ...; }` |
| A small script derived with `cp` | `writeShellApplication { name; runtimeInputs; text; }`, `writeText`, `writeTextFile` |
| Hand-rendered TOML, JSON, YAML config | `pkgs.formats.toml { }`, `.json`, `.yaml`, then `.generate` |
| Joining packages into one tree | `symlinkJoin`, `buildEnv` |
| `src = ./.` | `lib.fileset.toSource` |
| Boolean `enable` module option | `lib.mkEnableOption`; package option `lib.mkPackageOption` |
| `warn`/`throw` guarded by `if` | `lib.warnIf cond msg value`, `lib.throwIf cond msg value` |

## Checkable rules

- Every `.nix` file is formatted by `nixfmt` (2-space indent, trailing commas in argument sets).
- Package files list their arguments explicitly, with no `...`; modules keep `...`.
- No `rec` in `mkDerivation`-family calls; self-references go through `finalAttrs`.
- No `with` at file scope; no `with lib;` or `with pkgs;` anywhere in package code. `with lib.maintainers;`, `with lib.teams;`, and `with lib.licenses;` are allowed.
- No `<...>` lookup paths and no `builtins.currentSystem` outside a non-flake entry point's default argument.
- No import from derivation in nixpkgs-bound code.
- `meta` is the last attribute; `passthru` precedes it.
- `version` starts with a digit; `pname` has no uppercase letters; attribute names are `lowerCamelCase` except package names.
- Multi-line phases use indented strings, start with `runHook preX`, and end with `runHook postX`.
- Every list conditional uses `lib.optional(s)`, `lib.optionalString`, or `lib.optionalAttrs`.
- No dead code: no unused arguments, `let` bindings, or `inherit` entries.
- Each pin, non-obvious patch, non-default flag, and disabled test carries a comment saying why.

### Grep-able

Each rule is a regular expression (PCRE syntax) over a `.nix` file, with the severity to report. `error` should block; `warn` needs a human look.

- `NL01` (error) `(mkDerivation|build[A-Z]\w*|buildPythonPackage|buildPythonApplication)\s+rec\s*\{`: use `(finalAttrs: { ... })`.
- `NL02` (warn) `\bwith\s+lib\s*;`: use explicit `lib.` prefixes. `with lib.maintainers;`, `with lib.licenses;`, and `with lib.teams;` don't match.
- `NL03` (warn) `\bwith\s+pkgs\s*;`: list dependencies as arguments.
- `NL04` (warn) `<nixpkgs[^>]*>|\bNIX_PATH\b`: no lookup paths; pin the input.
- `NL05` (warn) `builtins\.(currentSystem|getEnv|currentTime)`: impure; allowed only as a default argument of a non-flake entry point.
- `NL06` (error) `\bstdenv\.(isDarwin|isLinux|isAarch64|isx86_64)\b`: use `stdenv.hostPlatform.isX`.
- `NL07` (error) `\bstdenv\.lib\b`: use `lib`.
- `NL08` (error) `\bmdDoc\b`: removed; write plain markdown.
- `NL09` (warn) `\belse\s*\[\s*\]|\belse\s+null\b`: use `lib.optional(s)` or `lib.optionalString`.
- `NL10` (warn) `\bsed\s+(-[a-zA-Z]*i|--in-place)`: use `substituteInPlace --replace-fail`.
- `NL11` (error) `--replace(?![-\w])`: deprecated; use `--replace-fail`, `--replace-warn`, or `--replace-quiet`.
- `NL12` (error) `\bsubstituteAll(Files)?\b`: removed; use `replaceVars`.
- `NL13` (warn) `=\s*"\$\{[A-Za-z_][\w.]*\}"\s*;`: unnecessary string conversion (`tag = version;`).
- `NL14` (warn, multi-line) `(?m)^\s*\.\.\.\s*\n\s*\}:`: ellipsis in a package file's arguments. Skip modules (files that mention `options` or `config`).
- `NL15` (warn) `\bsrc\s*=\s*\./\.\s*;`: use `lib.fileset.toSource`.
- `NL16` (warn) `\b(fakeHash|fakeSha256|fakeSha512)\b`: placeholder hash; replace before committing.
- `NL17` (warn) `(readFile|import|fromJSON|fromTOML|importJSON|importTOML)\s*\(?\s*"\$\{[^}]*\}`: possible IFD; confirm the path isn't a build output.
- `NL18` (warn) `\$\{[A-Za-z_][\w.]*\}/bin/[\w.-]+`: consider `lib.getExe` or `lib.getExe'`.
- `NL19` (warn) `\bnixfmt-rfc-style\b|\bnixfmt-classic\b`: use `nixfmt`.
- `NL20` (warn) `=\s*https?://[^\s";]+\s*;`: unquoted URL; quote it.
- `NL21` (warn, file-level) a `(build|install|check|configure|installCheck|patch|unpack)Phase = ''` block with no `runHook` call inside it.

NL14, NL17, NL18, and NL21 produce false positives: modules, paths that are legitimately source inputs, non-main binaries, and phases that call `runHook` through a helper. Report them as `warn` with the matched line and never auto-fix them.

## Evidence

From `find-rules.py`; support is the number of PRs behind the rule and cr is how many had a formal changes-requested review.

| Rule | Support | cr |
|---|---|---|
| Format with nixfmt | 590 | 165 |
| Remove unused code, bindings, attributes | 578 | 86 |
| Use `lib.optional` / `lib.optionals` for conditional lists | 292 | 72 |
| Use explicit `lib.` prefixes, not `with lib;` | 191 | 101 |
| `finalAttrs` instead of `rec` (two further phrasings: 154 / 78 and 126 / 69) | 178 | 76 |
| Sorted lists and declarations | 172 | 52 |
| `lib.optionalString` for conditional strings | 160 | 44 |
| Keep comments out of string literals | 83 | 26 |
| `with lib.maintainers; [ ... ]` form | 78 | 16 |
| `lib.getExe` / `lib.getExe'` over hand-built paths | 59 | 20 |
| Always call `runHook` in custom phases | 58 | 9 |
| No IFD in nixpkgs | 34 | 10 |

Counts show what reviewers ask for. They don't show that following a rule gets a PR merged.

## Dated advice to ignore

- `stdenv.isDarwin`, `stdenv.isLinux`: the tree has no remaining uses; write `stdenv.hostPlatform.isDarwin`.
- `stdenv.lib`: gone; take `lib` as an argument.
- `lib.mdDoc` and `mdDoc`: removed from `lib`; option descriptions are plain markdown now.
- `meta = with lib; { license = licenses.mit; ... }`: the current hello package writes `lib.licenses.gpl3Plus` and `with lib.maintainers;`.
- `lib.licenses.MIT`, `Apache2`, and `proprietary` (seen in some older snippets, including [code patterns](code-patterns.md) and [common mistakes](common-mistakes.md)): those attributes don't exist. Use `mit`, `asl20`, `unfree`.
- `nixfmt-rfc-style`, `nixfmt-classic`, `nixpkgs-fmt` as "the formatter": `nixfmt` is the one nixpkgs runs.
- `--replace` in `substituteInPlace`: deprecated with a runtime warning.
- `substituteAll`: removed in favour of `replaceVars`.
- `sha256 = "sha256-..."` in fetchers and other `sha256`-for-SRI habits: the manual's examples use `hash`.
- The RFC 166 layout in the "Skipping indentation levels" example of [common mistakes](common-mistakes.md) (`buildInputs =` on its own line, then `[`) predates the current formatter, which hugs the bracket (`buildInputs = [`). Run `nixfmt` instead of copying either layout.
- `pkgs/README.md` still contains `buildGoModule rec {` and a `lib.sources.sourcesByRegex` call; the library function is `sourceByRegex`. Both are upstream doc lag, not guidance.
- "Alphabetical order is required": it's reviewer custom, and the contributing guide says unwritten style points aren't to be raised in review. Offer it as a suggestion.
