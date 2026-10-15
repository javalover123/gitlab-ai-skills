# C/C++ artifact via stdenv.mkDerivation. Build-system hook auto-configures.
{
  stdenv,
  cmake,
  pkg-config,
  openssl,
  zlib,
}:
stdenv.mkDerivation {
  pname = "REPLACE_ME";
  version = "1.0.0";
  src = ../../.;
  strictDeps = true;
  nativeBuildInputs = [
    cmake
    pkg-config
  ];
  buildInputs = [
    openssl
    zlib
  ];
  # cmakeFlags = [ "-DBUILD_TESTING=ON" ];
}
