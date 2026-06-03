---
name: source-code-merge-controls
description: Guide for working with merge request approvals, merge methods, and squash settings in GitLab
version: 1.0.0
license: MIT
---

# Source Code: Merge Controls

This skill provides guidance for developers working on merge request approval features, merge methods (fast-forward, rebase), and squash settings in the GitLab codebase.

> **📅 Maintenance Note**: Sections marked with 📅 contain time-sensitive information (team contacts, active issues, roadmap). Last reviewed: **2026-05-23**.

## When to Use This Skill

Use this skill when:
- Implementing or modifying merge request approval rules
- Working with approval settings (author approval, committer approval, reset on push)
- Debugging approval state calculations
- Extending merge method options (fast-forward, rebase, squash)
- Working with the `ApprovalState` orchestrator class
- Implementing approval-related GraphQL or REST APIs

## Features Covered

| # | Feature | Tier | Description |
|---|---------|------|-------------|
| 4 | Required Merge Request Approvals | Premium+ | Rules requiring N approvals before merge |
| 29 | Optional Merge Request Approvals | Core+ | Basic approval without requirements |
| 36 | Merge Request Approval Settings | Premium+ | Author/committer approval, reset on push |
| 11 | Fast-forward merge with rebase | Core+ | Merge methods: ff, rebase, merge commit |
| 12 | Squash and merge | Core+ | Squash commits into single commit |

## Key Codebase Areas

### Models - Core (CE)

| File | Purpose |
|------|---------|
| `app/models/approval.rb` | Basic approval record (user approves MR) |
| `app/models/merge_request.rb` | MR model with `merge_method`, `squash_option` |
| `app/models/project.rb` | Project-level merge settings |
| `app/models/project_setting.rb` | Project settings including `squash_option` |
| `app/models/concerns/projects/squash_option.rb` | Squash option enum |

### Models - Approval Rules (EE - Premium+)

| File | Purpose |
|------|---------|
| `ee/app/models/approval_state.rb` | **Central orchestrator** - determines if MR is approved |
| `ee/app/models/approval_project_rule.rb` | Project-level approval rules (defaults) |
| `ee/app/models/approval_merge_request_rule.rb` | MR-specific approval rules |
| `ee/app/models/approval_wrapped_rule.rb` | Wrapper for presenting rules with calculated state |
| `ee/app/models/approval_wrapped_any_approver_rule.rb` | Wrapper for "any approver" rule type |
| `ee/app/models/approval_wrapped_code_owner_rule.rb` | Wrapper for code owner rules |
| `ee/app/models/approval_merge_request_rule_source.rb` | Links MR rules to source project rules |

### Key Concerns

| File | Purpose |
|------|---------|
| `ee/app/models/concerns/approval_rule_like.rb` | **Shared behavior** for all approval rule types |
| `ee/app/models/concerns/approval_rule_user_like.rb` | User association handling |
| `ee/app/models/concerns/security/approval_policy_filtering.rb` | Security policy integration |

### Services - Core (CE)

| File | Purpose |
|------|---------|
| `app/services/merge_requests/approval_service.rb` | Create approval for MR |
| `app/services/merge_requests/remove_approval_service.rb` | Remove/revoke approval |
| `app/services/merge_requests/merge_service.rb` | Execute merge with strategy |
| `app/services/merge_requests/squash_service.rb` | Squash commits into single commit |
| `app/services/merge_requests/rebase_service.rb` | Rebase MR branch onto target |

### Services - Approval Rules (EE)

| File | Purpose |
|------|---------|
| `ee/app/services/ee/merge_requests/approval_service.rb` | EE approval - SAML auth, password reauth |
| `ee/app/services/merge_requests/reset_approvals_service.rb` | Reset approvals on push |
| `ee/app/services/merge_requests/refresh/approval_service.rb` | Refresh approval rules on MR update |
| `ee/app/services/approval_rules/create_service.rb` | Create approval rules |
| `ee/app/services/approval_rules/update_service.rb` | Update approval rules |
| `ee/app/services/approval_rules/finalize_service.rb` | Finalize rules after merge |

### Controllers

| File | Purpose |
|------|---------|
| `app/controllers/projects/settings/merge_requests_controller.rb` | **Main settings** - merge method, squash |
| `ee/app/controllers/ee/projects_controller.rb` | EE project params including approval settings |

### GraphQL (EE)

| File | Purpose |
|------|---------|
| `ee/app/graphql/types/approval_rule_type.rb` | ApprovalRule type |
| `ee/app/graphql/types/approval_rule_type_enum.rb` | Rule type enum |
| `ee/app/graphql/types/merge_requests/approval_state_type.rb` | MergeRequestApprovalState |
| `ee/app/graphql/mutations/merge_requests/update_approval_rule.rb` | Update MR approval rule |

## Test Locations

### Model Specs

| File | Coverage |
|------|----------|
| `spec/models/approval_spec.rb` | Basic approval model |
| `ee/spec/models/approval_state_spec.rb` | Approval state orchestrator |
| `ee/spec/models/approval_project_rule_spec.rb` | Project approval rules |
| `ee/spec/models/approval_merge_request_rule_spec.rb` | MR approval rules |
| `ee/spec/models/approval_wrapped_rule_spec.rb` | Rule wrapper |

### Service Specs

| File | Coverage |
|------|----------|
| `spec/services/merge_requests/approval_service_spec.rb` | Approval creation |
| `spec/services/merge_requests/merge_service_spec.rb` | Merge execution |
| `spec/services/merge_requests/squash_service_spec.rb` | Squash commits |
| `spec/services/merge_requests/rebase_service_spec.rb` | Rebase MR |
| `ee/spec/services/merge_requests/reset_approvals_service_spec.rb` | Reset approvals |

### API Specs (EE)

| File | Coverage |
|------|----------|
| `ee/spec/requests/api/project_approvals_spec.rb` | Project approvals API |
| `ee/spec/requests/api/project_approval_rules_spec.rb` | Project rules API |
| `ee/spec/requests/api/merge_request_approvals_spec.rb` | MR approvals API |
| `ee/spec/requests/api/merge_request_approval_rules_spec.rb` | MR rules API |

## Documentation

| Path | Content |
|------|---------|
| [`doc/user/project/merge_requests/approvals/_index.md`](https://docs.gitlab.com/ee/user/project/merge_requests/approvals/) | Approvals overview |
| [`doc/user/project/merge_requests/approvals/rules.md`](https://docs.gitlab.com/ee/user/project/merge_requests/approvals/rules.html) | Approval rules |
| [`doc/user/project/merge_requests/approvals/settings.md`](https://docs.gitlab.com/ee/user/project/merge_requests/approvals/settings.html) | Approval settings |
| [`doc/user/project/merge_requests/methods/_index.md`](https://docs.gitlab.com/ee/user/project/merge_requests/methods/) | Merge methods |
| [`doc/user/project/merge_requests/squash_and_merge.md`](https://docs.gitlab.com/ee/user/project/merge_requests/squash_and_merge.html) | Squash and merge |

## Common Patterns

### ApprovalState - The Central Orchestrator

`ApprovalState` is the **key class** for understanding approval logic. It:
- Wraps approval rules for presentation
- Calculates approval requirements
- Determines if MR is approved
- Handles rule overrides

```ruby
# Get approval state for an MR
approval_state = merge_request.approval_state

# Check if approved
approval_state.approved?

# Get wrapped rules (for display)
approval_state.wrapped_approval_rules
# => [ApprovalWrappedRule, ApprovalWrappedCodeOwnerRule, ...]

# Get approvers needed
approval_state.approvers_left
```

### Verification Status Flow

```
MR created/updated
  → ApprovalState initialized
    → Loads project rules + MR-specific rules
    → Wraps rules with ApprovalWrappedRule
    → Calculates approvals_required vs approvals_received
    → Returns approved? status
```

### Rule Type Enum

```ruby
# ApprovalProjectRule / ApprovalMergeRequestRule
enum :rule_type, {
  regular: 0,        # User-defined rules
  code_owner: 1,     # CODEOWNERS-based
  report_approver: 2, # Security/license scan rules
  any_approver: 3    # Any user can approve
}
```

### Squash Option Enum

```ruby
# ProjectSetting / MergeRequest
enum :squash_option, {
  never: 0,       # Squash disabled
  always: 1,      # Always squash
  default_on: 2,  # Squash by default, can disable
  default_off: 3  # No squash by default, can enable
}
```

### Merge Method Settings

```ruby
# Project settings
project.merge_requests_ff_only_enabled      # Fast-forward only
project.merge_requests_rebase_enabled       # Rebase before merge

# Merge method values
# 'merge'        - Create merge commit
# 'rebase_merge' - Rebase then merge commit (semi-linear)
# 'ff'           - Fast-forward only (no merge commit)
```

### EE Module Prepending

CE classes are extended by EE modules using `prepend_mod`:

```ruby
# In app/services/merge_requests/approval_service.rb
class MergeRequests::ApprovalService
  # CE implementation
end

MergeRequests::ApprovalService.prepend_mod_with('MergeRequests::ApprovalService')

# In ee/app/services/ee/merge_requests/approval_service.rb
module EE::MergeRequests::ApprovalService
  # EE extensions (SAML auth, password reauth)
end
```

## EE vs CE

### Core (Free) Features

| Feature | Implementation |
|---------|----------------|
| Optional approvals | `Approval` model - simple approve/unapprove |
| Merge methods | `Project#merge_method` - ff, rebase, merge commit |
| Squash options | `ProjectSetting#squash_option` - never, always, default_on/off |

### Premium+ Features (EE)

| Feature | Implementation | License Check |
|---------|----------------|---------------|
| Required approvals | `ApprovalProjectRule#approvals_required` | `merge_request_approvers` |
| Multiple approval rules | Multiple `ApprovalProjectRule` records | `multiple_approval_rules_available?` |
| Approval settings | Project approval attributes | `merge_request_approvers` |
| Code owner approval | `ApprovalWrappedCodeOwnerRule` | `code_owner_approval_required` |
| Reset approvals on push | `reset_approvals_on_push` setting | `merge_request_approvers` |

### Feature Availability Checks

```ruby
# Check if approval rules are available
project.feature_available?(:merge_request_approvers)

# Check if multiple rules are available
project.multiple_approval_rules_available?

# Check if code owner approval is required
project.feature_available?(:code_owner_approval_required)
```

## API Endpoints

### REST API - Core

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/projects/:id/merge_requests/:mr_iid/approve` | Approve MR |
| POST | `/projects/:id/merge_requests/:mr_iid/unapprove` | Remove approval |

### REST API - Approval Rules (EE)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/projects/:id/approval_rules` | List project rules |
| POST | `/projects/:id/approval_rules` | Create project rule |
| PUT | `/projects/:id/approval_rules/:rule_id` | Update project rule |
| DELETE | `/projects/:id/approval_rules/:rule_id` | Delete project rule |
| GET | `/projects/:id/merge_requests/:mr_iid/approval_rules` | List MR rules |
| POST | `/projects/:id/merge_requests/:mr_iid/approval_rules` | Create MR rule |

### REST API - Approval Settings (EE)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/projects/:id/approval_settings` | Get project approval settings |
| PUT | `/projects/:id/approval_settings` | Update project approval settings |

### GraphQL

```graphql
# Query MR approval state
query {
  project(fullPath: "group/project") {
    mergeRequest(iid: "123") {
      approvalState {
        approved
        approvalsRequired
        approvalsLeft
        rules {
          name
          approvalsRequired
          approved
          approvedBy {
            nodes { username }
          }
          eligibleApprovers {
            nodes { username }
          }
        }
        suggestedApprovers {
          nodes { username }
        }
      }
    }
  }
}
```

## Testing Guidelines

### Running Tests

```bash
# Model specs
bin/rspec spec/models/approval_spec.rb
bin/rspec ee/spec/models/approval_state_spec.rb
bin/rspec ee/spec/models/approval_project_rule_spec.rb

# Service specs
bin/rspec spec/services/merge_requests/approval_service_spec.rb
bin/rspec spec/services/merge_requests/merge_service_spec.rb
bin/rspec ee/spec/services/merge_requests/reset_approvals_service_spec.rb

# API specs
bin/rspec ee/spec/requests/api/project_approval_rules_spec.rb
bin/rspec ee/spec/requests/api/merge_request_approvals_spec.rb
```

### Test Factories

```ruby
# Basic approval
create(:approval, merge_request: mr, user: user)

# Project approval rule (EE)
create(:approval_project_rule, project: project, approvals_required: 2)
create(:approval_project_rule, :code_owner, project: project)

# MR approval rule (EE)
create(:approval_merge_request_rule, merge_request: mr, approvals_required: 1)
create(:approval_merge_request_rule, :any_approver, merge_request: mr)

# With approvers
create(:approval_project_rule, project: project, users: [user1, user2])
create(:approval_project_rule, project: project, groups: [group])
```

### Common Test Scenarios

1. **Approval state calculation**: Test `approved?` with various rule configurations
2. **Rule inheritance**: Test project rules applying to MRs
3. **Rule overrides**: Test MR-specific rules overriding project rules
4. **Reset on push**: Test approvals removed when new commits pushed
5. **Merge method enforcement**: Test ff-only, rebase requirements
6. **Squash behavior**: Test squash options at project and MR level

## Troubleshooting

### "MR shows as not approved but has approvals"

1. **Check approval rules:**
   ```ruby
   # In rails console
   mr = MergeRequest.find(id)
   mr.approval_state.wrapped_approval_rules.each do |rule|
     puts "#{rule.name}: #{rule.approvals_received}/#{rule.approvals_required}"
   end
   ```

2. **Check if all rules are satisfied:**
   ```ruby
   mr.approval_state.approved?
   mr.approval_state.approvers_left
   ```

3. **Check for code owner rules:**
   ```ruby
   mr.approval_state.wrapped_approval_rules.select(&:code_owner?)
   ```

### "Approval rules not appearing on MR"

1. **Check project rules exist:**
   ```ruby
   project.approval_rules.count
   project.visible_approval_rules
   ```

2. **Check feature availability:**
   ```ruby
   project.feature_available?(:merge_request_approvers)
   ```

3. **Check rule sync:**
   ```ruby
   # Force refresh
   MergeRequests::SyncCodeOwnerApprovalRules.new(mr).execute
   ```

### "Merge method not working as expected"

1. **Check project settings:**
   ```ruby
   project.merge_method
   project.merge_requests_ff_only_enabled
   project.merge_requests_rebase_enabled
   ```

2. **Check MR compatibility:**
   ```ruby
   mr.can_be_merged?
   mr.ff_merge_possible?
   ```

## 📅 Known Issues & Active Work

### Active Issues (from GitLab search)

| Issue | Description | Status |
|-------|-------------|--------|
| [#506733](https://gitlab.com/gitlab-org/gitlab/-/issues/506733) | Reporter role cannot approve MR with overlapping protected branches | Open |
| [#557303](https://gitlab.com/gitlab-org/gitlab/-/issues/557303) | Display MRAP approval rules in MR UI while preventing edits | Open |
| [#515881](https://gitlab.com/gitlab-org/gitlab/-/issues/515881) | CODEOWNERS approval rules missing from initial MR webhook | Open |
| [#396631](https://gitlab.com/gitlab-org/gitlab/-/issues/396631) | Required approvals not blocking MR merge | Open |
| [#598657](https://gitlab.com/gitlab-org/gitlab/-/issues/598657) | Unauthorized approval rule reset weakens merge governance | Open |
| [#512116](https://gitlab.com/gitlab-org/gitlab/-/issues/512116) | Approval UI confusing after rebase | Open |
| [#431794](https://gitlab.com/gitlab-org/gitlab/-/issues/431794) | Project approval rules visible via REST but not GraphQL | Open |

### Active Development: Rearchitect Approval Rules

There is an ongoing effort to rearchitect approval rules. Key resources:

- **Design Doc**: [Rearchitect Approval Rules](https://handbook.gitlab.com/handbook/engineering/architecture/design-documents/rearchitect_approval_rules/)
- **Epic**: Rearchitect Approval Rules (internal)
- **Goal**: Unify project and MR rules with a single model, enable group-level rules

**Current architecture issues being addressed:**
- Rules are derived from project to MR (complex sync logic)
- Code owner rules tightly coupled to approval rules at DB level
- No group-level approval rules yet

## 📅 Architecture & Planning Documents

| Document | Content |
|----------|---------|
| [Rearchitect Approval Rules Design Doc](https://handbook.gitlab.com/handbook/engineering/architecture/design-documents/rearchitect_approval_rules/) | Architecture redesign for approval rules |
| [Approval Rules Re Architecture Sync Notes](https://docs.google.com/document/d/1ML9RuNZ9rMoVPqf68HWyAuyh7TloKgCViinZGIicwS8) | Meeting notes with implementation details |

## 📅 Customer Guidance (from Slack)

### Approval Rules Retroactive Application

**Common question**: "Do project-level approval rules apply retroactively to open MRs?"

**Answer**: It depends on the "Prevent editing approval rules in merge requests" setting:
- **If enabled**: Changes to project rules apply to existing MRs
- **If disabled**: Changes only affect new MRs; existing MRs keep their rules

**To retroactively apply rules**:
1. Enable "Prevent editing approval rules in merge requests"
2. Add/modify the project-level approval rule
3. Existing MRs will inherit the new rules

**Source**: [Slack #a_rivian_ext](https://gitlab.slack.com/archives/C018NJJNMDY/p1776960463063319)

### Rebase and Approval Reset

**Common confusion**: "Does `/rebase` reset approvals?"

**Answer**: Not always. GitLab uses `patch-id` to determine if the code changed:
- **Clean rebase (no conflicts)**: Approvals preserved
- **Rebase with merge conflicts**: Approvals reset (code changed)
- **MWPS (Merge When Pipeline Succeeds)**: Always needs to be re-set after rebase

**Source**: [Slack #engineering-fyi](https://gitlab.slack.com/archives/CJWA4E9UG/p1778584032234799)

### LDAP/SAML Sync and Approver Removal

**⚠️ Known Issue**: LDAP/SAML group sync can remove approvers from rules.

**What happens**: When SAML group sync runs with an empty group list, users are removed from groups. If those groups were configured as approvers, users lose approver status.

**Symptoms**:
- Approval rules exist but approvers list is empty
- No audit log entries for rule changes
- Affects multiple projects simultaneously

**Workaround**: Use MR Approval Policies (Ultimate) instead of approval rules, or ensure LDAP/SAML sync is stable.

**Source**: [Slack #support_self-managed](https://gitlab.slack.com/archives/C4Y5DRKLK/p1777522661395329)

## 📅 Key Settings Reference

### Project Approval Settings (EE)

| Setting | Purpose | Default |
|---------|---------|---------|
| `reset_approvals_on_push` | Remove approvals when new commits pushed | false |
| `disable_overriding_approvers_per_merge_request` | Prevent MR-level rule overrides | false |
| `merge_requests_author_approval` | Allow author to approve own MR | false |
| `merge_requests_disable_committers_approval` | Prevent committers from approving | false |
| `require_password_to_approve` | Require password/SAML reauth to approve | false |

### Project Merge Settings (CE)

| Setting | Purpose | Default |
|---------|---------|---------|
| `merge_method` | Merge strategy (merge/rebase_merge/ff) | merge |
| `squash_option` | Squash behavior (never/always/default_on/default_off) | default_off |
| `only_allow_merge_if_pipeline_succeeds` | Require passing pipeline | false |
| `only_allow_merge_if_all_discussions_are_resolved` | Require resolved discussions | false |

## 📅 Team & Communication

### Slack Channels

| Channel | Purpose |
|---------|---------|
| `#g_create_source-code` | Source Code group general |
| `#g_create_code-review` | Code Review group (shared ownership) |

### Feature Category

- **Feature Category**: `code_review_workflow` (approvals), `source_code_management` (merge methods)
- **Groups**: Source Code + Code Review (Create Stage)

> **Note**: Merge controls features are shared between Source Code and Code Review groups. Approvals are primarily owned by Code Review, while merge methods are owned by Source Code.

## Related Resources

- **Epic**: [Organizations Feature Parity - Source Code](https://gitlab.com/groups/gitlab-org/-/epics/20702)
- **API Docs**: [Merge Request Approvals API](https://docs.gitlab.com/ee/api/merge_request_approvals.html)
- **API Docs**: [Project-level Approval Rules API](https://docs.gitlab.com/ee/api/project_level_mr_approvals.html)

## Related Skills

- `source-code-branch-protection` - Branch protection and access controls
- `source-code-push-rules` - Push rules including approval requirements (Premium+)
- `source-code-code-owners` - CODEOWNERS integration with approvals

---

## Skill Feedback

> **For agents**: After using this skill, please note any feedback in your session checkpoint to help improve this skill.

- **What was missing?** Information you had to search for that should be here
- **What was unhelpful?** Sections that added noise without value
- **What gotchas did you hit?** Undocumented issues that should be in Troubleshooting
- **What was most useful?** Sections that saved significant time/effort
