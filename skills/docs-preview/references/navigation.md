# How the docs.gitlab.com side nav works

`<skill-dir>` is the docs-preview skill directory.

Contents:

- [Where the nav lives](#where-the-nav-lives)
- [From navigation.yaml to a rendered sidebar](#from-navigationyaml-to-a-rendered-sidebar)
- [Nav entry rules](#nav-entry-rules)
- [Carry a nav section in the project and swap it in](#carry-a-nav-section-in-the-project-and-swap-it-in)
- [Production: the docs-gitlab-com MR](#production-the-docs-gitlab-com-mr)

## Where the nav lives

The left nav for every project comes from one file:
`data/en-us/navigation.yaml` in docs-gitlab-com. Product repos do not control
it. Top-level sections start with a header comment in column 0, such as
`# GITLAB RUNNER`, followed by entries:

```yaml
- title: GitLab Runner
  url: 'runner/'
  submenu:
    - title: Install
      url: 'runner/install/'
```

A product can appear in more than one section. For example, administration
pages for a feature often sit under the Administer section while the user
pages sit under the feature's own section. Search for every `url:` with your
prefix before you assume one block owns your pages.

## From navigation.yaml to a rendered sidebar

1. `make build-data` (`go run cmd/main.go build`) reads navigation.yaml and
   writes `data/<lang>/page-metadata.json`: one key per page URL (no leading
   slash, for example `runner/install/`), each with `trail_items`, a list of
   `{title, path}` from the section root down to the page.
2. The theme's `has-left-nav` and `sidebar-nav` partials read that trail. No
   trail, no sidebar. There is no build error in `serve`, so a page missing
   from the nav looks fine except for the missing left column.
3. The sidebar is server-rendered for the active top-level section, then a Vue
   component replaces it on load. HTML checks (curl, `site_check.py`) are valid
   for "the sidebar exists and marks this page active". Collapse and mobile
   behavior need a real browser.

Hugo watches the data directory, but it does not run `build-data`. After any
navigation.yaml change, run `<skill-dir>/scripts/regen-nav-data.sh <docs-gitlab-com>`, wait
for Hugo to reload, then re-run the checks. `site_check.py trail` warns when
navigation.yaml is newer than page-metadata.json.

## Nav entry rules

Follow the [global nav guidelines](https://docs.gitlab.com/development/documentation/site_architecture/global_nav/).
`site_check.py nav --nav-file <file>` checks them from source.
docs-gitlab-com also has `make check-pages-not-in-nav` and
`make check-global-navigation` (filter the latter to your prefix).

## Carry a nav section in the project and swap it in

Until the docs-gitlab-com MR merges, nobody else sees your new nav. To make
previews (yours, a colleague's, CI review apps) show it:

1. Keep the section in the product repo, for example `docs/navigation.yaml`.
   Start it with comment lines that say it is the source of truth until the
   docs-gitlab-com MR merges. Comment lines are not copied by the swap.
2. Swap it into the local docs-gitlab-com checkout:

   ```shell
   <skill-dir>/scripts/swap-nav.sh <parent>/docs-gitlab-com/data/en-us/navigation.yaml '# GITLAB RUNNER' docs/navigation.yaml
   <skill-dir>/scripts/regen-nav-data.sh <parent>/docs-gitlab-com
   ```

   The swap replaces everything from the header line to the next column-0
   `# ` header, so comments inside a section must be indented. It is
   idempotent, and `--check` reports whether the checkout already matches.
3. A preview wrapper can run the swap on every start. If it also updates an
   old docs-gitlab-com clone, it must skip the update when the checkout has
   changes other than the swap.
4. If your pages also appear in another section, either carry that section
   too or check nav coverage against the full swapped navigation.yaml:
   `site_check.py nav --nav-file <parent>/docs-gitlab-com/data/en-us/navigation.yaml`.

## Production: the docs-gitlab-com MR

- Moving, adding, or removing pages in the product repo needs a matching MR in
  docs-gitlab-com that edits `data/en-us/navigation.yaml`. Merge them together;
  link each MR from the other.
- Copy the swapped section from the project file, so the two stay identical.
  After the docs-gitlab-com MR merges, delete the project copy or keep it in
  sync, and say which in the product MR description.
- The product MR's own CI cannot prove the production nav. Say in the MR
  description that the nav MR is required and link it.
