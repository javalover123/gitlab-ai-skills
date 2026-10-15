# treefmt-nix config. Exposed as `nix fmt` (flake `formatter`).
#
# Program names were checked against github:numtide/treefmt-nix (Oct 2026):
# `programs.ruff` no longer exists; Python uses `ruff-format` and `ruff-check`.
{
  projectRootFile = "flake.nix";
  programs = {
    nixfmt.enable = true; # Nix
    # rustfmt.enable = true; # Rust
    # gofmt.enable = true; # Go
    # rufo.enable = true; # Ruby
    # ruff-format.enable = true; # Python formatting
    # ruff-check.enable = true; # Python lint fixes
    # prettier.enable = true; # JS, TS, JSON, Markdown
    # clang-format.enable = true; # C and C++
  };
}
