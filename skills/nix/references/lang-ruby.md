# Ruby

Load this when you package a Ruby application, a gem-based CLI, or a gem with native extensions, in your own flake or in nixpkgs. Both routes use the same pipeline: `bundix` turns `Gemfile.lock` into a committed `gemset.nix`, and `bundlerEnv` or `bundlerApp` consumes it with no import-from-derivation.

**Contents:** [Choosing the approach](#choosing-the-approach) · [In your own flake or project](#in-your-own-flake-or-project) · [In nixpkgs](#in-nixpkgs) · [Dated advice to ignore](#dated-advice-to-ignore)

## Choosing the approach

| Goal | Own flake or project | nixpkgs |
|---|---|---|
| Whole application environment, dev shell | `bundlerEnv` with `gemdir` (and `groups` if you filter) | rarely; prefer `bundlerApp` for an installable app |
| Gem-based CLI or app with named executables | `bundlerApp` with `exes` | `bundlerApp` in `pkgs/by-name`, `bundlerUpdateScript` as `updateScript` |
| A gem that other gems or users `require` | `ruby.withPackages` | add to `rubyPackages` (`with-packages/Gemfile`, then `update-ruby-packages`) |
| Native-extension gem needs libraries or flags | `gemConfig` override | entry in `gem-config/default.nix` |
| One gem built by hand | `buildRubyGem` | seldom needed; the generated set covers it |

## In your own flake or project

### The transform pipeline

```
Gemfile --(bundle lock)--> Gemfile.lock --(bundix)--> gemset.nix --(bundlerEnv)--> env
```

`bundix` walks the lockfile and writes `gemset.nix`, a committed file mapping each gem to its version, source, and hash. Nix needs a checksum per input and `Gemfile.lock` doesn't carry one, which is why the extra file exists. Regenerate it whenever `Gemfile.lock` changes:

```bash
bundle lock              # developer's normal step
bundix                   # regenerate gemset.nix (commit it)
```

`bundix -l` also creates a fresh `Gemfile.lock` when the `Gemfile` is newer. Ship the one-command update path as `scripts/update-deps.sh`.

### `bundlerEnv`: application or dev environment

```nix
{ bundlerEnv, ruby_3_4 }:
bundlerEnv {
  name = "myapp-gems";
  ruby = ruby_3_4;
  gemdir = ./.;                 # directory with Gemfile, Gemfile.lock, gemset.nix
  # Optional filter. `default` is always kept; leave `groups` out to keep every gem.
  groups = [ "default" "production" "development" "test" ];
}
```

`bundlerEnv` exposes `wrappedRuby`, a Ruby with the gems on its load path. In a dev shell, put both the env and `env.wrappedRuby` on the path so `ruby`, `irb`, and `bundle` resolve the gems. If the gemset includes `bundler` itself, `/bin/bundle` collides with the one from Ruby; wrap one side in `lowPrio` (`(lib.lowPrio gems.wrappedRuby)`).

### `bundlerApp`: CLI tools

Use this when you want named executables only (a gem-based CLI). It avoids the `bin/rake` and `bin/bundler` collisions `bundlerEnv` can cause:

```nix
{ bundlerApp }:
bundlerApp {
  pname = "mytool";
  gemdir = ./.;
  exes = [ "mytool" ];          # only these end up on PATH
}
```

When the tool shells out to other programs, wrap it in `postBuild` with `makeWrapper` (add `nativeBuildInputs = [ makeWrapper ];`) rather than patching the gem:

```nix
{ bundlerApp, makeWrapper, lib, git }:
bundlerApp {
  pname = "mytool";
  gemdir = ./.;
  exes = [ "mytool" ];
  nativeBuildInputs = [ makeWrapper ];
  postBuild = ''
    wrapProgram $out/bin/mytool --prefix PATH : ${lib.makeBinPath [ git ]}
  '';
}
```

### Native-extension gems (pg, nokogiri, sqlite3, ...)

Gems with C extensions need build inputs and sometimes configure flags. nixpkgs already patches many in `pkgs/development/ruby-modules/gem-config/default.nix`; check there first, because `defaultGemConfig` has entries for `pg` and `nokogiri` already. Override `gemConfig` locally when you need a different library (a particular PostgreSQL major, say) or a private gem:

```nix
{ bundlerEnv, defaultGemConfig, postgresql_16, libxml2, libxslt, zlib, pkg-config }:
bundlerEnv {
  name = "myapp-gems";
  gemdir = ./.;
  gemConfig = defaultGemConfig // {
    pg = attrs: {
      buildFlags = [ "--with-pg-config=${postgresql_16.pg_config}/bin/pg_config" ];
    };
    nokogiri = attrs: {
      nativeBuildInputs = [ pkg-config ];
      buildInputs = [ libxml2 libxslt zlib ];
    };
  };
}
```

The same `gemConfig` argument works on `ruby.override { defaultGemConfig = ...; }` for `ruby.withPackages`, and through an overlay on `defaultGemConfig`. If a gem isn't handled, add it here rather than patching the Gemfile.

### Dev shell

```nix
{ mkShell, bundlerEnv, bundix, ruby_3_4 }:
let
  gems = bundlerEnv {
    name = "myapp-gems";
    ruby = ruby_3_4;
    gemdir = ../..;
    groups = [ "default" "development" "test" ];
  };
in
mkShell {
  packages = [ gems gems.wrappedRuby bundix ];
}
```

In `.envrc`, add `watch_file gemset.nix` so the shell reloads when gems change. Files that bundler reads at runtime, such as `.ruby-version` or vendored gems the Gemfile references, must reach the build via `extraConfigPaths = [ "${./.}/.ruby-version" ];` on `bundlerEnv`, or they aren't visible in the sandboxed build.

### Alternatives and gotchas

- **ruby-nix and the inscapist bundix fork** target app developers rather than package maintainers: they track only `gemset.nix` instead of a whole directory and ship a flake template (`nix flake init -t github:inscapist/ruby-nix`). Consider them if stock bundix is awkward for a large app.
- **Precompiled platform gems** are a known bundix problem (see bundix PR 68, linked from the manual). Make bundler pick source gems: `bundle config set --local force_ruby_platform true` (project) or `bundle config set force_ruby_platform true` (global). The nixpkgs update script sets `BUNDLE_FORCE_RUBY_PLATFORM=1` for the same reason.
- **Groups:** when `groups` is set, `bundled-common` keeps gems in `default` plus the listed groups and drops the rest, so missing dev or test gems in a shell usually mean a `groups` list that omits them. With `groups` unset (`null`) the filter is off and every gem in `gemset.nix` is built.
- Large Rails apps work with this exact approach: `bundlerEnv`, the full `groups` list, and `gemConfig` overrides for the few native gems.

### What the developer still does

`bundle add`, `bundle update`, `bundle exec`, `rails`, `rake`, and `irb` all work as before. The only new step is regenerating `gemset.nix` after a lockfile change, which the update script automates.

## In nixpkgs

There are three places a Ruby change can land, and picking the right one is most of the work.

| You're adding | Where | Mechanism |
|---|---|---|
| An application or CLI | `pkgs/by-name/<xx>/<name>/` with `package.nix`, `Gemfile`, `Gemfile.lock`, `gemset.nix` | `bundlerApp` plus `bundlerUpdateScript` |
| A library gem for `ruby.withPackages` and `rubyPackages` | `pkgs/development/ruby-modules/with-packages/Gemfile` | `./maintainers/scripts/update-ruby-packages` regenerates `pkgs/top-level/ruby-packages.nix` |
| A fix for a native-extension gem | `pkgs/development/ruby-modules/gem-config/default.nix` | an `attrs: { ... }` entry named after the gem |

`ruby` currently points at `ruby_3_4` in `all-packages.nix`, although the manual text still says MRI 3.3. Trust the tree.

### Packaging an application

Write a `Gemfile` naming the gem, then generate the lock files (`bundle lock`, `bundix`). Pin a version with `gem 'mdl', '0.5.0'` when you need one; otherwise rerunning the two commands picks up the latest.

```nix
{ lib, bundlerApp, bundlerUpdateScript }:

bundlerApp {
  pname = "example";
  gemdir = ./.;
  exes = [ "example" ];

  passthru.updateScript = bundlerUpdateScript "example";

  meta = {
    description = "Short description without the package name";
    homepage = "https://example.org";
    license = lib.licenses.mit;
    maintainers = with lib.maintainers; [ ];
    platforms = lib.platforms.unix;
  };
}
```

`bundlerUpdateScript "<attrPath>"` deletes `gemset.nix` and `Gemfile.lock`, exports `BUNDLE_FORCE_RUBY_PLATFORM=1`, runs `bundler lock --update` and `bundix`, then formats the result with `nixfmt`. It finds the directory through `meta.position`, so the attribute path must evaluate.

### Rules and arguments that trip people up

- `bundlerApp` takes `pname` (the gem name; the version comes from the gemset), `gemdir`, `exes`, optionally `scripts` for Ruby programs that depend on the gems (such as `scripts/rails`), `postBuild`, `gemConfig`, `nativeBuildInputs`, and `buildInputs`. List every executable you want in `exes`; anything not listed isn't exposed.
- `bundlerEnv` takes `name` or `pname`; with only `pname`, the main gem must exist in the gemset or evaluation throws. `groups` defaults to `null` (no filtering); set it only when you want to drop groups.
- A gem with C extensions that needs system libraries gets `buildInputs` (and `nativeBuildInputs = [ pkg-config ]` when it probes with pkg-config) through `gemConfig` or `gem-config/default.nix`. Reviewers commonly ask for this when a gem has undeclared native dependencies (support 25, 3 with formal changes-requested).
- Prefer system libraries over the gem's bundled copy, as the `nokogiri` entry does (`--use-system-libraries` with explicit include and lib paths), and avoid `--with-pg-config=${postgresql}/bin/pg_config` where pkg-config can find `libpq`; the `pg` entry says the first form adds a reference to the whole PostgreSQL package.
- Runtime tools the gem calls via `PATH` belong in a `postBuild` wrapper, not in `buildInputs`.
- Don't hand-edit `gemset.nix`; rerun `bundix`. Check the generated set with the security audit script (`./maintainers/scripts/audit-ruby-packages/audit-ruby-packages.bash`) when you add to the shared Gemfile.
- Test a new shared gem with `NIX_PATH=nixpkgs=$PWD nix-shell -p "ruby.withPackages (ps: with ps; [ name-of-your-gem ])"`.

### Checkable rules

- Ruby applications use `bundlerApp` (or `bundlerEnv` with a justification), not hand-assembled `buildRubyGem` stacks.
- `gemdir` contains `Gemfile`, `Gemfile.lock`, and `gemset.nix`, all committed.
- `exes` is non-empty for `bundlerApp`.
- `passthru.updateScript = bundlerUpdateScript "<attr>";` is present.
- Native-extension gems have a `gem-config` or `gemConfig` entry that supplies their libraries.
- Package attributes don't depend on a bare `ruby` alias when a version-specific attribute is required; use `ruby_3_4` and friends explicitly.

### Evidence

| Rule | support | cr |
|---|---|---|
| Use `gemConfig` to inject native dependencies into `buildInputs` | 25 | 3 |
| Use `bundlerApp` instead of `bundlerEnv` for Ruby applications | 5 | 2 |
| Ruby applications should use `bundlerApp` with proper lock file management | 6 | 1 |

## Dated advice to ignore

- The manual still says the default `ruby` is MRI 3.3; `all-packages.nix` sets `ruby = ruby_3_4`.
- Older nixify guidance said `bundlerEnv` exposes only the `default` group unless you list the others. In the current source a `null` `groups` keeps every gem; only an explicit list filters.
