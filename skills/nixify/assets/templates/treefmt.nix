# treefmt-nix config. Exposed as `nix fmt` (flake `formatter`) and as a check.
{
  projectRootFile = "flake.nix";
  programs = {
    nixfmt.enable = true;        # Nix
    # rustfmt.enable = true;     # Rust
    # gofmt.enable = true;       # Go
    # rufo.enable = true;        # Ruby
    # ruff.enable = true;        # Python
    # prettier.enable = true;    # JS/TS/JSON/MD
    # clang-format.enable = true;# C/C++
  };
}
