---
name: find-reusable-patterns
description: Find reusable implementations across a codebase before writing new code, using the GitLab Orbit knowledge graph. Use when someone asks "is there an existing X", "how do we usually do Y", wants to reuse a pattern instead of rebuilding it, or types /find-reusable-patterns. Returns candidate implementations ranked by how widely they are already used.
version: 0.1.0
license: MIT
category: Development Workflow
compatibility: ""
metadata:
  audience: developers
  workflow: local
  slash-command: enabled
---

## Find reusable patterns with GitLab Orbit

Help a developer reuse existing code instead of rebuilding it. Use
[GitLab Orbit](https://gitlab.com/gitlab-org/orbit/knowledge-graph) — the graph
that indexes source code (and, on Remote, the full SDLC) — to find the closest
existing implementations of a described capability and rank them by reuse.

### When to use this skill

Whenever a developer is about to build something that may already exist:

- "I need a rate limiter."
- "Is there already a retry-with-backoff helper?"
- "How do we usually handle S3 uploads here?"

### How to run it

Pick the access method that matches the environment. Both read the same idea:
find matching definitions, then rank them by how many places import them.

**GitLab Orbit Local (source code, DuckDB SQL via the `orbit` CLI or MCP `run_sql`):**

First derive a keyword from the intent (for example, "rate limiter" -> `limiter`).
Confirm table/column names with `orbit schema` if unsure, then:

```shell
# 1. Candidate definitions whose name matches the capability
orbit sql -F json "
  SELECT name, fqn, file_path, definition_type
  FROM gl_definition
  WHERE lower(name) LIKE '%limiter%'
  LIMIT 50"

# 2. Rank by reuse: how many distinct files import a matching symbol
orbit sql -F json "
  SELECT identifier_name, import_path,
         COUNT(DISTINCT file_path) AS importing_files
  FROM gl_imported_symbol
  WHERE lower(identifier_name) LIKE '%limiter%'
  GROUP BY identifier_name, import_path
  ORDER BY importing_files DESC
  LIMIT 20"

# 3. Read the top match to confirm it fits (content is the full source text)
orbit sql -F json "
  SELECT name, fqn, file_path, start_line, end_line, content
  FROM gl_definition
  WHERE fqn = '<fqn-of-top-match>'
  LIMIT 1"
```

**GitLab Orbit Remote / GitLab Duo Agent Platform:** ask in plain language, e.g.
"Using GitLab Orbit, find existing implementations of rate limiting across
my-org, ranked by how many places import them, and show the project, file, and
definition for the top matches." Orbit runs the graph queries for you.

### The Orbit Local schema you rely on

| Table | Key columns |
|-------|-------------|
| `gl_definition` | `name`, `fqn`, `file_path`, `definition_type`, `start_line`, `end_line`, `content` |
| `gl_file` | `path`, `name`, `extension`, `language`, `content` |
| `gl_imported_symbol` | `file_path`, `import_type`, `import_path`, `identifier_name` |
| `gl_directory` | `path`, `name` |
| `gl_edge` | edges between the nodes above (run `orbit schema gl_edge` for columns) |

### How to present results

- Show the **top 3** matches, best first.
- For each: **definition name**, **type**, **file path**, and the **reuse count**
  (importing files). On Remote, also include the **project** and a likely
  **owner** (most active contributor to that project).
- Recommend which one to reuse, and suggest reading its `content` to confirm fit.
- If nothing matches, say so plainly — do not invent a result.

### Notes

- Orbit is in **beta**; the ontology and query DSL may change. If a query fails,
  run `orbit schema` (Local) and adjust column names.
- Orbit Local covers source code only. Owners, merge requests, and pipelines are
  available on Orbit Remote.
