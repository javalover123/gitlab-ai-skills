# Node frontend via buildNpmPackage. Update npmDepsHash with scripts/update-deps.sh.
# pnpm projects use fetchPnpmDeps with pnpmConfigHook instead; npm workspaces
# keep buildNpmPackage and set npmWorkspace. See references/lang-nodejs.md.
{ buildNpmPackage }:
buildNpmPackage {
  pname = "REPLACE_ME";
  version = "0.1.0";
  src = ../../.;
  npmDepsHash = "sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=";
  installPhase = ''
    runHook preInstall
    cp -r dist $out
    runHook postInstall
  '';
}
