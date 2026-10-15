---
name: docs-preview
description: "Runs the docs.gitlab.com Hugo site (docs-gitlab-com) locally for a project's documentation and verifies the rendered pages: side nav, nav trails, redirects, internal links and anchors, and cards. Use when asked to preview docs locally, run make view or the docs site, find out why a page has no side nav or sidebar, check redirects or broken anchors after moving or renaming pages, or swap a project's navigation section into a local preview. Do not use for a style or content review of a docs change (use docs-review) or for writing or restructuring docs (use docs-change)."
version: 0.2.0
license: MIT
category: Documentation
compatibility: opencode
metadata:
  audience: developers, technical-writers
  workflow: local
---

# docs-preview

Preview a project's docs inside the docs-gitlab-com Hugo site and check the
rendered result with scripts, not by eye. Works for the gitlab `doc/` tree and
any project that docs-gitlab-com mounts (maps a sibling checkout into the
site) under a prefix (`runner`, `cli`). Needs `python3` 3.9+, and network
access for the first clone. `<skill-dir>` is this skill's directory; mount
name, docs root, and prefix are defined in
[setup.md](references/setup.md#directory-layout-and-mounts).

## Gotchas

- **Agent background tasks can time out.** Start the server detached with
  `nohup`, and watch its log for failure as well as success.
- **Reuse a running server, and never stop one you did not start.** If port
  1313 is taken, Hugo picks a random port and the browser keeps showing the
  old server.
- **Editing navigation.yaml does not update the sidebar.** The nav trails in
  `page-metadata.json` change only after `make build-data`: run
  `<skill-dir>/scripts/regen-nav-data.sh <docs-gitlab-com>`.
- **A partial build makes `make check-global-navigation` report thousands of
  unrelated missing pages.** Filter its output to your prefix.

## Workflow

Emit `PHASE <n> (<name>): COMPLETE | PARTIAL | BLOCKED - <counts>` after each.

1. **Preflight:** run `<skill-dir>/scripts/doctor.sh <docs-gitlab-com> [<mount-name>]`.
   Fix every FAIL before starting. Setup and every known pitfall:
   [references/setup.md](references/setup.md).
2. **Serve:** reuse a running preview, or start one detached and wait. First
   export the Yarn `PATH` and mise env from
   [Tools and versions](references/setup.md#tools-and-versions):

   ```shell
   cd <docs-gitlab-com>
   nohup mise exec -- make view > "${TMPDIR:-/tmp}/docs-serve.log" 2>&1 < /dev/null &
   <skill-dir>/scripts/wait-for-server.sh http://localhost:1313/<prefix>/ "${TMPDIR:-/tmp}/docs-serve.log"
   ```

3. **Navigation:** if the project carries its own nav section, run
   `<skill-dir>/scripts/swap-nav.sh <docs-gitlab-com>/data/en-us/navigation.yaml '<header line>' <section file>`
   (the header line is the section's column-0 comment, such as
   `'# GITLAB RUNNER'`), then `<skill-dir>/scripts/regen-nav-data.sh <docs-gitlab-com>`.
   How the side nav works: [references/navigation.md](references/navigation.md).
4. **Verify:** run `python3 <skill-dir>/scripts/site_check.py all --base <url> --prefix <prefix> --docs-root <docs_root> [--site-dir <docs-gitlab-com>] [--nav-file <nav_file>]`.
   It exits 0 on pass, 1 on failures, and 2 with no server or bad arguments.
   What each check means: [references/verify.md](references/verify.md).
5. **Report:** list pass or fail per check with file:line, the URLs to open,
   and whether a docs-gitlab-com nav MR is needed. End with
   `PREVIEW: PASS | FAIL | BLOCKED - <failures> failures, <warnings> warnings`.

## Scripts

`doctor.sh`, `wait-for-server.sh`, `swap-nav.sh`, `regen-nav-data.sh`, and
`site_check.py`, in `<skill-dir>/scripts/`. Each prints its usage with
`--help`.

## Safety rules

- Read-only for the product repo: never commit, push, or open an MR. The nav
  swap edits only the local docs-gitlab-com checkout; never commit it there.
- Ask before upgrading global tools, resetting a docs-gitlab-com checkout with
  local changes, or stopping a server you did not start. When another skill
  runs this one in auto mode, do none of these: report `BLOCKED` with the
  doctor output instead.

## Contributing Improvements

Change this skill in [gabrielengel_gl/docs-skills-lab](https://gitlab.com/gabrielengel_gl/docs-skills-lab).
