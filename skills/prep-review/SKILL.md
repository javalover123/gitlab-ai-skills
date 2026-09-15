---
name: prep-review
description: "Check the status of, review, or respond to feedback on an existing GitLab Platform Readiness Enablement Process (PREP) assessment. Use when asked to review a PREP merge request, check if a PREP/readiness assessment is complete or ready for GA, evaluate PREP evidence quality as a reviewer, or address/respond to PREP reviewer feedback. Do not use for starting a brand-new PREP assessment; use prep-start for that instead."
version: 0.1.0
license: MIT
category: Development Workflow
compatibility: opencode
metadata:
  audience: developers
  workflow: gitlab
  keywords: PREP, readiness assessment, platform readiness, production readiness, infrastructure platforms, review
---

# prep-review

Reviews and status checks for an in-flight PREP assessment in [`gitlab-org/architecture/readiness`](https://gitlab.com/gitlab-org/architecture/readiness). Pick the mode that matches the request.

## Mode A: checking a feature's PREP status

Use this when someone asks whether a feature's PREP is ready, or how far along it is.

```bash
glab api "projects/gitlab-org%2Farchitecture%2Freadiness/repository/files/features%2F<feature>%2FREADME.md/raw?ref=main"
glab mr list -R gitlab-org/architecture/readiness --search "<feature>"
```

Read the feature's status table. "Complete" tracks assessment progress, not remediation: it means every question in that category has an evidence-backed answer and every gap has a tracking issue, not that the gaps are closed. Don't report a category as done with no issues just because its row shows a checkmark; open the linked tracking issues and check whether they're gating GA.

For a GA-readiness check specifically, verify against the Final Validation bar: every applicable category assessed and approved, every deferred item from earlier stages either closed or carrying an explicit GA exception, and no unresolved blocking issues. See [references/evidence-bar.md](references/evidence-bar.md).

## Mode B: reviewing an MR

Confirm scope before you read a single answer. Resolve the changed files' owners from the live `CODEOWNERS`; if they resolve to more than one distinct owner (or owner-set), ask for a split before reviewing content at all. The resolution logic, including per-file overrides and dual ownership, is in [references/evidence-bar.md](references/evidence-bar.md).

Then review for evidence quality, not completeness. Completeness gaps are already tracked as TODOs and issues by design, so your job is catching claims that are wrong, not claims that are merely unfinished. The checklist, plus the two most common failure modes (unsupported claims, and "Not Applicable" answers that turn out to be answerable), lives in the same reference file.

Once you're satisfied, approve and merge it yourself. No PREP maintainer is needed, as long as the MR stays scoped to your section or sections. Approval is required from every section an MR touches.

## Mode C: addressing feedback as the feature owner

- Respond with more evidence, not reassurance. Link the thing the reviewer actually asked about.
- If you and a reviewer can't converge in MR comments, don't let it stall: escalate with the `Disagreement Escalation` issue template rather than arguing indefinitely in the thread.
- If the *question itself* is unclear, wrong, or missing something (not just hard to answer), file `Process Feedback and Enhancement` so the template improves for the next team, instead of quietly working around it.
- Update the feature's `README.md` status table (`Last Updated`, `Key Findings`) as items resolve. It's the one file with no `CODEOWNERS` entry, so you can update it without waiting on a category approval.

## Agent Guidelines

1. Never mark a category "reviewed" or "approved" on someone else's behalf. Only report what's actually in the MR or issue state.
2. Treat a blanket "Not Applicable" as a claim to verify, not a fact; it has been wrong before (see references).
3. When escalating, use the repo's own issue templates (`Disagreement Escalation`, `Process Feedback and Enhancement`) instead of improvising a new format.
4. Don't approve or merge across more than one CODEOWNERS section in a single pass; flag the split first.

## References

| Topic | Location |
|---|---|
| CODEOWNERS resolution, evidence-quality checklist, GA/Final-Validation bar | [references/evidence-bar.md](references/evidence-bar.md) |
