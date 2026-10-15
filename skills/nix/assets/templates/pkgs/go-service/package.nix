# Go service via buildGoModule. Update vendorHash with scripts/update-deps.sh.
{ buildGoModule, lib }:
buildGoModule {
  pname = "REPLACE_ME";
  version = "0.1.0";
  src = lib.cleanSource ../../.;
  vendorHash = lib.fakeHash; # build once, then paste the hash from the error
  ldflags = [
    "-s"
    "-w"
  ];
  meta.mainProgram = "REPLACE_ME";
}
