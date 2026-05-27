---
name: source-code-commit-signing
description: Guide for working with commit signing features (GPG, SSH, X.509, S/MIME) in GitLab
version: 1.0.0
license: MIT
---

# Source Code: Commit Signing

This skill provides guidance for developers working on commit signing features in the GitLab codebase. It covers GPG, SSH, and X.509 signature verification, key management, and the "reject unsigned commits" push rule.

> **📅 Maintenance Note**: Sections marked with 📅 contain time-sensitive information (team contacts, active issues, roadmap). Last reviewed: **2026-05-23**.

## When to Use This Skill

Use this skill when:
- Implementing or modifying commit signature verification
- Working with GPG, SSH, or X.509 key management
- Debugging signature verification issues
- Extending the commit signature UI or API
- Working with the `CommitSignature` concern shared across signature types
- Implementing "reject unsigned commits" push rule features

## Features Covered

| # | Feature | Tier | Description |
|---|---------|------|-------------|
| 18 | Sign Commits with GPG | Core+ | GPG/PGP signature verification |
| 19 | Sign Commits with SSH | Core+ | SSH key signature verification |
| 20 | Sign Commits and Tags with X.509 | Core+ | X.509/S/MIME certificate verification |
| 28 | S/MIME Signed Commits | Core+ | S/MIME certificate support (via X.509) |
| 14 | Reject unsigned commits | Premium+ | Push rule to block unsigned commits |
| 15 | Verified Committer | Premium+ | Require commits from verified committers |

## Key Codebase Areas

### Models - Signature Storage

| File | Purpose |
|------|---------|
| `app/models/commit_signatures/gpg_signature.rb` | GPG signature record |
| `app/models/commit_signatures/ssh_signature.rb` | SSH signature record |
| `app/models/commit_signatures/x509_commit_signature.rb` | X.509 signature record |
| `app/models/concerns/commit_signature.rb` | **Shared concern** for all signature types |
| `app/models/concerns/signature_type.rb` | Signature type enum |

### Models - Key Management

| File | Purpose |
|------|---------|
| `app/models/gpg_key.rb` | User's GPG public key |
| `app/models/gpg_key_subkey.rb` | GPG subkeys |
| `app/models/x509_certificate.rb` | X.509 certificate |
| `app/models/x509_issuer.rb` | X.509 certificate issuer |
| `app/models/key.rb` | SSH keys (also used for auth) |

### Library - Signature Verification

| File | Purpose |
|------|---------|
| `lib/gitlab/gpg/commit.rb` | GPG commit signature verification |
| `lib/gitlab/gpg/signature.rb` | GPG signature parsing and validation |
| `lib/gitlab/gpg/tag.rb` | GPG tag signature verification |
| `lib/gitlab/gpg/invalid_gpg_signature_updater.rb` | Re-verify signatures when keys change |
| `lib/gitlab/ssh/commit.rb` | SSH commit signature verification |
| `lib/gitlab/ssh/signature.rb` | SSH signature parsing |
| `lib/gitlab/ssh/tag.rb` | SSH tag signature verification |
| `lib/gitlab/x509/commit.rb` | X.509 commit signature verification |
| `lib/gitlab/x509/signature.rb` | X.509 signature parsing |
| `lib/gitlab/x509/certificate.rb` | X.509 certificate handling |
| `lib/gitlab/x509/tag.rb` | X.509 tag signature verification |

### Workers

| File | Purpose |
|------|---------|
| `app/workers/create_commit_signature_worker.rb` | Async signature verification on push |
| `app/workers/invalid_gpg_signature_update_worker.rb` | Re-verify GPG signatures when key added |
| `app/workers/x509_certificate_revoke_worker.rb` | Handle certificate revocation |
| `app/workers/x509_issuer_crl_check_worker.rb` | Check certificate revocation lists |

### Controllers

| File | Purpose |
|------|---------|
| `app/controllers/user_settings/gpg_keys_controller.rb` | GPG key management UI |

### GraphQL

| File | Purpose |
|------|---------|
| `app/graphql/types/commit_signature_interface.rb` | Base interface for all signature types |
| `app/graphql/types/commit_signatures/gpg_signature_type.rb` | GPG signature GraphQL type |
| `app/graphql/types/commit_signatures/ssh_signature_type.rb` | SSH signature GraphQL type |
| `app/graphql/types/commit_signatures/x509_signature_type.rb` | X.509 signature GraphQL type |
| `app/graphql/types/commit_signatures/verification_status_enum.rb` | Verification status enum |

## Test Locations

### Model Specs

| File | Coverage |
|------|----------|
| `spec/models/commit_signatures/gpg_signature_spec.rb` | GPG signature model |
| `spec/models/commit_signatures/ssh_signature_spec.rb` | SSH signature model |
| `spec/models/commit_signatures/x509_commit_signature_spec.rb` | X.509 signature model |
| `spec/models/gpg_key_spec.rb` | GPG key model |
| `spec/models/gpg_key_subkey_spec.rb` | GPG subkey model |

### Library Specs

| File | Coverage |
|------|----------|
| `spec/lib/gitlab/gpg/commit_spec.rb` | GPG commit verification |
| `spec/lib/gitlab/gpg/signature_spec.rb` | GPG signature parsing |
| `spec/lib/gitlab/gpg/invalid_gpg_signature_updater_spec.rb` | Signature re-verification |
| `spec/lib/gitlab/gpg/tag_spec.rb` | GPG tag verification |

## Documentation

| Path | Content |
|------|---------|
| [`doc/user/project/repository/signed_commits/_index.md`](https://docs.gitlab.com/ee/user/project/repository/signed_commits/) | Signed commits overview |
| [`doc/user/project/repository/signed_commits/gpg.md`](https://docs.gitlab.com/ee/user/project/repository/signed_commits/gpg.html) | GPG signing guide |
| [`doc/user/project/repository/signed_commits/ssh.md`](https://docs.gitlab.com/ee/user/project/repository/signed_commits/ssh.html) | SSH signing guide |
| [`doc/user/project/repository/signed_commits/x509.md`](https://docs.gitlab.com/ee/user/project/repository/signed_commits/x509.html) | X.509/S/MIME signing guide |
| [`doc/user/project/repository/signed_commits/web_commits.md`](https://docs.gitlab.com/ee/user/project/repository/signed_commits/web_commits.html) | Web-based commit signing |

## Common Patterns

### CommitSignature Concern

All signature types include the `CommitSignature` concern, which provides:

```ruby
module CommitSignature
  # Shared functionality:
  # - sha_attribute :commit_sha
  # - belongs_to :project
  # - enum :verification_status (from Enums::CommitSignature)
  # - scope :by_commit_sha
  
  # Class methods:
  # - safe_create!(attributes) - idempotent creation
  # - unsigned_commit_shas(commit_shas) - find commits without signatures
  
  # Instance methods:
  # - commit - load the commit object
  # - signed_by_user - abstract, must be implemented
  # - verified_committer? - true if verified or verified_system
  # - verification_status - may re-check email if mailmap enabled
end
```

**Key insight**: When modifying shared behavior, changes to `CommitSignature` affect GPG, SSH, AND X.509 signatures.

### Verification Status Enum

```ruby
# From Enums::CommitSignature.verification_statuses
{
  unverified: 0,
  verified: 1,
  same_user_different_email: 2,
  other_user: 3,
  unverified_key: 4,
  unknown_key: 5,
  multiple_signatures: 6,
  revoked_key: 7,
  verified_system: 8,
  unverified_author_email: 9
}
```

### Signature Verification Flow

```
git push
  → CreateCommitSignatureWorker.perform_async(commit_shas, project_id)
    → For each commit:
      → Check commit.signature_type (:PGP, :X509, or :SSH)
      → Instantiate appropriate Gitlab::{Gpg,X509,Ssh}::Commit
      → Call commit.signature (triggers verification)
      → Signature record created/updated in database
```

### GPG Key Verification

```ruby
# GPG key is verified if ANY email in the key matches a verified user email
gpg_key.verified?
  # → user_infos.any? { |info| user.verified_email?(info[:email]) }

# Check if key is verified for a specific email
gpg_key.verified_and_belongs_to_email?(email)
```

### Signature Re-verification

When a user adds a new GPG key, existing signatures may need re-verification:

```ruby
# Triggered after GPG key creation
InvalidGpgSignatureUpdateWorker.perform_async(gpg_key.id)
  → Gitlab::Gpg::InvalidGpgSignatureUpdater.new(gpg_key).run
    → Find signatures with matching keyid but unknown_key status
    → Re-verify and update verification_status
```

## EE vs CE

### Core (Free) Features
- GPG signature verification
- SSH signature verification
- X.509/S/MIME signature verification
- Key management UI
- Signature display in UI

### Premium+ Features (EE)

| Feature | File | License Check |
|---------|------|---------------|
| Reject unsigned commits | `ee/app/models/push_rule.rb` | `reject_unsigned_commits` |
| Verified committer requirement | `ee/app/models/push_rule.rb` | `commit_committer_check` |

### EE Extensions

```ruby
# Push rule settings (EE)
push_rule.reject_unsigned_commits  # Block unsigned commits
push_rule.commit_committer_check   # Require verified committer

# Policy checks
project.feature_available?(:reject_unsigned_commits)
```

## API Endpoints

### REST API - GPG Keys

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/v4/user/gpg_keys` | List current user's GPG keys |
| GET | `/api/v4/user/gpg_keys/:key_id` | Get specific GPG key |
| POST | `/api/v4/user/gpg_keys` | Add GPG key |
| DELETE | `/api/v4/user/gpg_keys/:key_id` | Delete GPG key |
| POST | `/api/v4/user/gpg_keys/:key_id/revoke` | Revoke GPG key |
| GET | `/api/v4/users/:id/gpg_keys` | List user's GPG keys (admin) |

### GraphQL

```graphql
# Query commit signature
query {
  project(fullPath: "group/project") {
    repository {
      commits(first: 10) {
        nodes {
          sha
          signature {
            verificationStatus
            ... on GpgSignature {
              gpgKeyPrimaryKeyid
              gpgKeyUserName
              gpgKeyUserEmail
            }
            ... on SshSignature {
              keyFingerprintSha256
            }
            ... on X509Signature {
              x509Certificate {
                subject
                email
              }
            }
          }
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
bin/rspec spec/models/commit_signatures/
bin/rspec spec/models/gpg_key_spec.rb

# Library specs
bin/rspec spec/lib/gitlab/gpg/
bin/rspec spec/lib/gitlab/ssh/
bin/rspec spec/lib/gitlab/x509/

# Worker specs
bin/rspec spec/workers/create_commit_signature_worker_spec.rb
```

### Test Factories

```ruby
# GPG signature
create(:gpg_signature, project: project, commit_sha: commit.sha)
create(:gpg_signature, :verified, project: project)
create(:gpg_signature, :unverified, project: project)

# GPG key
create(:gpg_key, user: user)
create(:gpg_key, :with_subkeys, user: user)

# SSH signature
create(:ssh_signature, project: project, commit_sha: commit.sha)

# X.509 signature
create(:x509_commit_signature, project: project)
```

### Common Test Scenarios

1. **Signature verification**: Verify correct status for valid/invalid signatures
2. **Key matching**: Test signature-to-key association
3. **Email verification**: Test verified vs unverified email handling
4. **Re-verification**: Test signature update when key is added/revoked
5. **Push rule enforcement**: Test reject_unsigned_commits (EE)

## Troubleshooting

### "Signature shows as unverified but key is valid"

1. **Check email verification:**
   ```ruby
   # In rails console
   user = User.find_by_username('username')
   gpg_key = user.gpg_keys.first
   gpg_key.emails_with_verified_status
   # => {"user@example.com" => true, "other@example.com" => false}
   ```

2. **Check commit email matches key:**
   ```ruby
   commit = project.commit('sha')
   commit.committer_email
   # Must match one of the verified emails in the key
   ```

3. **Force re-verification:**
   ```ruby
   InvalidGpgSignatureUpdateWorker.perform_async(gpg_key.id)
   ```

### "Signature not appearing for commits"

1. **Check if worker ran:**
   ```ruby
   # Signature should exist
   CommitSignatures::GpgSignature.find_by(commit_sha: 'sha')
   ```

2. **Manually trigger verification:**
   ```ruby
   CreateCommitSignatureWorker.new.perform(['sha1', 'sha2'], project.id)
   ```

3. **Check commit has signature:**
   ```ruby
   commit = project.commit('sha')
   commit.signature_type  # => :PGP, :X509, :SSH, or nil
   ```

### "GPG key won't upload"

1. **Validate key format:**
   ```ruby
   key_text = "-----BEGIN PGP PUBLIC KEY BLOCK-----..."
   Gitlab::Gpg.fingerprints_from_key(key_text)
   # Should return array with fingerprint
   ```

2. **Check for duplicate:**
   ```ruby
   GpgKey.find_by(fingerprint: 'FINGERPRINT')
   ```

### "X.509 certificate issues"

1. **Check certificate chain:**
   ```ruby
   cert = X509Certificate.find_by(...)
   cert.x509_issuer  # Should have valid issuer
   ```

2. **Check CRL status:**
   ```ruby
   # Certificate revocation is checked by X509IssuerCrlCheckWorker
   ```

## 📅 Known Issues & Active Work

### Active Issues (from GitLab search)

| Issue | Description | Status |
|-------|-------------|--------|
| [#595925](https://gitlab.com/gitlab-org/gitlab/-/issues/595925) | Support Customer-managed CAs for X.509/S/MIME on Dedicated | Open |
| [#578500](https://gitlab.com/gitlab-org/gitlab/-/issues/578500) | Implement CRL and OCSP validation for X.509 certificates | Open |
| [#523435](https://gitlab.com/gitlab-org/gitlab/-/issues/523435) | Improve error feedback for X.509 signed commits validation | Open |
| [#506038](https://gitlab.com/gitlab-org/gitlab/-/issues/506038) | Commit Signature Verification intermittently shows unverified | Open |
| [#28347](https://gitlab.com/gitlab-org/gitlab/-/work_items/28347) | Unclear difference between "removing" and "revoking" GPG keys | Open |

### Feature Flags

| Flag | Type | Purpose |
|------|------|---------|
| `x509_forced_cert_loading` | ops | X.509 certificate loading behavior |
| `use_web_based_commit_signing_enabled` | beta | Web-based commit signing |
| `render_gpg_signed_tags_verification_status` | development | GPG tag verification display |
| `render_ssh_signed_tags_verification_status` | development | SSH tag verification display |
| `gpg_commit_delegate_to_signature` | development | GPG commit delegation |

### Related to Push Rules

The "reject unsigned commits" and "verified committer" features are part of Push Rules. See `source-code-push-rules` skill for more details on:
- `ee/app/models/push_rule.rb`
- Push rule inheritance (group → project)
- License checks

### Web Commit Signing

GitLab can sign commits made through the web UI:
- Group-level setting: `group.web_commit_signing_enabled?`
- Uses GitLab's internal GPG key
- Signatures show as `verified_system` status

## 📅 Incident Learnings

### 2026-01-06: ssh_signatures Index Removal Incident

**What happened**: A post-deployment migration removed the `index_ssh_signatures_on_commit_sha` index, replacing it with a composite index `(project_id, commit_sha)`. Queries filtering only by `commit_sha` began timing out, causing Sidekiq backlog of 600-700K jobs.

**Root cause**: Composite index column order matters - an index on `(project_id, commit_sha)` cannot efficiently support queries filtering only on `commit_sha`.

**Lessons**:
1. When dropping indexes, verify all dependent queries will still have coverage
2. The `ssh_signatures` table is performance-critical - changes need extra scrutiny
3. Symptoms (PgBouncer saturation, Sidekiq backlog) can mask the underlying cause

**Reference**: [Incident Doc](https://docs.google.com/document/d/1niqcxLzYxjeZReNRb6oub9mZOi8CkUeudyuz4kI6MIk)

## 📅 Customer Guidance (from Slack)

### Automated/CI Bot Commit Signing

For customers asking how to sign commits from CI pipelines or bots:

1. **Create a dedicated GitLab user** for the automation (e.g., `ci-bot@company.com`)
2. **Generate a signing key** - SSH is simplest for automation:
   ```bash
   git config --global gpg.format ssh
   git config --global user.signingkey ~/.ssh/botkey.pub
   git config --global commit.gpgsign true
   git config --global user.name "CI Bot"
   git config --global user.email "ci-bot@company.com"
   git commit -S -m "Automated commit"
   ```
3. **Add the public key** to the bot's GitLab account with usage type "Authentication & Signing" or "Signing"
4. **Enforce with push rules** (Premium+): Enable "Reject unsigned commits" to require all commits be signed

**Note**: The dedicated user will consume a seat. CI job tokens are associated with the user who triggered the pipeline, not a bot account.

**Source**: [Slack #amer-cse-connect](https://gitlab.slack.com/archives/C08GMT6GTCH/p1776787798276569)

### Keyless Signing with Sigstore

For SLSA L3 compliance or avoiding long-lived credentials:
- GitLab supports [keyless signing via Sigstore](https://docs.gitlab.com/ci/yaml/signing_examples/)
- Self-hosted Sigstore: See MR [!231623](https://gitlab.com/gitlab-org/gitlab/-/merge_requests/231623)
- Useful for CI pipelines where ephemeral certificates are preferred

### Revoke vs Remove SSH Keys

**Important UX distinction** (from [Slack #g_pajamas-design-system](https://gitlab.slack.com/archives/CDNNDD1T3/p1773836825592379)):

| Action | Effect on Past Commits | Use Case |
|--------|------------------------|----------|
| **Remove** | Past commits remain verified | Cleanup, key rotation |
| **Revoke** | Past commits become unverified | Compromised key |

This distinction is documented but often confuses users. Related issue: [#28347](https://gitlab.com/gitlab-org/gitlab/-/work_items/28347)

## 📅 Architecture & Planning Documents

| Document | Content |
|----------|---------|
| [SLSA Level 3 Design Doc](https://handbook.gitlab.com/handbook/engineering/architecture/design-documents/slsa_level_3/) | SLSA L3 signing architecture |
| [GovTech SLSA Discussion](https://drive.google.com/file/d/1EFqc4pooCbXM8wf2sqJ_3L93KwiqHkfq) | Roadmap for signing/verification |
| [Blog: Signed Commits](https://docs.google.com/document/d/1mXncvTn-vHxGCkhRbKGH7pDsOtIQ491oVEShtYlbqUA) | Why/how commit signing works (internal draft) |

## 📅 Team & Communication

### Slack Channels

| Channel | Purpose |
|---------|---------|
| `#g_create_source-code` | Source Code group general |
| `#g_create_source-code-be` | Backend engineering |
| `#f_slsa_level3` | SLSA L3 signing discussions |

### Feature Category

- **Feature Category**: `source_code_management`
- **Group**: Source Code (Create Stage)

## Related Resources

- **Epic**: [Organizations Feature Parity - Source Code](https://gitlab.com/groups/gitlab-org/-/epics/20702)
- **Feature Category**: `source_code_management`
- **API Docs**: [GPG Keys API](https://docs.gitlab.com/ee/api/users.html#list-all-gpg-keys)

## Related Skills

- `source-code-branch-protection` - Branch protection and access controls
- `source-code-push-rules` - Push rules including reject unsigned commits (Premium+)

---

## Skill Feedback

> **For agents**: After using this skill, please note any feedback in your session checkpoint to help improve this skill.

- **What was missing?** Information you had to search for that should be here
- **What was unhelpful?** Sections that added noise without value
- **What gotchas did you hit?** Undocumented issues that should be in Troubleshooting
- **What was most useful?** Sections that saved significant time/effort
