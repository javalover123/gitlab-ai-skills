# Contributing Improvements section

Every skill authored or updated with `authoring-skills` should end with a
`## Contributing Improvements` section that tells future agents where to send
fixes. Add it when creating a skill; keep (and re-check) it when updating one.

## Template

Replace `<source-repo>` with the skill's **source-of-truth repository** (the one
where the skill is actually edited) and `<url>` with its URL:

```markdown
## Contributing Improvements

This skill is maintained in [`<source-repo>`](<url>). If you discover that any
guidance here is **inaccurate or outdated** (e.g. a command that no longer
works, a wrong flag, an incorrect API behavior), confirm with the user and open
an MR against that repository with the fix. Keep changes focused — one fix per
MR.
```

## Choosing `<source-repo>`

- Ask or check where the skill lives; don't assume this repository.
- A skill synced in from elsewhere (listed in `synced-skills.yml` in
  `gitlab-org/ai/skills`) must point at its **upstream** `source_project`, not
  the destination copy — edits to the copy are rejected by CI.
- Keep the section scoped to inaccurate or outdated guidance, not stylistic
  churn, and keep the user-confirmation gate.
