# Rust app via crane + rust-overlay toolchain. craneLib and rustToolchain are
# provided by the flake scope (callPackage args).
{ craneLib, rustToolchain, pkg-config, openssl, lib }:
let
  crane = craneLib.overrideToolchain rustToolchain;
  src = crane.cleanCargoSource ../../.;
  commonArgs = {
    inherit src;
    strictDeps = true;
    nativeBuildInputs = [ pkg-config ];
    buildInputs = [ openssl ];
  };
  cargoArtifacts = crane.buildDepsOnly commonArgs;
in
crane.buildPackage (commonArgs // { inherit cargoArtifacts; })
