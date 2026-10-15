# Fetchers and sources

Load this when you pin a package's source, compute or update a hash, add a patch from the network, or name an unreleased snapshot version. Package structure is in [derivation-authoring](derivation-authoring.md), license and provenance metadata in [meta-and-licensing](meta-and-licensing.md), patch policy in [patches-and-overrides](patches-and-overrides.md), version bumps in [versioning-and-updates](versioning-and-updates.md).

Verified against `doc/build-helpers/fetchers.chapter.md`, `pkgs/README.md`, and the fetcher sources in `pkgs/build-support/` (Oct 2026).

**Contents:** [Pick the fetcher](#pick-the-fetcher) · [SRI hashes](#sri-hashes) · [Hash workflow](#hash-workflow) · [`tag` or `rev`](#tag-or-rev) · [Git options and their costs](#git-options-and-their-costs) · [Never mutable URLs](#never-mutable-urls) · [Patches](#patches) · [Unstable versions](#unstable-versions) · [Provenance](#provenance) · [Checkable rules](#checkable-rules) · [Evidence](#evidence) · [Dated advice to ignore](#dated-advice-to-ignore)

## Pick the fetcher

Nixpkgs fetchers (`pkgs.fetch*`) are fixed-output derivations that download at build time, so they use binary caches and only re-download when the hash changes. Nix's eval-time `builtins.fetchurl`, `fetchTarball`, and `fetchGit` aren't allowed in nixpkgs, and neither is import-from-derivation.

| Source | Fetcher | Notes |
|---|---|---|
| GitHub repository at a tag or commit | `fetchFromGitHub` | Downloads GitHub's snapshot archive (via `fetchzip`) |
| GitLab | `fetchFromGitLab` | `domain` selects a self-hosted instance |
| Codeberg, Forgejo, Gitea | `fetchFromCodeberg`, `fetchFromForgejo`, `fetchFromGitea` | The latter two take `domain` |
| Sourcehut, Bitbucket | `fetchFromSourcehut`, `fetchFromBitbucket` | |
| Any other git host | `fetchgit` | Use an `https://` URL; `git://` can't go through proxies |
| Release asset (tarball, zip, binary) | `fetchurl` | Hash covers the downloaded file |
| Archive where you want the unpacked tree hashed | `fetchzip` | `stripRoot` (default `true`) drops the single top-level directory |
| GNU, Apache, SourceForge, and similar | `fetchurl` with `mirror://gnu/...` | Mirror names are in `pkgs/build-support/fetchurl/mirrors.nix` |
| Patch from a commit or PR URL | `fetchpatch2` (or `fetchpatch`) | See [Patches](#patches) |
| Download that needs a login or has no redistribution right | `requireFile` | Unfree software only; the user adds the file to the store |
| Dependencies of a language package | the language builder's hash (`vendorHash`, `cargoHash`, `npmDepsHash`, `fetchPypi`) | [Go](lang-go.md), [Rust](lang-rust.md), [Node.js](lang-nodejs.md), [Python](lang-python.md) |

- Use `fetchFromGitHub` for repository snapshots (the review checklist asks for "the most appropriate function"). Use `fetchurl` on a release asset when it contains files the git archive lacks, such as a pre-generated `configure`, or when it's the project's blessed download location.
- Prefer `mirror://` URLs when a mirror exists. Fetch from official locations, a trusted mirror, or a mirror the authors trust.
- Prefer sources with high availability and protocols that proxies support.
- Don't `fetchurl` a GitHub archive URL by hand; the checklist expects `fetchFromGitHub` there.

## SRI hashes

```nix
{
  src = fetchFromGitHub {
    owner = "example";
    repo = "foo";
    tag = "v${finalAttrs.version}";
    hash = "sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=";
  };
}
```

- Use the `hash` attribute with an SRI string (`sha256-<base64>`). The manual calls `sha256`, `sha512`, `sha1`, `outputHash`, and `outputHashAlgo` backwards-compatibility spellings. Fetchers still accept them, and `pkgs/README.md` says the preferred hash *type* is sha256.
- The hash is of the fetcher's *output*, not of the remote file. For `fetchzip` and `fetchFromGitHub`, that's the unpacked tree. A tarball's `sha256sum` won't match.
- Nixpkgs doesn't standardize one text encoding (base16, nix32, and base64 all work), but SRI is what `hash` expects and what Nix prints on mismatch.
- Never type a hash from memory or copy one from another package. Get it from a build error, a prefetch tool, or a checksum upstream publishes over a secure channel. If you can't run a build (no network), leave `lib.fakeHash` and tell the reader the hash is unverified.

## Hash workflow

1. **Placeholder.** Set `hash = "";` or `hash = lib.fakeHash;`. The other fake values are `lib.fakeSha256` and `lib.fakeSha512`. Use only these: `fetchurl` keeps TLS verification on for the fake hashes (and for `netrcPhase` fetches), so an arbitrary invented hash turns it off for that download.
2. **Build.** Run `nix-build -A foo` (or `nix build .#foo` in a flake). Nix fails with `specified: sha256-AAAA...` and `got: sha256-<real>`.
3. **Paste the `got:` value** and rebuild.
4. **Re-blank after any change.** If you change `url`, `tag`, `rev`, `owner`, `repo`, `fetchSubmodules`, `stripRoot`, or any other fetcher parameter, blank the hash again. A stale hash makes Nix reuse the old store path, so you silently keep the old source.
5. **Prefetch instead, when you know how the fetcher hashes.**
6. **Use an upstream hash** when upstream publishes `sha256` or `sha512` over HTTPS. Don't use `md5`; compute `sha256`.

| Need | Command |
|---|---|
| Unpacked GitHub archive (matches `fetchFromGitHub`) | `nix-prefetch-url --unpack --type sha256 https://github.com/<owner>/<repo>/archive/refs/tags/<tag>.tar.gz` |
| One file (matches `fetchurl`) | `nix store prefetch-file <url>`, prints an SRI hash |
| Git checkout (matches `fetchgit`) | `nix-prefetch-git --url <url> --rev <ref>`, add `--fetch-submodules` if needed |
| Local file | `nix hash file --type sha256 --sri <file>` |
| Nix32 or hex to SRI | `nix hash convert --hash-algo sha256 --to sri <hash>` |
| Hash of an existing package's source | `nix-prefetch-url '<nixpkgs>' -A <pkg>.src` |

`nix-prefetch-url` prints Nix's base-32 form, so convert it. `nix store prefetch-file`, `nix hash file`, and `nix hash convert` are marked experimental in Nix 2.34, so they need the `nix-command` feature. `nix hash to-sri` is deprecated in favor of `nix hash convert`. Example: `nix hash convert --hash-algo sha256 --to sri e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` prints `sha256-47DEQpj8HBSa+/TImW+5JCeuQeRkm5NMpJWZG3hSuFU=`.

The manual says to use the fake-hash method unless you understand how your fetcher computes its hash. Tools like `nurl` and `nix-init` (both packaged in nixpkgs, but not part of the manual) generate fetcher expressions from a URL.

## `tag` or `rev`

```nix
{
  # release
  src = fetchFromGitHub {
    owner = "example";
    repo = "foo";
    tag = "v${finalAttrs.version}";
    hash = "sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=";
  };
}
```

```nix
{
  # untagged snapshot
  src = fetchFromGitHub {
    owner = "example";
    repo = "foo";
    rev = "0123456789abcdef0123456789abcdef01234567";
    hash = "sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=";
  };
}
```

- `fetchFromGitHub` asserts that exactly one of `tag` and `rev` is given. Both fail evaluation.
- For a tag, use `tag`. It fetches `refs/tags/<tag>` and avoids the branch-versus-tag ambiguity of `rev = version`. When upstream tags are bare version numbers, write `tag = finalAttrs.version;`, not `"${finalAttrs.version}"` (CONTRIBUTING lists the interpolation as an unnecessary string conversion).
- For a snapshot, use `rev` with the *full* 40-character commit hash. GitHub shares commit hashes across forks, and abbreviated hashes have produced 404s.
- Corpus rules disagree: one says "use `tag`" (support 76), another "use commit hashes instead of tags" (support 75). The manual prefers `tag` for releases. Use a commit hash only when no tag exists or upstream moves tags.
- `finalAttrs.src.tag` is available, e.g. for `meta.changelog`.
- `fetchgit` also accepts `tag`; the manual says it's the same as `rev = "refs/tags/${tag}"`. Without `rev` or `tag`, `fetchgit` falls back to `HEAD`, which isn't pinned; always provide one.

## Git options and their costs

`fetchFromGitHub` downloads a snapshot archive, which gives a stable hash and a fast fetch. It switches to `fetchgit` (a real `git clone`) when any of these is set: `fetchSubmodules`, `deepClone`, `leaveDotGit`, `fetchLFS`, `forceFetchGit`, a non-empty `sparseCheckout`, or a non-empty `rootDir`.

| Option | Use it when | Cost |
|---|---|---|
| `fetchSubmodules = true` | The build needs submodule contents (check `.gitmodules` and the build files) | Falls back to `git clone`, which is less efficient than a snapshot; bundled third-party code may duplicate something nixpkgs already packages |
| `leaveDotGit = true` | The build reads git metadata (`git describe`, commit hash) | The manual says the `.git` format isn't stable, so the hash can drift; use it only with a `postFetch` that deletes `.git` |
| `deepClone = true` | You need history, not just the checkout | Implies `leaveDotGit`; same instability |
| `fetchTags = true` | `git describe` must see tags | Implies `leaveDotGit`. `fetchFromGitHub` rejects `fetchTags` on its own (evaluation fails), so add `forceFetchGit = true` or `leaveDotGit = true` |
| `sparseCheckout`, `rootDir` | Only a subdirectory is needed | `rootDir` can't be combined with `leaveDotGit` |
| `fetchLFS = true` | The repository stores assets in Git LFS | Pulls LFS objects through `git-lfs` and also forces `fetchgit` |

- Set `fetchSubmodules` only when the build uses them. Reviewers commonly ask for that (support 33, cr 10), and the same corpus asks you to avoid `fetchgit` with `fetchSubmodules` plus `deepClone` where `fetchFromGitHub` works (support 38, cr 9).
- `fetchgit` defaults `fetchSubmodules` to `true`; `fetchFromGitHub` defaults it to `false`. Don't assume the same behavior when you swap fetchers.
- Prefer feeding version info into the build (a flag, an environment variable, or `postPatch`) over keeping `.git`. When you do need it:

```nix
{
  src = fetchFromGitHub {
    owner = "example";
    repo = "foo";
    tag = "v${finalAttrs.version}";
    leaveDotGit = true;
    postFetch = ''
      cd "$out"
      git rev-parse HEAD > $out/COMMIT
      find "$out" -name .git -print0 | xargs -0 rm -rf
    '';
    hash = "sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=";
  };
}
```

- Security-critical components that a package vendors, such as crypto or web engines, should be unvendored in favor of the nixpkgs package (`pkgs/README.md`). That's another reason to question `fetchSubmodules`.

## Never mutable URLs

A fixed-output hash only helps if the URL keeps serving the same bytes.

```nix
# BAD: the contents change when upstream moves the branch or cuts a release
{
  src = fetchurl {
    url = "https://github.com/example/foo/archive/refs/heads/main.tar.gz";
    hash = "sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=";
  };
}
```

- Don't pin a branch name (`rev = "main"`), a `latest` redirect (`releases/latest/download/...`), a rolling download page, or a pull-request patch URL.
- Don't use `http://` or `git://`; use HTTPS. Insecure channels also make prefetched hashes untrustworthy.
- Pin a version-specific release asset, a tag, or a full commit hash.
- If upstream only serves an unversioned URL, the hash will break at the next upstream update. Ask upstream for versioned artifacts or reconsider packaging.

## Patches

`fetchpatch2` and `fetchpatch` both normalize a downloaded patch before hashing it, so volatile parts that forges add don't change the hash.

```nix
{
  patches = [
    (fetchpatch2 {
      name = "fix-gcc14-build.patch";
      url = "https://github.com/example/foo/commit/0123456789abcdef0123456789abcdef01234567.patch?full_index=1";
      hash = "sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=";
    })
  ];
}
```

- `pkgs/README.md` says patches already published upstream *should* be fetched with `fetchpatch2`. If the patch has short hashes in its `index` lines (`index 0c97fcc35..f533e464a 100644`), use `fetchpatch` instead, or expand them: GitHub supports `?full_index=1`.
- Both take `relative`, `stripLen`, `extraPrefix`, `excludes`, `includes`, `hunks`, `revert`, and `decode`. `excludes` and `includes` can't be combined.
- Normalization runs *after* these options, so changing any of them changes the hash.
- Give each patch a descriptive `name` and a comment with its reason. The reviewer checklist asks for an upstream URL or a reason it wasn't upstreamed.
- Use a stable commit URL, not an open pull request. PR patches change when the PR updates, and forges garbage-collect commits after rebases.
- Vendor the `.patch` file (`patches = [ ./0001-fix.patch ];`) when it solves a packaging-only problem, can't be fetched easily, or its URL is likely to vanish.

## Unstable versions

For a commit with no release, set `version` to the latest upstream version before it, then `-unstable-` and the commit date:

```nix
{
  version = "2.2-unstable-2022-03-15";
}
```

- The date is `YYYY-MM-DD`, from the fetched commit. With no suitable earlier release, use `0` as the base: `"0-unstable-2022-03-15"`. `version` must start with a digit.
- Pair this with `rev = "<full commit hash>"`.
- Updaters: `passthru.updateScript = unstableGitUpdater { };` or `nix-update-script { extraArgs = [ "--version=branch" ]; }`.
- Prefer a tagged release over a snapshot when one exists.

## Provenance

If the package ships prebuilt binaries from the source you fetch (a `.deb`, a release binary, a wheel), set `meta.sourceProvenance` ([meta-and-licensing](meta-and-licensing.md#source-provenance)). Fetch binaries with `fetchurl` or `fetchzip` and a versioned URL.

## Checkable rules

- Fetcher attributes use `hash = "sha256-..."` (or another SRI string), not `sha256 =` or `sha1 =`.
- `fetchFromGitHub` (and the other `fetchFrom*` helpers) pass exactly one of `tag` and `rev`.
- A `rev` is a 40-hex-digit commit, not a branch name or a short hash; `rev = version` doesn't appear.
- No URL contains `refs/heads/`, `/latest/`, `git://`, or `http://`.
- No placeholder hash other than `""`, `lib.fakeHash`, `lib.fakeSha256`, or `lib.fakeSha512` is left in a finished package, and none of those four remains either.
- `fetchSubmodules`, `leaveDotGit`, `deepClone`, `fetchTags`, and `fetchLFS` are set only with a comment or build requirement behind them.
- Patches fetched from the network use `fetchpatch2` (or `fetchpatch` with short-hash patches), set `name`, and come from a commit or tag URL, not a PR.
- `version` begins with a digit; snapshot versions match `<base>-unstable-YYYY-MM-DD`.
- No `builtins.fetchurl`, `builtins.fetchTarball`, `builtins.fetchGit`, or import-from-derivation in nixpkgs expressions.

## Evidence

| Rule | support | cr |
|---|---|---|
| Verify hashes match the real contents | 623 | 132 |
| Use `hash` in SRI format | 305 | 128 |
| Use `fetchpatch` with explicit parameters for upstream patches | 278 | 60 |
| Use `fetchFromGitHub` for GitHub sources | 208 | 103 |
| Use `tag` instead of `rev` for version tags | 76 | 27 |
| Use `mirror://` URLs when mirrors exist | 80 | 22 |
| Prefer `hash` over legacy `sha256` | 73 | 37 |

## Dated advice to ignore

- `sha256 = "..."`, `sha256 = lib.fakeSha256`, and bare nix32 strings in new code: use `hash` (older nix.dev tutorials still show `sha256 =`).
- `rev = "v${version}"` and `rev = version` for release tags: use `tag`.
- `nix hash to-sri` and `nix-hash --to-sri`: use `nix hash convert`.
- `fetchzip`'s `extraPostFetch`: deprecated, use `postFetch`.
- "Use `fetchpatch` for upstream patches" (the corpus wording): `fetchpatch2` is the documented default now, with `fetchpatch` for short-hash patches.
- "Always `fetchSubmodules = true` when the repository has submodules": only when the build needs them.
- "Verify the hash is stable across platforms" and merge-rate numbers attached to these rules are correlation, not policy.
