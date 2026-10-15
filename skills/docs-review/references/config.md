# Configuration

Put `.docs-review.yml` in the root of the docs project. Every key is optional.
An unknown key gets a warning and is ignored.

Every script reads the file as committed at the base of the change, so an MR
cannot change its own review. `--config` is an explicit local override.

```yaml
docs_root: doc                  # docs/source for a standalone project
url_prefix: ""                  # docs.gitlab.com path prefix, for example orbit/
vale_config: .vale.ini          # default: the cached GitLab rules
nav_file: null                  # a project's copy of its navigation section
product_terms:
  - use: GitLab Orbit
    avoid: ["Orbit Knowledge Graph"]
cross_repo_search_groups: [gitlab-org, gitlab-com]
technical_writer: null          # else CODEOWNERS
custom_heading_ids: false
first_time_threshold: 3         # fewer earlier merged docs MRs: a first-time docs writer
importance: {}                  # rule id or glob: 1-5, overrides the default importance
safety_cap: 50                  # runaway cap, an alarm, not a target (0 turns it off)
landing_paths: []               # extra pages that make a change severe
severe_paths: []
auto_mode: false                # allow auto mode when CI=true
code_examples:
  allow_run: ["glab --help"]    # command prefixes the facts reviewer may run
  sandbox: none                 # or docker: allow commands that write or change state
facts:
  source_projects: []           # code to check claims against
  use_orbit: true
lint_disable: []                # built-in checks to turn off
```
