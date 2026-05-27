---
name: source-code-mirroring
description: Repository mirroring - push, pull, and bidirectional sync between GitLab and external repositories
version: 1.0.0
license: MIT
---

# Source Code: Repository Mirroring

Repository mirroring allows GitLab to synchronize repositories with external Git hosts. Push mirroring (Core+) pushes changes to external repositories, while pull mirroring (Premium+) pulls changes from external sources into GitLab.

> **📅 Maintenance Note**: Sections marked with 📅 contain time-sensitive information (team contacts, active issues, roadmap, architecture docs). These should be reviewed periodically. Last reviewed: **2026-05-23**.

## When to Use This Skill

Use this skill when:
- Implementing or debugging push/pull mirroring features
- Investigating mirror sync failures or stuck mirrors
- Working on branch filtering for mirrors (protected branches, regex)
- Handling mirror authentication (SSH, password, deploy keys)
- Debugging Geo replication issues related to mirroring
- Working on CI/CD pipeline triggers from mirror updates

## Features Covered

| # | Feature | Tier | Description |
|---|---------|------|-------------|
| 5 | Repository pull and bidirectional mirroring | Premium+ | Pull changes from external repositories into GitLab |
| 13 | Remote repository push mirroring | Core+ | Push GitLab repository changes to external hosts |

## Key Codebase Areas

### Models

#### Push Mirroring (CE - Core)

| File | Purpose |
|------|---------|
| `app/models/remote_mirror.rb` | Main push mirror model with state machine, sync logic, scheduling |
| `app/models/remote_mirrors/attributes.rb` | Allowed attributes whitelist for push mirrors |
| `app/models/remote_mirrors/host_keys_converter.rb` | SSH host key conversion |
| `app/models/concerns/mirror_authentication.rb` | Shared auth concern (SSH/password) |
| `app/models/ssh_host_key.rb` | SSH host key detection and caching |

#### Push Mirroring (EE - Premium+)

| File | Purpose |
|------|---------|
| `ee/app/models/ee/remote_mirror.rb` | Adds `mirror_branch_regex` support, Geo checks |
| `ee/app/models/ee/remote_mirrors/attributes.rb` | EE allowed attributes (adds `mirror_branch_regex`) |
| `ee/app/models/concerns/mirror_configuration.rb` | Mirror branches setting enum (all/protected/regex) |

#### Pull Mirroring (EE - Premium+)

| File | Purpose |
|------|---------|
| `app/models/project_import_state.rb` | Import state machine (table: `project_mirror_data`) |
| `ee/app/models/ee/project_import_state.rb` | EE extensions: retry logic, scheduling, Geo integration |
| `ee/app/models/ee/project.rb` | Pull mirror attributes on Project |
| `app/models/project_import_data.rb` | Import credentials storage |
| `ee/app/models/repositories/pull_mirrors/attributes.rb` | Pull mirror allowed attributes whitelist |

### Services

#### Push Mirror Services (CE)

| File | Purpose |
|------|---------|
| `app/services/remote_mirrors/create_service.rb` | Create push mirror |
| `app/services/remote_mirrors/update_service.rb` | Update push mirror |
| `app/services/remote_mirrors/destroy_service.rb` | Delete push mirror |
| `app/services/remote_mirrors/sync_service.rb` | Trigger push mirror sync |
| `app/services/projects/update_remote_mirror_service.rb` | Execute push mirror update (LFS, URL validation) |

#### Pull Mirror Services (EE)

| File | Purpose |
|------|---------|
| `ee/app/services/repositories/pull_mirrors/update_service.rb` | Create/update pull mirror configuration |
| `ee/app/services/start_pull_mirroring_service.rb` | Trigger pull mirror sync |
| `ee/app/services/projects/update_mirror_service.rb` | Execute pull mirror update (branches, tags, LFS) |

### Controllers

| File | Purpose |
|------|---------|
| `app/controllers/projects/mirrors_controller.rb` | Main controller for push mirrors |
| `ee/app/controllers/ee/projects/mirrors_controller.rb` | EE extensions for pull mirrors |

### Workers (Background Jobs)

#### Push Mirroring (CE)

| File | Purpose |
|------|---------|
| `app/workers/repository_update_remote_mirror_worker.rb` | Execute push mirror sync with locking |
| `app/workers/remote_mirror_notification_worker.rb` | Send failure notifications |

#### Pull Mirroring (EE)

| File | Purpose |
|------|---------|
| `ee/app/workers/repository_update_mirror_worker.rb` | Execute pull mirror sync |
| `ee/app/workers/update_all_mirrors_worker.rb` | Cron job to schedule all due pull mirrors |

### GraphQL

**No dedicated mirror GraphQL types/mutations.** Mirrors are managed through REST API and controller actions.

Only reference: `app/graphql/types/permission_types/project.rb` (line 18) exposes `:admin_remote_mirror` permission.

### Lib Utilities

| File | Purpose |
|------|---------|
| `lib/gitlab/git/remote_mirror.rb` | Gitaly remote mirror wrapper |
| `ee/lib/gitlab/mirror.rb` | Pull mirror capacity/scheduling management |
| `ee/lib/gitlab/repositories/mirror/branch_skip_filter.rb` | Branch filtering logic |
| `ee/lib/gitlab/repositories/mirror/local_remote_branch_comparator.rb` | Branch comparison for LFS updates |

## Test Locations

### Model Specs (CE)

| File | Coverage |
|------|----------|
| `spec/models/remote_mirror_spec.rb` | Push mirror model, state machine, scheduling |
| `spec/models/project_import_state_spec.rb` | Import state machine |

### Model Specs (EE)

| File | Coverage |
|------|----------|
| `ee/spec/models/remote_mirror_spec.rb` | EE push mirror extensions |
| `ee/spec/models/project_import_state_spec.rb` | EE pull mirror state |
| `ee/spec/models/concerns/mirror_configuration_spec.rb` | Branch filtering config |

### Service Specs

| File | Coverage |
|------|----------|
| `spec/services/remote_mirrors/*_spec.rb` | Push mirror CRUD services |
| `spec/services/projects/update_remote_mirror_service_spec.rb` | Push mirror execution |
| `ee/spec/services/projects/update_mirror_service_spec.rb` | Pull mirror execution |
| `ee/spec/services/start_pull_mirroring_service_spec.rb` | Pull mirror trigger |
| `ee/spec/services/repositories/pull_mirrors/update_service_spec.rb` | Pull mirror config |

### API Specs

| File | Coverage |
|------|----------|
| `spec/requests/api/remote_mirrors_spec.rb` | Push mirror REST API |
| `ee/spec/requests/api/remote_mirrors_spec.rb` | EE push mirror API |
| `ee/spec/requests/api/project_mirror_spec.rb` | Pull mirror REST API |

### Feature Specs

| File | Coverage |
|------|----------|
| `spec/features/projects/remote_mirror_spec.rb` | Push mirror UI |
| `ee/spec/features/projects/mirror_spec.rb` | Pull mirror UI |

## Documentation

| Path | Content |
|------|---------|
| [`doc/user/project/repository/mirror/_index.md`](https://docs.gitlab.com/ee/user/project/repository/mirror/) | Overview, creating mirrors |
| [`doc/user/project/repository/mirror/push.md`](https://docs.gitlab.com/ee/user/project/repository/mirror/push.html) | Push mirror configuration |
| [`doc/user/project/repository/mirror/pull.md`](https://docs.gitlab.com/ee/user/project/repository/mirror/pull.html) | Pull mirror configuration (Premium+) |
| [`doc/user/project/repository/mirror/bidirectional.md`](https://docs.gitlab.com/ee/user/project/repository/mirror/bidirectional.html) | Bidirectional setup |
| [`doc/user/project/repository/mirror/troubleshooting.md`](https://docs.gitlab.com/ee/user/project/repository/mirror/troubleshooting.html) | Troubleshooting guide |

## Common Patterns

### State Machine Pattern

Both push and pull mirrors use state machines to track sync status:

```ruby
# Push mirror states (RemoteMirror)
# update_status: none -> started -> finished/failed/to_retry

# Pull mirror states (ProjectImportState)
# status: none -> scheduled -> started -> finished/failed/canceled
```

**Key insight**: Check `update_status` for push mirrors, `status` for pull mirrors when debugging sync issues.

### Scheduling Pattern

```ruby
# Push mirrors: Triggered on repository changes, scheduled with backoff delay
remote_mirror.schedule_update

# Pull mirrors: Scheduled by cron job based on capacity and next_execution_timestamp
UpdateAllMirrorsWorker.perform_async
```

**Key insight**: Push mirrors react to changes; pull mirrors run on a schedule. The `remote_mirror_no_delay` feature flag can skip backoff for push mirrors.

### Authentication Pattern

Both mirror types share the `MirrorAuthentication` concern:

```ruby
# Shared concern for SSH and password auth
include MirrorAuthentication

# Credentials stored encrypted in:
# - RemoteMirror (push)
# - ProjectImportData (pull)
```

### Branch Filtering (EE)

```ruby
# Three modes for filtering which branches to mirror:
# 1. All branches (default)
# 2. Protected branches only
remote_mirror.only_protected_branches = true

# 3. Regex pattern (mutually exclusive with protected branches)
remote_mirror.mirror_branch_regex = '^release-.*'
```

**Key insight**: `only_protected_branches` and `mirror_branch_regex` are mutually exclusive. The `BranchSkipFilter` class implements the filtering logic.

### CE/EE Split Pattern

```ruby
# Models use prepend_mod_with for EE extensions
class RemoteMirror < ApplicationRecord
  prepend_mod_with('RemoteMirror')
  # ...
end
```

## EE vs CE

### Core (Free) Features

| Feature | Implementation |
|---------|----------------|
| Push mirroring | `RemoteMirror` model, sync to external repos |
| SSH/password auth | `MirrorAuthentication` concern |
| LFS sync (push) | `UpdateRemoteMirrorService` handles LFS objects |

### Premium+ Features (EE)

| Feature | Implementation | License Check |
|---------|----------------|---------------|
| Pull mirroring | `ProjectImportState`, `UpdateMirrorService` | `project.feature_available?(:repository_mirrors)` |
| Bidirectional mirroring | Combination of push + pull | `repository_mirrors` feature |
| Branch regex filtering | `mirror_branch_regex` attribute | `project.feature_available?(:repository_mirrors)` |
| Protected branches only | `only_protected_branches` attribute | Available in CE for push mirrors |

### Feature Availability Checks

```ruby
# Check if pull mirroring is available
project.feature_available?(:repository_mirrors)

# Check permissions
can?(current_user, :admin_mirror, project)      # Pull mirrors
can?(current_user, :admin_remote_mirror, project) # Push mirrors
```

## API Endpoints

### REST API - Push Mirrors

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/v4/projects/:id/remote_mirrors` | List push mirrors |
| GET | `/api/v4/projects/:id/remote_mirrors/:mirror_id` | Get push mirror |
| POST | `/api/v4/projects/:id/remote_mirrors` | Create push mirror |
| PUT | `/api/v4/projects/:id/remote_mirrors/:mirror_id` | Update push mirror |
| DELETE | `/api/v4/projects/:id/remote_mirrors/:mirror_id` | Delete push mirror |
| POST | `/api/v4/projects/:id/remote_mirrors/:mirror_id/sync` | Trigger sync |
| GET | `/api/v4/projects/:id/remote_mirrors/:mirror_id/public_key` | Get SSH public key |

### REST API - Pull Mirrors (EE)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/v4/projects/:id/mirror/pull` | Get pull mirror config |
| PUT | `/api/v4/projects/:id/mirror/pull` | Update pull mirror |
| POST | `/api/v4/projects/:id/mirror/pull` | Create/trigger pull mirror |

## Database Tables

| Table | Purpose |
|-------|---------|
| `remote_mirrors` | Push mirror configuration |
| `project_mirror_data` | Pull mirror state (aliased as `ProjectImportState`) |
| `projects` | Contains mirror columns: `mirror`, `mirror_user_id`, `mirror_trigger_builds`, `only_mirror_protected_branches`, `mirror_overwrites_diverged_branches`, `mirror_branch_regex` |

## Testing Guidelines

### Running Tests

```bash
# Push mirror tests
bin/rspec spec/models/remote_mirror_spec.rb
bin/rspec spec/services/remote_mirrors/
bin/rspec spec/requests/api/remote_mirrors_spec.rb

# Pull mirror tests (EE)
bin/rspec ee/spec/models/project_import_state_spec.rb
bin/rspec ee/spec/services/projects/update_mirror_service_spec.rb
bin/rspec ee/spec/requests/api/project_mirror_spec.rb
```

### Test Factories

```ruby
# Push mirror
create(:remote_mirror, project: project, url: 'https://example.com/repo.git')
create(:remote_mirror, :ssh, project: project)

# Pull mirror (EE)
create(:project, :mirror, import_url: 'https://example.com/repo.git')
create(:import_state, :mirror, project: project)
```

### Common Test Scenarios

1. **Mirror sync success**: Verify state transitions and timestamps
2. **Mirror sync failure**: Verify retry logic and error handling
3. **Branch filtering**: Test protected branches and regex patterns
4. **Authentication**: Test SSH keys, passwords, deploy tokens
5. **Stuck mirrors**: Test timeout detection and recovery

## Troubleshooting

### "Mirror sync is stuck"

1. **Check mirror state:**
   ```ruby
   # Push mirror
   remote_mirror = project.remote_mirrors.find(mirror_id)
   remote_mirror.update_status
   remote_mirror.last_error
   
   # Pull mirror
   project.import_state.status
   project.import_state.last_error
   ```

2. **Check for stuck mirrors:**
   ```ruby
   # Push mirrors stuck > 1 hour
   RemoteMirror.stuck.count
   
   # Pull mirrors stuck
   Project.stuck_mirrors.count
   ```

3. **Force retry:**
   ```ruby
   # Push mirror
   remote_mirror.update!(update_status: :none)
   remote_mirror.schedule_update
   
   # Pull mirror
   project.import_state.force_import_job!
   ```

### "Mirror authentication failed"

1. **Verify credentials:**
   ```ruby
   # Check if URL is valid
   remote_mirror.url
   remote_mirror.safe_url  # Masked password
   
   # Check SSH key
   remote_mirror.ssh_public_key
   ```

2. **Test connectivity:**
   ```ruby
   # Check SSH host keys
   SshHostKey.new(project: project, url: remote_mirror.url).fingerprint
   ```

### "Branches not syncing"

1. **Check branch filtering:**
   ```ruby
   remote_mirror.only_protected_branches?
   remote_mirror.mirror_branch_regex
   ```

2. **Verify protected branches:**
   ```ruby
   project.protected_branches.pluck(:name)
   ```

## 📅 Known Issues & Active Work

### Active Issues (from GitLab search)

| Issue | Description | Status |
|-------|-------------|--------|
| [#1063](https://gitlab.com/gitlab-org/gitlab/-/issues/1063) | Allow overwrite option to be modified for pull mirroring without deleting/re-adding | Open - Backlog |
| [#454607](https://gitlab.com/gitlab-org/gitlab/-/issues/454607) | Revisit the presentation of the setup information for mirroring repositories | Open |
| [#500876](https://gitlab.com/gitlab-org/gitlab/-/issues/500876) | User Impersonation in CI/CD Pipelines via CI/CD Runs for External Repository Project (Security) | Open - Confidential |

### Feature Flags

| Flag | Type | Purpose |
|------|------|---------|
| `remote_mirror_no_delay` | ops | Skip backoff delay for push mirrors |
| `validate_pull_mirror_url` | development | Validate pull mirror URL reachability |

## 📅 Architecture & Planning Documents

| Document | Content |
|----------|---------|
| [Development Guide: Repository Mirroring](https://docs.gitlab.com/development/repository_mirroring/) | Explanation of mirroring process, step-by-step flow |
| [Deep Dive Video (2018)](https://www.youtube.com/watch?v=sSZq0fpdY-Y) | Tiago Botelho's deep dive on Pull Repository Mirroring (GitLab team) |
| [Deep Dive Slides (PDF)](https://gitlab.com/gitlab-org/create-stage/uploads/8693404888a941fd851f8a8ecdec9675/Gitlab_Create_-_Pull_Mirroring_Deep_Dive.pdf) | Slides from the deep dive presentation |
| [Tier 2 Oncall Playbook](https://internal.gitlab.com/handbook/engineering/tier2-oncall/playbooks/create/repository-mirroring) | Technical playbook for incident response (internal) |
| [Remote Mirrors API](https://docs.gitlab.com/api/remote_mirrors/) | Push mirror API documentation |
| [Project Pull Mirroring API](https://docs.gitlab.com/api/project_pull_mirroring/) | Pull mirror API documentation |

### Pull Mirroring Data Flow (from Tier 2 Playbook)

```
API/Cron Trigger
    → UpdateAllMirrorsWorker
    → ProjectImportScheduleWorker (capacity check)
    → RepositoryUpdateMirrorWorker
    → Projects::UpdateMirrorService
    → Gitaly: fetch_remote
    → Update branches/tags
    → Mark finished/failed
```

**Key insight**: Pull mirrors use `Gitlab::Import::StuckProjectImportJobsWorker` to mark jobs that haven't progressed after `IMPORT_JOBS_EXPIRATION` hours as failed. Runs at 15 minutes past every hour.

### Push Mirroring Data Flow (from Tier 2 Playbook)

```
Repository Change/Manual Trigger
    → RemoteMirror#sync
    → RepositoryUpdateRemoteMirrorWorker (with exclusive lock)
    → Projects::UpdateRemoteMirrorService
    → Lfs::PushService (if LFS enabled)
    → Gitaly: update_remote_mirror
    → Mark finished/failed
```

**Key insight**: Push mirroring is triggered by `PostReceiveWorker#update_remote_mirrors` whenever a project push is received.

### Capacity Management

- Maximum pull mirroring capacity: `mirror_max_capacity` setting
- Current/available capacity managed in Redis by `Gitlab::Mirror`
- See runbooks to increase maximum capacity

### Monitoring Dashboards (Grafana)

| Dashboard | Purpose |
|-----------|---------|
| [RepositoryUpdateMirrorWorker](https://dashboards.gitlab.net/goto/tRvtKGUHg?orgId=1) | Pull mirrors |
| [UpdateAllMirrorsWorker](https://dashboards.gitlab.net/goto/bpFbFMUHg?orgId=1) | Pull mirror scheduling |
| [StuckProjectImportJobsWorker](https://dashboards.gitlab.net/goto/hoGU-n8Hg?orgId=1) | Pull mirror stuck jobs |
| [RepositoryUpdateRemoteMirrorWorker](https://dashboards.gitlab.net/goto/8ac2FG8NR?orgId=1) | Push mirrors |

## 📅 Incident Learnings

### 2026-04-24: Pull Mirror + Auto DevOps Pipeline Saturation

**What happened**: Customer set up a pull mirror with pipeline triggers and Auto DevOps on a repo with substantial tag history. First sync fired pipelines for every existing tag and saturated a Dedicated shard.

**Root cause**: On first sync of a new pull mirror, GitLab treats it as regular push events per ref, not as a bulk backfill operation.

**Lessons**:
1. Warn customers about enabling "Trigger pipelines for mirror updates" on repos with large tag history
2. Consider implementing bulk backfill detection for initial mirror syncs
3. Auto DevOps default runs on tags - this can cause unexpected load

**Reference**: [Slack #g_runner_core](https://gitlab.slack.com/archives/C09EDQXBMPH/p1777045944612249)

### Security Mirror Divergence Pattern

**What happened**: AI Gateway security mirror diverged from canonical due to merge conflicts, blocking deployments for 5 days.

**Root cause**: Push mirroring fails silently when conflicts exist; no automatic notification or recovery.

**Lessons**:
1. Never use squash merge for sync MRs from canonical to security mirror
2. Merge conflicts must be fixed as an atomic commit inside the sync MR
3. Consider scheduled CI jobs to trigger mirror syncs for critical repos

**Reference**: [Slack #g_ai_framework](https://gitlab.slack.com/archives/C051K31F30R/p1775588285948689)

## 📅 Customer Guidance (from Slack)

### Mirroring vs Migration

**Question**: "Should we use mirroring to migrate from Bitbucket to GitLab?"

**Answer**: Mirroring is NOT recommended for migrations:
- Repository mirroring only syncs Git refs (branches/tags/commits), NOT PR/MR metadata
- The Bitbucket importer brings over Git history AND pull requests (comments, reviewers, approvals)
- With mirroring-only, there's no clear path for cutting over SCM ownership
- Mirroring means paying double licenses and split-brain for repositories

**Recommendation**: Use the Bitbucket importer (or Congregate) for proper migrations. Use mirroring only for ongoing sync scenarios where you need both systems active.

**Source**: [Slack #a_swift_internal](https://gitlab.slack.com/archives/C081MQR525T/p1776160073127249)

### Community Fork Mirroring Issues

**Question**: "Repository mirroring for community fork is unreliable - what alternatives exist?"

**Answer**: Known issues with mirroring large repos:
- Mirror sometimes starts but doesn't do anything (times out after full day)
- Mirror sometimes errors
- Most often, mirror just isn't scheduled

**Workarounds**:
1. Scheduled CI job that triggers the actual mirror
2. Manual clone/push (takes ~5 minutes for large repos)
3. Scheduled CI job that does `git fetch upstream && git push fork`

**Source**: [Slack #developer-relations-engineering](https://gitlab.slack.com/archives/C09NBNCJFQV/p1778157767152869)

## 📅 Team & Communication

### Slack Channels

| Channel | Purpose |
|---------|---------|
| `#g_create_source-code` | Source Code group general |
| `#f_repository_mirroring` | Mirroring feature discussions |

### Feature Category

- **Feature Category**: `source_code_management`
- **Group**: Source Code (Create Stage)

## Related Resources

- **Push Mirror API Docs**: [Remote Mirrors API](https://docs.gitlab.com/ee/api/remote_mirrors.html)
- **Pull Mirror API Docs**: [Project Mirror API](https://docs.gitlab.com/ee/api/project_mirror.html)
- **Troubleshooting Guide**: [Mirror Troubleshooting](https://docs.gitlab.com/ee/user/project/repository/mirror/troubleshooting.html)

## Related Skills

- `source-code-branch-protection` - Branch filtering uses protected branches
- `source-code-push-rules` - Push rules can affect mirrored content

---

## Skill Feedback

> **For agents**: After using this skill, please note any feedback in your session checkpoint to help improve this skill.

- **What was missing?** Information you had to search for that should be here
- **What was unhelpful?** Sections that added noise without value
- **What gotchas did you hit?** Undocumented issues that should be in Troubleshooting
- **What was most useful?** Sections that saved significant time/effort
