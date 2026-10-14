# Node frontend via buildNpmPackage. Update npmDepsHash with scripts/update-deps.sh.
# For pnpm use the pnpm.configHook pattern; for workspaces use yarn-berry.
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
