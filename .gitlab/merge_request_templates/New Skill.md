## New Skill: `<skill-name>`

### Description

<!-- Brief description of what this skill does and when an agent should use it -->

### Checklist

- [ ] Created `skills/<skill-name>/SKILL.md` with required frontmatter (`name`, `description`, `license`, `compatibility`)
- [ ] Ran `lefthook run auto-fix` (or ran the three generator scripts manually) to update:
  - [ ] README.md skills table
  - [ ] catalog.json
  - [ ] .claude-plugin/ manifests
- [ ] All CI jobs pass
- [ ] Skill content follows existing conventions (see `skills/glab/SKILL.md` as reference)
