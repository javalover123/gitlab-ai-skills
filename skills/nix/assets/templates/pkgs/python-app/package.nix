# Python app. For Poetry projects use poetry2nix.mkPoetryApplication instead.
# This sketch assumes a uv2nix-built pythonSet threaded via the scope.
{ pythonSet, workspace }:
pythonSet.mkVirtualEnv "REPLACE_ME-env" workspace.deps.default
