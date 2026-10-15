# Node.js

Load this when you package a JavaScript or TypeScript application with Nix, either in your own flake or as a nixpkgs package. The rule that matters most is the same in both places: use the Nix tool that understands your lockfile. Feeding a pnpm project to an npm builder produces install failures that look unrelated to the cause.

**Contents:** [Choosing the approach](#choosing-the-approach) · [In your own flake or project](#in-your-own-flake-or-project) · [In nixpkgs](#in-nixpkgs) · [Dated advice to ignore](#dated-advice-to-ignore)

## Choosing the approach

| Lockfile | Own flake or project | nixpkgs |
|---|---|---|
| `package-lock.json` | `buildNpmPackage` with `npmDepsHash`; `importNpmLock` when `npmRoot` is a local path | `buildNpmPackage` with `npmDepsHash` |
| `pnpm-lock.yaml` | `fetchPnpmDeps` + `pnpmConfigHook` (+ `pnpmBuildHook`) | same, with a pinned `pnpm_N` |
| `yarn.lock` with `# yarn lockfile v1` | `fetchYarnDeps` + `yarnConfigHook`, `yarnBuildHook`, `yarnInstallHook` | same |
| `yarn.lock` with `__metadata:` (Berry v3/v4) | `yarn-berry_N.fetchYarnBerryDeps` + `yarnBerryConfigHook` | same |
| any, but the lockfile can't keep up | impure build (see Escape hatch) | not allowed; commit a regenerated lockfile instead |

`node2nix`, `nodePackages`, and `yarn2nix` (`mkYarnPackage`, `mkYarnModules`) no longer exist in nixpkgs. The 26.05 release notes record the removals and `pkgs/top-level/aliases.nix` throws for each name. `npmlock2nix` and `nix-npm-buildpackage` live outside nixpkgs, need import-from-derivation, are pre-1.0, and have open npm v7+ lockfile problems; the manual lists them only under "Outside Nixpkgs".

## In your own flake or project

### buildNpmPackage (npm)

```nix
{ buildNpmPackage, lib }:
buildNpmPackage {
  pname = "myfrontend";
  version = "0.1.0";
  src = ../..;
  npmDepsHash = lib.fakeHash; # build once, copy the real hash from the error
  # npmBuildScript = "build";          # default is "build"
  # npmWorkspace = "packages/app";     # for a workspace member
  installPhase = ''
    runHook preInstall
    cp -r dist $out
    runHook postInstall
  '';
}
```

`prefetch-npm-deps package-lock.json` prints the hash without a failed build. `makeCacheWritable = true;` helps when npm tries to write into its cache, but it slows the build, so leave it off until you see the error. For Electron projects set `env.ELECTRON_SKIP_BINARY_DOWNLOAD = "1";`.

`importNpmLock` replaces the dependency references in `package.json` and `package-lock.json` with store paths, so no hash is needed. It reads the lockfile at evaluation time, which works with a local `npmRoot = ./.;` and is import-from-derivation for a fetched source. Pair it with its own config hook:

```nix
{ buildNpmPackage, importNpmLock }:
buildNpmPackage {
  pname = "hello";
  version = "0.1.0";
  src = ./.;
  npmDeps = importNpmLock { npmRoot = ./.; };
  npmConfigHook = importNpmLock.npmConfigHook;
}
```

### pnpm

```nix
{
  stdenv,
  nodejs,
  pnpm_11,
  fetchPnpmDeps,
  pnpmConfigHook,
  pnpmBuildHook,
}:
stdenv.mkDerivation (finalAttrs: {
  pname = "myapp";
  version = "0.1.0";
  src = ../..;
  nativeBuildInputs = [
    nodejs
    pnpm_11
    pnpmConfigHook
    pnpmBuildHook
  ];
  pnpmDeps = fetchPnpmDeps {
    inherit (finalAttrs) pname version src;
    pnpm = pnpm_11;
    fetcherVersion = 4;
    hash = "sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=";
  };
  installPhase = ''
    runHook preInstall
    cp -r dist $out
    runHook postInstall
  '';
})
```

The older `pnpm.fetchDeps` and `pnpm.configHook` attributes are deprecated aliases for the top-level `fetchPnpmDeps` and `pnpmConfigHook`. `fetcherVersion = 1` and `2` are removed; the minimum is 3 and the manual says to use 4 for new packages. If your flake pins an older nixpkgs, use the highest `fetcherVersion` that revision accepts. Changing it changes the hash. Pin `pnpm` to a major version (`pnpm_9`, `pnpm_10`, `pnpm_11`, and so on) because store formats change between majors; plain `pnpm` follows the newest.

`pnpmConfigHook` already runs `pnpm install --ignore-scripts`, so postinstall downloads don't fire. For `buildNpmPackage` use `npmFlags = [ "--ignore-scripts" ];` or `env.NPM_CONFIG_IGNORE_SCRIPTS = "true";`.

### Yarn

Yarn v1 uses hooks over an offline cache: set `yarnOfflineCache = fetchYarnDeps { yarnLock = finalAttrs.src + "/yarn.lock"; hash = ...; }` and list `yarnConfigHook`, `yarnBuildHook`, `yarnInstallHook`, and `nodejs` in `nativeBuildInputs`. Yarn Berry uses `yarn-berry_4.fetchYarnBerryDeps` for the `offlineCache` attribute plus `yarn-berry_4.yarnBerryConfigHook`; optional platform-specific dependencies need a `missing-hashes.json` from `yarn-berry-fetcher missing-hashes`.

### Workspaces

`buildNpmPackage` handles npm workspaces with `npmWorkspace = "packages/app";` plus `npmDepsFetcherVersion = 2;`, which enables packument caching (the 26.05 release notes say it fixes workspace builds; the default is 1 and changing it invalidates `npmDepsHash`). pnpm workspaces use `pnpmWorkspaces = [ "<name>" ]` passed to both the derivation and `fetchPnpmDeps`, and a `pnpm --filter=<name> build` build phase.

### Embedding a frontend into another build

Build the frontend with `buildNpmPackage` or the pnpm hooks to produce `dist/`, then feed that derivation into a Rust or Go build's `preBuild` so the final binary embeds the assets. See [worked-example-gkg-orbit.md](worked-example-gkg-orbit.md).

### Escape hatch

When lockfile tooling can't keep up with a fast-moving setup, an impure derivation (`__noChroot = true;`) lets `npm` or `pnpm` reach the network. Nix only honors it with `sandbox = relaxed` in the daemon configuration. Use it sparingly and document why, and don't use it for nixpkgs packages.

### Dev shell

```nix
{ mkShell, nodejs, pnpm, typescript-language-server }:
mkShell { packages = [ nodejs pnpm typescript-language-server ]; }
```

`npm install`, `npm run`, `pnpm i`, and `pnpm build` work unchanged; only the build is Nixified. After a lockfile change, re-derive the hash (`prefetch-npm-deps`, or an update script). The old `pkgs.nodePackages.typescript-language-server` attribute is gone; use the top-level name. To get a Nix-managed `node_modules` in the shell, `importNpmLock.buildNodeModules` with `importNpmLock.hooks.linkNodeModulesHook` symlinks packages into place on shell entry; set `package-lock-only = true` in `.npmrc` so `npm add` edits only the lockfile.

## In nixpkgs

Applications go in `pkgs/by-name/<xx>/<name>/package.nix`. Library-only npm packages don't get packaged: the 25.05 and 25.11 release notes remove several `nodePackages` entries because "it is a library, and projects should depend on it instead". Reviewers commonly request `buildNpmPackage` over older mechanisms (support 27, 10 with formal changes-requested), and the older mechanisms are now deleted.

```nix
{
  lib,
  buildNpmPackage,
  fetchFromGitHub,
  nix-update-script,
  versionCheckHook,
}:

buildNpmPackage (finalAttrs: {
  pname = "example";
  version = "1.2.3";

  src = fetchFromGitHub {
    owner = "example";
    repo = "example";
    tag = "v${finalAttrs.version}";
    hash = lib.fakeHash;
  };

  npmDepsHash = lib.fakeHash;

  nativeInstallCheckInputs = [ versionCheckHook ];
  doInstallCheck = true;

  passthru.updateScript = nix-update-script { };

  meta = {
    description = "Short description without the package name";
    homepage = "https://example.org";
    license = lib.licenses.mit;
    maintainers = with lib.maintainers; [ ];
    mainProgram = "example";
  };
})
```

### Rules and arguments that trip people up

- Pick the package manager the lockfile belongs to, and match upstream's Node.js major version via `nodejs = nodejs_24;` (any `nodejs_N` attribute). Cryptic V8 errors usually mean the Node version is too new for the project.
- The default install phase runs `npm pack --json --dry-run` to decide which files to copy into `$out/lib/node_modules/<name>/`, and takes binaries and manpages from the `bin` and `man` keys of `package.json`. A package without those keys installs no executable.
- `dontNpmBuild = true;` for packages with no build script (the most common override in `pkgs/by-name`). `npmBuildScript = "..."` when the script isn't called `build`. Setting `buildPhase` or `installPhase` yourself also disables the matching default; keep `runHook preBuild` and the other hook calls in them.
- `npmFlags` goes to every npm command; the usual values are `[ "--ignore-scripts" ]` and `[ "--legacy-peer-deps" ]`. `npmInstallFlags`, `npmBuildFlags`, `npmPackFlags`, `npmRebuildFlags`, and `npmPruneFlags` target one command each. Use `npmPackFlags = [ "--ignore-scripts" ];` when the `prepack` script runs the build you already did.
- `buildNpmPackage` sets `strictDeps = true` and `dontStrip = true` by default and adds `nodejs`, `nodejs.python`, and (on Darwin) `cctools` to `nativeBuildInputs`.
- A lockfile missing upstream, or one that pins a yanked version: generate it with `npm install --package-lock-only`, commit it next to `package.nix`, copy it in with `postPatch = ''cp ${./package-lock.json} package-lock.json'';`, and use `nix-update-script { extraArgs = [ "--generate-lockfile" ]; }`. When you patch `package.json` or the lockfile, pass `patches` to the dependency fetcher too (`inherit (finalAttrs) patches;`), or the hash no longer matches.
- Changing `npmDepsFetcherVersion` or `fetcherVersion` changes the hash, and the config hook fails with "npmDepsHash is out of date" if the two disagree.
- A hash that never stabilizes between runs means the lockfile resolves something non-reproducible; fix the lockfile, don't bump the hash repeatedly.

### Native modules

Native addons (`node-gyp`, `node-pre-gyp`) compile at install time. The npm config hook already exports `npm_config_nodedir` and `npm_config_node_gyp`, and `nodejs.python` is on the path. You supply the rest: native libraries in `buildInputs`, `pkg-config` in `nativeBuildInputs`, and `npmFlags = [ "--build-from-source" ];` (seen in the tree) when an addon would otherwise try to download a prebuilt binary. For Electron apps, point `npm_config_nodedir` at `electron.headers` (an app in nixpkgs does this in `preConfigure`) and set `env.ELECTRON_SKIP_BINARY_DOWNLOAD = "1";`.

### pnpm in nixpkgs

Use the same shape as the flake example with `finalAttrs`, pin `pnpm` to a major version (`pnpm_11` in the manual's example), and set `fetcherVersion = 4`. Other arguments you'll meet: `pnpmRoot` plus `sourceRoot` on `fetchPnpmDeps` when the project sits in a subdirectory, `pnpmWorkspaces` for workspaces, `pnpmInstallFlags` and `prePnpmInstall` (these run in both the fetcher and the config hook, so pass them to `fetchPnpmDeps` with `inherit (finalAttrs)`), `pnpmBuildScript` and `pnpmBuildFlags` for the build hook, and `dontPnpmConfigure` and `dontPnpmBuild` to turn the hooks off.

### Checkable rules

- Node packages in nixpkgs use `buildNpmPackage` or the pnpm/yarn hooks; there is no reference to `nodePackages`, `node2nix`, `mkYarnPackage`, `pnpm.fetchDeps`, or `pnpm.configHook`.
- `npmDepsHash` (or `pnpmDeps`, `yarnOfflineCache`, `offlineCache`) is a real hash, not `lib.fakeHash` or an empty string.
- `fetchPnpmDeps` sets `fetcherVersion = 4` for new packages (3 is the minimum a current nixpkgs accepts).
- `pnpm` is a pinned `pnpm_N` attribute when the manual's guidance applies.
- Custom `buildPhase` or `installPhase` bodies call `runHook`.
- `src` uses `tag = "v${finalAttrs.version}"` where upstream tags releases.
- `passthru.updateScript` is set so bumps include the dependency hash.

### Evidence

| Rule | support | cr |
|---|---|---|
| Use `buildNpmPackage` for Node.js packages instead of legacy methods | 27 | 10 |
| Prefer the standard language builder (`buildNpmPackage` for Node.js) | 17 | 5 |
| Use `fetchYarnDeps` and `buildNpmPackage` for yarn and npm dependencies | 5 | 0 |

## Dated advice to ignore

- "Don't add packages to `nodePackages`; use `buildNpmPackage`": the direction is right, but the set was removed in 26.05, so the question no longer arises.
- "Prefer `mkYarnPackage` or `buildNpmPackage`" (seen in review rules): `mkYarnPackage`, `mkYarnModules`, and `yarn2nix` were removed; use the Yarn v1 hooks.
- `fixup_yarn_lock` and `yarn2nix-moretea`: removed together with `yarn2nix`.
- "`yarn2nix` is the only tool that supports npm workspaces": `buildNpmPackage` supports them with `npmWorkspace` and `npmDepsFetcherVersion = 2`.
- "`node2nix` is being migrated away from": it's already removed.
- `pnpm.fetchDeps`, `pnpm.configHook`, and `fetcherVersion = 1` or `2`: deprecated or removed; use `fetchPnpmDeps`, `pnpmConfigHook`, and `fetcherVersion = 4`.
