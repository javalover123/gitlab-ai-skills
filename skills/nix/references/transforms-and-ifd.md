# Transforms & IFD — the dependency-import philosophy

**Principle:** transform the dependency manager's own artifact (the lockfile)
into Nix. Developers never hand-edit a Nix list of dependencies. There are three
mechanisms, with a real performance/ergonomics tradeoff between them.

## The three mechanisms

| Strategy | Examples | Eval cost | Dep-bump step | Caching | CI friendliness |
|---|---|---|---|---|---|
| **FOD vendor hash** | `buildGoModule` `vendorHash`, `buildNpmPackage` `npmDepsHash`, `buildRustPackage` `cargoHash`, `fetchPnpmDeps` | cheap (one FOD) | bump one hash | coarse (one big blob) | **best** — pure eval |
| **Committed generated Nix** | gomod2nix `gomod2nix.toml`, bundix `gemset.nix`, cargo2nix `Cargo.nix`, crate2nix | cheap (no IFD) | re-run generator + commit | granular (per-module) | **good** — pure eval, reviewable diff |
| **Lockfile parsed at eval time** | crane, poetry2nix, uv2nix, `importCargoLock` | **moderate** (a Nix-language parse of the lockfile; **expensive** if it becomes IFD, see below) | none (zero generated files / hashes; `importCargoLock` still needs `outputHashes` for git dependencies) | tool-dependent | **good if the lockfile is a plain source path**, **needs care** if it is read from a build output |

## What IFD is, and why it matters

Import-from-derivation = the Nix evaluator needs the *result of building
something* in order to continue evaluating (e.g. a tool parses `Cargo.lock` into
Nix at eval time).

> When the store path needs to be accessed, evaluation is paused, the
> corresponding store object is realised, and then evaluation resumes.

Because Nix evaluation is typically single-threaded, IFD can make evaluation
**stall** until those builds finish — which is exactly why **IFD is not allowed
inside nixpkgs** (`pkgs/README.md`: Hydra evaluates the whole package set, and
sequential builds during evaluation would make evaluation times impractical).
Not every CI supports it: Hercules CI added native IFD support
but notes evaluation blocks until the IFD builds complete. IFD can be disabled
entirely with `allow-import-from-derivation = false`.

**Reading a lockfile isn't IFD by itself.** `builtins.readFile` plus
`builtins.fromTOML` on a file that's already in the evaluated source (a path in
your repository or a flake input) is pure evaluation. It becomes IFD only when
the file lives in a store path that has to be *built* first, such as
`"${src}/Cargo.lock"` where `src` is a `fetchFromGitHub` result, or a lockfile a
derivation generated. nixpkgs' `rustPlatform.importCargoLock` reads the lock with
`readFile` and `fromTOML` (see `pkgs/build-support/rust/import-cargo-lock.nix`),
so `importCargoLock { lockFile = ./Cargo.lock; }` with a committed file
is IFD-free, while pointing `lockFile` at a fetched source makes it IFD. uv2nix
likewise reads `uv.lock` in pure Nix at evaluation time. For crane and
poetry2nix, apply the same test: where does the lockfile or manifest they read
come from?

## nixify defaults

1. **Prefer FOD vendor-hash or committed-generated transforms** for CI eval
   performance. These keep `nix flake check` fast and work on every CI.
2. **Always ship a one-command update path** so the "annoying" hash bump or
   generator re-run is trivial:
   - Go: re-derive `vendorHash` (set `lib.fakeHash`, build, copy) — or
     `gomod2nix generate`.
   - Ruby: `bundle lock && bundix` → `gemset.nix`.
   - Node: re-derive `npmDepsHash` / pnpm deps hash.
   `scripts/update-deps.sh` wraps these per detected language.
3. **Use lockfile-parsing tooling (crane, poetry2nix, uv2nix) when its
   ergonomics win** — notably Rust (crane's caching is worth it) and Python
   (uv2nix for `uv.lock`). Keep the lockfile a plain source path so evaluation
   stays IFD-free. If a setup does read a build output, **confirm the team's CI
   tolerates the eval cost** and document the `allow-import-from-derivation`
   requirement in the MR.

## Why this matters for "near-zero Nix interaction"

The whole point of transforms is that the developer's mental model stays
"`Cargo.toml` + `cargo update`" / "`Gemfile` + `bundle`". The lockfile is the
contract. The only residue is either (a) a hash to bump or (b) a generated file
to regenerate — both reduced to one command. Hand-maintaining a Nix dependency
list (the thing this principle forbids) is what makes Nix adoption fail in
practice, because it creates a second source of truth the developer must keep in
sync by hand.
