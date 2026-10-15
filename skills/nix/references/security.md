# Security rules for packages, modules, and flakes

Load this when you touch a vulnerability fix, package a binary release, write a fetcher, handle a secret, or decide whether to trust a flake. It's the supply-chain and runtime checklist reviewers apply. For longer systemd templates see [security hardening](security-hardening.md) (corrections are in [NixOS modules](nixos-modules.md)); for module-side secrets and hardening see [NixOS modules](nixos-modules.md); for fetcher mechanics see [fetchers and sources](fetchers-and-sources.md); for PR mechanics see [upstreaming and PRs](upstreaming-and-prs.md).

Sources: `pkgs/README.md`, `CONTRIBUTING.md`, the Nixpkgs manual (stdenv hardening, meta, fetchers, configuration), `systemd.exec(5)`, `nix` 2.34 `--help` and man pages, and small evaluations run against nixpkgs master. "Measured" marks a claim checked by evaluating against nixpkgs master.

**Contents:** [Fixing a vulnerability](#fixing-a-vulnerability) · [Secrets never enter the store](#secrets-never-enter-the-store) · [Quoting and escaping](#quoting-and-escaping) · [Fetchers and the network](#fetchers-and-the-network) · [Binary and prebuilt packages](#binary-and-prebuilt-packages) · [Build hardening flags](#build-hardening-flags) · [Runtime hardening of services](#runtime-hardening-of-services) · [Reproducibility checks](#reproducibility-checks) · [Flake inputs, `nixConfig`, and `--impure`](#flake-inputs-nixconfig-and---impure) · [Checkable rules](#checkable-rules) · [Evidence](#evidence) · [Dated advice to ignore](#dated-advice-to-ignore)

## Fixing a vulnerability

- Prefer updating to the release that fixes it. If the fix is only a patch, add the patch to the tree and name it after the CVE (`CVE-2024-00000.patch`); a fetched patch needs an explicit `name` as well.
- Put the CVE identifiers, the advisory or NVD link, and the upstream release notes in the commit message. The review corpus backs this heavily (406 PRs, 6 with changes requested, so it's mostly done unprompted rather than enforced).
- Keep the fix apart from unrelated work: one logical commit (CONTRIBUTING), and a separate PR from version bumps or refactors. Reviewers asked for this in 128 PRs (26 with changes requested) so the fix can be backported without dragging other changes along.
- If a fix forces you to disable a protection, comment what fails, why, and link the upstream issue (66 PRs).

```nix
{ lib, fetchpatch, ... }:
{
  patches = [
    (fetchpatch {
      name = "CVE-2024-00000.patch";
      url = "https://example.com/project/commit/0123abcd.patch";
      hash = lib.fakeHash; # replace with the real hash after the first build
    })
  ];
}
```

### Branches and backports

- Land it on `master` first (critical security fixes may skip the staging branches and go straight to `master` or `release-*`), then backport to each supported `release-YY.MM`. A maintainer can add the `backport release-YY.MM` label to the merged PR and a bot opens the backport; otherwise open a PR against `release-YY.MM` yourself. Never target `nixos-YY.MM`; it's a channel pointer.
- If `master` and the release carry different major versions, so the patch differs, open separate PRs. Only supported releases take changes; `nix-instantiate --eval -A lib.trivial.oldestSupportedRelease` names the oldest.
- Release branches take backward-compatible changes: security fixes, patch and minor bumps. Major version bumps are acceptable there only for things like browsers and clients that break without them. So on a release branch prefer the targeted patch or minor bump (32 PRs), while on `master` bump to the latest release that fixes every known CVE rather than the minimum fixed version (25 PRs, a weak signal).
- The Nixpkgs security tracker (`tracker.security.nixos.org`) matches CVEs to derivations and opens issues for maintainers. Triage: find the earliest fixed version or a patch; if `master` isn't fixed, submit the fix there, then backport; close the issue when every vulnerable branch has it.

### `knownVulnerabilities`

If a package can't be updated, mark it rather than deleting it:

```nix
{
  meta.knownVulnerabilities = [
    "CVE-2024-00001: heap overflow in the parser, no fixed release upstream"
  ];
}
```

Measured: evaluating such a package fails with "Refusing to evaluate package ... because it is marked as insecure" and lists the entries; adding `permittedInsecurePackages = [ "example-2.1.0" ]` to the nixpkgs config lets it through. Users can also set `allowInsecurePredicate` or export `NIXPKGS_ALLOW_INSECURE=1`. Each entry should be a CVE id plus a one-line description. The bar for new packages is higher: `pkgs/README.md` says a package that would immediately need `knownVulnerabilities` is unlikely to be fit for nixpkgs, and that unmaintained security-sensitive software, packages depending on known-vulnerable libraries, and vendored copies of security-critical components deserve scrutiny. If you remove a package for security reasons, cite the specific vulnerabilities (29 PRs).

## Secrets never enter the store

Everything evaluated from Nix (`pkgs.writeText`, `environment.etc.*.text`, `builtins.readFile` of a secret, a string in `settings`) is copied into the world-readable store. Deliver secrets at run time:

| Mechanism | Use for |
|---|---|
| `*File` option plus `LoadCredential` and `$CREDENTIALS_DIRECTORY` | Preferred for services; readable only by the unit's user and root, kept in non-swappable memory where possible (`systemd.exec(5)`). |
| `EnvironmentFile` | Programs that read only environment variables. |
| Start-time substitution (`replace-secret`, `utils.genJqSecretsReplacementSnippet`) into a file under `RuntimeDirectory` | Config files that need the secret inline. |
| `users.users.<name>.hashedPasswordFile` | Login passwords; read at every activation. |

Declare file options as `nullOr types.externalPath`, document the expected format, and pass strings such as `"/run/secrets/token"`; a path literal like `./token` is copied into the store. Use restrictive modes (`0400` or `0600`; `UMask = "0077"`, `StateDirectoryMode`) for files a module creates. [NixOS modules](nixos-modules.md) has a worked example. The two closest corpus rules have small support (10 and 7 PRs), so read them as a reminder rather than a measured trend.

## Quoting and escaping

- In build scripts and `script`/`preStart` text, wrap any interpolated value that isn't a fixed literal in `lib.escapeShellArg` (one value) or `lib.escapeShellArgs` (a list). Example from the library docs: `escapeShellArg "esc'ape\nme"` yields `'esc'\''ape\nme'`. 50 PRs across three near-duplicate rules ask for it (9 with changes requested on the strongest).
- In systemd `Exec*` lines, use `utils.escapeSystemdExecArgs`/`escapeSystemdExecArg`; shell escaping doesn't cover systemd's `%` and `$` expansion.
- Generate config files with `pkgs.formats.*` generators rather than concatenating strings; the manual notes that, for example, the `javaProperties` generator takes care of escaping.
- New top-level packages must enable `__structuredAttrs = true`; it passes attributes as structured data instead of flattened shell variables (stdenv chapter). See [derivation authoring](derivation-authoring.md).

## Fetchers and the network

- Builds run in the sandbox with no network. Only fixed-output derivations, which is what fetchers are, may download, and they must declare their hash. A build step that fetches on its own (`npm install`, `cargo fetch`, `go mod download`, `pip install`) must be replaced by a vendored or fixed-output dependency fetch; see the language references ([Go](lang-go.md), [Rust](lang-rust.md), [Node.js](lang-nodejs.md), [Python](lang-python.md)). Don't use import-from-derivation; nixpkgs disallows it and CI evaluates with it off.
- Test with the sandbox on. It's the default on Linux; elsewhere add `sandbox = true` to `nix.conf` first (CONTRIBUTING).
- Use `https://` sources and a real `hash`. The only placeholders allowed while you obtain a hash are `""`, `lib.fakeHash`, `lib.fakeSha256`, and `lib.fakeSha512`. The fetchurl source passes a CA bundle to curl only for those; with any other hash it adds `--insecure`, so an arbitrary made-up hash disables TLS verification for that fetch and the hash you copy from the error could belong to tampered content.
- Never add `-k` or `--insecure` to `curlOpts` or `curlOptsList`. For a proxy with a private CA, the supported route is `NIX_SSL_CERT_FILE` in the environment (fetchers inherit it).
- Obtain upstream hashes over a secure channel: `http://` URLs aren't safe to prefetch from. Use upstream's sha256 or sha512 when offered; for md5, compute sha256 yourself. Prefer the SRI `hash` attribute (`sha256 = ...` still works, but the manual says `hash` is preferred).
- When you change any fetcher parameter, update the hash; otherwise a matching store path may be reused and new content is never fetched.
- Fetch a release by `tag` (`fetchFromGitHub { tag = ...; }`) rather than `rev = version`; the manual says `tag` is safer against branch and tag name conflicts. The corpus has 38 PRs on TLS and unsafe fetch methods (5 with changes requested), a weak but consistent signal.

## Binary and prebuilt packages

`pkgs/README.md`: build from source where possible, because binaries risk supply-chain attacks and vendored outdated libraries. When you must package a binary:

```nix
{
  lib,
  stdenv,
  fetchurl,
  autoPatchelfHook,
  zlib,
  openssl,
}:
stdenv.mkDerivation (finalAttrs: {
  pname = "example-bin";
  version = "1.0.0";

  src = fetchurl {
    url = "https://example.com/releases/v${finalAttrs.version}/example-linux-x64.tar.gz";
    hash = lib.fakeHash;
  };

  nativeBuildInputs = [ autoPatchelfHook ];

  # Resolved by autoPatchelf from the ELF headers.
  buildInputs = [
    stdenv.cc.cc.lib
    zlib
  ];

  # Loaded with dlopen at run time, so the ELF headers don't mention it.
  runtimeDependencies = [ (lib.getLib openssl) ];

  installPhase = ''
    runHook preInstall
    install -Dm755 example $out/bin/example
    runHook postInstall
  '';

  meta = {
    description = "Prebuilt example daemon";
    homepage = "https://example.com";
    license = lib.licenses.unfree;
    sourceProvenance = [ lib.sourceTypes.binaryNativeCode ];
    platforms = [ "x86_64-linux" ];
    mainProgram = "example";
  };
})
```

This evaluates on current nixpkgs with the fake hash (instantiated, not built).

- `autoPatchelfHook` patches the ELF files of the outputs to find libraries from `buildInputs` and `nativeBuildInputs`, and fails on an unresolved dependency by default. `runtimeDependencies` is added unconditionally to every executable's rpath, which is what `dlopen`ed libraries need (66 PRs, 13 with changes requested). `autoPatchelfIgnoreMissingDeps` (a list, or `[ "*" ]`) hides gaps; use it only for named libraries that really come from the host, such as a GPU driver, with a comment. `dontAutoPatchelf` turns the hook off for a manual `autoPatchelf` call.
- `meta.sourceProvenance` is required for anything not built from source. Values in `lib.sourceTypes`: `fromSource`, `binaryNativeCode`, `binaryBytecode`, `binaryFirmware`, `obfuscatedCode`. Listing a type says the package contains it; omitting one doesn't prove it's absent. An unset attribute means no known type other than `fromSource`. Mixed packages list several (`[ fromSource binaryFirmware ]`).
- Set an honest `meta.license` (`lib.licenses.unfree` or a free license; `lib.licenses.proprietary` doesn't exist) and explicit `platforms`. [Meta and licensing](meta-and-licensing.md) has the rest.
- Unvendor security-critical bundled libraries and use the nixpkgs package instead.

## Build hardening flags

`stdenv.mkDerivation` accepts `hardeningDisable` and `hardeningEnable`, each a list of flag names. Names (from `pkgs/stdenv/generic/make-derivation.nix`): `bindnow`, `format`, `fortify`, `fortify3`, `glibcxxassertions`, `libcxxhardeningextensive`, `libcxxhardeningfast`, `nostrictaliasing`, `pacret`, `pic`, `relro`, `shadowstack`, `stackclashprotection`, `stackprotector`, `strictflexarrays1`, `strictflexarrays3`, `strictoverflow`, `trivialautovarinit`, `zerocallusedregs`. `hardeningDisable` also accepts `"all"`.

- On by default (per the manual): `format`, `stackprotector`, `fortify`, `fortify3`, `pic`, `strictoverflow`, `relro`, `bindnow`, `zerocallusedregs`, `stackclashprotection`, `libcxxhardeningfast`, and `strictflexarrays1`. Off by default, and worth enabling for packages that handle untrusted input such as network services: `nostrictaliasing`, `strictflexarrays3`, `shadowstack`, `trivialautovarinit`, `glibcxxassertions`, `libcxxhardeningextensive`, and `pacret` (aarch64).
- Disable the narrowest flag that fixes a build or run-time failure, never `"all"` casually, and comment the failure and the upstream issue. Typical pairs: `format` for `-Werror=format-security` errors; `relro` and `bindnow` together for programs that load modules with `dlopen` (the manual says that if `relro` has to go, `bindnow` almost always must too); `fortify` for `_FORTIFY_SOURCE` redefinition or old-code errors (disabling it implies disabling `fortify3`).
- An unknown name aborts evaluation: `hardeningDisable = [ "pie" ]` fails with "mkDerivation was called with unsupported hardening flags" (measured).
- Support varies by compiler, architecture, OS, and libc; unsupported combinations are silently ignored. `NIX_DEBUG=1` shows which flags apply to a compiler invocation.

```nix
{
  # Upstream passes non-literal format strings: https://example.com/project/issues/1
  hardeningDisable = [ "format" ];
  hardeningEnable = [ "trivialautovarinit" ];
}
```

## Runtime hardening of services

Use `DynamicUser` or a dedicated unprivileged user, never root without a comment, plus the systemd sandboxing directives and `systemd-analyze security <unit>`. The skeleton and the corrections to the older templates are in [NixOS modules](nixos-modules.md); the longer set is [security hardening](security-hardening.md). Review support: 41 PRs prefer systemd's native isolation over manual workarounds and running as root; 11 ask you to verify that restrictions don't block legitimate operations, which a VM test does.

## Reproducibility checks

- `nix build --rebuild .#pkg` (`nix-build --check -A pkg` for non-flake) rebuilds an already-built package and compares it with the store path; a mismatch means non-determinism (embedded timestamps, paths, parallel ordering). Run it on binary-affecting changes to packages other people depend on.
- `nixpkgs-review rev HEAD` (CONTRIBUTING) builds the packages affected by a commit; run built executables from `./result/bin`.
- `nix store diff-closures before after` shows unintended dependency changes between two builds.
- A rebuild check only means something when sources are hash-pinned and the sandbox is on.

## Flake inputs, `nixConfig`, and `--impure`

- `flake.lock` is the pin: it records each input's locked URL, revision, and `narHash`. Review lock diffs like code. `nix flake update <input>` prints the old and new revision with dates; `nix flake lock` adds only missing entries and never moves existing ones; `nix flake metadata` shows the resolved tree of inputs and `follows` (measured). In CI, `--no-update-lock-file` fails with "requires lock file changes but they're not allowed" when the lock is stale, instead of rewriting it (measured). `--override-input` implies `--no-write-lock-file`.
- Duplicate or surprising nested inputs are a smell: point them at your own with `inputs.<name>.inputs.nixpkgs.follows = "nixpkgs"`. Non-flake inputs (`flake = false`) get a hash but no further structure; pin them as tightly.
- Indirect references (`nixpkgs#hello`, `<nixpkgs>`) resolve through the registry or `NIX_PATH` at run time. On NixOS built with `lib.nixosSystem`, `nixpkgs.flake.setFlakeRegistry` pins `nixpkgs` to the system's input (measured); elsewhere, name the full reference.
- A flake's `nixConfig` can ask to set any `nix.conf` option. Unless `accept-flake-config` is on, only `bash-prompt`, `bash-prompt-prefix`, `bash-prompt-suffix`, `flake-registry`, and `commit-lock-file-summary` are accepted silently; everything else prompts (`man nix3-flake`). The default is `accept-flake-config = false` (measured). Don't set it to `true` globally or pass `--accept-flake-config` for flakes you haven't read. Read every `nixConfig` key before accepting it: `extra-substituters` and `extra-trusted-public-keys` decide where binaries come from and whose signatures you trust (see `require-sigs` in the Nix manual).
- `trusted-users` is root-equivalent: the Nix manual says adding a user is "essentially equivalent to giving that user root access". Keep `require-sigs` at its default of `true`.
- `nix run`, `nix develop` (the `shellHook`), and direnv's `use flake` execute code from the flake outside the build sandbox. Building a package runs its build scripts inside the sandbox, but a malicious package can still produce malicious output you then run. Read a flake before running it, and pin it by revision.
- Flake evaluation is pure by default. Measured in a flake: `builtins.getEnv "HOME"` returns `""` and `builtins.currentSystem` is missing without `--impure`, and both work with it. `--impure` ("allow access to mutable paths and repositories") makes the result depend on the machine; don't use it to deploy. If you reach for `getEnv` to pass a secret, you'd be copying that secret into the store; use a runtime file instead.
- `nixos-rebuild` accepts `--impure` and `--accept-flake-config` as pass-throughs; neither belongs in a standard deploy command.

## Checkable rules

- A security commit message contains a CVE id or an advisory URL, and a patch fixing a CVE is named `CVE-<id>.patch`.
- Fetchers use `https://` sources and `hash`; no `curlOpts` containing `-k` or `--insecure`; placeholders are only `""`, `lib.fakeHash`, `lib.fakeSha256`, or `lib.fakeSha512`.
- A package with `meta.knownVulnerabilities` lists CVE ids, and a package removed for security cites them.
- Binary packages set `meta.sourceProvenance`, an accurate `meta.license`, explicit `meta.platforms`, `autoPatchelfHook` (or `patchelf`), and `runtimeDependencies` for `dlopen`ed libraries.
- Every `hardeningDisable` entry is a name in the known list and has a comment saying what fails.
- Values interpolated into shell text pass through `lib.escapeShellArg(s)`; values interpolated into `Exec*` lines pass through `utils.escapeSystemdExecArg(s)`.
- No secret appears in `settings`, `Environment`, `pkgs.writeText`, `environment.etc.*.text`, or an eval-time `builtins.readFile`; secret options are `nullOr types.externalPath` and delivered with `LoadCredential`, `EnvironmentFile`, or runtime substitution.
- A backport targets `release-YY.MM`, not `nixos-YY.MM`, and a fix with divergent code uses separate PRs.
- Flake CI runs with `--no-update-lock-file`; deploy commands contain neither `--impure` nor `--accept-flake-config`.

## Evidence

| Rule | support | cr |
|---|---|---|
| Document security fixes with CVE ids, notes, and advisory links | 406 | 6 |
| Keep security updates in their own PR for backporting | 128 | 26 |
| List `dlopen`ed libraries in `runtimeDependencies` | 66 | 13 |
| Comment why a security feature is disabled | 66 | 2 |
| Prefer systemd isolation over manual workarounds and root | 41 | 10 |
| `lib.escapeShellArg(s)` for interpolated shell values | 20 | 9 |
| Don't disable TLS verification in fetchers | 38 | 5 |
| Use `knownVulnerabilities` instead of removing | 31 | 2 |
| Per-file permissions: restrictive defaults | 25 | 6 |

Support counts are PRs backing each rule; cr counts PRs with a formal changes-requested review. Several of these have low cr; the corpus also asks reviewers to merge security fixes quickly once tests pass, which is about process, not code.

## Dated advice to ignore

- `hardeningEnable = [ "pie" ]` or `hardeningDisable = [ "pie" ]`: not in `knownHardeningFlags`, evaluation aborts.
- `licenses.proprietary` (in `code-patterns.md`'s binary template): not a license in `lib.licenses`; use `lib.licenses.unfree`. That template also lists only four `sourceTypes` (`obfuscatedCode` exists) and uses `with lib;` in `meta`.
- Placeholder hashes other than the four fake values (an arbitrary `sha256-...` you typed to get the build to print the real one): they switch TLS verification off for the fetch.
- "Mark vulnerable packages with `knownVulnerabilities` instead of removing them", read as a license to add new vulnerable packages: `pkgs/README.md` says a package that would need it immediately isn't fit for nixpkgs. The rule applies to packages already in the tree.
- `nixos-rebuild --use-remote-sudo` and `nix flake lock --update-input` appear in older deploy scripts; both are deprecated ([NixOS systems](nixos-systems.md)).
- Advice to "disable auto-update and telemetry by default" is a weak signal in the corpus (27 PRs, 44% merged); do it when the package would otherwise phone home or modify its own installation, not as a blanket rule.
