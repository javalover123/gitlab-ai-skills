# CODEOWNERS scope and the evidence-quality bar

## Resolving scope before you review

`CODEOWNERS` in `gitlab-org/architecture/readiness` is the single source of truth for who reviews what, and category folder names are not a reliable stand-in for it: several categories share one owner, and per-file overrides (including files owned by two sections at once) put individual files under a different owner than the rest of their folder. The full resolution mechanics live in `prep-start`'s reference, [`../../prep-start/references/review-and-splitting.md`](../../prep-start/references/review-and-splitting.md); this section covers what to do with that resolution once you have it.

Fetch `CODEOWNERS` fresh, then resolve the changed files' owner-set:

```bash
glab api "projects/gitlab-org%2Farchitecture%2Freadiness/repository/files/CODEOWNERS/raw?ref=main"
```

If the files resolve to more than one distinct owner or owner-set, ask for a split before you review the content. A real automated check in this repo (`.gitlab/duo/mr-review-instructions.yaml`) posts exactly this kind of request when it detects a multi-owner MR: it names the owning teams, lists which files belong to which, and proposes a split table. Follow the same shape when you raise it by hand.

## The evidence-quality bar

PREP templates follow a three-axis design: what's being asked, who owns the answer, and when it's answerable. Your review job maps to the first axis. Every answer needs to demand evidence rather than accept an opinion, so push back on anything that reads like "does X work well?" instead of "here's the analysis result for X, with a link." A gap is fine; a gap with no tracking issue, no owner, and no target stage is not.

Two failure modes show up more often than the rest, and both are worth extra scrutiny:

- **Confidently wrong, not just incomplete.** An assessment that states something as settled when the underlying decision or ADR is still `Proposed`, or that describes a component's behavior in a way the actual code contradicts, is far more dangerous than one that honestly says "not yet assessed." Incomplete is disclosed and tracked; wrong is silent until someone checks.
- **"Not Applicable" answers deserve the most skepticism, not the least.** A real Artifact Registry assessment had `installation_configuration` marked not-applicable wholesale, and a reviewer found three of its templates were, in fact, answerable. Read every N/A as a claim to verify against the actual architecture, not a box to skip past.

## The GA / Final Validation bar

Before a Final Validation MR can merge, check for all of these:

- Every applicable category is assessed and has explicit approval from its owning team, not just a merged MR.
- Every item deferred at an earlier stage (Planning & Design, Beta, Limited Availability) is either closed or carries an explicit, written GA exception with an owner.
- No unresolved blocking issue remains open against the feature.
- Categories marked not applicable carry a real justification, not a silent drop from the tracking issue.
- Risk assessment, monitoring, and rollback plans are present for anything genuinely risky, not boilerplate placeholders.
- Feature owner and engineering manager certification are both recorded.

A feature can be "assessed" everywhere and still not be GA-ready if any of the above is missing; don't conflate the two when you report status.
