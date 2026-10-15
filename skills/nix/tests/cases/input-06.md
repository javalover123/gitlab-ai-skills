# Test Case: Report on finished work

You bumped `pkgs/by-name/ba/bar/package.nix` from 1.2 to 1.3 (version and `src.hash` changed, nothing
else). You then ran `scripts/gates.sh --context nixpkgs` in a sandbox with Nix and the nixpkgs checkout
but no aarch64 or Darwin builders, no GitHub access, and no `nixpkgs-review`. This is its full output:

```
context: nixpkgs
files in scope: 1
PASS antipatterns: 1 file(s) vs review-derived rules
PASS parse: nix-instantiate --parse
SKIP format: nixfmt not found (try: nix shell nixpkgs#nixfmt)
PASS eval bar: nix-instantiate -A bar
PASS build bar: nix-build -A bar
PASS meta bar: meta evaluates
SKIP by-name vet: ci/nixpkgs-vet.sh needs network access to fetch the base branch

Gates run:   antipatterns PASS parse PASS eval bar PASS build bar PASS meta bar PASS
Not run:     format (nixfmt not found) by-name vet (network) manual: passthru.tests / nixosTests manual: nixpkgs-review wip manual: build on each platform in meta.platforms
```

The package's `meta.platforms` lists x86_64-linux, aarch64-linux, and aarch64-darwin, and `bar` has
three dependent packages. The build ran on x86_64-linux. Tell me where this stands before I open the PR.
