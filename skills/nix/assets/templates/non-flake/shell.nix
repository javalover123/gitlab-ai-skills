# shell.nix for a project without flakes. Enter it with `nix-shell`.
#
# nixpkgs is pinned with npins. One-time setup, from the project root:
#   npins init --bare
#   npins add github nixos nixpkgs --branch nixos-unstable
# `init --bare` writes npins/default.nix and an empty npins/sources.json;
# `add` fetches the branch head and records its revision and hash in
# sources.json (plain `npins init` also adds a nixpkgs pin). Commit the whole
# npins/ directory. Bump the pin with `npins update`; that's the only step that
# moves nixpkgs. `import ./npins` returns an attribute set of sources, and
# `sources.nixpkgs` is the pinned nixpkgs tree.
#
# Why not <nixpkgs>? It reads $NIX_PATH, so two machines can resolve it to
# different trees. Importing nixpkgs with `config = { }` and `overlays = [ ]`
# also keeps ~/.config/nixpkgs and system overlays out of the result.
{
  sources ? import ./npins,
  system ? builtins.currentSystem,
  pkgs ? import sources.nixpkgs {
    inherit system;
    config = { };
    overlays = [ ];
  },
}:
# mkShellNoCC has no C compiler; switch to mkShell if anything here builds C.
pkgs.mkShellNoCC {
  packages = [
    pkgs.jq
    pkgs.npins
  ];
}
