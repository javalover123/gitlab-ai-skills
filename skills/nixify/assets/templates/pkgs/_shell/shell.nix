# devShells.default. Put the project's NATIVE toolchain here, pinned.
# The goal: cargo/go/bundle/uv/npm behave exactly as outside Nix.
{ mkShell, pkgs }:
mkShell {
  packages = with pkgs; [
    # --- pick per language ---
    # rustToolchain rust-analyzer cargo-nextest
    # go gopls gotools
    # ruby_3_3 bundix
    # uv python312            (or poetry)
    # nodejs pnpm
    # cmake ninja pkg-config clang-tools
    # --- shared niceties ---
    treefmt
  ];
  # RUST_SRC_PATH = "${pkgs.rustToolchain}/lib/rustlib/src/rust/library";
}
