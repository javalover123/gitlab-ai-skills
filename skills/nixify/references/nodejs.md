# Node.js — nixify playbook

**Default builder:** `buildNpmPackage` (npm), with pnpm hooks or yarn-berry for
the other package managers.
**Lockfile transform:** a fixed-output-derivation deps hash (no codegen).
**Golden rule:** use the Nix tool that *understands your lockfile*. Mismatches
(feeding a pnpm project to an npm builder) cause confusing install failures.

## Pick by lockfile

| Lockfile | Tool | Hash / mechanism | Notes |
|---|---|---|---|
| `package-lock.json` | `buildNpmPackage` | `npmDepsHash` (via `fetchNpmDeps`) | nixpkgs default. |
| `pnpm-lock.yaml` | `pnpmConfigHook` + `fetchPnpmDeps` | FOD store + `fetcherVersion` | Modern apps. |
| `yarn.lock` | `yarn2nix` / yarn-berry | parses yarn.lock | **Only tool supporting npm workspaces** per the nixpkgs manual. |

`node2nix` (codegen) is legacy — nixpkgs is migrating off it (issue #229475).
`npmlock2nix` / `nix-npm-buildpackage` are pre-1.0 and stumble on npm v7+
lockfile formats. Avoid all three for new work.

## buildNpmPackage (npm)

```nix
{ buildNpmPackage, lib }:
buildNpmPackage {
  pname = "myfrontend";
  version = "0.1.0";
  src = ../..;
  npmDepsHash = "sha256-AAAA…";        # fakeHash → build → copy real hash
  # npmBuildScript = "build";          # default is "build"
  # npmWorkspace = "packages/app";     # for a workspace member
  installPhase = ''
    runHook preInstall
    cp -r dist $out
    runHook postInstall
  '';
}
```

`makeCacheWritable = true;` helps some toolchains; for Electron set
`ELECTRON_SKIP_BINARY_DOWNLOAD=1`.

## pnpm

```nix
{ stdenv, nodejs, pnpm, lib }:
stdenv.mkDerivation (finalAttrs: {
  pname = "myapp"; version = "0.1.0"; src = ../..;
  nativeBuildInputs = [ nodejs pnpm.configHook ];
  pnpmDeps = pnpm.fetchDeps {
    inherit (finalAttrs) pname version src;
    fetcherVersion = 1;
    hash = "sha256-AAAA…";
  };
  buildPhase = ''pnpm run build'';
  installPhase = ''cp -r dist $out'';
})
```

Set `NPM_CONFIG_IGNORE_SCRIPTS=true` (or pnpm's equivalent) to block
postinstall scripts that try to download binaries at build time.

## Workspaces

For monorepos with npm workspaces, **yarn-berry / yarn2nix** is currently the
reliable path (the nixpkgs manual notes buildNpmPackage's workspace support is
limited). pnpm workspaces work via the pnpm hook scoped to a member.

## Embedding a frontend into another build

A common pattern (and the GKG/Orbit case): build the frontend with
`buildNpmPackage`/pnpm to produce `dist/`, then feed that derivation into a Rust
or Go build's `preBuild` so the final binary embeds the assets. See
`references/worked-example-gkg-orbit.md`.

## Escape hatch

When lockfile tooling can't keep up with a fast-moving npm setup, an impure
build (`__noChroot = true`, "the heretic way") lets `npm`/`pnpm` run with
network access while the rest stays sandboxed. Use sparingly and document it.

## Dev shell

```nix
mkShell { packages = [ pkgs.nodejs pkgs.pnpm pkgs.nodePackages.typescript-language-server ]; }
```

`npm install`, `npm run`, `pnpm i`, `pnpm build` work unchanged. Only the *build*
is Nixified; the `node_modules` dev workflow is untouched. After a lockfile
change, re-derive the deps hash (automated by the update script).
