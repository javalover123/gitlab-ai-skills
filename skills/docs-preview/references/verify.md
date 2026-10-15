# Verify a rendered docs section

`<skill-dir>` is the docs-preview skill directory.

Contents:

- [Run the checks](#run-the-checks)
- [What each check verifies](#what-each-check-verifies)
- [Read the results](#read-the-results)

## Run the checks

```shell
python3 <skill-dir>/scripts/site_check.py all --base http://localhost:1313 --prefix <prefix> --docs-root <docs_root> \
    [--site-dir <docs-gitlab-com>] [--nav-file <nav_file>]
```

- Run one check by name instead of `all`. Arguments, `--scope`, `--json`,
  and exit codes: `--help`.
- `<prefix>` and `<docs_root>` come from the mount:
  [setup.md](setup.md#directory-layout-and-mounts). `AGENTS.md` and
  `CLAUDE.md` are skipped, as Hugo skips them.
- With prefix `''` on a partial local build, set `--scope` to the
  directories you mounted, or links to unmounted projects fail.
- The run order after a nav edit is: swap, `regen-nav-data.sh`, wait for the
  reload, then verify.

## What each check verifies

| Check | Needs | Verifies | Finding ids (severity) |
|---|---|---|---|
| `files` | source only | No `index.md` (must be `_index.md`); no `x.md` next to `x/_index.md` | `index-md`, `duplicate-path` (blocker) |
| `nav` | `--nav-file` | Every page has an entry; entries are unique, relative, end with `/`, have no anchor, and point at a real page, not a stub | `nav-missing-page` (major), `nav-dead-entry`, `nav-duplicate` (blocker), `nav-bad-url` (major) |
| `trail` | `--site-dir` | Each page has `trail_items` in page-metadata.json and the trail ends at the page; warns when nav data is stale | `trail-missing`, `trail-mismatch` (major), `metadata-stale` (minor) |
| `sidebar` | server | The rendered page has `global-nav-wrapper` and a link to itself with `aria-current="page"` | `page-not-rendered` (blocker), `sidebar-missing` (major), `sidebar-not-active` (minor) |
| `redirects` | server | `redirect_to` resolves from the stub's directory to a file; the stub emits a meta refresh; the target returns 200 and is not another stub; `remove_date` is `YYYY-MM-DD` | `redirect-target-missing`, `redirect-no-refresh`, `redirect-target-broken`, `redirect-chain` (blocker), `redirect-remove-date` (minor) |
| `links` | server | Every same-host link in scope returns 200; every `#anchor` exists as an `id` on the target; flags links that go through a redirect stub | `link-broken`, `anchor-broken` (blocker), `link-to-redirect` (minor) |
| `cards` | server | Every `- [Title](page.md)` item in a `{{< cards >}}` block renders a card; every card has a description | `cards-dropped`, `card-no-description`, `cards-count` (major) |

Not covered: external links (other hosts are skipped), JavaScript behavior
(collapse, search), visual layout, and anything only the strict Hugo build
catches ([setup.md](setup.md#strict-build-what-ci-runs)).

## Read the results

Text output, one line per finding, then a summary per check:

```plaintext
FAIL docs-preview.anchor-broken doc/user/example.md:42 /user/example/#old-heading: Anchor #old-heading does not exist on /user/example/. ...
WARN docs-preview.link-to-redirect doc/user/other.md:7 /user/moved/: Link goes through the redirect stub /user/moved/. ...
links: 278 checked, 1 failures, 1 warnings
site-check: FAIL (1 failures, 1 warnings)
```

- `FAIL` lines are blocker or major and fail the run. `WARN` lines are
  minor and do not.
- The file path is relative to the git repo that holds the docs root. The line
  is the first source line that contains the anchor, the link target, or the
  front matter `title`; it is a pointer, not an exact column.
- Common causes: `anchor-broken` after a heading rename (update every inbound
  link, or keep the old heading); `sidebar-missing` plus `trail-missing` on the
  same page (no nav entry, or stale nav data); `cards-dropped` when a card links
  to a page you just turned into a redirect.
- `--json` (or `--out FILE`) writes the docs-review findings format:
  `{"version": 1, "target": {...}, "findings": [...]}`, each finding with
  `id`, `reviewer: docs-preview`, `severity`, `confidence`, `file`, `line`,
  `quote`, `message`, `source`, `fixable: manual`, and a `fingerprint` (sha1 of
  `id|file|quote`). The `docs-review` skill can merge these with its own findings.
