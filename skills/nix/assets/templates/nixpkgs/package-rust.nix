# pkgs/by-name/ex/example/package.nix
# A Rust program built with rustPlatform.buildRustPackage and the compiler
# nixpkgs ships. crane, rust-overlay and fenix belong in your own flakes;
# nixpkgs doesn't accept them (they need import-from-derivation or extra inputs).
{
  lib,
  rustPlatform,
  fetchFromGitHub,
  versionCheckHook,
  nix-update-script,
}:

rustPlatform.buildRustPackage (finalAttrs: {
  pname = "example";
  version = "1.2.3";

  src = fetchFromGitHub {
    owner = "example";
    repo = "example";
    tag = "v${finalAttrs.version}";
    hash = lib.fakeHash;
  };

  # Hash of the vendored crates, built from upstream's Cargo.lock. Use
  # lib.fakeHash, build, paste the hash from the error. cargoSha256 is gone.
  cargoHash = lib.fakeHash;

  __structuredAttrs = true;

  # Tests run by default. Skip individual tests and say why:
  # checkFlags = [ "--skip=tests::needs_network" ];

  doInstallCheck = true;
  nativeInstallCheckInputs = [ versionCheckHook ];

  passthru.updateScript = nix-update-script { };

  meta = {
    description = "Tool that does a thing";
    homepage = "https://github.com/example/example";
    changelog = "https://github.com/example/example/releases/tag/${finalAttrs.src.tag}";
    license = lib.licenses.mit;
    maintainers = [ ];
    mainProgram = "example";
  };
})
