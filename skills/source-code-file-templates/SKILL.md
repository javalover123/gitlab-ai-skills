---
name: source-code-file-templates
description: Group file templates and custom project templates - Premium+ EE features for standardized templates
version: 1.0.0
license: MIT
---

# Source Code: File Templates

This skill covers GitLab's template features: **group file templates** (share Dockerfiles, .gitignore, CI/CD templates across a group) and **custom project templates** (create new projects from template projects). Both are Premium+ EE features that enable organizations to standardize development patterns.

> **📅 Maintenance Note**: Sections marked with 📅 contain time-sensitive information (team contacts, active issues, roadmap, architecture docs). These should be reviewed periodically. Last reviewed: **2026-05-23**.

## When to Use This Skill

Use this skill when:
- Working on group file templates (Dockerfiles, .gitignore, GitLab CI YAML templates)
- Implementing or debugging custom project templates
- Investigating template inheritance across group hierarchies
- Working with `TemplateFinder`, `CustomFileTemplates`, or `TemplateSetting`
- Debugging "template not found" or template visibility issues
- Understanding how templates propagate from instance → group → project

## Features Covered

| # | Feature | Tier | Description |
|---|---------|------|-------------|
| 1 | Group File Templates | Premium+ | Share Dockerfiles, .gitignore, CI/CD templates across a group |
| 2 | Custom Project Templates | Premium+ | Create new projects from template projects in a subgroup |
| 3 | Instance File Templates | Premium+ | Instance-wide file templates (admin setting) |
| 4 | Instance Project Templates | Premium+ | Instance-wide project templates (admin setting) |

## Key Codebase Areas

### Models

| File | Purpose |
|------|---------|
| `app/models/namespaces/template_setting.rb` | Stores `file_template_project_id` and `custom_project_templates_group_id` per namespace |
| `ee/app/models/ee/group.rb` | Group extensions for `checked_file_template_project`, `group_project_template_available?` |
| `ee/app/models/ee/namespace.rb` | Namespace extensions for `checked_file_template_project` |
| `ee/app/models/ee/application_setting.rb` | Instance-level `file_template_project` setting |

### Finders

| File | Purpose |
|------|---------|
| `app/finders/template_finder.rb` | Core template finder for vendored templates |
| `ee/app/finders/ee/template_finder.rb` | EE extension adding custom template support |
| `ee/app/finders/projects/group_templates_finder.rb` | Finds project templates available to a group |
| `ee/app/finders/groups_with_templates_finder.rb` | Finds groups that have project templates configured |

### Libraries

| File | Purpose |
|------|---------|
| `ee/lib/gitlab/custom_file_templates.rb` | Core logic for custom file templates - inheritance, lookup |
| `lib/gitlab/template/base_template.rb` | Base class for all template types |
| `lib/gitlab/template/dockerfile_template.rb` | Dockerfile template handling |
| `lib/gitlab/template/gitignore_template.rb` | .gitignore template handling |
| `lib/gitlab/template/gitlab_ci_yml_template.rb` | CI/CD YAML template handling |
| `ee/lib/gitlab/template/custom_template.rb` | Custom template base class |
| `ee/lib/gitlab/template/custom_dockerfile_template.rb` | Custom Dockerfile templates |
| `ee/lib/gitlab/template/custom_gitignore_template.rb` | Custom .gitignore templates |
| `ee/lib/gitlab/template/custom_gitlab_ci_yml_template.rb` | Custom CI/CD YAML templates |

### Controllers

| File | Purpose |
|------|---------|
| `app/controllers/projects/templates_controller.rb` | Project template endpoints |
| `ee/app/controllers/ee/admin/application_settings_controller.rb` | Instance template settings |
| `ee/app/controllers/ee/groups/params.rb` | Group params including `file_template_project_id` |

### Services

| File | Purpose |
|------|---------|
| `ee/app/services/ee/groups/update_service.rb` | Validates `file_template_project_id` changes |
| `ee/app/services/ee/projects/create_from_template_service.rb` | Creates projects from group templates |
| `ee/app/services/ee/projects/create_service.rb` | Project creation with template support |

## Test Locations

### Model Specs

| File | Coverage |
|------|----------|
| `spec/models/namespaces/template_setting_spec.rb` | Template setting validations |
| `ee/spec/models/ee/group_spec.rb` | Group template methods |

### Finder Specs

| File | Coverage |
|------|----------|
| `spec/finders/template_finder_spec.rb` | Core template finder |
| `ee/spec/finders/ee/template_finder_spec.rb` | EE template finder extensions |
| `ee/spec/finders/projects/group_templates_finder_spec.rb` | Group project templates |

### Library Specs

| File | Coverage |
|------|----------|
| `ee/spec/lib/gitlab/custom_file_templates_spec.rb` | Custom file template logic |
| `ee/spec/lib/gitlab/template/custom_templates_spec.rb` | Custom template classes |

## Documentation

| Path | Content |
|------|---------|
| [`doc/user/group/manage.md#group-file-templates`](https://docs.gitlab.com/ee/user/group/manage.html#group-file-templates) | Group file templates setup |
| [`doc/user/group/custom_project_templates.md`](https://docs.gitlab.com/ee/user/group/custom_project_templates.html) | Custom project templates |
| [`doc/administration/settings/instance_template_repository.md`](https://docs.gitlab.com/ee/administration/settings/instance_template_repository.html) | Instance template repository |
| [`doc/administration/custom_project_templates.md`](https://docs.gitlab.com/ee/administration/custom_project_templates.html) | Instance project templates |

## Common Patterns

### Template Inheritance Hierarchy

Templates are resolved from most-specific to least-specific:

```
Project → Parent Group → ... → Root Group → Instance
```

```ruby
# In Gitlab::CustomFileTemplates
def namespace_template_projects_hash
  project
    .ancestors_upto(nil)
    .preload_file_templates
    .select { |namespace| namespace.checked_file_template_project }
    .index_with { |namespace| namespace.checked_file_template_project }
end
```

**Key insight**: Templates from closer ancestors override those from further ancestors. Instance templates are the fallback.

### Checked vs Unchecked Template Project

Always use `checked_file_template_project` instead of `file_template_project`:

```ruby
# WRONG - bypasses visibility checks
group.file_template_project  # private method for a reason!

# CORRECT - includes visibility and feature checks
group.checked_file_template_project
```

**Key insight**: `checked_file_template_project` validates:
1. The project exists and is accessible
2. The feature `custom_file_templates_for_namespace` is available
3. The project is within the group hierarchy

### Template Setting Storage

Template settings are stored in `namespace_template_settings` table (not directly on namespaces):

```ruby
# Reading
group.file_template_project_id
# Delegates to: namespace_template_setting&.file_template_project_id

# Writing
group.file_template_project_id = project.id
# Creates/updates namespace_template_setting record
```

**Key insight**: Columns were moved from `namespaces` table to `namespace_template_settings` for better normalization. See "📅 Recent Migrations" section for details.

### Custom Project Templates Subgroup Requirement

Project templates must be in a **direct subgroup** of the group:

```ruby
# In Namespaces::TemplateSetting
def custom_project_templates_group_allowed
  return if custom_project_templates_group_id.blank?
  return if namespace&.children&.exists?(id: custom_project_templates_group_id)

  errors.add(:custom_project_templates_group_id, 'has to be a subgroup of the group')
end
```

**Key insight**: Nested subgroups are NOT supported - only direct children can be template sources.

## EE vs CE

### Core (Free) Features

| Feature | Implementation |
|---------|----------------|
| Vendored templates | `Gitlab::Template::*Template` classes |
| Issue/MR description templates | `Gitlab::Template::IssueTemplate`, `MergeRequestTemplate` |

### Premium+ Features (EE)

| Feature | Implementation | License Check |
|---------|----------------|---------------|
| Group file templates | `Gitlab::CustomFileTemplates` | `custom_file_templates_for_namespace` |
| Custom project templates | `Projects::GroupTemplatesFinder` | `group_project_templates` |
| Instance file templates | `ApplicationSetting.file_template_project` | `custom_file_templates` |

### Feature Availability Checks

```ruby
# Group file templates
group.feature_available?(:custom_file_templates_for_namespace)

# Group project templates
group.group_project_template_available?
# Equivalent to: group.feature_available?(:group_project_templates)

# Instance file templates
License.feature_available?(:custom_file_templates)
```

## API Endpoints

### REST API

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/v4/projects/:id/templates/:type` | List templates available to project |
| GET | `/api/v4/projects/:id/templates/:type/:name` | Get specific template |
| GET | `/api/v4/templates/licenses` | List license templates |
| GET | `/api/v4/templates/gitignores` | List .gitignore templates |
| GET | `/api/v4/templates/dockerfiles` | List Dockerfile templates |
| GET | `/api/v4/templates/gitlab_ci_ymls` | List CI/CD YAML templates |

### MCP Tool Parameters

#### gitlab_search (for templates)

| Parameter | Type | Description |
|-----------|------|-------------|
| `scope` | string | Use `blobs` to search template content |
| `project_id` | string | Template project path |
| `search` | string | Template name or content |

### Template Types

```ruby
# Valid template types for API
TEMPLATE_TYPES = %w[dockerfiles gitignores gitlab_ci_ymls licenses issues merge_requests]
```

### GraphQL

#### Types

| File | Purpose |
|------|---------|
| `app/graphql/types/ci/template_type.rb` | CI/CD template type |
| `app/graphql/types/work_items/description_template_type.rb` | Issue/MR description template type |

#### Resolvers

| File | Purpose |
|------|---------|
| `app/graphql/resolvers/ci/template_resolver.rb` | Resolve CI/CD templates |
| `app/graphql/resolvers/work_items/description_templates_resolver.rb` | Resolve description templates |
| `app/graphql/resolvers/work_items/description_template_content_resolver.rb` | Get template content |
| `ee/app/graphql/ee/resolvers/work_items/description_templates_resolver.rb` | EE extension for group templates |
| `ee/app/graphql/ee/resolvers/work_items/description_template_content_resolver.rb` | EE extension for template content |

#### Example Queries

```graphql
# Get CI/CD template
query {
  ciTemplate(name: "Ruby") {
    name
    content
  }
}

# Get description templates for a project
query {
  project(fullPath: "group/project") {
    workItemDescriptionTemplates {
      nodes {
        name
        content
        category
      }
    }
  }
}
```

## Testing Guidelines

### Running Tests

```bash
# Core template finder
bin/rspec spec/finders/template_finder_spec.rb

# EE template finder
bin/rspec ee/spec/finders/ee/template_finder_spec.rb

# Custom file templates
bin/rspec ee/spec/lib/gitlab/custom_file_templates_spec.rb

# Group project templates
bin/rspec ee/spec/finders/projects/group_templates_finder_spec.rb

# Group template settings
bin/rspec spec/models/namespaces/template_setting_spec.rb
```

### Test Factories

```ruby
# Group with file template project
create(:group).tap do |group|
  template_project = create(:project, :repository, group: group)
  group.update!(file_template_project_id: template_project.id)
end

# Group with project templates subgroup
create(:group).tap do |group|
  templates_subgroup = create(:group, parent: group)
  create(:project, :repository, group: templates_subgroup)
  group.update!(custom_project_templates_group_id: templates_subgroup.id)
end

# Namespace template setting
create(:namespace_template_setting,
  namespace: group,
  file_template_project_id: project.id
)
```

### Common Test Scenarios

1. **Template inheritance**: Verify templates from parent groups are accessible
2. **Feature availability**: Test behavior when license doesn't include feature
3. **Visibility checks**: Ensure private templates aren't exposed to non-members
4. **Template not found**: Handle missing templates gracefully

## Troubleshooting

### "Template not found" when template exists

1. **Check feature availability:**
   ```ruby
   group.feature_available?(:custom_file_templates_for_namespace)
   # => Should be true for Premium+
   ```

2. **Check template project is set correctly:**
   ```ruby
   group.checked_file_template_project
   # => Should return the project, not nil
   
   group.namespace_template_setting&.file_template_project_id
   # => Should have the project ID
   ```

3. **Check template file exists in correct location:**
   ```ruby
   # Templates must be in specific directories
   # Dockerfiles: Dockerfile/*
   # .gitignore: .gitignore/*
   # CI/CD: .gitlab-ci-yml/* or .gitlab/ci-templates/*
   ```

### Custom project templates not showing

1. **Check subgroup is direct child:**
   ```ruby
   group.children.exists?(id: templates_subgroup_id)
   # => Must be true (not nested subgroup)
   ```

2. **Check feature availability:**
   ```ruby
   group.group_project_template_available?
   # => Should be true for Premium+
   ```

3. **Check user has access:**
   ```ruby
   user.can?(:create_projects, group)
   # => User must be able to create projects in the group
   ```

### Templates not propagating to new projects

1. **Check import_type field:**
   ```ruby
   # Projects created from templates have:
   project.import_type
   # => "gitlab_custom_project_template" for group templates
   ```

2. **Check ProjectTemplateExportWorker ran:**
   ```ruby
   # In Sidekiq logs, look for:
   # "Template Export job started"
   ```

## 📅 Known Issues & Active Work

### Active Issues (from GitLab search)

| Issue | Description | Status |
|-------|-------------|--------|
| [#580728](https://gitlab.com/gitlab-org/gitlab/-/work_items/580728) | CI/CD config file path not propagating from templates | Open |
| [#351032](https://gitlab.com/gitlab-org/gitlab/-/work_items/351032) | Custom templates incorrectly inherit commit history | Open |
| [#470133](https://gitlab.com/gitlab-org/gitlab/-/work_items/470133) | Custom template behavior (security feature, not bug) | Closed |

### Recent Migrations

| Migration | Purpose |
|-----------|---------|
| `20260416102001` | Remove FK `namespaces.file_template_project_id` |
| `20260416102002` | Remove FK `namespaces.custom_project_templates_group_id` |
| `20260416102003` | Remove index on `namespaces.file_template_project_id` |
| `20260416102004` | Remove index on `namespaces.custom_project_templates_group_id` |

**Context**: Template settings were migrated from `namespaces` table to `namespace_template_settings` table in 2026.

### Feature Flags

| Flag | Type | Purpose |
|------|------|---------|
| `constrain_group_project_templates` | ops | Group selector for browsing templates outside group context (removed in 19.0) |

## 📅 Architecture & Planning Documents

| Document | Content |
|----------|---------|
| [Instance Template Repository](https://docs.gitlab.com/ee/administration/settings/instance_template_repository.html) | How to set up instance-wide templates |
| [Custom Project Templates](https://docs.gitlab.com/ee/user/group/custom_project_templates.html) | Group project template setup |

## 📅 Incident Learnings

### 2026-04-30: Custom Template Import Stuck on Staging

**What happened**: Projects created from custom templates got stuck with "import in progress" message on staging environment.

**Root cause**: `import_shared_storage` Sidekiq queue was not being processed - configuration issue on staging.

**Lessons**:
1. `ProjectTemplateExportWorker` must run for template-based project creation
2. Check queue size: `Sidekiq::Queue.new('import_shared_storage').size`
3. Job logs show "Template Export job started" with job_id

**Reference**: [Slack #g_import](https://gitlab.slack.com/archives/C04RDL3MEH5/p1777512258194069)

## 📅 Customer Guidance (from Slack)

### Template Usage Analytics

**Question**: "How can I see how often project templates are used?"

**Answer**: No native analytics UI exists. Workaround: Query projects via API and filter by `import_type: "gitlab_custom_project_template"`. This shows projects created from templates but not which specific template was used.

**Alternative**: For pipeline logic reuse tracking, consider CI/CD Components which have native visibility in the CI/CD Catalog.

**Source**: [Slack #gitlab-thepokémoncompanyinternational](https://gitlab.slack.com/archives/C04NNAJSY4D/p1776104600478139)

### American Family Insurance Escalation (2026-02)

**Issues raised**:
1. CI/CD configuration file path not propagating from templates to new projects
2. Custom templates incorrectly inheriting commit history (unlike built-in templates)
3. Blocking "golden path" initiative for standardized pipelines

**Status**: Active escalation - product team engagement requested

**Source**: [Slack #esc_americanfamilyinsurance](https://gitlab.slack.com/archives/C05TESLT9MZ/p1772046136403269)

## 📅 Team & Communication

### Slack Channels

| Channel | Purpose |
|---------|---------|
| `#g_create_source-code` | Source Code group general |
| `#f_groups_and_projects` | Groups and projects features |
| `#g_import` | Import team (handles template imports) |

### Feature Category

- **Feature Category**: `source_code_management`
- **Group**: Source Code (Create Stage)

## Related Resources

- **API Docs**: [Project Templates API](https://docs.gitlab.com/ee/api/project_templates.html)
- **API Docs**: [Templates API](https://docs.gitlab.com/ee/api/templates.html)

## Related Skills

- `source-code-branch-protection` - Protected branches can be included in project templates
- `source-code-push-rules` - Push rules can be included in project templates

---

## Skill Feedback

> **For agents**: After using this skill, please note any feedback in your session checkpoint to help improve this skill.

- **What was missing?** Information you had to search for that should be here
- **What was unhelpful?** Sections that added noise without value
- **What gotchas did you hit?** Undocumented issues that should be in Troubleshooting
- **What was most useful?** Sections that saved significant time/effort
