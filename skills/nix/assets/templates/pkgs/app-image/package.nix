# Container image as a scoped output: packages.<system>.app-image.
# Default backend nix2container (fast push); swap to dockerTools.streamLayeredImage
# for zero extra inputs. `myapp` is a sibling package in pkgs/. `nix2container`
# ships no overlay, so it only resolves as an argument once flake.nix exposes it
# on `pkgs` (see the commented overlay in pkgsFor).
{
  nix2container,
  myapp,
  cacert,
}:
nix2container.buildImage {
  name = "registry.example.com/REPLACE_ME";
  tag = "latest";
  copyToRoot = [ cacert ];
  config = {
    Cmd = [ "${myapp}/bin/REPLACE_ME" ];
    Env = [ "SSL_CERT_FILE=${cacert}/etc/ssl/certs/ca-bundle.crt" ];
  };
}
