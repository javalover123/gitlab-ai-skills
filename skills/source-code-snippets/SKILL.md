---
name: source-code-snippets
description: Snippets - versioned code/text sharing with Git repositories
version: 1.0.0
license: MIT
---

# Source Code: Snippets

Snippets are versioned code and text sharing features backed by Git repositories. They support multiple files, syntax highlighting, comments, embedding, and can be personal (user-owned) or project-scoped.

> **📅 Maintenance Note**: Sections marked with 📅 contain time-sensitive information (team contacts, active issues, roadmap, architecture docs). These should be reviewed periodically. Last reviewed: **2026-05-23**.

## When to Use This Skill

Use this skill when:
- Working on snippet CRUD operations
- Implementing snippet repository features (versioning, multi-file)
- Working on snippet visibility and access control
- Debugging snippet embedding or cloning issues
- Working on snippet search or statistics

## Features Covered

| # | Feature | Tier | Description |
|---|---------|------|-------------|
| 31 | Snippets | Core+ | Versioned code/text sharing with Git repositories |

## Key Codebase Areas

### Models

| File | Purpose |
|------|---------|
| `app/models/snippet.rb` | Base snippet model with visibility, content, versioning |
| `app/models/personal_snippet.rb` | User-owned snippets (STI subclass) |
| `app/models/project_snippet.rb` | Project-scoped snippets (STI subclass) |
| `app/models/snippet_repository.rb` | Git repository backing for snippets |
| `app/models/snippet_blob.rb` | Individual file in multi-file snippet |
| `app/models/snippet_statistics.rb` | Storage statistics for snippets |
| `app/models/snippet_user_mention.rb` | @mentions in snippets |
| `app/models/snippet_input_action.rb` | File operations (create, update, delete, move) |
| `app/models/snippet_input_action_collection.rb` | Collection of file operations |

### Services

| File | Purpose |
|------|---------|
| `app/services/snippets/base_service.rb` | Base service with shared logic |
| `app/services/snippets/create_service.rb` | Create snippet with repository |
| `app/services/snippets/update_service.rb` | Update snippet content/metadata |
| `app/services/snippets/destroy_service.rb` | Delete snippet and repository |
| `app/services/snippets/bulk_destroy_service.rb` | Batch delete snippets |
| `app/services/snippets/count_service.rb` | Count snippets for user/project |
| `app/services/snippets/update_statistics_service.rb` | Update storage statistics |
| `app/services/snippets/repository_validation_service.rb` | Validate repository state |
| `app/services/snippets/update_repository_storage_service.rb` | Move repository storage |
| `app/services/search/snippet_service.rb` | Search snippets |

### Controllers

| File | Purpose |
|------|---------|
| `app/controllers/snippets_controller.rb` | Personal snippets UI |
| `app/controllers/projects/snippets_controller.rb` | Project snippets UI |
| `app/controllers/dashboard/snippets_controller.rb` | User dashboard snippets |
| `app/controllers/explore/snippets_controller.rb` | Public snippets exploration |
| `app/controllers/concerns/snippets_actions.rb` | Shared controller actions |
| `app/controllers/concerns/snippets_sort.rb` | Sorting logic |

### Finders

| File | Purpose |
|------|---------|
| `app/finders/snippets_finder.rb` | Query snippets with filters |

### GraphQL

| File | Purpose |
|------|---------|
| `app/graphql/resolvers/snippets_resolver.rb` | Root snippets query |
| `app/graphql/resolvers/projects/snippets_resolver.rb` | Project snippets |
| `app/graphql/resolvers/users/snippets_resolver.rb` | User snippets |

### Helpers

| File | Purpose |
|------|---------|
| `app/helpers/snippets_helper.rb` | View helpers |
| `app/helpers/routing/snippets_helper.rb` | URL helpers |

## Snippet Types

### Personal Snippets

- Owned by a user, not associated with any project
- Can be public, internal, or private
- Stored in user's namespace

### Project Snippets

- Associated with a specific project
- Visibility constrained by project visibility
- Stored in project's namespace

```ruby
# STI inheritance
class PersonalSnippet < Snippet; end
class ProjectSnippet < Snippet; end

# Check type
snippet.is_a?(PersonalSnippet)
snippet.is_a?(ProjectSnippet)
```

## Common Patterns

### Snippet Visibility

```ruby
# Visibility levels (same as projects)
Snippet::PRIVATE   # 0 - Only author (personal) or project members (project)
Snippet::INTERNAL  # 10 - Authenticated users (disabled on GitLab.com)
Snippet::PUBLIC    # 20 - Everyone

# Project snippets: project visibility takes precedence
# A public snippet in a private project is only visible to project members
```

### Multi-File Snippets

Snippets can contain up to 10 files:

```ruby
MAX_FILE_COUNT = 10

# Files are stored as blobs in the snippet's Git repository
snippet.blobs  # Returns array of SnippetBlob objects

# File operations via SnippetInputAction
actions = [
  { action: :create, file_path: 'file1.rb', content: '...' },
  { action: :update, file_path: 'file2.rb', content: '...' },
  { action: :delete, file_path: 'file3.rb' },
  { action: :move, file_path: 'new.rb', previous_path: 'old.rb' }
]
```

### Snippet Repository

Each snippet has a backing Git repository:

```ruby
# Repository is created on first content save
snippet.repository
snippet.repository.exists?

# Clone URL
snippet.http_url_to_repo
snippet.ssh_url_to_repo

# Repository path
snippet.repository.full_path  # e.g., "snippets/123"
```

### Content Size Limits

```ruby
# Content size controlled by admin setting
validates :content, bytesize: { maximum: -> { Gitlab::CurrentSettings.snippet_size_limit } }

# Default: 50MB (configurable in admin settings)
```

## API Endpoints

### REST API

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/v4/snippets` | List authenticated user's snippets |
| GET | `/api/v4/snippets/public` | List public snippets |
| GET | `/api/v4/snippets/:id` | Get single snippet |
| POST | `/api/v4/snippets` | Create personal snippet |
| PUT | `/api/v4/snippets/:id` | Update snippet |
| DELETE | `/api/v4/snippets/:id` | Delete snippet |
| GET | `/api/v4/snippets/:id/raw` | Get raw content |
| GET | `/api/v4/projects/:id/snippets` | List project snippets |
| POST | `/api/v4/projects/:id/snippets` | Create project snippet |

### GraphQL

```graphql
query {
  # Get snippets for current user
  snippets(first: 10) {
    nodes {
      id
      title
      visibility
      blobs {
        nodes {
          path
          rawPath
        }
      }
    }
  }
  
  # Get project snippets
  project(fullPath: "group/project") {
    snippets(first: 10) {
      nodes {
        id
        title
      }
    }
  }
}
```

## Test Locations

### Model Specs

| File | Coverage |
|------|----------|
| `spec/models/snippet_spec.rb` | Base snippet model |
| `spec/models/personal_snippet_spec.rb` | Personal snippets |
| `spec/models/project_snippet_spec.rb` | Project snippets |
| `spec/models/snippet_repository_spec.rb` | Repository backing |
| `spec/models/snippet_blob_spec.rb` | Multi-file blobs |

### Service Specs

| File | Coverage |
|------|----------|
| `spec/services/snippets/create_service_spec.rb` | Creation |
| `spec/services/snippets/update_service_spec.rb` | Updates |
| `spec/services/snippets/destroy_service_spec.rb` | Deletion |

### Request Specs

| File | Coverage |
|------|----------|
| `spec/requests/api/snippets_spec.rb` | REST API |

### Finder Specs

| File | Coverage |
|------|----------|
| `spec/finders/snippets_finder_spec.rb` | Query logic |

## Testing Guidelines

### Running Tests

```bash
# Model specs
bin/rspec spec/models/snippet_spec.rb
bin/rspec spec/models/personal_snippet_spec.rb
bin/rspec spec/models/project_snippet_spec.rb

# Service specs
bin/rspec spec/services/snippets/

# API specs
bin/rspec spec/requests/api/snippets_spec.rb

# All snippet related
bin/rspec --pattern '**/snippet*_spec.rb'
```

### Test Factories

```ruby
# Personal snippet
let(:snippet) { create(:personal_snippet, :public, author: user) }

# Project snippet
let(:project_snippet) { create(:project_snippet, project: project, author: user) }

# With repository
let(:snippet) { create(:personal_snippet, :repository, author: user) }

# Multi-file snippet
let(:snippet) { create(:personal_snippet, :repository) }
snippet.repository.create_file(user, 'file1.rb', 'content', ...)
```

## Troubleshooting

### Snippet repository not created

**Symptom**: Snippet exists but `snippet.repository.exists?` returns false

**Cause**: Repository creation failed or was skipped

**Fix**:
```ruby
# Rails console - recreate repository
Snippets::RepositoryValidationService.new(user, snippet).execute
```

### Cannot clone snippet

**Symptom**: Git clone fails with permission error

**Causes**:
1. Snippet is private and user not authenticated
2. Project snippet in private project
3. SSH key not configured

**Debug**:
```ruby
# Check visibility
snippet.visibility_level
snippet.project&.visibility_level

# Check access
Ability.allowed?(user, :read_snippet, snippet)
```

## Documentation

| Path | Content |
|------|---------|
| [`doc/user/snippets.md`](https://docs.gitlab.com/ee/user/snippets.html) | User guide |
| [`doc/api/snippets.md`](https://docs.gitlab.com/ee/api/snippets.html) | REST API reference |
| [`doc/api/project_snippets.md`](https://docs.gitlab.com/ee/api/project_snippets.html) | Project snippets API |

## EE vs CE

### Core (Free) Features

| Feature | Implementation |
|---------|----------------|
| Personal snippets | `PersonalSnippet` model, user-owned |
| Project snippets | `ProjectSnippet` model, project-scoped |
| Multi-file snippets | Up to 10 files per snippet |
| Snippet versioning | Git repository backing |
| Snippet embedding | Embed via `<script>` tag |
| Snippet cloning | Clone via Git over HTTP/SSH |

### Premium+/Ultimate Features (EE)

Snippets are a **Core feature** - all functionality is available in the free tier. There are no EE-specific snippet features.

### Feature Availability Checks

```ruby
# Snippets are always available (Core feature)
# No license check needed

# Check if user can create snippets
current_user.can?(:create_snippet)

# Check project snippet settings
project.snippets_enabled?
```

## 📅 Known Issues & Active Work

### Active Issues

| Issue | Description | Status |
|-------|-------------|--------|
| [#285877](https://gitlab.com/gitlab-org/gitlab/-/issues/285877) | Snippet search doesn't index file content | Open |
| [#330649](https://gitlab.com/gitlab-org/gitlab/-/issues/330649) | Snippet statistics not updating correctly | Open |

### Feature Flags

No active feature flags for snippets.

## 📅 Architecture & Planning Documents

| Document | Content |
|----------|---------|
| [Snippets Architecture](https://docs.gitlab.com/ee/development/snippets/) | Development guide for snippets |

## 📅 Incident Learnings

No major incidents documented for snippets. The feature is stable with Git repository backing since GitLab 13.0.

## 📅 Customer Guidance (from Slack)

### "Can snippets be used for sharing configuration files?"

**Question**: "Is there a way to share configuration templates across projects using snippets?"

**Answer**: Yes, snippets can store any text content including configuration files. However, for CI/CD templates specifically, consider using:
1. **CI/CD Components** (recommended for pipeline configs)
2. **Group file templates** (for Dockerfiles, .gitignore, etc.)
3. **Include remote** in `.gitlab-ci.yml` pointing to a snippet's raw URL

Snippets are better for ad-hoc sharing; templates are better for standardized reuse.

### "Why can't I see a project snippet?"

**Question**: "I created a public snippet in a private project but my colleague can't see it"

**Answer**: Project snippet visibility is constrained by project visibility. A "public" snippet in a private project is only visible to project members. For truly public snippets, use personal snippets instead.

## 📅 Team & Communication

### Slack Channels

| Channel | Purpose |
|---------|---------|
| `#g_create_source-code` | Source Code group general |

### Feature Category

- **Feature Category**: `source_code_management`
- **Group**: Source Code (Create Stage)

## Related Resources

- **Snippet Embedding**: Snippets can be embedded in any webpage via `<script>` tag
- **GitLab API Docs**: [Snippets API](https://docs.gitlab.com/ee/api/snippets.html)

## Related Skills

- `source-code-developer-tools-index` - Other developer tools
- `source-code-file-templates` - For standardized file templates (alternative to snippets for reuse)

---

## Skill Feedback

> **For agents**: After using this skill, please note any feedback in your session checkpoint to help improve this skill.

- **What was missing?** Information you had to search for that should be here
- **What was unhelpful?** Sections that added noise without value
- **What gotchas did you hit?** Undocumented issues that should be in Troubleshooting
- **What was most useful?** Sections that saved significant time/effort
