# Resolving CODEOWNERS and splitting PREP MRs

`CODEOWNERS` in `gitlab-org/architecture/readiness` is the single source of truth for who reviews what. Never infer ownership from a category's folder name; fetch it fresh before splitting any MR:

```bash
glab api "projects/gitlab-org%2Farchitecture%2Freadiness/repository/files/CODEOWNERS/raw?ref=main"
```

## Why the folder name lies

Each `CODEOWNERS` section covers both `/templates/<category>/` and `/features/*/<category>/` together, but two things break the one-category-one-owner assumption:

- **Several categories share one owner.** `service_architecture`, `installation_configuration`, `operational_lifecycle`, and `performance_scalability` are all owned by `@gitlab-com/gl-infra/software-delivery/operate` as of this writing. Splitting those into separate MRs buys no reviewer independence, so keep them together.
- **Per-file overrides beat the section default**, and the *last* matching entry in a section wins. Examples seen in the live file: `platform_strategy/cells.md` is owned by `@gitlab-com/gl-infra/tenant-scale/cells-infrastructure` plus `@tkuah`, not by the rest of `platform_strategy`'s default owners. And `service_architecture/postgresql_feature_needs.md` is matched by two sections (`Service Architecture` and `Data Architecture`): one line means OR, but two sections matching the same file means AND, so it needs approval from both teams before it can merge.

Ownership drifts as the process matures: categories get added, reassigned, or occasionally dropped entirely. One real assessment's history shows `quality_assurance` being removed from the process altogether because no team held its `CODEOWNERS` review. Treat any table you've seen before, including this one, as a starting point to re-verify, never as a fact to cite outright.

## The invite gotcha

A `CODEOWNERS` group has **no effect until a project Owner invites it as a direct (non-nested) member with at least Developer role.** Until then, GitLab creates the approval rule with zero eligible approvers and silently marks it **optional**: the MR merges without that team's review rather than being blocked, and nothing tells you this happened. If a category's owning team never seems to get an approval request, check membership before assuming the process itself is broken.

## How to split

1. Diff your branch against `main` and list changed files.
2. For each file, find its resolved owner(s) in `CODEOWNERS`: check for a per-file override first (last match wins within a section), then fall back to the section's directory-level entry, then check whether a *different* section also matches the same path (AND).
3. Group changed files by resolved owner-set. One group means one MR. More than one group means one MR per group, each carrying only that group's files.
4. Files owned by the same team can stay together even across category folders (`service_architecture` and `installation_configuration` in one MR is fine if both list the same operate team).

## What a well-split MR description looks like

A real example, paraphrased from an in-flight assessment split this way: single-category MRs each stated their owning team explicitly, led with "what is worth your time" (the finding most likely to be *wrong*, not merely incomplete), and closed with an explicit list of what the assessment doesn't yet claim. That framing carries over directly into how a reviewer should read these MRs; see the `prep-review` skill for that side of it.
