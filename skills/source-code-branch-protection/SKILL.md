---
name: source-code-branch-protection
description: Guide for working with branch protection, protected tags, branch rules, and access level restrictions in GitLab
version: 1.0.0
license: MIT
---

# Source Code: Branch Protection

This skill provides guidance for developers working on branch protection features in the GitLab codebase. It covers protected branches, protected tags, branch rules, and access level restrictions.

> **📅 Maintenance Note**: Sections marked with 📅 contain time-sensitive information (team contacts, active issues, roadmap, architecture docs). These should be reviewed periodically. Last reviewed: **2026-05-23**.

## When to Use This Skill

Use this skill when:
- Implementing or modifying branch protection rules
- Working with protected tags functionality
- Adding or changing push/merge access level restrictions
- Debugging branch rule enforcement issues
- Extending the branch rules UI or API
- Working with the `ProtectedRef` concern shared between branches and tags

## Features Covered

| # | Feature | Tier | Description |
|---|---------|------|-------------|
| 1 | Branch rules overview | Core+ | Unified view of all rules affecting a branch |
| 2 | Protected branches | Core+ | Prevent force-push, deletion, and unauthorized changes |
| 21 | Restrict push and merge access | Premium+ | Fine-grained access control by user/group/role |
| 22 | Protected tags | Core+ | Prevent tag modification and deletion |
| 23 | Git tags | Core+ | Tag creation and management |

## Key Codebase Areas

### Models

| File | Purpose |
|------|---------|
| `app/models/protected_branch.rb` | Core protected branch model with matching logic |
| `app/models/protected_tag.rb` | Protected tag model (simpler, create-only access) |
| `app/models/concerns/protected_ref.rb` | **Shared concern** for both branches and tags |
| `app/models/protected_branch/push_access_level.rb` | Who can push to protected branches |
| `app/models/protected_branch/merge_access_level.rb` | Who can merge to protected branches |
| `app/models/protected_branch/cache_key.rb` | Cache key generation for protection checks |

### Services

| File | Purpose |
|------|---------|
| `app/services/protected_branches/create_service.rb` | Create new protected branch rules |
| `app/services/protected_branches/update_service.rb` | Modify existing protection rules |
| `app/services/protected_branches/destroy_service.rb` | Remove protection from branches |
| `app/services/protected_branches/cache_service.rb` | **Critical**: Redis caching for protection checks |
| `app/services/protected_branches/api_service.rb` | API-specific service layer |
| `app/services/protected_branches/base_service.rb` | Base class with shared logic |
| `app/services/protected_branches/legacy_api_create_service.rb` | Legacy API compatibility |
| `app/services/protected_branches/legacy_api_update_service.rb` | Legacy API compatibility |

### Controllers

| File | Purpose |
|------|---------|
| `app/controllers/projects/settings/branch_rules_controller.rb` | Branch rules settings UI |
| `app/controllers/projects/protected_refs_controller.rb` | Base controller for protected refs |

### Finders

| File | Purpose |
|------|---------|
| `app/finders/protected_branches_finder.rb` | Query protected branches with filters |
| `app/finders/branches_finder.rb` | General branch finder (includes protection status) |

### GraphQL

| File | Purpose |
|------|---------|
| `app/graphql/types/projects/branch_rule_type.rb` | GraphQL type for branch rules |
| `app/graphql/types/branch_rules/branch_protection_type.rb` | Branch protection details type |

## Test Locations

### Model Specs

| File | Coverage |
|------|----------|
| `spec/models/protected_branch_spec.rb` | Core protection logic, matching, wildcards |
| `spec/models/protected_tag_spec.rb` | Tag protection logic |
| `spec/models/concerns/protected_ref_spec.rb` | Shared concern behavior |

### Service Specs

| File | Coverage |
|------|----------|
| `spec/services/protected_branches/create_service_spec.rb` | Creation scenarios |
| `spec/services/protected_branches/update_service_spec.rb` | Update scenarios |
| `spec/services/protected_branches/destroy_service_spec.rb` | Deletion scenarios |
| `spec/services/protected_branches/cache_service_spec.rb` | Cache behavior, TTL, invalidation |
| `spec/services/protected_branches/api_service_spec.rb` | API service layer |

### Request Specs

| File | Coverage |
|------|----------|
| `spec/requests/api/protected_branches_spec.rb` | REST API endpoints |
| `spec/requests/api/protected_tags_spec.rb` | Tag protection API |

## Documentation

| Path | Content |
|------|---------|
| [`doc/user/project/repository/branches/protected.md`](https://docs.gitlab.com/ee/user/project/repository/branches/protected.html) | Protected branches user guide |
| [`doc/user/project/repository/branches/branch_rules.md`](https://docs.gitlab.com/ee/user/project/repository/branches/branch_rules.html) | Branch rules overview |
| [`doc/user/project/repository/branches/protection_rules.md`](https://docs.gitlab.com/ee/user/project/repository/branches/protection_rules.html) | Protection rules reference |
| [`doc/user/project/repository/branches/_index.md`](https://docs.gitlab.com/ee/user/project/repository/branches/) | Branches index |
| [`doc/user/project/repository/tags/_index.md`](https://docs.gitlab.com/ee/user/project/repository/tags/) | Tags documentation |

## Common Patterns

### ProtectedRef Concern

Both `ProtectedBranch` and `ProtectedTag` include the `ProtectedRef` concern, which provides:

```ruby
module ProtectedRef
  # Shared functionality:
  # - belongs_to :project
  # - validates :name, presence: true
  # - delegate :matching, :matches?, :wildcard?, to: :ref_matcher
  # - scope :for_project
  
  # Class methods for access level checks:
  # - protected_ref_accessible_to?(ref, user, project:, action:, protected_refs:)
  # - developers_can?(action, ref, protected_refs:)
  # - access_levels_for_ref(ref, action:, protected_refs:)
  # - matching(ref_name, protected_refs:)
end
```

**Key insight**: When modifying shared behavior, changes to `ProtectedRef` affect both branches AND tags.

### CacheService Pattern

Protected branch checks are **performance-critical** (called on every push). The `CacheService` uses Redis to cache results:

```ruby
# How protection checks work:
ProtectedBranch.protected?(project, ref_name)
  # → Uses CacheService.fetch(ref_name) with Redis hash
  # → Cache key: based on project/group cache_key
  # → TTL: 1 day
  # → Limit: 1000 entries per project (safety valve)

# Cache invalidation happens via:
CacheService.new(project).refresh
  # → Called when protection rules change
  # → For groups: invalidates all project caches in the group
```

**When to invalidate cache**: Any change to protected branch rules must call `refresh` to clear stale cache entries.

### Access Level Checks

Access levels determine who can push/merge to protected branches:

```ruby
# Access level hierarchy (from Gitlab::Access):
NO_ACCESS      = 0
MINIMAL_ACCESS = 5
GUEST          = 10
REPORTER       = 20
DEVELOPER      = 30
MAINTAINER     = 40
OWNER          = 50
ADMIN          = 60

# Check if user can push:
ProtectedBranch.protected_ref_accessible_to?(
  ref_name,
  user,
  project: project,
  action: :push,
  protected_refs: project.all_protected_branches
)
```

### Wildcard Matching

Branch protection supports wildcards via `RefMatcher`:

```ruby
# Examples:
"main"           # Exact match
"release-*"      # Matches release-1.0, release-2.0, etc.
"*-stable"       # Matches 1.0-stable, 2.0-stable, etc.
"feature/*"      # Matches feature/login, feature/signup, etc.
```

The `RefMatcher` class handles the pattern matching logic.

## EE vs CE

### Core (Free) Features
- Basic protected branches (prevent force-push, deletion)
- Protected tags
- Branch rules overview
- Wildcard branch protection

### Premium+ Features (EE)
- **Restrict push and merge access** (#21) - Fine-grained access by user/group
- Code owner approval requirements
- Multiple approval rules per branch
- Push rules (separate feature, see `source-code-push-rules` skill)

### EE Extensions

EE functionality is added via module prepending:

```ruby
# In app/models/protected_branch.rb:
# (at bottom of file or via autoload)
ProtectedBranch.prepend_mod_with('ProtectedBranch')

# EE module location:
# ee/app/models/ee/protected_branch.rb
```

Check `ee/app/models/ee/protected_branch.rb` for Premium+ features like:
- `code_owner_approval_required`
- User/group-specific access levels
- Unprotect access levels

## Testing Guidelines

### Running Tests

```bash
# Model specs
bin/rspec spec/models/protected_branch_spec.rb
bin/rspec spec/models/protected_tag_spec.rb

# Service specs
bin/rspec spec/services/protected_branches/

# API specs
bin/rspec spec/requests/api/protected_branches_spec.rb

# Feature specs (if any)
bin/rspec spec/features/projects/settings/branch_rules_spec.rb
```

### Test Factories

```ruby
# Create protected branch
create(:protected_branch, project: project, name: 'main')

# With specific access levels
create(:protected_branch, :developers_can_push, project: project)
create(:protected_branch, :maintainers_can_push, project: project)
create(:protected_branch, :no_one_can_push, project: project)

# Protected tag
create(:protected_tag, project: project, name: 'v*')
```

### Common Test Scenarios

1. **Protection check**: Verify `ProtectedBranch.protected?(project, 'branch-name')` returns correct value
2. **Access level check**: Verify users with correct role can push/merge
3. **Wildcard matching**: Test pattern matching with various branch names
4. **Cache behavior**: Verify cache invalidation on rule changes
5. **Group-level rules**: Test inheritance of protection rules from groups

## API Endpoints

### REST API - Protected Branches

| Method | Endpoint | Purpose | Permission |
|--------|----------|---------|------------|
| GET | `/api/v4/projects/:id/protected_branches` | List protected branches | `read_protected_branch` |
| GET | `/api/v4/projects/:id/protected_branches/:name` | Get single protected branch | `read_protected_branch` |
| POST | `/api/v4/projects/:id/protected_branches` | Protect a branch | `create_protected_branch` |
| PATCH | `/api/v4/projects/:id/protected_branches/:name` | Update protection settings | `update_protected_branch` |
| DELETE | `/api/v4/projects/:id/protected_branches/:name` | Unprotect a branch | `delete_protected_branch` |

**Key parameters for POST/PATCH:**
- `name` (required): Branch name or wildcard pattern
- `push_access_level`: Access level for push (default: 40/Maintainer)
- `merge_access_level`: Access level for merge (default: 40/Maintainer)
- `allow_force_push`: Boolean (default: false)

### REST API - Protected Tags

| Method | Endpoint | Purpose | Permission |
|--------|----------|---------|------------|
| GET | `/api/v4/projects/:id/protected_tags` | List protected tags | `read_protected_tag` |
| GET | `/api/v4/projects/:id/protected_tags/:name` | Get single protected tag | `read_protected_tag` |
| POST | `/api/v4/projects/:id/protected_tags` | Protect a tag | `create_protected_tags` |
| DELETE | `/api/v4/projects/:id/protected_tags/:name` | Unprotect a tag | `delete_protected_tag` |

**Key parameters for POST:**
- `name` (required): Tag name or wildcard pattern
- `create_access_level`: Access level for creation (default: 40/Maintainer)

### GraphQL

| Mutation | Purpose |
|----------|---------|
| `branchRuleCreate` | Create a branch rule (protected branch) |
| `branchRuleUpdate` | Update branch rule settings |
| `branchRuleDelete` | Delete a branch rule |

**Example GraphQL mutation:**
```graphql
mutation {
  branchRuleCreate(input: {
    projectPath: "my-group/my-project"
    name: "release-*"
  }) {
    branchRule {
      id
      name
    }
    errors
  }
}
```

### API Source Files

| File | Purpose |
|------|---------|
| `lib/api/protected_branches.rb` | REST API for protected branches |
| `lib/api/protected_tags.rb` | REST API for protected tags |
| `app/graphql/mutations/branch_rules/create.rb` | GraphQL create mutation |
| `app/graphql/mutations/branch_rules/update.rb` | GraphQL update mutation |
| `app/graphql/mutations/branch_rules/delete.rb` | GraphQL delete mutation |

## Git Push Enforcement

Branch protection is enforced at push time via Gitaly checks. Understanding this flow helps debug "permission denied" issues.

### Check Flow

```
git push
  → GitLab Shell receives push
  → Gitlab::Checks::SingleChangeAccess.validate!
    → Gitlab::Checks::BranchCheck.validate!
      → ProtectedBranch.protected?(project, branch_name)  # Uses CacheService
      → Check force push permissions
      → Check push/merge/create/delete permissions
```

### Key Files

| File | Purpose |
|------|---------|
| `lib/gitlab/checks/branch_check.rb` | Main branch protection enforcement |
| `lib/gitlab/checks/force_push.rb` | Force push detection |
| `lib/gitlab/checks/single_change_access.rb` | Orchestrates all checks |

### Error Messages

The `BranchCheck` class defines these error messages:

| Error | Meaning |
|-------|---------|
| `force_push_protected_branch` | User tried to force push without permission |
| `push_protected_branch` | User lacks push access to protected branch |
| `merge_protected_branch` | User lacks merge access to protected branch |
| `create_protected_branch` | User tried to create a protected branch without permission |
| `delete_default_branch` | Cannot delete the default branch |
| `non_master_delete_protected_branch` | Only maintainers/owners can delete protected branches |

## Troubleshooting

### "User can push but shouldn't be able to"

1. **Check cache staleness:**
   ```ruby
   # In rails console
   project = Project.find_by_full_path('group/project')
   ProtectedBranches::CacheService.new(project).refresh
   ```

2. **Verify protection exists:**
   ```ruby
   ProtectedBranch.protected?(project, 'branch-name')
   # => true/false
   ```

3. **Check access levels:**
   ```ruby
   ProtectedBranch.access_levels_for_ref(
     'branch-name',
     action: :push,
     protected_refs: project.all_protected_branches
   )
   ```

### "User can't push but should be able to"

1. **Check user's access level:**
   ```ruby
   user = User.find_by_username('username')
   project.team.max_member_access(user.id)
   # => 30 (Developer), 40 (Maintainer), etc.
   ```

2. **Check if branch matches a wildcard:**
   ```ruby
   ProtectedBranch.matching('feature/my-branch', protected_refs: project.protected_branches)
   # Returns matching ProtectedBranch records
   ```

3. **Check for group-level protection:**
   ```ruby
   project.all_protected_branches  # Includes group-level rules
   project.protected_branches      # Project-level only
   ```

### "Protection not applying to wildcard branches"

1. **Test pattern matching:**
   ```ruby
   pb = ProtectedBranch.new(name: 'release-*')
   pb.matches?('release-1.0')  # => true/false
   ```

2. **Check RefMatcher directly:**
   ```ruby
   matcher = ProtectedBranch::RefMatcher.new('release-*')
   matcher.matches?('release-1.0')
   ```

### "Cache not invalidating"

1. **Force cache refresh:**
   ```ruby
   ProtectedBranches::CacheService.new(project).refresh
   ```

2. **Check Redis directly:**
   ```ruby
   # The cache uses a Redis hash with project-specific key
   # TTL is 1 day, limit is 1000 entries per project
   ```

3. **Verify service is called on rule changes:**
   - `CreateService`, `UpdateService`, `DestroyService` should all call `CacheService.refresh`

### "EE features not working"

1. **Check license:**
   ```ruby
   License.feature_available?(:protected_refs_for_users)
   ```

2. **Verify EE module is loaded:**
   ```ruby
   ProtectedBranch.ancestors.include?(EE::ProtectedBranch)
   # => true if EE is loaded
   ```

## 📅 Known Issues & Active Work

### Active Epics

| Epic | Description | Status |
|------|-------------|--------|
| [Branch Rules: Beta Scope](https://gitlab.com/groups/gitlab-org/-/work_items/21651) | Policy-based branch rule management at group level | Active (FY27) |
| [Branch Rules Initiative](https://gitlab.com/groups/gitlab-org/-/work_items/20360) | Umbrella epic for branch rules vision | Active |

### Key Issues to Watch

| Issue | Description | Impact |
|-------|-------------|--------|
| [#583592](https://gitlab.com/gitlab-org/gitlab/-/issues/583592) | Wildcard preview shows too many branches | UI inconsistency |
| [#432856](https://gitlab.com/gitlab-org/gitlab/-/issues/432856) | `branch.protected` attribute inconsistent with API | Race condition |
| [#554195](https://gitlab.com/gitlab-org/gitlab/-/issues/554195) | Branch rules user stories | Design research |
| [#454639](https://gitlab.com/gitlab-org/gitlab/-/issues/454639) | Vision for Branch rules | Product direction |

### Protected Tags Feature Requests

| Issue | Description |
|-------|-------------|
| [#592297](https://gitlab.com/gitlab-org/gitlab/-/issues/592297) | Enhance protected tags with approval requirements |
| [#573271](https://gitlab.com/gitlab-org/gitlab/-/issues/573271) | Enable Git-based updates for protected tags |
| [#25072](https://gitlab.com/gitlab-org/gitlab/-/issues/25072) | Configure protected tags at group level |
| [#7018](https://gitlab.com/gitlab-org/gitlab/-/issues/7018) | Restrict protected tags to users/groups (API) |

### Feedback Collection

- [Soliciting User Feedback on Branch Rules](https://gitlab.com/gitlab-org/gitlab/-/issues/388149) - Active feedback thread

## 📅 Architecture & Planning Documents

### Google Docs (Internal)

| Document | Purpose | Owner |
|----------|---------|-------|
| [Source Code Roadmap and Priorities – FY27](https://docs.google.com/document/d/1YqRSbylr1oGeZOcaBUNPyPo2IG2Bum0Xaqvi5uTD4kM) | **Primary roadmap** - Branch Rules vision, quarterly milestones, competitive analysis | Marie-Christine Babin |
| [Branch Rules Weekly](https://docs.google.com/document/d/1Wv-9J0fs90Mzot1kGPCDAPeKfwmGb8rRSMEhJGU89Dg) | Weekly sync notes and decisions | Team |
| [Source Code Branch Rules: Design Vision](https://docs.google.com/presentation/d/1BtnGb1UOj5FSgdkILqEvqIZagbJDKVdm8DMLonQ45uk) | UX/Design vision presentation | Alyssa Trinh |
| [Problem & Opportunity](https://docs.google.com/presentation/d/1B5jLHsMVX1v0ShdUWH80r4RR5Fh0V8UbwsOhcDJ01Ic) | Customer impact, competitive gaps, business case | Marie-Christine Babin |
| [User Stories](https://docs.google.com/spreadsheets/d/1uzC3G09Jq3W8pigBfuuegpKqIAJv-zEwziitDQIZzmM) | Behaviors for validation, design, engineering | Team |
| [Customer List](https://docs.google.com/spreadsheets/d/1OUX200_9TJK1QclZMI4XeTAThPQbNVB9o9aZPVR9jtI) | Customer impact and outreach targets | PM |
| [Competitive Audit](https://docs.google.com/presentation/d/1CJgQyQK-VtTZG7IK03ujzUpgQDW6-lT_ZFB6xPGPPOY) | GitHub Rulesets comparison | Team |
| [Notes - Approval Rules Re Architecture Sync](https://docs.google.com/document/d/1ML9RuNZ9rMoVPqf68HWyAuyh7TloKgCViinZGIicwS8) | Approval rules rearchitecture (related) | Gavin Hinfey |

### GitLab Handbook / Blueprints

| Document | Purpose |
|----------|---------|
| [Rearchitect Approval Rules](https://handbook.gitlab.com/handbook/engineering/architecture/design-documents/rearchitect_approval_rules/) | Architecture design document for approval rules refactor |

### Key Epics for Architecture

| Epic | Description |
|------|-------------|
| [#21022 - Branch Rules: Foundation for Policy-Based Management](https://gitlab.com/groups/gitlab-org/-/work_items/21022) | Policy object model and group-level architecture |
| [#21023 - Branch Rules: Migration Path](https://gitlab.com/groups/gitlab-org/-/work_items/21023) | Migration from protected branches to branch rules |
| [#20360 - Branch Rules Initiative](https://gitlab.com/groups/gitlab-org/-/work_items/20360) | Umbrella epic - long-term vision |
| [#17802 - Edit Branch Rules Tech Debt](https://gitlab.com/groups/gitlab-org/-/work_items/17802) | Technical debt cleanup |

### Spike Issues

| Issue | Description |
|-------|-------------|
| [#591097](https://gitlab.com/gitlab-org/gitlab/-/work_items/591097) | Backend spike - Policy object model |
| [#597844](https://gitlab.com/gitlab-org/gitlab/-/work_items/597844) | Frontend spike - UI scaffolding for policy management |

### Branch Rules Vision Summary

From the FY27 roadmap document:

> **Vision**: Empower teams to protect and manage branches confidently and flexibly at scale.

**Two Models, One Choice**: Branch Rules is not an enhancement to Protected Branches — it's a new model that coexists alongside the legacy system:

| Aspect | Old Model: Protected Branches | New Model: Branch Rules |
|--------|------------------------------|------------------------|
| Status | Long-term support | Active development |
| Scope | Project-level only | Group-level with inheritance |
| Concept | "Protected Branches" as distinct entity | Branches exist; rules get applied |
| Settings | Fragmented across pages | Unified, branch-centric |

**Migration Principles**:
1. Independent coexistence — both systems supported long-term
2. User-controlled migration — users decide when/if to migrate
3. No breaking changes — non-migrated users unaffected
4. Safe migration — all configurations preserved exactly
5. Reversible — can revert to Protected Branches
6. Earned adoption — users migrate for value, not force

## 📅 Team & Communication

### Slack Channels

| Channel | Purpose |
|---------|---------|
| `#f_branch-rules` | **Primary** - Branch Rules initiative discussions, weekly syncs |
| `#g_create_source-code` | Source Code group general |
| `#g_create_source-code-be` | Backend engineering discussions |
| `#g_create_source-code-social` | Team social channel |

### Key People (as of May 2026)

| Role | Person | Focus |
|------|--------|-------|
| PM | Marie-Christine Babin (@mcbabin) | Branch Rules initiative lead |
| EM | Andre Richards (@andrevr) | Backend engineering |
| UX | Alyssa Trinh (@alyssatrinh) | Branch rules design vision |
| BE | Joe Woodward (@jwoodwardgl) | Custom roles, permissions, branch rules backend |
| BE | Paulina Sedlak-Jakubowska (@psjakubowska) | Branch rules implementation |

### Current Focus Areas (FY27)

Based on recent Slack discussions:

1. **Custom Roles for Protected Branches** ([#584313](https://gitlab.com/gitlab-org/gitlab/-/issues/584313))
   - `admin_protected_branch` ability support
   - Permission model refactoring
   - Target: 19.2

2. **Branch Rules Beta** ([#21651](https://gitlab.com/groups/gitlab-org/-/work_items/21651))
   - Policy-based branch rule management at group level
   - Enforcement levels: Required, Encouraged, None
   - Migration path from legacy protected branches

3. **API Strategy**
   - Plan to deprecate old protected branches APIs once branch rules is adopted
   - GraphQL-first approach for new features

### Customer Escalations Driving Work

- **AmFam** - Custom roles for protected branches (30,000+ repos)
- **ExactSciences** - Group-level branch protection policies

## Related Resources

- **Epic**: [Organizations Feature Parity - Source Code](https://gitlab.com/groups/gitlab-org/-/epics/20702)
- **Feature Category**: `source_code_management`
- **Group**: Source Code (Create Stage)
- **Slack**: `#g_source_code`, `#f_branch-rules`
- **API Docs**: [Protected Branches API](https://docs.gitlab.com/ee/api/protected_branches.html)
- **API Docs**: [Protected Tags API](https://docs.gitlab.com/ee/api/protected_tags.html)

## Related Skills

- `source-code-push-rules` - Push rules and secret blocking (Premium+)
- `source-code-code-owners` - CODEOWNERS file enforcement (Premium+)
- `source-code-merge-controls` - Merge request settings and approvals

---

## Skill Feedback

> **For agents**: After using this skill, please note any feedback in your session checkpoint to help improve this skill.

- **What was missing?** Information you had to search for that should be here
- **What was unhelpful?** Sections that added noise without value
- **What gotchas did you hit?** Undocumented issues that should be in Troubleshooting
- **What was most useful?** Sections that saved significant time/effort
