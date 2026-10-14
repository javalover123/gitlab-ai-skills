# Container image as a scoped output: packages.<system>.app-image.
# Default backend nix2container (fast push); swap to dockerTools.streamLayeredImage
# for zero extra inputs. `myapp` is this flake's own package; `nix2container`
# is exposed into pkgs by the overlay in flake.nix's pkgsFor (it ships no
# overlay of its own, so without that this callPackage would fail to resolve
# the argument).
{ nix2container, myapp, cacert }:
nix2container.buildImage {
  name = "registry.example.com/REPLACE_ME";
  tag = "latest";
  copyToRoot = [ cacert ];
  config = {
    Cmd = [ "${myapp}/bin/REPLACE_ME" ];
    Env = [ "SSL_CERT_FILE=${cacert}/etc/ssl/certs/ca-bundle.crt" ];
  };
}
