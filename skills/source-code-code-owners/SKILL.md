---
name: source-code-code-owners
description: CODEOWNERS file parsing, validation, and MR approval integration (Premium+)
version: 1.0.0
license: MIT
---

# Source Code: Code Owners

The Code Owners feature defines who has expertise for specific parts of a project's codebase. It parses CODEOWNERS files, validates owner references, and integrates with merge request approval rules to require expert approval before merging.

> **Maintenance Note**: Sections marked with 📅 contain time-sensitive information (team contacts, active issues, roadmap, architecture docs). These should be reviewed periodically. Last reviewed: **2026-05-23**.

## When to Use This Skill

Use this skill when:
- Working on CODEOWNERS file parsing or validation
- Implementing or debugging Code Owner approval rules on merge requests
- Fixing issues with owner eligibility (users, groups, roles)
- Working on the integration between Code Owners and protected branches
- Debugging why approvals show as optional or why users don't appear as approvers

## Features Covered

| # | Feature | Tier | Description |
|---|---------|------|-------------|
| 30 | Code Owners | Premium+ | Define ownership rules via CODEOWNERS file, require approvals from experts |

## Key Codebase Areas

### Core Library (EE)

| File | Purpose |
|------|---------|
| `ee/lib/gitlab/code_owners.rb` | Main entry point - `for_blob`, `entries_for_merge_request`, `sections` |
| `ee/lib/gitlab/code_owners/file.rb` | Parses CODEOWNERS file, pattern matching with `File::fnmatch` |
| `ee/lib/gitlab/code_owners/loader.rb` | Loads entries for paths, resolves users/groups from references |
| `ee/lib/gitlab/code_owners/entry.rb` | Single CODEOWNERS entry (pattern, owners, section, approvals) |
| `ee/lib/gitlab/code_owners/section.rb` | Section metadata (name, optional, approvals, default_owners) |
| `ee/lib/gitlab/code_owners/section_parser.rb` | Parses section headers like `^[Documentation][2] @docs-team` |
| `ee/lib/gitlab/code_owners/reference_extractor.rb` | Extracts @usernames, @groups, @@roles from owner strings |
| `ee/lib/gitlab/code_owners/users_loader.rb` | Resolves usernames/emails to User objects |
| `ee/lib/gitlab/code_owners/groups_loader.rb` | Resolves group paths to Group objects |
| `ee/lib/gitlab/code_owners/errors.rb` | Validation error collection |
| `ee/lib/gitlab/code_owners/error.rb` | Individual validation error |

### Owner Validation (EE)

| File | Purpose |
|------|---------|
| `ee/lib/gitlab/code_owners/owner_validation/process.rb` | Orchestrates validation pipeline |
| `ee/lib/gitlab/code_owners/owner_validation/accessible_owners_filter.rb` | Filters owners with project access |
| `ee/lib/gitlab/code_owners/owner_validation/eligible_approvers_filter.rb` | Filters users who can approve MRs |
| `ee/lib/gitlab/code_owners/owner_validation/eligible_approver_groups_filter.rb` | Filters groups with eligible approvers |
| `ee/lib/gitlab/code_owners/owner_validation/qualified_groups_filter.rb` | Filters groups meeting role requirements |

### Services

| File | Purpose |
|------|---------|
| `ee/app/services/merge_requests/sync_code_owner_approval_rules.rb` | Syncs CODEOWNERS entries to MR approval rules |
| `ee/app/services/merge_requests/reviewer_assignment/code_owners_strategy.rb` | Auto-assigns reviewers based on Code Owners |

### Models

| File | Purpose |
|------|---------|
| `ee/app/models/approval_wrapped_code_owner_rule.rb` | Wraps approval rule with Code Owner logic |
| `ee/app/models/protected_branch/required_code_owners_section.rb` | Links protected branches to required sections |

### Workers

| File | Purpose |
|------|---------|
| `ee/app/workers/merge_requests/sync_code_owner_approval_rules_worker.rb` | Background job to sync approval rules |

### GraphQL

| File | Purpose |
|------|---------|
| `ee/app/graphql/ee/types/repository/code_owner_validation_type.rb` | Validation result type |
| `ee/app/graphql/ee/types/repository/code_owner_error_type.rb` | Individual error type |

### Frontend

| File | Purpose |
|------|---------|
| `ee/app/assets/javascripts/vue_shared/components/code_owners/code_owners.vue` | Code Owners display component |
| `ee/app/assets/javascripts/graphql_shared/queries/code_owners_info.query.graphql` | GraphQL query for Code Owners |

### Views

| File | Purpose |
|------|---------|
| `ee/app/views/projects/merge_requests/_code_owner_approval_rules.html.haml` | MR approval rules display |
| `ee/app/views/protected_branches/ee/_code_owner_approval_form.html.haml` | Protected branch settings form |
| `ee/app/views/protected_branches/ee/_code_owner_approval_table.html.haml` | Protected branch settings table |

## Test Locations

### Library Specs

| File | Coverage |
|------|----------|
| `ee/spec/lib/gitlab/code_owners_spec.rb` | Main module methods |
| `ee/spec/lib/gitlab/code_owners/file_spec.rb` | File parsing, pattern matching |
| `ee/spec/lib/gitlab/code_owners/loader_spec.rb` | Entry loading, user/group resolution |
| `ee/spec/lib/gitlab/code_owners/entry_spec.rb` | Entry behavior |
| `ee/spec/lib/gitlab/code_owners/section_parser_spec.rb` | Section header parsing |

### Service Specs

| File | Coverage |
|------|----------|
| `ee/spec/services/merge_requests/sync_code_owner_approval_rules_spec.rb` | Approval rule syncing |
| `ee/spec/services/merge_requests/reviewer_assignment/code_owners_strategy_spec.rb` | Auto-reviewer assignment |

### Feature Specs

| File | Coverage |
|------|----------|
| `ee/spec/features/merge_request/code_owner_approval_rules_spec.rb` | MR approval UI |
| `ee/spec/features/merge_request/code_owner_approvals_reset_after_merging_to_source_branch_spec.rb` | Approval reset behavior |
| `ee/spec/features/merge_request/code_owner_approvals_reset_after_pushing_merge_conflict_spec.rb` | Conflict handling |
| `ee/spec/features/projects/view_blob_with_code_owners_spec.rb` | File view with owners |

### Other Specs

| File | Coverage |
|------|----------|
| `ee/spec/lib/gitlab/checks/diffs/code_owners_check_spec.rb` | Push checks |
| `ee/spec/models/approval_wrapped_code_owner_rule_spec.rb` | Wrapped rule behavior |
| `ee/spec/models/protected_branch/required_code_owners_section_spec.rb` | Protected branch integration |
| `ee/spec/graphql/api/validate_code_owner_file_spec.rb` | GraphQL validation API |

## Documentation

| Path | Content |
|------|---------|
| [`doc/user/project/codeowners/_index.md`](https://docs.gitlab.com/ee/user/project/codeowners/) | Overview, setup, protected branches |
| [`doc/user/project/codeowners/reference.md`](https://docs.gitlab.com/ee/user/project/codeowners/reference.html) | Syntax reference, sections, patterns |
| [`doc/user/project/codeowners/advanced.md`](https://docs.gitlab.com/ee/user/project/codeowners/advanced.html) | Pattern matching, multiple approvals, inheritance |
| [`doc/user/project/codeowners/troubleshooting.md`](https://docs.gitlab.com/ee/user/project/codeowners/troubleshooting.html) | Common issues, validation |

## Common Patterns

### CODEOWNERS File Locations

GitLab checks these locations in order (first found wins):

```ruby
FILE_NAME = 'CODEOWNERS'
FILE_PATHS = [FILE_NAME, "docs/#{FILE_NAME}", ".gitlab/#{FILE_NAME}"].freeze
# Checks: ./CODEOWNERS, ./docs/CODEOWNERS, ./.gitlab/CODEOWNERS
```

### Pattern Matching

Uses `File::fnmatch` with specific flags:

```ruby
# FNM_DOTMATCH - allows * to match dotfiles like .gitignore
# FNM_PATHNAME - prevents * from matching / path separator
FNMATCH_FLAGS = (::File::FNM_DOTMATCH | ::File::FNM_PATHNAME).freeze

def path_matches?(pattern, path)
  ::File.fnmatch?(pattern, path, FNMATCH_FLAGS)
end
```

**Key insight**: Patterns are normalized before matching. A bare `*` becomes `/**/*`, patterns without leading `/` get `/**/` prefix.

### Section Header Parsing

Section headers support optional markers, approval counts, and default owners:

```ruby
# Examples:
# [Documentation]           - Required section
# ^[Documentation]          - Optional section (^ prefix)
# [Documentation][2]        - Requires 2 approvals
# [Documentation] @docs     - Default owner for section
# ^[Documentation][2] @docs - All combined
```

### Entry Resolution Flow

```
1. Parse CODEOWNERS file → sections + entries
2. For each modified path in MR:
   a. Find matching entries (last match per section wins)
   b. Extract owner references (@user, @group, @@role)
3. Resolve references:
   a. UsersLoader: username/email → User objects
   b. GroupsLoader: group path → Group objects  
   c. Entry.roles: @@role → role symbols
4. Create/update ApprovalMergeRequestRule for each entry
```

### Feature Availability Check

```ruby
# Always check feature availability before Code Owners operations
return [] unless project.feature_available?(:code_owners)
```

### Approval Rule Sync

The `SyncCodeOwnerApprovalRules` service keeps MR approval rules in sync:

```ruby
# Called when MR is created/updated or CODEOWNERS changes
MergeRequests::SyncCodeOwnerApprovalRules.new(merge_request).execute

# Creates ApprovalMergeRequestRule with:
# - rule_type: :code_owner
# - name: pattern (e.g., "*.rb")
# - section: section name
# - users/groups: resolved from entry
# - approvals_required: from section header
```

## EE vs CE

### This is an EE-Only Feature

Code Owners is **Premium+ only**. All code lives in `ee/` directories.

### Feature Availability Checks

```ruby
# Project-level check
project.feature_available?(:code_owners)

# Protected branch check for requiring approval
project.code_owner_approval_required_available?
ProtectedBranch.branch_requires_code_owner_approval?(project, branch_name)
```

### License Enforcement Points

| Location | Check |
|----------|-------|
| `Gitlab::CodeOwners.for_blob` | `project.feature_available?(:code_owners)` |
| `Gitlab::CodeOwners.entries_for_merge_request` | `project.feature_available?(:code_owners)` |
| `ApprovalWrappedCodeOwnerRule#branch_requires_code_owner_approval?` | `project.code_owner_approval_required_available?` |

## API Endpoints

### REST API

Code Owners doesn't have a dedicated REST API. Related settings are exposed through:

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/v4/projects/:id/protected_branches/:name` | Includes `code_owner_approval_required` |
| PATCH | `/api/v4/projects/:id/protected_branches/:name` | Set `code_owner_approval_required` |
| GET | `/api/v4/projects/:id/approval_settings` | Includes `selective_code_owner_removals` |
| PUT | `/api/v4/projects/:id/approval_settings` | Set `selective_code_owner_removals` |
| GET | `/api/v4/projects/:id/merge_requests/:iid/approval_state` | Rules include `code_owner: true/false` |

### GraphQL

```graphql
# Get Code Owners for a file/blob
query {
  project(fullPath: "group/project") {
    repository {
      # Path to CODEOWNERS file (if exists)
      codeOwnersPath
      
      # Get owners for a specific file
      blobs(paths: ["app/models/user.rb"], ref: "main") {
        nodes {
          codeOwners {
            username
            name
          }
        }
      }
    }
  }
}

# Validate CODEOWNERS file
query {
  project(fullPath: "group/project") {
    repository {
      validateCodeownerFile(ref: "main") {
        total
        validationErrors {
          code
          lines
        }
      }
    }
  }
}
```

**GraphQL Types:**
- `RepositoryCodeownerValidation` - Validation result with error count
- `RepositoryCodeownerError` - Individual validation error with code and line numbers

## Owner Eligibility Rules

### User Eligibility

Users referenced by `@username` must be authorized for the project:
- Direct membership with Developer, Maintainer, or Owner role
- Membership in project's group (direct or inherited)
- Membership in a group invited to the project

### Group Eligibility

Groups referenced by `@group_name` or `@nested/group/names`:
- Only **direct members** of the referenced group are eligible
- Inherited members are NOT included
- Group must be invited to project with Developer+ role

### Role Eligibility (@@role)

Roles referenced by `@@developer`, `@@maintainer`, `@@owner`:
- Only Developer, Maintainer, Owner roles can be Code Owners
- Only **direct project members** with that role are eligible
- Roles are NOT inclusive (@@developer doesn't include maintainers)

## Testing Guidelines

### Running Tests

```bash
# Core library specs
bin/rspec ee/spec/lib/gitlab/code_owners/

# Service specs
bin/rspec ee/spec/services/merge_requests/sync_code_owner_approval_rules_spec.rb

# Feature specs (slower, full stack)
bin/rspec ee/spec/features/merge_request/code_owner_approval_rules_spec.rb

# All Code Owners related
bin/rspec --pattern '**/code_owner*_spec.rb'
```

### Test Factories

```ruby
# Create project with CODEOWNERS file
let(:project) { create(:project, :repository) }

# Add CODEOWNERS content
project.repository.create_file(
  user,
  'CODEOWNERS',
  "*.rb @#{user.username}",
  message: 'Add CODEOWNERS',
  branch_name: 'master'
)

# Create MR with modified files
let(:merge_request) do
  create(:merge_request,
    source_project: project,
    target_project: project,
    source_branch: 'feature',
    target_branch: 'master')
end

# Stub license for EE features
stub_licensed_features(code_owners: true)
```

### Common Test Scenarios

1. **Pattern matching**: Test various glob patterns match expected files
2. **Section parsing**: Test optional sections, approval counts, default owners
3. **Owner resolution**: Test user, group, and role resolution
4. **Approval rule sync**: Test rules created/updated/deleted correctly
5. **Eligibility**: Test users/groups filtered by access level
6. **Protected branch integration**: Test approval required when enabled

## Troubleshooting

### "Approvals shown as optional"

A Code Owner approval rule is optional if:
1. User/group is not a member of the project
2. User/group reference is malformed or inaccessible
3. Code Owner approval on protected branch is not enabled
4. Section is marked as optional (`^[Section]`)
5. No eligible approvers due to MR approval settings conflicts

**Debug in Rails console:**
```ruby
project = Project.find_by_full_path('group/project')
mr = project.merge_requests.find_by(iid: 123)

# Check if feature is available
project.feature_available?(:code_owners)

# Check protected branch setting
ProtectedBranch.branch_requires_code_owner_approval?(project, mr.target_branch)

# Get Code Owner entries for MR
entries = Gitlab::CodeOwners.entries_for_merge_request(mr)
entries.each { |e| puts "#{e.pattern}: #{e.users.map(&:username)}, #{e.groups.map(&:full_path)}" }
```

### "User not shown as possible approver"

Check:
1. MR approval settings don't prevent the user from approving
2. Group visibility - private groups hide members from non-members
3. Username spelling in CODEOWNERS file
4. External users can't see internal groups

### "Approval rule is invalid"

This occurs when a Code Owner is not a direct member of the project.

**Fix:** Invite the group or user to the project directly.

### CODEOWNERS not updated when names change

CODEOWNERS file is NOT automatically updated when users/groups rename. You must manually edit the file.

**Prevention:** Use SAML SSO to prevent username changes.

## 📅 Known Issues & Active Work

### Active Issues (from GitLab search)

| Issue | Description | Status |
|-------|-------------|--------|
| [#238196](https://gitlab.com/gitlab-org/gitlab/-/issues/238196) | Bug in Code Owners / MR Approvals widget - section shows but no owner avatar | Open |
| [#419008](https://gitlab.com/gitlab-org/gitlab/-/issues/419008) | "Allowed to push" should bypass CODEOWNERS approvals in MRs | Open |
| [#595711](https://gitlab.com/gitlab-org/gitlab/-/issues/595711) | code_owner_approval_required not inherited from project templates | Open |
| [#580286](https://gitlab.com/gitlab-org/gitlab/-/issues/580286) | FF Rollout: optimize_codeowners_group_validation - performance optimization | In Progress |
| [#288851](https://gitlab.com/gitlab-org/gitlab/-/issues/288851) | Code Owners cannot inherit members from parent groups | Open |

### Feature Flags

| Flag | Type | Purpose |
|------|------|---------|
| `optimize_codeowners_group_validation` | ops | Performance optimization for group validation queries |
| `codeowner_role_approvers` | removed 17.9 | Role-based Code Owners (@@developer, @@maintainer) |
| `codeowners_file_exclusions` | removed 17.11 | Exclusion patterns (!pattern) |
| `accessible_code_owners_validation` | removed 18.2 | CODEOWNERS file validation UI |
| `check_inherited_groups_for_codeowners` | removed 18.8 | Groups shared with parent groups |

## 📅 Incident Learnings

### 2026-02-23: CODEOWNERS Change Triggers Gitaly Saturation (Dedicated)

**What happened**: A customer updated CODEOWNERS files across many repositories without updating the git-repo manifest's revision parameter. This triggered an edge case where CI runners performed unshallowing fetches (full clones) instead of shallow clones, saturating Gitaly.

**Root cause**: When CODEOWNERS changed but the manifest revision didn't match, git-repo's ancestry check failed, causing it to unshallow every repository.

**Lessons**:
1. CODEOWNERS changes can have unexpected downstream effects on CI behavior
2. Large-scale CODEOWNERS updates should be coordinated with manifest updates
3. Monitor for sudden spikes in unshallowing fetch volume

**Reference**: [Incident Review](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/team/-/work_items/11600)

## 📅 Customer Guidance (from Slack)

### "Can CODEOWNERS be the ONLY approvers?"

**Question**: "Customer wants CODEOWNERS as the only MR approvers, but other eligible users still see the Approve button."

**Answer**: The CODEOWNERS requirement ensures their approval is *required*, but by default other eligible members can still add approvals (they just won't satisfy the CODEOWNERS rule). Removing the "All eligible users" rule and only defining CODEOWNER-based rules is the closest you can get.

**Source**: [#spt_pairing](https://gitlab.slack.com/archives/C03UW0HPBGD/p1773293558981299)

### "Approvals reset after rebasing with target branch"

**Question**: "When a user merges with mainline and files owned by CODEOWNERS were touched, approvals reset even though the developer didn't change those files."

**Answer**: A merge commit changes the patch-id, triggering approval reset. Using 'Fast forward merge' or 'Semi Linear' forces a rebase instead, which doesn't change patch-id. However, this isn't directly linked to Code Owner approval - it's the general approval reset behavior.

**Source**: [#g_create_code-review](https://gitlab.slack.com/archives/C01EMBKS5DW/p1772039515800829)

### "CODEOWNERS vs Approval Rules - when to use which?"

**Question**: "What's the difference between CODEOWNERS and regular approval rules?"

**Answer**: 
- **CODEOWNERS**: For path-based ownership - "who owns this file/directory"
- **Approval Rules**: For expertise-based approval - "who should review this type of change"

CODEOWNERS is the only way to require approval based on *which files changed*. Regular approval rules apply to all MRs regardless of files.

**Source**: [#g_create_source-code](https://gitlab.slack.com/archives/CK75EF2A2/p1774249382270609)

### "Incompatibility with Global SAML/LDAP group memberships lock"

**Question**: "Why can't we use groups as Code Owners when Global SAML group memberships lock is enabled?"

**Answer**: Code Owners requires direct group memberships to projects. Global group memberships locks prevent groups from being invited as direct members. Options:
1. Use individual users as Code Owners instead of groups
2. Disable the Global group memberships lock if group-based Code Owners is higher priority

**Source**: [Troubleshooting docs](https://docs.gitlab.com/ee/user/project/codeowners/troubleshooting.html#incompatibility-with-global-group-memberships-locks)

### "Why are we getting 6 maintainer suggestions for 3 CODEOWNERS rules?"

**Question**: "After removing BE maintainers from the * rule, I'm getting 6 distinct maintainer suggestions for 3 CODEOWNERS rules."

**Answer**: This is expected behavior. The only requirement is that the relevant maintainers hit approve in the "Requires X approvals from Code Owners" section. The suggestions show all eligible approvers, not just the minimum required.

**Source**: [#backend](https://gitlab.slack.com/archives/C8HG8D9MY/p1775595506937139)

## 📅 Team & Communication

### Slack Channels

| Channel | Purpose |
|---------|---------|
| `#g_create_source-code` | Source Code group general |
| `#g_create_source-code-be` | Backend discussions |
| `#g_create_code-review` | Code Review group (shared ownership of approvals) |

### Feature Category

- **Feature Category**: `source_code_management`
- **Group**: Source Code (Create Stage)
- **PM**: Marie-Christine Babin
- **BE EM**: andrevr
- **FE EM**: andrevr

## Related Resources

- **Video**: [Code Owners Introduction](https://www.youtube.com/watch?v=RoyBySTUSB0)
- **Epic**: [Organizations Feature Parity #20702](https://gitlab.com/groups/gitlab-org/-/epics/20702)
- **Handbook**: [CODEOWNERS approval guidance](https://docs.gitlab.com/development/code_review/#codeowners-approval)

## Related Skills

- `source-code-branch-protection` - Protected branches integrate with Code Owners for required approvals
- `source-code-merge-controls` - Approval rules work alongside Code Owner rules
- `source-code-push-rules` - Push rules can complement Code Owners for enforcement

---

## Skill Feedback

> **For agents**: After using this skill, please note any feedback in your session checkpoint to help improve this skill.

- **What was missing?** Information you had to search for that should be here
- **What was unhelpful?** Sections that added noise without value
- **What gotchas did you hit?** Undocumented issues that should be in Troubleshooting
- **What was most useful?** Sections that saved significant time/effort
