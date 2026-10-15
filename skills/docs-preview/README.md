# docs-preview

Runs the docs.gitlab.com site locally for a project's docs and checks the
rendered pages.

## How it works

1. **Preflight:** `scripts/doctor.sh` checks the tools and the
   docs-gitlab-com checkout, and prints the fix for each failure.
1. **Serve:** reuses a running preview or starts one.
1. **Navigation:** swaps in the project's own nav section, if it has one.
1. **Verify:** `scripts/site_check.py` checks the side nav, nav trails,
   redirects, links, anchors, and cards.
1. **Report:** pass or fail for each check, with the URLs to open.

## Development

Change the skill here. Full tests:
[gabrielengel_gl/docs-skills-lab](https://gitlab.com/gabrielengel_gl/docs-skills-lab).
Every script prints its usage with `--help`.
