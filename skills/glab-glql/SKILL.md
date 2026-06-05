---
name: glab-glql
description: Execute GLQL queries against GitLab projects and groups using glab CLI
version: 1.0.0
license: MIT
metadata:
  audience: developers
  author: dgruzd
  workflow: gitlab
---

# GLQL Skill

Execute [GitLab Query Language (GLQL)](https://docs.gitlab.com/user/glql/) queries via `glab api`.
GLQL queries issues, merge requests, and epics across projects and groups.

`POST /api/v4/glql` was introduced in GitLab 18.7. There is no native `glab glql` subcommand;
use `glab api --method POST glql` as a passthrough.

## Basic usage

```bash
glab api --method POST glql \
  --raw-field 'glql_yaml=query: project = "group/project" AND state = opened'
```

## YAML format (recommended)

Use `--raw-field` to pass a multi-line YAML string. All options go in the same `glql_yaml` value:

```bash
glab api --method POST glql \
  --raw-field 'glql_yaml=fields: id,title,state,author
project: gitlab-org/gitlab
limit: 5
sort: created desc
query: assignee = currentUser() AND state = opened'
```

## Configuration options

| Option    | Required | Description |
|-----------|----------|-------------|
| `query`   | Yes      | GLQL filter expression |
| `fields`  | No       | Comma-separated fields to return. Default: `title` |
| `project` | No       | Scope to `group/project`. Cannot combine with `group` |
| `group`   | No       | Scope to a group slug. Cannot combine with `project` |
| `limit`   | No       | 1-100. Default: 100 |
| `sort`    | No       | `field asc\|desc` (e.g. `created desc`, `due asc`, `merged desc`) |

## Scoping

```bash
# Project scope
--raw-field 'glql_yaml=fields: id,title,assignees
project: gitlab-org/gitlab
limit: 10
query: state = opened AND assignee = currentUser()'

# Group scope -- MUST add a narrowing filter or it will time out on large groups
--raw-field 'glql_yaml=fields: id,title,state
group: gitlab-org
limit: 10
query: state = opened AND assignee = currentUser()'
```

## References

- [Query fields and operators](references/query-reference.md) -- filters, operators, date syntax
- [Output fields, jq patterns, pagination](references/output-reference.md) -- response shape, jq snippets
