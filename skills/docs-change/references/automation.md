# Run docs-change and docs-review headless

Contents:

- [What runs where](#what-runs-where)
- [GitLab CI example](#gitlab-ci-example)
- [Roll out in steps](#roll-out-in-steps)

## What runs where

Review and writing are separate jobs, so they can be separate CI stages with
separate permissions:

| Stage | Skill | Writes | Token needs |
|---|---|---|---|
| `docs-review` | `docs-review`, auto mode, no `--fix` | MR notes only (summary note plus inline findings). Read-only on the repository. | `api` |
| `docs-apply` | `docs-review` phase 6 (`--fix`) on the review job's `findings.json` | New commits on the MR source branch | `api`, `write_repository` |
| `docs-change` (manual) | `docs-change`, auto mode | New commits on the MR branch, or a new branch and MR | `api`, `write_repository` |

Splitting the stages lets a team turn on the review without giving the job
push rights. A dry run needs only `read_api`. Run the jobs only for MRs from
the project itself, as the rules below do: the job reads untrusted text and
holds a write token.

## GitLab CI example

The agent CLI is an example (Claude Code headless with `claude -p`). Any
agent that can load skills works, such as `opencode run`. Check your CLI's
`--help` for its tool and permission flags.

```yaml
stages: [docs-review, docs-apply]

.docs-agent:
  image: node:22-bookworm      # needs git, python3, glab, and the agent CLI
  variables:
    DOCS_REVIEW_MODE: auto
    GIT_DEPTH: 0               # the review diffs base..head
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event" && $CI_MERGE_REQUEST_SOURCE_PROJECT_ID == $CI_PROJECT_ID
      changes:
        paths: ["doc/**/*"]     # your docs_root
        compare_to: refs/heads/$CI_DEFAULT_BRANCH
  before_script:
    - apt-get update -qq && apt-get install -y -qq python3 git >/dev/null
    - ./scripts/ci/install-docs-tools.sh   # glab, vale, markdownlint-cli2 at the project's pinned versions
    - npm install -g @anthropic-ai/claude-code
    - mkdir -p ~/.claude/skills
    - git clone --depth 1 https://gitlab.com/gitlab-org/ai/skills.git /tmp/ai-skills   # the published skills; pin a commit
    - cp -R /tmp/ai-skills/skills/docs-review /tmp/ai-skills/skills/docs-change ~/.claude/skills/
    - echo "$GITLAB_TOKEN" | glab auth login --hostname "$CI_SERVER_HOST" --stdin
  interruptible: true
  resource_group: docs-agent-$CI_MERGE_REQUEST_IID   # one agent run per MR at a time
  allow_failure: true                                # advisory until the team trusts it
  artifacts:
    when: always
    access: developer                                # findings can quote non-public text
    expire_in: 2 weeks
    paths: [docs-review-out/]

docs-review:
  extends: .docs-agent
  stage: docs-review
  script:
    - claude -p "Use the docs-review skill in auto mode. Review the docs in MR !$CI_MERGE_REQUEST_IID of $CI_PROJECT_PATH. Write report.md and findings.json to docs-review-out/. Do not apply fixes and do not edit files."

docs-apply:
  extends: .docs-agent
  stage: docs-apply
  needs: [docs-review]
  rules:
    # Do not re-apply on the pipeline that the apply job's own push started.
    - if: $CI_COMMIT_MESSAGE =~ /^docs: apply docs-review fixes/
      when: never
    - !reference [.docs-agent, rules]
  script:
    - git fetch origin "$CI_MERGE_REQUEST_SOURCE_BRANCH_NAME"
    - git checkout -B "$CI_MERGE_REQUEST_SOURCE_BRANCH_NAME" FETCH_HEAD
    - test "$(git rev-parse HEAD)" = "$CI_COMMIT_SHA" || { echo "Branch moved since review; skipping."; exit 0; }
    - claude -p "Use the docs-review skill in auto mode with --fix. Apply the findings in docs-review-out/findings.json to MR !$CI_MERGE_REQUEST_IID. Push only new commits to $CI_MERGE_REQUEST_SOURCE_BRANCH_NAME."

docs-change:
  extends: .docs-agent
  stage: docs-review
  when: manual                 # a person starts it on a code MR
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event" && $CI_MERGE_REQUEST_SOURCE_PROJECT_ID == $CI_PROJECT_ID
      when: manual
  script:
    - claude -p "Use the docs-change skill in auto mode. Document the user-facing changes in MR !$CI_MERGE_REQUEST_IID of $CI_PROJECT_PATH on its source branch. Write the plan and the docs-review report to docs-review-out/."
```

## Roll out in steps

1. Dry run: add `--dry-run` to the prompts. Read the artifacts on a few MRs.
2. Review only: remove `--dry-run` from `docs-review`. Keep `docs-apply` off.
3. Apply: turn on `docs-apply` once the team agrees with most findings.
4. Keep `allow_failure: true` until false positives are rare.
