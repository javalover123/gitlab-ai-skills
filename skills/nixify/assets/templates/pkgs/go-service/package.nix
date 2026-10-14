# Go service via buildGoModule. Update vendorHash with scripts/update-deps.sh.
{ buildGoModule, lib }:
buildGoModule {
  pname = "REPLACE_ME";
  version = "0.1.0";
  src = lib.cleanSource ../../.;
  vendorHash = "sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=";  # lib.fakeHash → build → paste
  ldflags = [ "-s" "-w" ];
  meta.mainProgram = "REPLACE_ME";
}
