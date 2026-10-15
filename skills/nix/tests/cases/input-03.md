# Test Case: NixOS module for a small service

Write a NixOS module for `kvstored`, a daemon with about 40 upstream config keys. It reads a TOML
file, needs a data directory, listens on a port, and has an optional auth token the admin keeps in a
file outside the Nix store. I want it upstreamable to nixpkgs.
