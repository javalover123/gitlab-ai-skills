# docs-change

Writes a GitLab docs change from a prompt, a spec, or a code MR, and opens or
updates the docs MR.

## How it works

1. **Plan:** picks page roles and topic types, and lists the pages to add,
   change, move, or redirect.
1. **Write:** writer subagents, one per set of pages.
1. **Check:** runs `docs-review`'s checks and `docs-preview`, if installed.
1. **Self-review:** `docs-review` reviews the branch. Its reviewers never
   write, and the writers never review. Fixes run for at most 3 cycles.
1. **MR:** opens or updates the MR with a description.

## Development

Source, tests, and evals:
[gabrielengel_gl/docs-skills-lab](https://gitlab.com/gabrielengel_gl/docs-skills-lab).
Review quality is measured through `docs-review`
([development](../docs-review/README.md#development)).
