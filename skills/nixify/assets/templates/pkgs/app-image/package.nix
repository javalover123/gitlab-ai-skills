# Container image as a scoped output: packages.<system>.app-image.
# Default backend nix2container (fast push); swap to dockerTools.streamLayeredImage
# for zero extra inputs. `nix2container` and `myapp` come from the flake scope.
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
