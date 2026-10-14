# Ruby — nixify playbook

**Default builder:** `bundlerEnv` (whole gemset) and `bundlerApp` (CLI tools).
**Lockfile transform:** `bundix` → committed `gemset.nix` (no IFD).
**Why:** lowest friction, no eval-time impurity, reviewable diffs, and the
developer keeps using `bundle` / `bundle exec` / `ruby` exactly as before.

## The transform pipeline

```
Gemfile --(bundle lock)--> Gemfile.lock --(bundix)--> gemset.nix --(bundlerEnv)--> env
```

`bundix` is "the Nix transformation of the Gemfile.lock": it walks the lockfile
and writes `gemset.nix`, a committed file mapping each gem to its version,
source, and hash. Regenerate it whenever `Gemfile.lock` changes:

```bash
bundle lock              # developer's normal step
bundix                   # regenerate gemset.nix (commit it)
```

Ship this as the one-command update path (`scripts/update-deps.sh` handles it).

## Builders

### `bundlerEnv` — application / dev environment

```nix
{ bundlerEnv, ruby_3_3 }:
bundlerEnv {
  name = "myapp-gems";
  ruby = ruby_3_3;
  gemdir = ./.;                 # dir containing Gemfile, Gemfile.lock, gemset.nix
  # Expose more than the default group — Rails apps usually need these:
  groups = [ "default" "production" "development" "test" ];
}
```

`bundlerEnv` exposes `wrappedRuby` (a Ruby with the gems on its load path). In a
dev shell, put both the env and `env.wrappedRuby` on the path so `ruby`, `irb`,
`bundle` all resolve the gems.

### `bundlerApp` — CLI tools (preferred for tool packages)

Use this when you only want named executables (e.g. packaging a gem-based CLI).
It avoids the `bin/rake` / `bin/bundler` path-collision problems `bundlerEnv`
can cause when you only need one binary:

```nix
{ bundlerApp }:
bundlerApp {
  pname = "mytool";
  gemdir = ./.;
  exes = [ "mytool" ];          # only these end up on PATH
}
```

### `buildRubyGem` — a single gem (rare; usually for nixpkgs contribution)

## Native-extension gems (pg, nokogiri, sqlite3, …)

Gems with C extensions need build inputs and sometimes configure flags. nixpkgs
patches the common ones centrally in `pkgs/development/ruby-modules/gem-config/`.
Locally, override `gemConfig`:

```nix
bundlerEnv {
  # …
  gemConfig = pkgs.defaultGemConfig // {
    pg = attrs: {
      buildInputs = [ pkgs.postgresql ];
      buildFlags = [ "--with-pg-config=${pkgs.postgresql}/bin/pg_config" ];
    };
    nokogiri = attrs: {
      buildInputs = [ pkgs.libxml2 pkgs.libxslt pkgs.zlib ];
    };
  };
}
```

If you hit a gem that isn't handled, add it here rather than patching the
Gemfile.

## Dev shell

```nix
{ mkShell, bundlerEnv, ruby_3_3 }:
let gems = bundlerEnv { name = "myapp-gems"; ruby = ruby_3_3; gemdir = ../..; groups = [ "default" "development" "test" ]; };
in mkShell {
  packages = [ gems gems.wrappedRuby pkgs.bundix ];
}
```

In `.envrc`, add `watch_file gemset.nix` so the shell reloads when gems change.

`.ruby-version` and similar config files that bundler reads at runtime must be
passed via `extraConfigPaths` to `bundlerEnv`, or they won't be visible in the
sandboxed build.

## Alternatives & gotchas

- **ruby-nix / inscapist bundix fork** — a fork "to better meet the needs of
  ruby app developers instead of package maintainers"; tracks only `gemset.nix`
  rather than a whole directory, and ships a flake template
  (`nix flake init -t github:inscapist/ruby-nix`). Consider it if the stock
  bundix workflow is awkward for a large app.
- **Platform-specific precompiled gems** are a known bundix pain point
  (precompiled native gems with platform suffixes). The reliable workaround is
  forcing build-from-source (avoid committing `BUNDLE_FORCE_RUBY_PLATFORM`
  conflicts; set bundler to the ruby platform so bundix sees source gems).
- **Groups:** `bundlerEnv` exposes only the `default` group unless you list the
  others. Missing dev/test gems in the shell is almost always a `groups`
  omission.
- Large Rails apps (GitLab-shaped) work with this exact approach: `bundlerEnv` +
  full `groups` + `gem-config` overrides for the handful of native gems.

## What the developer still does, unchanged

`bundle add`, `bundle update`, `bundle exec`, `rails`, `rake`, `irb` — all
normal. The only new step is regenerating `gemset.nix` after a lockfile change,
which the update script automates.
