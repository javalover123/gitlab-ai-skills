# Test Case: Review a package submitted to nixpkgs

Review this `pkgs/by-name/fo/foo-cli/package.nix` before the author opens a PR.

```nix
{ lib, stdenv, fetchFromGitHub, cmake, openssl, darwin }:

stdenv.mkDerivation rec {
  name = "foo-cli-${version}";
  version = "2.4.0";

  src = fetchFromGitHub {
    owner = "example";
    repo = "foo-cli";
    rev = version;
    sha256 = "0r1bz6f0m1f4q4w4f1m5r1n8a3b0x7m0z0k9n3y2c1p5s8d7h6g4";
  };

  buildInputs = [ cmake openssl ] ++ lib.optionals stdenv.isDarwin [ darwin.apple_sdk.frameworks.Security ];

  doCheck = false;

  postPatch = ''
    sed -i 's|/usr/bin/openssl|${openssl}/bin/openssl|' src/main.c
  '';

  meta = with lib; {
    description = "A command line tool for foo.";
    license = licenses.gpl3;
  };
}
```
