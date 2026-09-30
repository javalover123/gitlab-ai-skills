# Using this at GitLab

- Targets: `gitlab-production-main` (main DB) and `gitlab-production-ci` (CI DB); `gitlab-production-registry` for container-registry queries. Other
  databases are listed by `postgresai projects`; skip `*-deprecated` entries.
- Docs: [Database Lab](https://docs.gitlab.com/development/database/database_lab/#use-the-postgresai-cli).
- Local GDK databases: use the `gitlab-psql` skill instead; this skill is for production-sized data.
- Before requesting a database review: [db-review-flow.md](db-review-flow.md).
