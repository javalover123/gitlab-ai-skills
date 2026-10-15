# Rust app via crane + rust-overlay toolchain. craneLib and rustToolchain aren't
# in nixpkgs; supply them as callPackage arguments from an overlay in flake.nix
# (after adding the crane and rust-overlay inputs, with rust-overlay's overlay
# listed first):
#   final: _prev: {
#     craneLib = inputs.crane.mkLib final;
#     rustToolchain = final.rust-bin.fromRustupToolchainFile ./rust-toolchain.toml;
#   }
# For a package headed to nixpkgs use rustPlatform.buildRustPackage instead.
{
  craneLib,
  rustToolchain,
  pkg-config,
  openssl,
}:
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
