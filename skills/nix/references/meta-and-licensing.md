# Package metadata and licensing

Load this when you write or review a package's `meta` attribute set: description, license, maintainers, platforms, provenance, and the rules reviewers enforce on them. Structure and phases are in [derivation-authoring](derivation-authoring.md), language builders in the `lang-*` files ([Python](lang-python.md), [Go](lang-go.md), [Rust](lang-rust.md), [Node.js](lang-nodejs.md), [Ruby](lang-ruby.md), [C/C++](lang-c-cpp.md)), source pinning in [fetchers-and-sources](fetchers-and-sources.md), the PR side in [upstreaming-and-prs](upstreaming-and-prs.md), and test metadata in [testing](testing.md).

Verified against `doc/stdenv/meta.chapter.md`, `pkgs/README.md` (Meta attributes), `maintainers/README.md`, `maintainers/maintainer-list.nix`, `lib/licenses/`, `pkgs/stdenv/generic/check-meta.nix` and `problems.nix` (Oct 2026).

**Contents:** [Placement and checking](#placement-and-checking) · [Attribute reference](#attribute-reference) · [Description](#description) · [Licenses](#licenses) · [Source provenance](#source-provenance) · [Maintainers](#maintainers) · [Platforms and brokenness](#platforms-and-brokenness) · [knownVulnerabilities](#knownvulnerabilities) · [mainProgram](#mainprogram) · [Checkable rules](#checkable-rules) · [Evidence](#evidence) · [Dated advice to ignore](#dated-advice-to-ignore)

## Placement and checking

- `meta` is the last attribute in the derivation; `passthru` and other meta-like sets come before it.
- `meta` isn't passed to the builder, so editing it never rebuilds the package.
- Nixpkgs can type-check it for you. Evaluate with `config.checkMeta = true` and typos (`licence`) and wrong types (a non-string `description`) become errors: `nix-build -A foo --arg config '{ checkMeta = true; }'` from a nixpkgs checkout. It's off by default.
- Use `lib.licenses.x` style references. `with lib.maintainers; [ name ]` stays the convention for maintainers.

```nix
{
  meta = {
    description = "Library for decoding PNG images";
    homepage = "https://example.org/libfoo";
    changelog = "https://example.org/libfoo/releases/tag/${finalAttrs.src.tag}";
    license = lib.licenses.zlib;
    maintainers = with lib.maintainers; [ someone ];
    platforms = lib.platforms.all;
  };
}
```

## Attribute reference

| Attribute | Rule |
|---|---|
| `description` | One sentence, capitalized, no leading article, doesn't start with or mention the package name, no trailing punctuation, factual |
| `longDescription` | Optional CommonMark text for details that don't fit the description |
| `homepage` | Official project URL (string, or list of strings); prefer HTTPS |
| `changelog` | Link (or list of links) to the changelog for *this* version, e.g. built from `finalAttrs.src.tag` or `finalAttrs.version`; not the default branch |
| `license` | Value from `lib.licenses`; must match upstream; see [Licenses](#licenses) |
| `sourceProvenance` | List from `lib.sourceTypes`; required when not built from source |
| `maintainers` / `teams` | Registered maintainers; required for new packages |
| `mainProgram` | Name of the primary executable, when there is one |
| `platforms` | Where the package builds; set it or Hydra won't cache it |
| `badPlatforms` | Platforms where it's known not to build |
| `broken` | `true`, or an expression, when the package can't build |
| `knownVulnerabilities` | List of strings (usually CVE IDs); makes the package insecure |
| `downloadPage`, `donationPage` | Optional upstream URLs; prefer authoritative project pages |
| `identifiers` | Optional CPE and PURL data, e.g. `identifiers.cpeParts.vendor = "gnu";` |
| `hydraPlatforms`, `timeout`, `priority`, `branch`, `mainDarwinApp` | Situational; see the manual |

`pkgs/README.md` says `license` must be set, `maintainers` must be set for new packages, and `mainProgram` must be set when a main executable exists. Its quick start calls the remaining attributes optional but recommends at least `description`, `homepage`, and `license`, and the new-package review checklist also checks `description` and `platforms`. Treat all of these as required for a new package.

## Description

```nix
# BAD: article, package name, trailing period, subjective
{ description = "A fast and amazing libpng replacement."; }
```

```nix
# GOOD
{ description = "Library for decoding PNG images"; }
```

Write what it is or does, not what it's called. Don't write "A", "An", or "The" first, don't write the package name, and don't end with a period.

## Licenses

`meta.license` must match what upstream actually ships, and it must be set.

- **Reference `lib.licenses.<attr>`.** The manual allows a single value or a list ("both are valid"), so a one-license package takes `license = lib.licenses.mit;` without brackets. A list means parts of the package carry different licenses. String forms (`"gpl3Only"`, `"GPL-3.0-only"`) are accepted but frowned upon.
- **Choose the SPDX-exact attribute.** `gpl3Only` is `GPL-3.0-only`; `gpl3Plus` is `GPL-3.0-or-later`. The legacy attributes `gpl2`, `gpl3`, `lgpl2`, `lgpl21`, and `lgpl3` carry `deprecated = true`. Pick `-Only` or `-Plus` from upstream's license headers: "either version 3 of the License, or (at your option) any later version" means `gpl3Plus`.
- **Find the attribute** by SPDX ID: `nix-instantiate --eval --strict -E '(import ./lib).getLicenseFromSpdxId "GPL-3.0-or-later" == (import ./lib).licenses.gpl3Plus'`, or grep `spdxId` in `lib/licenses/licenses.nix`. Case doesn't matter for the lookup.
- **Dual or compound licenses.** `lib/licenses` provides `OR` (user's choice), `AND` (both apply), `WITH` (license plus exception), and `PLUS` (this version or later):

```nix
{
  license = lib.licenses.OR [
    lib.licenses.mit
    lib.licenses.asl20
  ];
}
```

```nix
{ license = lib.licenses.WITH lib.licenses.gpl2Only lib.licenses.classpathException20; }
```

- **Unknown license.** Use the closest attribute only if it's the same license. Otherwise add an entry to `lib/licenses/licenses.nix`, or write an in-place attribute set with `fullName`, `url`, and `free` when no other package could use it.
- **No upstream license.** The default is `lib.licenses.unfree` (software is all-rights-reserved unless granted otherwise). Ask upstream, and don't package software with unclear redistribution rights without that clarification.

### Unfree licenses

| Attribute | Meaning |
|---|---|
| `lib.licenses.unfree` | Can't be redistributed, so it stays out of the Nixpkgs channel; you can still build it yourself |
| `lib.licenses.unfreeRedistributable` | The *output* may be redistributed. If your builder modifies the binaries (`patchelf` counts), the license isn't redistributable any more; use `unfree` |
| `lib.licenses.unfreeRedistributableFirmware` | Redistributable firmware, treated as free for channel and image purposes |
| `lib.licenses.free` | Catch-all for free licenses missing from the list; prefer a specific attribute |

- Unfree packages are blocked by default and hidden from search. Users opt in with `NIXPKGS_ALLOW_UNFREE=1`, `allowUnfreePackages`, `allowUnfreePredicate`, or `allowUnfree`. When you test one, enable it yourself.
- Pair `unfree` with `sourceProvenance` if you repackage a binary.
- Fetch with `requireFile` only when the download can't be automated.
- `config.allowlistedLicenses` applies to unfree licenses only; `blocklistedLicenses` applies to all.

## Source provenance

Set `meta.sourceProvenance` whenever any part of the output isn't built from source by a nixpkgs derivation. The values in `lib.sourceTypes` are `fromSource`, `binaryNativeCode`, `binaryBytecode`, `binaryFirmware`, and `obfuscatedCode`.

```nix
{ sourceProvenance = with lib.sourceTypes; [ binaryNativeCode ]; }
```

- Repackaging a `.deb`, `.rpm`, `.whl`, or release binary: `binaryNativeCode` (the README says "almost always").
- Downloaded `.jar` files: `binaryBytecode`. Vendor firmware blobs: `binaryFirmware`.
- Absence of the attribute means "no known non-source parts", not a guarantee. It's independent of `meta.license`.
- Users can exclude non-source packages with `NIXPKGS_ALLOW_NONSOURCE=0` (check-meta reads the variable).

## Maintainers

- `meta.maintainers = with lib.maintainers; [ handle ];` is required for new packages. `meta.teams = with lib.teams; [ team ];` is available for groups defined in `maintainers/team-list.nix`.
- If both are empty, nixpkgs generates a `maintainerless` problem. Users can turn it into a warning or error.
- Handles come from `maintainers/maintainer-list.nix`. An entry needs `name`, `github`, and `githubId` (the stable identity; check it at `https://api.github.com/user/<githubId>`). `email`, `matrix`, and `keys` are optional. Keep the file alphabetical and prefix a handle with `_` when the GitHub name begins with a digit. `handle == github` is strongly preferred.
- Validate the file with `nix-build lib/tests/maintainers.nix`.
- **Registration commit.** When you add yourself as part of another change, put the `maintainer-list.nix` edit in its own commit titled `maintainers: add <handle>`, before the commits that change packages (CONTRIBUTING and `maintainers/README.md`).
- Never invent a handle or `githubId`. If the user hasn't given you a registered maintainer, ask for the GitHub handle and ID, or leave a clear note that registration is missing. Adding someone else as a maintainer needs their consent (corpus support 16, cr 2).
- A maintainer is expected to keep the package building and updated for at least one release cycle. Security-critical, fast-moving packages (browsers and their forks) need a committer among the maintainers.

## Platforms and brokenness

- Set `meta.platforms`. Without it the package gets no Hydra binaries. The manual prefers `lib.platforms.all` plus `badPlatforms` for the exceptions; common values are `lib.platforms.linux`, `lib.platforms.unix`, `lib.platforms.darwin`, or explicit system strings (`"x86_64-linux"`) for binary repackages.
- `meta.badPlatforms` wins over `platforms`. Hydra never builds those. Example from the manual:

```nix
{
  meta.platforms = lib.platforms.all;
  meta.badPlatforms = [ lib.systems.inspect.platformPatterns.isStatic ];
}
```

- `lib.meta.availableOn platform pkg` tests availability using `platforms` and `badPlatforms`. Packages use it to enable optional features per platform. It ignores `broken`.
- `meta.broken = true` hides the package from search and blocks building unless the user allows broken packages. Its value can be an expression, so you can express conditions:

```nix
{ meta.broken = !(stdenv.buildPlatform.canExecute stdenv.hostPlatform); }
```

- Use `broken` when the package can't build and you can't fix it yet; add a comment saying why and when to remove it. The manual says unconditionally broken packages should eventually be removed unless fixed. If the failure is platform-specific, use `badPlatforms` or narrow `platforms` instead of a blanket `broken`.
- `meta.broken = true` is shorthand for `meta.problems.broken.message = "This package is broken.";`. Set the problem yourself to customize the message.

## knownVulnerabilities

```nix
{
  meta.knownVulnerabilities = [
    "CVE-2024-3094: Malicious backdoor allowing unauthorized remote code execution"
  ];
}
```

A non-empty list marks the package insecure; users must set `NIXPKGS_ALLOW_INSECURE` or `permittedInsecurePackages`. A *new* package that would need this is unlikely to be accepted (`pkgs/README.md`). Use the list for existing packages you can't update, not as a substitute for updating.

## mainProgram

- Set it to the exact executable name in `$out/bin` (or `$bin/bin`) when the package has one primary executable. A hardcoded string, never `pname`.
- Leave it out when there are no executables, or several with no clear main program.
- It drives `nix run` and `lib.getExe`; `lib.getExe` warns when it's missing and falls back to the package name.
- `versionCheckHook` runs the main program by default, so set `mainProgram` before you enable the hook.

## Checkable rules

- With `config.checkMeta = true`, the package evaluates (no unknown keys, correct types).
- `meta.description` is present, starts with an uppercase letter, has no trailing `.`, doesn't start with `A `, `An `, `The `, or the package name.
- `meta.license` is a `lib.licenses.*` value, a list of them, or a compound built with `OR`/`AND`/`WITH`/`PLUS`. (The synthesis rule "must be a list" is wrong.)
- No license attribute with `deprecated = true` (`gpl2`, `gpl3`, `lgpl2`, `lgpl21`, `lgpl3`).
- `meta.maintainers` or `meta.teams` is non-empty; every handle exists in `lib.maintainers`.
- `meta.mainProgram` is a string literal equal to a file in `bin/`, when set.
- `meta.platforms` is set; `meta.broken` has an explanatory comment.
- `meta.changelog` is a versioned URL, not a branch URL.
- Binary repackages carry `meta.sourceProvenance` without `fromSource` alone.
- `meta` is the final attribute of the derivation.
- The commit that edits `maintainers/maintainer-list.nix` contains nothing else and precedes package commits.

## Evidence

| Rule | support | cr |
|---|---|---|
| Use current license identifiers (`gpl3Plus` rather than deprecated `gpl3`) | 602 | 147 |
| `meta.license` declared with SPDX-exact attributes | 333 | 59 |
| Document platform breakage with `platforms`, `badPlatforms`, `broken` | 355 | 29 |
| Include a `description` | 152 | 44 |
| Include `meta.changelog` | 105 | 10 |
| Include `mainProgram` for a primary executable | 87 | 32 |
| Use `with lib.maintainers; [ ... ]` | 78 | 16 |
| Register yourself in a separate commit before the package change | 36 | 14 |

## Dated advice to ignore

- "`meta.license` must be a list": the manual says a list and a single license are both valid. Use a plain value for one license.
- `maintainers-list.nix`: the real file is `maintainers/maintainer-list.nix`.
- `meta = with lib; { license = licenses.mit; ... }` and `lib.licenses.MIT` or `lib.licenses.proprietary`: current packages write `lib.licenses.mit`, and `MIT` and `proprietary` don't exist in `lib.licenses`. The skill's [code-patterns](code-patterns.md) template still shows the old forms.
- `lib.licenses.gpl3`, `gplv3`, and the other deprecated attributes: use the `Only`/`Plus` variants.
- "Add yourself to the maintainers list only after you have a track record": the maintainers README encourages anyone who cares about a package to register, with no prerequisite. The commit-separation rule still applies.
- "Keep `with lib.maintainers` names alphabetical": the alphabetical requirement is for `maintainer-list.nix` itself; the docs set no order for a package's list.
- "Set `meta.platforms` or `meta.broken`" as alternatives: they do different jobs. `platforms` says where it works; `broken` says it currently doesn't.
- Merge-rate figures in the review corpus (for example for maintainer or unfree packages) are correlation only.
