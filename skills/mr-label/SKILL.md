---
name: mr-label
description: Apply the correct GitLab MR type/subtype labels and evidence-based milestone when creating or updating a merge request. Use when opening or updating an MR.
version: 0.1.0
license: MIT
category: Development Workflow
metadata:
  audience: developers
  workflow: gitlab
---

# MR Label

Apply GitLab's required MR type/subtype labels and an evidence-based milestone whenever creating or updating a merge request. Apply changes after the MR exists when the GitLab integration supports updates; otherwise report the exact labels and milestone to apply.

## Instructions

1. Inspect the MR title, description, diff, linked issues/epics, target project, existing labels/milestone, and the target project's available labels and milestones.
2. Treat the linked issue or epic as the primary source of intent and scheduling; use the diff only to validate that the implementation matches it.
3. Apply exactly one primary type label: `type::feature` (new/changed user-facing capability), `type::bug` (defect fix), or `type::maintenance` (upkeep that's neither).
4. Apply at most one subtype label, only with clear evidence, and only if it exists in the target project's label taxonomy:
   - Feature: `feature::addition`, `feature::enhancement`, `feature::consolidation`
   - Bug: `bug::functional`, `bug::performance`, `bug::availability`, `bug::ux`, `bug::vulnerability`
   - Maintenance: `maintenance::refactor`, `maintenance::removal`, `maintenance::dependency`, `maintenance::scalability`, `maintenance::usability`, `maintenance::pipelines`, `maintenance::workflow`
5. Resolve conflicts: a fix for a shipped defect is `type::bug` even if it adds a small capability; internal cleanup/dependency/pipeline/tooling work is `type::maintenance` unless it clearly fits automation/process improvement. If the MR mixes unrelated intents, recommend splitting it rather than applying multiple type labels.
6. Assign the milestone in order of authority: the linked issue/epic's milestone > an explicitly stated milestone that matches an available project milestone > the project's current active milestone if the MR is clearly part of it. Never infer a milestone from the calendar or MR creation date, and never overwrite an existing milestone without evidence the work was rescheduled.
7. Change only the type/subtype labels and milestone; preserve unrelated labels and don't remove labels owned by another workflow without evidence.
9. Report the result: **Type**, **Subtype** (or `not applied`), **Milestone** (or `not assigned` with the reason), and any conflicts or compliance follow-up.

## Examples

- **Add `report_artifacts` support to custom flows** → `type::feature` + `feature::addition`; milestone from the linked work item.
- **Fix Windows path normalization in file discovery** → `type::bug` + `bug::functional`; preserve the linked issue's milestone.
- **Update CI rules and pin the Node.js version** → `type::maintenance` + `maintenance::pipelines` (or `maintenance::dependency` if the pin is the primary purpose, not both).
- **MR links two issues in different milestones** → classify by implementation intent, leave the milestone unset, and report the conflict instead of guessing.

## Guidelines

- Prefer the narrowest label the evidence supports; label namespaces are case-sensitive and vary by project.
- Only apply one scoped label for `type::<feature|maintenance|bug>`
- Only apply one scoped label for `<feature|maintenance|bug>::<subtype>`
- Don't infer a subtype from a filename — classify the actual purpose of the change.
- Treat uncertainty as a reason to escalate, not to guess.
- Don't merge the MR, send messages, or change code as part of this skill.

## Sources

- [Work Type Classification and Definitions for Issues and Merge Requests](https://internal.gitlab.com/handbook/security/security_operations/trust_and_safety/guides-and-documentation/work-type-classification-and-definitions/issues-and-merge-requests)
- [SIRT's Guide to GitLab Patch Releases](https://internal.gitlab.com/handbook/security/security_operations/sirt/resources/gitlab/patch_release_summary)
- [Product and Feature Development - Legal Risk Checklist](https://internal.gitlab.com/handbook/legal-and-corporate-affairs/legal-and-compliance/legal-risk-checklist)
- [Legal - Privacy](https://internal.gitlab.com/handbook/legal-and-corporate-affairs/legal-privacy)
