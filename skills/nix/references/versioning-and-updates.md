# Versioning and updates

Load this for version bumps, snapshot (unreleased) versions, update scripts and bots, renaming or removing packages, keeping several versions, release-note obligations, and updating flake inputs. For the commit and PR mechanics around a bump, see [upstreaming-and-prs](upstreaming-and-prs.md); for fetcher arguments and hashes, see [fetchers-and-sources](fetchers-and-sources.md).

Everything here was checked against nixpkgs master (Oct 2026): `pkgs/README.md`, `CONTRIBUTING.md`, `pkgs/top-level/aliases.nix`, `pkgs/common-updater/`, and `maintainers/scripts/`.

**Contents:** [Bumping a version](#bumping-a-version) · [Version strings](#version-strings) · [Automating updates](#automating-updates) · [Deprecating and removing](#deprecating-and-removing) · [Several versions of one package](#several-versions-of-one-package) · [Backports and branches](#backports-and-branches) · [Updating flake inputs](#updating-flake-inputs) · [Checkable rules](#checkable-rules) · [Evidence](#evidence) · [Dated advice to ignore](#dated-advice-to-ignore)

## Bumping a version

Several things change together. A bump that edits only `version` builds the old source under a new name.

| Change | Why |
|---|---|
| `version` | The new release |
| Source `hash` (`src`) | The hash is of the old tarball |
| Dependency hash, if the language builder has one | See the table below |
| `patches` | Drop what upstream merged; re-check the rest still apply |
| `postPatch`/`substituteInPlace` strings | `--replace-fail` makes a stale pattern fail the build instead of passing silently |
| `meta.changelog`, `meta.license` | Licenses change between versions; the changelog URL usually embeds the version |
| Build and runtime dependencies | New releases add, rename, and drop inputs |

Language builders carry their own dependency hash, and it changes whenever the lockfile or version does:

| Builder | Attribute to refresh |
|---|---|
| `buildGoModule` | `vendorHash` (`null` if you commit a vendor directory) |
| `buildRustPackage` | `cargoHash` (or `cargoDeps`/`cargoLock`; `cargoSha256` is deprecated) |
| `buildNpmPackage` | `npmDepsHash` |
| pnpm | `pnpmDeps` (`fetchPnpmDeps`, with `hash` and `fetcherVersion`) |
| yarn | `yarnOfflineCache` (`fetchYarnDeps` hash) |
| Python | `src` hash; check `dependencies` and `build-system` against upstream metadata |

Details for each ecosystem are in the `lang-*` references. To get a hash: put `lib.fakeHash` in place, build, and copy the `got:` value from the mismatch error. Or let an updater do it (below). Use SRI form (`sha256-...`). `maintainers/scripts/sha-to-sri.py` rewrites old hex or base32 hashes, and `nix-hash --to-sri --type sha256 <old>` converts one.

Fetch by tag, not by pinning `rev = version`:

```nix
{
  src = fetchFromGitHub {
    owner = "example";
    repo = "foo";
    tag = "v${finalAttrs.version}";
    hash = "sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=";
  };
  meta.changelog = "https://github.com/example/foo/releases/tag/v${finalAttrs.version}";
}
```

When you change the source format (a tarball to a git fetch, GitHub to a different host), check the new origin is the official one; the manual makes this a review point. If the new source is a fork, look for community consensus first.

### Checks before you call it done

- Build on the platforms you can reach. The release-supported systems are `x86_64-linux`, `aarch64-linux`, and `aarch64-darwin` (`pkgs/top-level/release-supported-systems.json`). `x86_64-darwin` support was dropped for 26.11, so don't add it to new test claims.
- Run `nixpkgs-review wip` (or `pr N`) to rebuild dependents. A bump that breaks consumers needs a fix to the consumers in the same PR, or a separate versioned attribute (below).
- Run the executables, not just the build. `versionCheckHook` and `passthru.tests` catch some regressions automatically.
- Read the upstream changelog for breaking changes that affect the package's options or its dependents.
- Confirm `meta.license` still matches upstream. Licenses change between releases.
- Use the commit title `foo: 1.2.3 -> 1.2.4` and put the changelog link in the body. The `foo:` prefix queues the automatic CI builds.

### Not downgrading

Reviewers commonly push back on downgrades (136 PRs in the corpus, with changes requested in 9) and expect a technical reason: a regression upstream, an incompatibility with a dependent. If a new release breaks something, prefer fixing forward, patching, or pinning the old version with a comment that says why and when to unpin. Pinned or special versions must carry that comment; the manual lists it as a review point.

## Version strings

Rules from `pkgs/README.md`:

- `version` must start with a digit (`nix-env` parses derivation names that way).
- Stable releases use the upstream version as published.
- A commit without a release uses the last release before it, then `-unstable-`, then the commit's date in `YYYY-MM-DD`: `2.2-unstable-2022-03-15`. The date is the fetched commit's.
- A project with no suitable release (no tags, `latest` tags, date-named tags) uses `0`: `0-unstable-2022-03-15`.

```nix
{
  version = "0-unstable-2026-03-15";
  src = fetchFromGitHub {
    owner = "example";
    repo = "foo";
    rev = "0123456789abcdef0123456789abcdef01234567";
    hash = "sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=";
  };
}
```

Fetch a snapshot by full commit hash. Short hashes are ambiguous across forks on GitHub.

Prefer official releases to snapshots, and stable to pre-release. Reviewers commonly ask for a release when one exists (the corpus rule against pre-release packaging has 159 supporting PRs). When you must package a pre-release, keep upstream's pre-release suffix in `version` (`0.3.1rc2` is a valid example in the manual), so it sorts correctly and reads as pre-release.

Changing a patch set doesn't need a version change.

## Automating updates

### `passthru.updateScript`

Add one when upstream publishes releases regularly. The bot and `maintainers/scripts/update.nix` both use it. The accepted forms are an executable file, a list of script plus arguments, or an attribute set with `command`, `attrPath`, and `supportedFeatures`.

For most packages, use a general-purpose updater:

```nix
{
  passthru.updateScript = nix-update-script { };
}
```

`nix-update-script` wraps the `nix-update` tool. It finds a new version, updates `version`, the source hash, and language dependency hashes (`cargoHash`, `vendorHash`, `npmDepsHash`, ...). It was by far the most common form in `pkgs/by-name` at the time of writing (about 4,100 packages, against about 570 for `gitUpdater`), and `buildPythonPackage` and `buildPythonApplication` default to it.

Extra `nix-update` arguments go through `extraArgs`. These are the ones used in nixpkgs, counted from the tree:

| Argument | Use |
|---|---|
| `--version-regex=REGEX` | Pick tags matching a pattern, with a capture group for the version (monorepos, `release-1.2` style tags, `v` prefixes) |
| `--use-github-releases` | Use GitHub releases rather than tags |
| `--version=branch` | Track a branch's HEAD and write an `-unstable-DATE` version (`0-unstable-...`, or `<last tag>-unstable-...`); `--version=branch=main` names the branch |
| `--version=unstable` | Used by packages that track pre-release tags (alpha, beta); it doesn't write the dated form |
| `--version=skip` | Leave `version` alone and refresh the other hashes |
| `--subpackage NAME` | Also update a sub-derivation (a frontend, vendored deps) |
| `--generate-lockfile` | Regenerate a lockfile the package ships |
| `--custom-dep NAME` | Update an extra dependency hash |
| `--url URL`, `--override-filename PATH`, `--system SYSTEM`, `--src-only`, `--commit` | Less common; see `nix-update --help` |

```nix
{
  passthru.updateScript = nix-update-script {
    extraArgs = [
      "--version-regex"
      "release-(.*)"
    ];
  };
}
```

`nix-update-script` also takes `attrPath` when the attribute path differs from where the package is found.

Other updaters in `pkgs/common-updater`:

- `gitUpdater { }` updates to the newest git tag. Arguments include `rev-prefix` (a `v` prefix), `ignoredVersions` and `allowedVersions` (regexes), `odd-unstable`, `patchlevel-unstable`, and `url`.
- `unstableGitUpdater { }` tracks HEAD and writes the `-unstable-DATE` version. Arguments include `hardcodeZeroVersion` (use `0` as the base version), `tagPrefix`, `tagFormat`, `branch`, and `url`.
- `genericUpdater` is the base the others build on, for when you supply your own version-listing command.
- `directoryListingUpdater` and `httpTwoLevelsUpdater` scan release listing pages for upstreams that don't use git tags.

Match the updater to the package's origin: release-tracking packages use `nix-update-script { }` or `gitUpdater`, snapshot packages use `--version=branch` or `unstableGitUpdater`.

Run an update by hand from a nixpkgs checkout with `nix-shell maintainers/scripts/update.nix --argstr package foo`. Add `--arg commit true` to have it create commits. Update scripts receive `UPDATE_NIX_NAME`, `UPDATE_NIX_PNAME`, `UPDATE_NIX_OLD_VERSION`, and `UPDATE_NIX_ATTR_PATH`, and run in parallel, so they shouldn't commit on their own.

For packages in your own flake, `nix-update` has options for operating on a flake; this reference doesn't list them because they aren't documented in the nixpkgs tree. Check `nix-update --help` for your installed version.

### The update bot

`r-ryantm` runs `nixpkgs-update` against all of nixpkgs and opens version-bump PRs. A `passthru.updateScript` gives it an explicit, more reliable procedure than its built-in guessing. A package whose version must not auto-update carries a `# nixpkgs-update: no auto update` comment in its file (about 200 files in the tree). If a bot PR arrives for your package, treat it like any bump: review the changelog, check dependents, and fix patches it can't.

## Deprecating and removing

Compatibility comes first. Breaking widely used attributes, arguments, or helpers without a migration path is the best-supported rule in this category (642 PRs, 69 with changes requested). Give users a warning, then a throw with an explanation, then remove, in that order.

### Removing a package from nixpkgs

1. Delete the package directory (and its entry in `all-packages.nix` if it has one).
2. Add an alias in `pkgs/top-level/aliases.nix` (vim plugins have `pkgs/applications/editors/vim/plugins/aliases.nix`). Package sets generally don't get aliases.
3. Evaluate: `nix-env -qaP -f . --show-trace` should list packages without errors.
4. Explain why in the commit message, linking the source if upstream declared the project discontinued.

```nix
{
  foo = throw "foo was discontinued upstream in March 2021"; # Added 2021-03-15
}
```

The current convention in the file: `# Added YYYY-MM-DD`, entries sorted ASCIIbetically, a throw message that says what happened and what to use instead. Don't add a Nixpkgs release note for a plain removal; the throwing alias is the notice.

Aliases that rename, rather than remove, use `warnAlias`:

```nix
{
  oldname = warnAlias "'oldname' has been renamed to 'newname'" newname; # Added 2026-05-20
}
```

Lifecycle: normal alias, then `warnAlias`, then `throw`, then deletion. `maintainers/scripts/remove-old-aliases.py --year YYYY [--month M] --file pkgs/top-level/aliases.nix` converts or deletes entries older than the cutoff. An alias that should stay forever (a common typo, a distro name) ends in `preserve, reason: <why>`. Keep those rare.

Aliases only exist for users outside nixpkgs; nixpkgs itself must not use them (`config.allowAliases` gates them). If a package has been broken for a full release cycle, with nobody fixing it, removal is the usual next step (`meta.broken` says "should be removed eventually unless fixed"). Try finding a new maintainer or fixing small problems first.

### Deprecating in your own flake or overlay

```nix
final: prev: {
  oldname = prev.lib.warnOnInstantiate "oldname was renamed to newname" final.newname;
}
```

`lib.warn`, `lib.warnIf`, and `lib.warnOnInstantiate` print an evaluation warning; `throw` or `lib.throwIf` stops evaluation. Put the replacement and, where known, the removal date in the message. For NixOS options, use the renamed and removed option helpers described in [nixos-modules](nixos-modules.md) (`mkRenamedOptionModule`, `mkRemovedOptionModule`, `mkAliasOptionModule`); the removed form takes replacement instructions as a string and should always provide them.

### Release notes

- Breaking or significant package changes (other than removals) go in the next `doc/release-notes/rl-YYMM.section.md`, under "Backward Incompatibilities" or "Other Notable Changes".
- Adding or removing a NixOS module, or other breaking NixOS changes, go in `nixos/doc/manual/release-notes`.
- Library changes go in the `lib` sections of the same file.
- Add your entry at an arbitrary position in the list, not the end; the file asks for this to avoid merge conflicts.

## Several versions of one package

Keep an old version only when something needs it: dependents that don't build with the new one, or a legitimately different major release. The manual's example is that nixpkgs carries several GCC versions because some packages don't build with the newest. Each extra version is maintenance, so Go, for instance, drops a version as soon as upstream stops supporting it.

Naming (`pkgs/README.md`):

- The attribute name reflects the version: `json-c_0_9`, `json-c_0_11`, `go_1_24`. Version parts are joined with `_`.
- If there's an obvious default, add an unversioned attribute: `json-c = json-c_0_9;`.
- In commit messages for package sets with versions (`python3Packages`), use the unversioned attribute unless the change is version-specific.
- One version lives at `pkgs/by-name/xy/xyz/package.nix`. Several versions that share code can't use the automatic `by-name` attribute creation; define the attributes yourself.

New top-level `callPackage` calls outside `by-name` fail CI, and files outside a package's directory can't be shared from inside `by-name`. The workaround from `pkgs/by-name/README.md` is an `inherit` over a local attribute set:

```nix
{
  inherit
    ({
      foo_1 = callPackage ../tools/foo/1.nix { };
      foo_2 = callPackage ../tools/foo/2.nix { };
    })
    foo_1
    foo_2
    ;
}
```

When a dependent requires a specific version, name that version in its function arguments (`{ libbar_2, ... }`) instead of overriding the argument elsewhere. If the requirement changes, a downstream override then fails visibly.

## Backports and branches

Version bumps are backport-eligible for patch releases and for minor releases without breaking changes. Major bumps with breaking changes are acceptable only in narrow cases (clients that stop working without an update, security-critical applications such as browsers). Toolchain and stdenv-level bumps rebuild many packages and go to `staging`; see [build-closure-and-platforms](build-closure-and-platforms.md) for rebuild counts and [upstreaming-and-prs](upstreaming-and-prs.md) for branch routing.

## Updating flake inputs

| Goal | Command |
|---|---|
| Update every input | `nix flake update` |
| Update one input | `nix flake update nixpkgs` |
| Add missing inputs without touching existing locks | `nix flake lock` |
| Try a different input without writing the lock file | `nix build --override-input nixpkgs path:/path/to/nixpkgs .#foo` |
| Update and commit the lock file in one step | `nix flake update --commit-lock-file` |

`nix flake update` prints each input's old and new revision and date; paste that into the commit message. `nix flake lock` never changes locked entries, so it's the safe command when you only added an input. `--override-input` implies `--no-write-lock-file`, so it can't dirty your lock file; use it to test a nixpkgs PR checkout or a local fork of an input.

`nix flake lock --update-input` and `--recreate-lock-file` are deprecated in current Nix (2.34); use `nix flake update <input>`.

Lock hygiene:

- Commit `flake.lock`. Reproducibility lives there.
- Update inputs in their own commit, separate from feature work, and name which inputs moved.
- Update one input at a time when you can, so a regression has one suspect.
- Dedupe with `follows` (`inputs.foo.inputs.nixpkgs.follows = "nixpkgs"`) so the lock doesn't carry three nixpkgs revisions, which costs evaluation time and closure size.
- After an update, run `nix flake check` and build the outputs; a lock bump is a dependency bump.
- Pick the nixpkgs branch deliberately: `nixos-unstable` and `nixpkgs-unstable` track master, `nixos-YY.MM` tracks a stable release. If an input URL uses the channel tarball `nixexprs.tar.xz` from `channels.nixos.org`, move to `nixexprs.tar.zst`; the `.xz` form is discontinued after 2027-12-31 (26.11 release notes).

## Checkable rules

- `version` starts with a digit.
- A snapshot version matches `<base>-unstable-YYYY-MM-DD`, where `<base>` is the last release or `0`.
- A snapshot's `src` pins a full commit `rev`; a release's `src` uses `tag`.
- A change to `version` is accompanied by a change to `src.hash` and any language dependency hash, in the same commit.
- Packages with regular upstream releases define `passthru.updateScript`; snapshot packages use `--version=branch` or `unstableGitUpdater`.
- A removed package has a `throw` alias in `pkgs/top-level/aliases.nix` with an `Added YYYY-MM-DD` comment and a message that says why and what to use instead.
- Renames use `warnAlias` (or `lib.warnOnInstantiate` outside nixpkgs), not a silent alias.
- Pinned or special versions have a comment giving the reason and the unpin condition.
- Attribute names for extra versions end in the version (`_1_2`), with an unversioned default alias.
- Breaking package changes have an entry in `doc/release-notes`; plain removals don't.

## Evidence

From `find-rules.py --category versioning-and-updates`:

| Rule | support | cr |
|---|---|---|
| Avoid breaking changes to widely used attributes; provide deprecation warnings and a migration path | 642 | 69 |
| Date-based versions for unreleased code (`0-unstable-YYYY-MM-DD`) | 127 | 46 |
| Prefer official release tags over commit snapshots | 197 | 57 |
| Verify dependents still build after a bump | 318 | 32 |
| Prefer `nix-update` and `passthru.updateScript` to custom scripts | 94 | 25 |
| Deprecation messages and migration paths on removal | 237 | 37 |
| `throw` with a reason and replacement when deprecating a package | 81 | 18 |
| Update the hash with the version | 49 | 16 |
| Don't downgrade without strong justification | 136 | 9 |

## Dated advice to ignore

- `version = "unstable-2024-01-01"` (no leading digit): superseded by `0-unstable-YYYY-MM-DD` or `<release>-unstable-YYYY-MM-DD`. About 250 older `version = "unstable-..."` lines remain in the tree; the manual requires a leading digit, so don't copy them.
- "Use semantic versioning conventions for unreleased packages" (215 PRs): vague. The concrete rule is the `-unstable-DATE` form above.
- `cargoSha256` and `vendorSha256`: `cargoSha256` is deprecated and `buildGoModule` now throws on `vendorSha256`; use `cargoHash` and `vendorHash`.
- `nix flake lock --update-input` and `--recreate-lock-file`: deprecated; use `nix flake update`.
- "Close PRs for outdated, stale, or superseded versions" (299 PRs): that describes PR triage when a newer bump exists. It isn't a packaging rule, and doesn't mean "keep only the newest version"; the multi-version section above governs.
- "Avoid pinning exact versions; use flexible constraints" (54 PRs, 44% merged): mixed and context-dependent. For nixpkgs packages the rule is a comment that explains the pin, not a ban on pinning.
