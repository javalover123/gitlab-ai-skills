# Set up a local docs.gitlab.com preview

`<skill-dir>` is the docs-preview skill directory. Run its scripts as
`<skill-dir>/scripts/...` from any directory.

Contents:

- [How the preview works](#how-the-preview-works)
- [Directory layout and mounts](#directory-layout-and-mounts)
- [Tools and versions](#tools-and-versions)
- [Start a preview](#start-a-preview)
- [Run detached and wait](#run-detached-and-wait)
- [Strict build (what CI runs)](#strict-build-what-ci-runs)
- [Pitfalls](#pitfalls)
- [Stop a preview](#stop-a-preview)

## How the preview works

docs.gitlab.com is one Hugo site in
[docs-gitlab-com](https://gitlab.com/gitlab-org/technical-writing/docs-gitlab-com).
Each product repo keeps its own Markdown, and docs-gitlab-com mounts it from a
sibling directory (`module.mounts` in `config/_default/hugo.yaml`). `make view`
runs `clean add-latest-icons build-data build-frontend`, then `hugo serve`, at
`http://localhost:1313`. Markdown edits in the product repo reload live.

If the project ships its own preview wrapper (a `docs:serve` task, or a script
such as `scripts/docs/site.sh`), read it first and use it: it usually does the
clone, the link, and the nav swap for you. The steps below are what such a
wrapper does.

## Directory layout and mounts

docs-gitlab-com expects sibling checkouts named as in `hugo.yaml`:

```plaintext
<parent>/
├── docs-gitlab-com/
├── gitlab/              # mounted at the site root (prefix '')
├── gitlab-runner/       # docs/ mounted at runner/
├── cli/                 # docs/source mounted at cli/
└── <your-project>/      # whatever source the mount names
```

Read the current mounts instead of trusting a list:

```shell
grep -n -A1 'source: \.\./' docs-gitlab-com/config/_default/hugo.yaml
```

Terms used in this skill:

- **Mount**: one `module.mounts` entry, which maps a sibling checkout's
  docs directory into the site.
- **Mount name** (`<mount-name>`): the sibling directory that the mount's
  `source` names, for example `gitlab-runner`.
- **Docs root** (`<docs_root>`): the mount's `source`, relative to
  `<parent>`, for example `gitlab-runner/docs`. Scripts take it as a path
  from your working directory.
- **Prefix** (`<prefix>`): the docs.gitlab.com path of the section, which is
  the mount's `target` minus `content/`, for example `runner`. `content`
  alone means prefix `''`. It is the value of `site_check.py --prefix` and
  of `url_prefix` in `.docs-review.yml`.

You do not need every project. Clone or symlink only yours:

```shell
ln -sfn ~/src/my-project <parent>/<mount-name>
```

A symlink keeps live reload working against your real checkout. `make
clone-docs-projects` clones everything, which takes a long time and is rarely
needed for one project.

## Tools and versions

- `mise` installs the pinned tools from `docs-gitlab-com/mise.toml` (Hugo
  extended, Go, Node, and the linters). `make setup` runs the install.
- Go is needed by `make build-data` (`go run cmd/main.go build`).
- Yarn comes from `packageManager` in `package.json` (Yarn 4). Install a shim
  with corepack into a directory that comes first on `PATH`:

  ```shell
  mkdir -p <parent>/bin
  mise exec -- corepack enable --install-directory <parent>/bin yarn
  export PATH="<parent>/bin:$PATH" COREPACK_ENABLE_DOWNLOAD_PROMPT=0
  ```

- Run mise inside docs-gitlab-com with the trust env, so it trusts only that
  checkout and does not walk up into a parent project's `mise.toml`:

  ```shell
  export MISE_CEILING_PATHS=<parent> MISE_TRUSTED_CONFIG_PATHS=<parent>/docs-gitlab-com
  ```

Run `<skill-dir>/scripts/doctor.sh <parent>/docs-gitlab-com <mount-name>` to check all of
this at once.

## Start a preview

1. Clone docs-gitlab-com into `<parent>` (shallow is enough:
   `git clone --depth 1 https://gitlab.com/gitlab-org/technical-writing/docs-gitlab-com.git`).
1. Link your project as its mount name (see above).
1. If your project carries a nav section, swap it in
   ([navigation.md](navigation.md)).
1. In docs-gitlab-com, install Node dependencies: `mise exec -- make install-nodejs-dependencies`.
1. Start the server detached (next section).

## Run detached and wait

Agent tool calls and background tasks have time limits, so start the server
outside them and watch the log. Export the Yarn `PATH` and mise trust env from
[Tools and versions](#tools-and-versions) first:

```shell
cd <parent>/docs-gitlab-com
nohup mise exec -- make view > "${TMPDIR:-/tmp}/docs-serve.log" 2>&1 < /dev/null &
<skill-dir>/scripts/wait-for-server.sh http://localhost:1313/<prefix>/ "${TMPDIR:-/tmp}/docs-serve.log"
```

`wait-for-server.sh` exits 0 when the page answers 200, 1 as soon as the log
shows a build error, and 3 on timeout (default 900 s for a cold first run).

## Strict build (what CI runs)

`serve` tolerates problems that fail CI. Before you call a change done, the
strict build is the real gate:

```shell
mise exec -- make add-latest-icons build-data
mise exec -- hugo --gc --printPathWarnings --panicOnWarning
mise exec -- make check-index-pages SEARCH_DIR=../<docs_root>
mise exec -- make check-pages-not-in-nav
mise exec -- make check-global-navigation 2>&1 | grep -E '(^|[[:space:]])/?<prefix>/'
```

The last command needs a built `public/`, and its raw output on a partial
local build lists every page from projects you did not mount. Only lines for
your prefix count. A full build takes minutes and rewrites `public/`; do not
run it while someone relies on the running server's output.

## Pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| `mise ERROR Failed to install tools: aqua:... no asset found` | Old mise with stale aqua registry asset names | Upgrade mise (ask first; it is a global tool). Interim: `MISE_DISABLE_TOOLS=<tool>,<tool>` for tools the preview does not need, such as hadolint or lychee. |
| `This project's package.json defines "packageManager": "yarn@4..." However the current global version of Yarn is 1.22...` | A global Yarn 1 answers `yarn --version`, so a wrapper skipped the corepack shim | Install the corepack shim and put its directory first on `PATH` (see Tools). Check the version starts with 2-9, not that the command succeeds. |
| `mise ERROR Config files in .../docs-gitlab-com/mise.toml are not trusted` | Running mise in docs-gitlab-com by hand | Export `MISE_CEILING_PATHS` and `MISE_TRUSTED_CONFIG_PATHS` as above, or `mise trust` once. |
| Starting the preview installs a whole unrelated toolchain | A project mise task runs in the product repo's env, which pins its own tools | Call the preview script directly, not through the project's `mise run` task. |
| Server stops after a while | Agent background tasks can time out | Start with `nohup ... & disown` outside the agent's task runner. |
| Browser shows an old version | 1313 was taken, Hugo picked a random port | `lsof -nP -iTCP:1313 -sTCP:LISTEN`. Reuse that server, or stop it only if you started it. A wrapper should refuse to start when the port is busy. |
| Colleague pulls the MR and sees the old side nav | Their docs-gitlab-com clone has the production nav; the new nav lived only in your local clone | Carry the nav section in the product repo and swap it in ([navigation.md](navigation.md)); update an old clone before previewing. |
| Pages render but have no side nav | Page missing from navigation.yaml, or page-metadata.json is stale | Add the nav entry, run `<skill-dir>/scripts/regen-nav-data.sh <parent>/docs-gitlab-com`, re-run the checks. |
| Your section is missing entirely, no error | Mount source path does not exist (wrong mount name or broken symlink) | `<skill-dir>/scripts/doctor.sh <parent>/docs-gitlab-com <mount-name>`; fix the link. |
| `WARN Invalid internal redirect path in ...` | `redirect_to` does not resolve from the stub's own directory | Fix the relative path. In `serve` the stub just has no meta refresh; the strict build fails. |
| `Duplicate content path` | Both `x.md` and `x/_index.md` exist | Keep one; redirect the other URL if it was published. |
| `make check-index-pages` fails | A directory uses `index.md` | Rename to `_index.md`. |
| `WARN could not load release dates from ../www-gitlab-com/data/releases.yml` | Optional data file | Ignore it. Do not treat it as an error in monitors. |
| Elasticsearch variables not set | Local preview uses Pagefind search instead | Ignore it. |
| CI never ran the docs build on the MR | `[skip ci]` in the MR title or commit skips every pipeline | Check the title before relying on CI: `glab ci list --ref <branch>`. |
| Playwright or another browser tool reports the profile is in use | Another session holds the browser profile | Use an isolated profile, or rely on the HTML checks in `site_check.py`. |

## Stop a preview

Stop only a server you started: `kill <pid>` from the `nohup` start, or
`kill $(lsof -ti tcp:1313)` after you confirm the PID is yours. Leave the
docs-gitlab-com nav swap in place or restore it with
`git -C <parent>/docs-gitlab-com checkout -- data/en-us/navigation.yaml`.
