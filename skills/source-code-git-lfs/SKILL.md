---
name: source-code-git-lfs
description: Git Large File Storage (LFS) - managing large binary files outside Git repositories
version: 1.0.0
license: MIT
---

# Source Code: Git LFS

Git Large File Storage (LFS) is an open source Git extension that helps repositories manage large binary files efficiently. Instead of storing large files directly in Git, LFS stores them in object storage and replaces them with small pointer files in the repository.

> **📅 Maintenance Note**: Sections marked with 📅 contain time-sensitive information (team contacts, active issues, roadmap, architecture docs). These should be reviewed periodically. Last reviewed: **2026-05-23**.

## When to Use This Skill

Use this skill when:
- Working on LFS object storage, upload, or download logic
- Debugging LFS authentication or authorization issues
- Implementing LFS file locking features
- Working on LFS integration with mirroring or import/export
- Debugging "smudge" errors or missing LFS objects
- Optimizing LFS performance or storage cleanup

## Features Covered

| # | Feature | Tier | Description |
|---|---------|------|-------------|
| 24 | Git LFS 2.0 support | Core+ | Store large files in object storage with pointer files in Git |

## Key Codebase Areas

### Models

| File | Purpose |
|------|---------|
| `app/models/lfs_object.rb` | LFS object record - oid (SHA256), size, file storage |
| `app/models/lfs_objects_project.rb` | Links LFS objects to projects (many-to-many) |
| `app/models/lfs_file_lock.rb` | File locking to prevent concurrent edits |
| `app/models/lfs_download_object.rb` | Represents object to download during import |

### Controllers

| File | Purpose |
|------|---------|
| `app/controllers/repositories/lfs_api_controller.rb` | Batch API for download/upload operations |
| `app/controllers/repositories/lfs_storage_controller.rb` | Direct file upload/download endpoints |
| `app/controllers/repositories/lfs_locks_api_controller.rb` | File locking API |
| `app/controllers/concerns/lfs_request.rb` | Shared LFS request handling |

### Services

| File | Purpose |
|------|---------|
| `app/services/projects/lfs_pointers/lfs_import_service.rb` | Import LFS objects during project import |
| `app/services/projects/lfs_pointers/lfs_download_service.rb` | Download individual LFS objects |
| `app/services/projects/lfs_pointers/lfs_link_service.rb` | Link existing LFS objects to projects |
| `app/services/projects/lfs_pointers/lfs_list_service.rb` | List LFS pointers in repository |
| `app/services/projects/lfs_pointers/lfs_object_download_list_service.rb` | Build download list for import |
| `app/services/projects/lfs_pointers/lfs_download_link_list_service.rb` | Generate download URLs |
| `app/services/projects/move_lfs_objects_projects_service.rb` | Move LFS associations between projects |
| `app/services/merge_requests/link_lfs_objects_service.rb` | Link LFS objects when MR is merged |
| `app/services/merge_requests/mergeability/check_lfs_file_locks_service.rb` | Check for locked files in MR |

### Library Classes

| File | Purpose |
|------|---------|
| `lib/gitlab/lfs_token.rb` | Generate LFS authentication tokens |
| `lib/gitlab/git/lfs_pointer_file.rb` | Parse LFS pointer file format |
| `lib/gitlab/git/lfs_changes.rb` | Detect LFS changes in commits |
| `lib/gitlab/checks/lfs_check.rb` | Pre-receive hook for LFS validation |
| `lib/gitlab/checks/lfs_integrity.rb` | Verify LFS object integrity |
| `lib/gitlab/verify/lfs_objects.rb` | Rake task to verify LFS objects |
| `lib/gitlab/cleanup/orphan_lfs_objects.rb` | Clean up unreferenced LFS objects |
| `lib/gitlab/cleanup/orphan_lfs_file_references.rb` | Clean up orphan references |
| `lib/gitlab/metrics/lfs.rb` | LFS metrics collection |

### Workers

| File | Purpose |
|------|---------|
| `app/workers/remove_unreferenced_lfs_objects_worker.rb` | Background cleanup of orphan objects |

### Uploaders

| File | Purpose |
|------|---------|
| `app/uploaders/lfs_object_uploader.rb` | CarrierWave uploader for LFS files |

### Import/Export

| File | Purpose |
|------|---------|
| `lib/gitlab/import_export/lfs_saver.rb` | Export LFS objects |
| `lib/gitlab/import_export/lfs_restorer.rb` | Import LFS objects |
| `lib/bulk_imports/common/pipelines/lfs_objects_pipeline.rb` | Bulk import LFS objects |
| `lib/backup/tasks/lfs.rb` | Backup LFS objects |

## Test Locations

### Model Specs

| File | Coverage |
|------|----------|
| `spec/models/lfs_object_spec.rb` | LFS object model |
| `spec/models/lfs_objects_project_spec.rb` | Project associations |
| `spec/models/lfs_file_lock_spec.rb` | File locking |
| `spec/models/lfs_download_object_spec.rb` | Download object |

### Request Specs

| File | Coverage |
|------|----------|
| `spec/requests/lfs_http_spec.rb` | Full LFS HTTP API |
| `spec/requests/lfs_locks_api_spec.rb` | File locking API |
| `spec/requests/api/internal/lfs_spec.rb` | Internal LFS API |

### Service Specs

| File | Coverage |
|------|----------|
| `spec/services/projects/lfs_pointers/lfs_download_service_spec.rb` | Download service |
| `spec/services/projects/lfs_pointers/lfs_import_service_spec.rb` | Import service |
| `spec/services/projects/lfs_pointers/lfs_link_service_spec.rb` | Link service |
| `spec/services/projects/lfs_pointers/lfs_list_service_spec.rb` | List service |

### Library Specs

| File | Coverage |
|------|----------|
| `spec/lib/gitlab/lfs_token_spec.rb` | Token generation |
| `spec/lib/gitlab/git/lfs_pointer_file_spec.rb` | Pointer parsing |
| `spec/lib/gitlab/git/lfs_changes_spec.rb` | Change detection |
| `spec/lib/gitlab/checks/lfs_check_spec.rb` | Pre-receive checks |
| `spec/lib/gitlab/checks/lfs_integrity_spec.rb` | Integrity verification |
| `spec/lib/gitlab/verify/lfs_objects_spec.rb` | Verification rake task |

## Documentation

| Path | Content |
|------|---------|
| [`doc/topics/git/lfs/_index.md`](https://docs.gitlab.com/ee/topics/git/lfs/) | User guide, setup, configuration |
| [`doc/administration/lfs/_index.md`](https://docs.gitlab.com/ee/administration/lfs/) | Admin guide, object storage setup |
| [`doc/user/project/repository/files/git_attributes.md`](https://docs.gitlab.com/ee/user/project/repository/files/git_attributes.html) | .gitattributes for LFS tracking |

## EE vs CE

### Core (Free) Features

| Feature | Implementation |
|---------|----------------|
| LFS object storage | `LfsObject` model, object storage |
| LFS push/pull | `LfsApiController`, batch API |
| LFS file locking | `LfsFileLock` model |
| Fork network sharing | `LfsObjectsProject` associations |
| LFS in CI/CD | `GIT_LFS_SKIP_SMUDGE` variable |

### Premium+/Ultimate Features (EE)

Git LFS is a **Core feature** - all functionality is available in the free tier. There are no EE-specific LFS features.

### Feature Availability Checks

```ruby
# LFS is always available (Core feature)
# Check if LFS is enabled for a project
project.lfs_enabled?

# Check admin setting
Gitlab::CurrentSettings.lfs_enabled?

# Check if object storage is configured
LfsObjectUploader.object_store_enabled?
```

## GraphQL

### Types

| File | Purpose |
|------|---------|
| `app/graphql/types/lfs_object_type.rb` | LFS object type (if exists) |

### Queries

LFS does not have extensive GraphQL support. Most LFS operations use the REST-based Git LFS Batch API. Repository-level LFS info is available via:

```graphql
query {
  project(fullPath: "group/project") {
    lfsEnabled
    statistics {
      lfsObjectsSize
    }
  }
}
```

**Note**: Individual LFS object queries are not exposed via GraphQL. Use the REST API for LFS operations.

## Common Patterns

### LFS Pointer File Format

```plaintext
version https://git-lfs.github.com/spec/v1
oid sha256:4d7a214614ab2935c943f9e0ff69d22eadbb8f32b1258daaa5e2ca24d17e2393
size 804
```

Parsing in Ruby:
```ruby
# lib/gitlab/git/lfs_pointer_file.rb
class LfsPointerFile
  VERSION_LINE = "version https://git-lfs.github.com/spec/v1"
  
  def self.parse(data)
    return unless data.start_with?(VERSION_LINE)
    
    oid = data[/oid sha256:(\h{64})/, 1]
    size = data[/size (\d+)/, 1]&.to_i
    
    new(oid, size) if oid && size
  end
end
```

### LFS Object Storage

LFS objects are stored by their SHA256 OID:
```ruby
# OID format: 64 hex characters (SHA256)
validates :oid, presence: true, uniqueness: true, format: { with: /\A\h{64}\z/ }

# Storage path: sharded by first 2 chars of OID
# e.g., "ab/cd/abcd1234..." 
```

### LFS Authentication Flow

```
1. Git client sends batch request to /info/lfs/objects/batch
2. GitLab validates user auth (HTTP Basic or token)
3. GitLab returns signed URLs for upload/download
4. Client uploads/downloads directly to object storage (or proxied)
```

```ruby
# Token generation for LFS auth
Gitlab::LfsToken.new(user, project).basic_encoding
```

### Linking LFS Objects to Projects

```ruby
# LFS objects are shared across projects via lfs_objects_projects
# When forking, objects are linked, not copied
LfsObjectsProject.link_to_project!(lfs_object, project, :project)

# Check if project has access (including fork network)
lfs_object.project_allowed_access?(project)
```

### Fork Network Sharing

```ruby
# LFS objects are shared across fork networks
# A fork can access LFS objects from its source
def project_allowed_access?(project)
  if project.fork_network_member
    # Check if any project in fork network has this object
    lfs_objects_projects
      .where("EXISTS(?)", project.fork_network.fork_network_members...)
      .exists?
  else
    lfs_objects_projects.where(project_id: project.id).exists?
  end
end
```

### Direct vs Proxied Downloads

```ruby
# If object storage supports direct download and proxy is disabled
if lfs_object.file_storage? || lfs_object.proxy_download_enabled?
  # Proxy through GitLab
  proxy_download_actions(lfs_object)
else
  # Direct download from object storage with presigned URL
  direct_download_actions(lfs_object)
end
```

## API Endpoints

### LFS Batch API (Git LFS Protocol)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/:project.git/info/lfs/objects/batch` | Batch download/upload request |
| GET | `/:project.git/gitlab-lfs/objects/:oid` | Download LFS object |
| PUT | `/:project.git/gitlab-lfs/objects/:oid/:size` | Upload LFS object |

### File Locking API

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/:project.git/info/lfs/locks` | Create lock |
| GET | `/:project.git/info/lfs/locks` | List locks |
| POST | `/:project.git/info/lfs/locks/verify` | Verify locks |
| POST | `/:project.git/info/lfs/locks/:id/unlock` | Delete lock |

### Internal API

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/v4/internal/lfs` | Internal LFS operations |

## Testing Guidelines

### Running Tests

```bash
# Model specs
bin/rspec spec/models/lfs_object_spec.rb
bin/rspec spec/models/lfs_objects_project_spec.rb

# Request specs (full API)
bin/rspec spec/requests/lfs_http_spec.rb

# Service specs
bin/rspec spec/services/projects/lfs_pointers/

# All LFS related
bin/rspec --pattern '**/lfs*_spec.rb'
```

### Test Factories

```ruby
# Create LFS object
let(:lfs_object) { create(:lfs_object, :with_file) }

# Link to project
let(:lfs_objects_project) { create(:lfs_objects_project, project: project, lfs_object: lfs_object) }

# Create file lock
let(:lfs_file_lock) { create(:lfs_file_lock, project: project, path: 'path/to/file.psd') }
```

### Common Test Scenarios

1. **Upload flow**: Test batch request → upload → finalize
2. **Download flow**: Test batch request → download (direct vs proxied)
3. **Fork access**: Test LFS object access across fork network
4. **File locking**: Test lock creation, verification, unlock
5. **Import/export**: Test LFS objects included in project export

## Troubleshooting

### "Smudge error" - LFS object not found

**Symptom**: `Smudge error: Error downloading... Object does not exist on the server`

**Causes**:
1. LFS object was never uploaded (pointer committed without object)
2. Object storage misconfiguration
3. Object deleted or corrupted
4. Network/auth issues during download

**Debug steps**:
```bash
# Check if file is pointer or actual content
cat path/to/file  # If shows "version https://git-lfs..." it's a pointer

# Try to pull LFS objects
git lfs pull

# Check LFS status
git lfs status

# Verify object exists on server (Rails console)
LfsObject.find_by(oid: 'sha256_oid_here')
```

### LFS objects not downloading after clone

**Symptom**: Files show as small pointer files instead of actual content

**Fix**:
```bash
# Install LFS hooks
git lfs install

# Pull all LFS objects
git lfs pull

# Or fetch specific files
git lfs fetch --include="*.psd"
```

### "Object does not exist" during mirroring

**Symptom**: Mirror fails with LFS 404 errors

**Causes**:
1. Source doesn't have LFS objects (only pointers)
2. `proxy_download` not enabled for object storage
3. LFS objects not linked to mirrored project

**Debug**:
```ruby
# Check if LFS objects exist for project
project.lfs_objects.count

# Check object storage config
Gitlab.config.lfs.object_store
```

### Large repository size despite using LFS

**Symptom**: Repository size still large even with LFS

**Causes**:
1. Large files committed before LFS was set up
2. LFS objects counted in project statistics

**Fix**: Use `git lfs migrate` to convert history:
```bash
git lfs migrate import --include="*.psd,*.ai" --everything
```

## 📅 Known Issues & Active Work

### Common Support Issues

| Issue Type | Description |
|------------|-------------|
| Smudge errors | Most common - object not found during checkout |
| Mirroring failures | LFS objects not transferred with mirror |
| Storage calculation | LFS storage counted separately from repo size |
| Helm migration | LFS issues after Omnibus → Helm migration |

## 📅 Incident Learnings

### LFS + Mirroring: Objects Not Transferred

**What happened**: Customer mirrored repository but LFS objects showed 404 errors on destination.

**Root cause**: Mirroring only syncs Git refs, not LFS objects. LFS objects must be separately transferred or `proxy_download` must be enabled.

**Lessons**:
1. Mirroring does NOT include LFS objects automatically
2. For LFS-heavy repos, consider direct migration instead of mirroring
3. Enable `proxy_download` if destination needs to fetch from source's object storage

**Reference**: [#spt_pairing](https://gitlab.slack.com/archives/C03UW0HPBGD/p1774633261615589)

### LFS Contributing to Gitaly Saturation

**What happened**: Large binary-heavy repository caused Gitaly CPU saturation during git operations.

**Root cause**: Repository contained large binary objects that should have been in LFS. Git pack operations were expensive.

**Lessons**:
1. Repositories with large binaries should use LFS
2. Monitor `git-pack-objects` CPU time vs wall time
3. Consider LFS for any file type that changes frequently and is > 1MB

**Reference**: [Gitaly incident](https://gitlab.slack.com/archives/C0AGQLFTYPN/p1772077248024239)

## 📅 Customer Guidance (from Slack)

### "Can we display LFS text files in MR diffs?"

**Question**: "Is there a server side setting to display text-based LFS files in the MR page?"

**Answer**: No, LFS files (even text ones) are treated as opaque blobs by the MR diff engine. Workaround: Use CI to run `git lfs pull`, generate a text diff, and post it as an MR comment via the API.

**Source**: [#a_rivian_ext](https://gitlab.slack.com/archives/C018NJJNMDY/p1774541802877459)

### "Files show as pointers after new machine setup"

**Question**: "Can't open Adobe Illustrator files from repo - they're tiny files"

**Answer**: LFS client not installed or not initialized. Run:
```bash
brew install git-lfs  # or download from git-lfs.com
git lfs install
git lfs pull
```

**Source**: [#it_help](https://gitlab.slack.com/archives/CK4EQH50E/p1773139485553109)

## 📅 Team & Communication

### Slack Channels

| Channel | Purpose |
|---------|---------|
| `#g_create_source-code` | Source Code group general |
| `#g_create_source-code-be` | Backend discussions |

### Feature Category

- **Feature Category**: `source_code_management`
- **Group**: Source Code (Create Stage)

## Related Resources

- **Git LFS Spec**: https://github.com/git-lfs/git-lfs/blob/main/docs/spec.md
- **Git LFS Website**: https://git-lfs.com/

## Related Skills

- `source-code-mirroring` - Mirroring doesn't include LFS objects by default
- `source-code-push-rules` - Max file size push rules complement LFS

---

## Skill Feedback

> **For agents**: After using this skill, please note any feedback in your session checkpoint to help improve this skill.

- **What was missing?** Information you had to search for that should be here
- **What was unhelpful?** Sections that added noise without value
- **What gotchas did you hit?** Undocumented issues that should be in Troubleshooting
- **What was most useful?** Sections that saved significant time/effort
