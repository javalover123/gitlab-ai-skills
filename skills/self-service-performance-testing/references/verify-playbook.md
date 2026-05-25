# GitLab Verify Playbook

**Repo:** https://gitlab.com/gitlab-org/quality/quality-engineering/gitlab-verify-playbook
**Status:** Experimental — work-in-progress, bugs and gaps possible. Reach out in **#g_performance_enablement** before adopting.
**Development Epic:** https://gitlab.com/groups/gitlab-org/quality/quality-engineering/-/epics/114

The GitLab Verify Playbook is an Ansible playbook + Python script that automates
[Pre- and Post-Upgrade Checks](https://docs.gitlab.com/ee/update/index.html#pre-upgrade-and-post-upgrade-checks)
and verifies that a GitLab instance is up and functional after deployment or reconfiguration.

**Important distinction:** This tool verifies instance health and functional readiness — it does
not perform load testing or measure performance metrics (response times, throughput, etc.). Use
GPT, CPT, or Sitespeed Runway for performance testing. Use the Verify Playbook to confirm a
GitLab instance is operational after a deployment or upgrade.

## What It Does

The playbook runs a set of automated checks against a GitLab instance:

- `gitlab-rake gitlab:check` — verifies core GitLab components are configured correctly
- `gitlab-rake gitlab:doctor:secrets` — checks that secrets are consistent
- `gitlab-rake gitlab:elastic:info` — checks Advanced Search (Elasticsearch) status if applicable

It parses the output of these commands and reports whether the instance passed or failed each check.

## When to Use It

Use the Verify Playbook when:

- You've deployed or upgraded a GitLab instance and need to confirm it's healthy
- You're running automated post-deployment verification in a CI/CD pipeline
- You want to automate the manual pre/post-upgrade checklist steps

Do **not** use it for:

- Load testing or performance benchmarking → use GPT or CPT
- Frontend performance measurement → use Sitespeed Runway
- Functional testing of GitLab product features (it does not test product functionality)

## How to Use It

### Option 1: With GitLab Environment Toolkit (GET)

The playbook is designed to work with environments managed by
[GitLab Environment Toolkit](https://gitlab.com/gitlab-org/gitlab-environment-toolkit):

```bash
# Copy files into the correct GET locations
./copy_to_get.sh

# Run the verify playbook
ansible-playbook -i environments/<ENVIRONMENT_NAME>/inventory playbooks/verify.yml
```

### Option 2: Script Only

Run the Python parser directly against command output you've already collected:

```bash
./ansible/playbooks/gitlab_check_parse.py \
  "<GITLAB_CHECK_OUTPUT>" \
  "<GITLAB_DOCTOR_SECRETS_OUTPUT>" \
  "<GITLAB_ELASTIC_INFO_OUTPUT>"
```

| Variable | How to get it |
|---|---|
| `<GITLAB_CHECK_OUTPUT>` | Run `gitlab-rake gitlab:check` on the instance, or pass `""` to skip |
| `<GITLAB_DOCTOR_SECRETS_OUTPUT>` | Run `gitlab-rake gitlab:doctor:secrets` on the instance, or pass `""` to skip |
| `<GITLAB_ELASTIC_INFO_OUTPUT>` | Run `gitlab:elastic:info` if using Advanced Search, or pass `""` to skip |

## Relationship to Performance Testing

The Verify Playbook is complementary to performance testing, not a replacement:

| Need | Tool |
|---|---|
| Is the instance up and healthy after deployment? | **Verify Playbook** |
| How fast does the API respond under load? | **GPT** or **CPT** |
| How do Core Web Vitals look on key pages? | **Sitespeed Runway** |
| Does my MR change hurt performance? | **CPT** |

A typical deployment workflow might run the Verify Playbook first (is it up?), then GPT
(does it perform at the expected level?).

## Access and Support

The playbook is experimental. Before adopting it:

1. Review the [Development Epic](https://gitlab.com/groups/gitlab-org/quality/quality-engineering/-/epics/114)
   to understand current progress and known gaps.
2. Reach out in **#g_performance_enablement** on Slack for guidance.
3. File issues in the [repo](https://gitlab.com/gitlab-org/quality/quality-engineering/gitlab-verify-playbook)
   if you encounter bugs.
