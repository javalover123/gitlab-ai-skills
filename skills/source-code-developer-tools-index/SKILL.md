---
name: source-code-developer-tools-index
description: Lightweight index of miscellaneous Source Code developer tools and features
version: 1.0.0
license: MIT
---

# Source Code: Developer Tools Index

This is a **lightweight index** for miscellaneous Source Code features that don't warrant full skills. Each feature has a brief description, key file locations, and documentation links. For complex features, see the dedicated skills.

> **Note**: This is an index, not a comprehensive skill. For detailed workflows, patterns, and troubleshooting, see the dedicated skills for major features.

## When to Use This Skill

Use this skill when:
- Working on a feature listed below that doesn't have a dedicated skill
- Need to quickly find file locations for a Source Code feature
- Looking for documentation links for minor features
- Triaging issues across multiple Source Code features

## Features Index

### 1. Commit Graph and Reporting Tools (#3)

**Description**: Visual commit history, network graph, repository analytics.

| Type | Location |
|------|----------|
| Controller | `app/controllers/projects/network_controller.rb` |
| Views | `app/views/projects/network/` |
| JS | `app/assets/javascripts/network/` |
| Docs | [`doc/user/project/repository/index.md`](https://docs.gitlab.com/ee/user/project/repository/) |

**Feature Category**: `source_code_management`

---

### 2. Create Branches from Issues (#6)

**Description**: Create a branch directly from an issue with auto-naming.

| Type | Location |
|------|----------|
| Service | `app/services/branches/create_service.rb` |
| Controller | `app/controllers/projects/branches_controller.rb` |
| Frontend | `app/assets/javascripts/issues/create_merge_request_dropdown.js` |
| Docs | [`doc/user/project/repository/branches/index.md#create-a-branch-from-an-issue`](https://docs.gitlab.com/ee/user/project/repository/branches/#create-a-branch-from-an-issue) |

**Key Pattern**:
```ruby
# Branch name from issue
"#{issue.iid}-#{issue.title.parameterize}"
```

**Feature Category**: `source_code_management`

---

### 3. Allow Edits from Upstream Maintainers (#7)

**Description**: Fork setting to allow upstream maintainers to push to MR branches.

| Type | Location |
|------|----------|
| Model | `app/models/merge_request.rb` (`allow_collaboration` attribute) |
| Service | `app/services/merge_requests/update_service.rb` |
| Docs | [`doc/user/project/merge_requests/allow_collaboration.md`](https://docs.gitlab.com/ee/user/project/merge_requests/allow_collaboration.html) |

**Key Attribute**: `merge_request.allow_collaboration` (boolean)

**Feature Category**: `code_review_workflow`

---

### 4. Fuzzy File Finder (#8)

**Description**: Quick file search with fuzzy matching (keyboard shortcut: `t`).

| Type | Location |
|------|----------|
| Controller | `app/controllers/projects/find_file_controller.rb` |
| Frontend | `app/assets/javascripts/projects/find_file/` |
| API | `lib/api/search.rb` (blobs scope) |
| Docs | [`doc/user/project/repository/files/index.md#find-a-file`](https://docs.gitlab.com/ee/user/project/repository/files/#find-a-file) |

**Keyboard Shortcut**: Press `t` on any repository page

**Feature Category**: `source_code_management`

---

### 5. Xcode Integration (#16)

**Description**: Open repository in Xcode via `xcode://` URL scheme.

| Type | Location |
|------|----------|
| Helper | `app/helpers/projects_helper.rb` (`xcode_uri`) |
| View | `app/views/projects/buttons/_xcode_link.html.haml` |
| Docs | [`doc/user/project/repository/index.md#xcode`](https://docs.gitlab.com/ee/user/project/repository/#xcode) |

**URL Scheme**: `xcode://clone?repo=<git_url>`

**Feature Category**: `source_code_management`

---

### 6. Cherry-picking Changes (#17)

**Description**: Cherry-pick commits or MR changes to another branch.

| Type | Location |
|------|----------|
| Service | `app/services/commits/cherry_pick_service.rb` |
| Controller | `app/controllers/projects/commit/cherry_pick_controller.rb` |
| Docs | [`doc/user/project/merge_requests/cherry_pick_changes.md`](https://docs.gitlab.com/ee/user/project/merge_requests/cherry_pick_changes.html) |

**Key Service**:
```ruby
Commits::CherryPickService.new(project, current_user, params).execute
```

**Feature Category**: `source_code_management`

---

### 7. Git Tags (#23)

**Description**: Create, list, delete tags. Protected tags covered in `source-code-branch-protection` skill.

| Type | Location |
|------|----------|
| Model | `app/models/tag.rb` (virtual model) |
| Service | `app/services/tags/create_service.rb`, `destroy_service.rb` |
| Controller | `app/controllers/projects/tags_controller.rb` |
| API | `lib/api/tags.rb` |
| Docs | [`doc/user/project/repository/tags/index.md`](https://docs.gitlab.com/ee/user/project/repository/tags/) |

**Related Skill**: `source-code-branch-protection` (for protected tags)

**Feature Category**: `source_code_management`

---

### 8. Keep Personal Email Private (#25)

**Description**: Use a private commit email instead of personal email.

| Type | Location |
|------|----------|
| Model | `app/models/user.rb` (`commit_email`, `private_commit_email`) |
| Settings | `app/controllers/user_settings/emails_controller.rb` |
| Docs | [`doc/user/profile/index.md#use-an-automatically-generated-private-commit-email`](https://docs.gitlab.com/ee/user/profile/#use-an-automatically-generated-private-commit-email) |

**Private Email Format**: `{user_id}-{username}@{hostname}`

**Feature Category**: `user_profile`

---

### 9. Download Repository Files (#26)

**Description**: Download individual files or archives from repository.

| Type | Location |
|------|----------|
| Controller | `app/controllers/projects/raw_controller.rb` |
| Controller | `app/controllers/projects/repositories_controller.rb` (archives) |
| API | `lib/api/repositories.rb` |
| Docs | [`doc/user/project/repository/files/index.md#download-a-file`](https://docs.gitlab.com/ee/user/project/repository/files/#download-a-file) |

**Archive Formats**: `zip`, `tar`, `tar.gz`, `tar.bz2`

**Feature Category**: `source_code_management`

---

### 10. AsciiDoc Support (#27)

**Description**: Render AsciiDoc files in repository browser.

| Type | Location |
|------|----------|
| Library | `lib/gitlab/asciidoc.rb` |
| Renderer | `app/helpers/markup_helper.rb` |
| Config | `lib/gitlab/asciidoc/include_processor.rb` |
| Docs | [`doc/user/asciidoc.md`](https://docs.gitlab.com/ee/user/asciidoc.html) |

**Supported Extensions**: `.adoc`, `.ad`, `.asciidoc`

**Feature Category**: `source_code_management`

---

### 11. Activity Stream (#32)

**Description**: Project and group activity feeds (events).

| Type | Location |
|------|----------|
| Model | `app/models/event.rb` |
| Controller | `app/controllers/projects/activity_controller.rb` |
| Finder | `app/finders/events_finder.rb` |
| API | `lib/api/events.rb` |
| Docs | [`doc/user/project/working_with_projects.md#view-project-activity`](https://docs.gitlab.com/ee/user/project/working_with_projects.html#view-project-activity) |

**Event Types**: `push`, `issue`, `merge_request`, `note`, `milestone`, `wiki_page`

**Feature Category**: `user_profile`

---

### 12. Initialize README on Project Creation (#33)

**Description**: Option to create initial README.md when creating a project.

| Type | Location |
|------|----------|
| Service | `app/services/projects/create_service.rb` |
| Template | `app/views/projects/_new_project_fields.html.haml` |
| Docs | [`doc/user/project/index.md#create-a-blank-project`](https://docs.gitlab.com/ee/user/project/index.html#create-a-blank-project) |

**Parameter**: `initialize_with_readme: true`

**Feature Category**: `groups_and_projects`

---

### 13. Repository Languages (#34)

**Description**: Detect and display programming languages used in repository.

| Type | Location |
|------|----------|
| Model | `app/models/repository_language.rb` |
| Service | `app/services/projects/detect_repository_languages_service.rb` |
| Worker | `app/workers/detect_repository_languages_worker.rb` |
| Docs | [`doc/user/project/repository/index.md#repository-languages`](https://docs.gitlab.com/ee/user/project/repository/#repository-languages) |

**Detection**: Uses `github-linguist` gem via Gitaly

**Feature Category**: `source_code_management`

---

### 14. Git Protocol v2 Support (#35)

**Description**: Support for Git wire protocol version 2 (faster clones/fetches).

| Type | Location |
|------|----------|
| Config | `config/gitlab.yml` (`gitaly.git_protocol_v2`) |
| Gitaly | Handled by Gitaly service |
| Docs | [`doc/administration/git_protocol.md`](https://docs.gitlab.com/ee/administration/git_protocol.html) |

**Note**: Enabled by default since GitLab 12.8

**Feature Category**: `gitaly`

---

## Testing Quick Reference

```bash
# Run tests for a specific feature
bin/rspec spec/services/branches/create_service_spec.rb  # Branch creation
bin/rspec spec/services/commits/cherry_pick_service_spec.rb  # Cherry-pick
bin/rspec spec/services/tags/  # Tags
bin/rspec spec/models/event_spec.rb  # Activity stream
bin/rspec spec/lib/gitlab/asciidoc_spec.rb  # AsciiDoc
```

## Related Skills

| Skill | Features Covered |
|-------|------------------|
| `source-code-branch-protection` | Protected branches, protected tags, branch rules |
| `source-code-commit-signing` | GPG, SSH, X.509, S/MIME signatures |
| `source-code-merge-controls` | Approvals, squash, fast-forward, rebase |
| `source-code-mirroring` | Pull, push, bidirectional mirroring |
| `source-code-push-rules` | Push rules, secret blocking |
| `source-code-code-owners` | CODEOWNERS file |
| `source-code-git-lfs` | Git Large File Storage |
| `source-code-snippets` | Code snippets |
| `source-code-file-templates` | Group file templates, project templates |

## Feature Categories

Most features in this index use `source_code_management` feature category. Exceptions:
- `allow_collaboration` → `code_review_workflow`
- `private_commit_email` → `user_profile`
- `activity_stream` → `user_profile`
- `initialize_readme` → `groups_and_projects`
- `git_protocol_v2` → `gitaly`

## 📅 Team & Communication

### Slack Channels

| Channel | Purpose |
|---------|---------|
| `#g_create_source-code` | Source Code group general |
| `#g_create_source-code-be` | Backend discussions |
| `#g_create_source-code-fe` | Frontend discussions |

### Feature Category

- **Primary Feature Category**: `source_code_management`
- **Group**: Source Code (Create Stage)

## 📅 Known Issues

These features are generally stable. Common issues:

| Feature | Common Issue | Workaround |
|---------|--------------|------------|
| Cherry-pick | Conflicts on cherry-pick | Use `git cherry-pick -x` locally for better conflict resolution |
| File finder | Slow on large repos | Use `git ls-files` locally for faster results |
| Activity stream | Missing events | Check `events` table, ensure `Event` was created |

---

## Skill Feedback

> **For agents**: If you find yourself frequently using this index for a specific feature, consider whether it warrants a full skill.

- **Promote to full skill if**: Feature has complex patterns, common bugs, or frequent customer questions
- **Keep as index entry if**: Feature is straightforward with clear file locations
