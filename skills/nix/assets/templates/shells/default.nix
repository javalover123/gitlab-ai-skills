# devShells.default. Lives outside pkgs/ because everything under pkgs/ is
# autoloaded as a package. Put the project's native toolchain here so cargo,
# go, bundle, uv and npm behave exactly as they do outside Nix.
#
# mkShell brings a C compiler; use mkShellNoCC when nothing here compiles C,
# links through cc, or builds native extensions.
{
  mkShell,
  jq,
  # Add the toolchain by argument name, for example:
  #   go gopls gotools          (Go)
  #   rustc cargo rust-analyzer (Rust, or a rust-overlay toolchain)
  #   uv python3                (Python)
  #   nodejs pnpm               (Node.js)
  #   cmake ninja pkg-config clang-tools (C and C++)
}:
mkShell {
  packages = [
    jq
  ];
}
