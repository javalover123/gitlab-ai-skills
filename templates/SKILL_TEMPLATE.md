---
name: <skill-name>
description: <One-line description of what this skill covers>
version: 1.0.0
license: MIT
---

# Source Code: <Feature Name>

<2-3 sentence overview of what this skill covers and its purpose.>

> **📅 Maintenance Note**: Sections marked with 📅 contain time-sensitive information (team contacts, active issues, roadmap, architecture docs). These should be reviewed periodically. Last reviewed: **<YYYY-MM-DD>**.

## When to Use This Skill

Use this skill when:
- <Trigger 1>
- <Trigger 2>
- <Trigger 3>
- <Trigger 4>

## Features Covered

| # | Feature | Tier | Description |
|---|---------|------|-------------|
| <N> | <Feature name> | Core+/Premium+/Ultimate | <Brief description> |

## Key Codebase Areas

### Models

| File | Purpose |
|------|---------|
| `app/models/<file>.rb` | <Purpose> |
| `ee/app/models/<file>.rb` | <EE Purpose> |

### Services

| File | Purpose |
|------|---------|
| `app/services/<path>/<file>.rb` | <Purpose> |

### Controllers

| File | Purpose |
|------|---------|
| `app/controllers/<path>/<file>.rb` | <Purpose> |

### GraphQL

| File | Purpose |
|------|---------|
| `app/graphql/types/<file>.rb` | <Purpose> |

## Test Locations

### Model Specs

| File | Coverage |
|------|----------|
| `spec/models/<file>_spec.rb` | <What it tests> |

### Service Specs

| File | Coverage |
|------|----------|
| `spec/services/<path>/<file>_spec.rb` | <What it tests> |

## Documentation

| Path | Content |
|------|---------|
| [`doc/user/<path>/<file>.md`](https://docs.gitlab.com/ee/user/<path>/<file>.html) | <Content description> |

## Common Patterns

### <Pattern Name>

<Explanation of the pattern and why it's important.>

```ruby
# Code example showing the pattern
```

**Key insight**: <Important takeaway about this pattern>

## EE vs CE

### Core (Free) Features

| Feature | Implementation |
|---------|----------------|
| <Feature> | <How it's implemented> |

### Premium+/Ultimate Features (EE)

| Feature | Implementation | License Check |
|---------|----------------|---------------|
| <Feature> | <How it's implemented> | `<feature_flag_or_method>` |

### Feature Availability Checks

```ruby
# How to check if features are available
project.feature_available?(:feature_name)
```

## API Endpoints

### REST API

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/v4/<path>` | <Purpose> |
| POST | `/api/v4/<path>` | <Purpose> |

### GraphQL

```graphql
# Example query
query {
  project(fullPath: "group/project") {
    # fields
  }
}
```

## Testing Guidelines

### Running Tests

```bash
# Commands to run relevant tests
bin/rspec spec/models/<file>_spec.rb
bin/rspec spec/services/<path>/
```

### Test Factories

```ruby
# Key factories for testing
create(:factory_name, attribute: value)
```

### Common Test Scenarios

1. **Scenario 1**: <What to test>
2. **Scenario 2**: <What to test>

## Troubleshooting

### "<Common problem description>"

1. **Check X:**
   ```ruby
   # Rails console command
   ```

2. **Check Y:**
   ```ruby
   # Another command
   ```

## 📅 Known Issues & Active Work

### Active Issues (from GitLab search)

| Issue | Description | Status |
|-------|-------------|--------|
| [#XXXXX](https://gitlab.com/gitlab-org/gitlab/-/issues/XXXXX) | <Description> | Open |

### Feature Flags

| Flag | Type | Purpose |
|------|------|---------|
| `flag_name` | ops/beta/development | <Purpose> |

## 📅 Architecture & Planning Documents

| Document | Content |
|----------|---------|
| [Document Name](URL) | <What it contains> |

## 📅 Incident Learnings

### <Date>: <Incident Title>

**What happened**: <Brief description>

**Root cause**: <What caused it>

**Lessons**:
1. <Lesson 1>
2. <Lesson 2>

**Reference**: [Incident Doc](URL)

## 📅 Customer Guidance (from Slack)

### <Common Question/Scenario>

**Question**: "<The question customers ask>"

**Answer**: <The answer with context>

**Source**: [Slack #channel](URL)

## 📅 Team & Communication

### Slack Channels

| Channel | Purpose |
|---------|---------|
| `#g_create_source-code` | Source Code group general |
| `#<other-channel>` | <Purpose> |

### Feature Category

- **Feature Category**: `<feature_category>`
- **Group**: <Group Name> (<Stage> Stage)

## Related Resources

- **Epic**: [Epic Name](URL)
- **API Docs**: [API Name](URL)

## Related Skills

- `<skill-name>` - <Brief description of relationship>

---

## Skill Feedback

> **For agents**: After using this skill, please note any feedback in your session checkpoint to help improve this skill.

- **What was missing?** Information you had to search for that should be here
- **What was unhelpful?** Sections that added noise without value
- **What gotchas did you hit?** Undocumented issues that should be in Troubleshooting
- **What was most useful?** Sections that saved significant time/effort
