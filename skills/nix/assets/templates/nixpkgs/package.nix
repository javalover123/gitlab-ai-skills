# pkgs/by-name/fo/foo/package.nix
# `fo` is the first two characters of the attribute name, lowercased. The
# attribute exists automatically; nothing is added to all-packages.nix.
# Build with `nix-build -A foo` from a nixpkgs checkout.
{
  lib,
  stdenv,
  fetchFromGitHub,
  cmake,
  pkg-config,
  zlib,
  versionCheckHook,
  nix-update-script,
}:

stdenv.mkDerivation (finalAttrs: {
  pname = "foo";
  version = "1.2.3";

  src = fetchFromGitHub {
    owner = "example";
    repo = "foo";
    # `tag` makes the fetcher fail if upstream moves it; `rev` doesn't.
    tag = "v${finalAttrs.version}";
    # lib.fakeHash fails the first build and prints the real hash to paste.
    hash = lib.fakeHash;
  };

  # New top-level packages must enable both; strictDeps makes a misplaced
  # input fail in a native build instead of only when cross-compiling.
  __structuredAttrs = true;
  strictDeps = true;

  # Tools that run during the build.
  nativeBuildInputs = [
    cmake
    pkg-config
  ];

  # Libraries the binary links against.
  buildInputs = [ zlib ];

  # Runs `foo --version` (then `--help`) after install and fails the build if
  # the version string is missing. Needs meta.mainProgram.
  doInstallCheck = true;
  nativeInstallCheckInputs = [ versionCheckHook ];

  passthru.updateScript = nix-update-script { };

  meta = {
    description = "Tool that does a thing";
    homepage = "https://example.org/foo";
    changelog = "https://example.org/foo/releases/tag/${finalAttrs.src.tag}";
    license = lib.licenses.mit;
    # Your handle, registered in maintainers/maintainer-list.nix in an earlier
    # commit: maintainers = with lib.maintainers; [ yourhandle ];
    maintainers = [ ];
    mainProgram = "foo";
    platforms = lib.platforms.unix;
  };
})
