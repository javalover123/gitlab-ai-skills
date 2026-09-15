# Review Size: Evidence Grades

The skill uses ≤200 / warn-at-300 / refuse-at-400 LOC thresholds. Here's
where those numbers come from and why you should treat them as adjustable
policy, not proven law.

## What the research actually shows

### The one number that gets cited everywhere (Grade D)

SmartBear's case study of a Cisco Systems team — 2,500 reviews, 3.2M LOC,
50 developers, 10 months — is the origin of the "200–400 LOC" figure. Their
[Best Practices for Code Review](https://smartbear.com/learn/code-review/best-practices-for-peer-code-review/)
says detection of defects peaks when reviewing "fewer than 200–400 LOC" and
reviewers "wear out" after about 60 minutes.

**Grade D, not A.** SmartBear sells a code review tool. This is one team at
one company in 2006, published in a promotional book, never refereed. The
near-universal web repetition of "400 lines" is circular citation, not
replication. Use the threshold as a starting default; change it if your team
data says otherwise.

### The only controlled experiment on decomposition (Grade A)

[*The effects of change decomposition on code review — a controlled experiment*](https://pmc.ncbi.nlm.nih.gov/articles/PMC7924728/)
(PeerJ Computer Science, 28 professional and graduate developers) found that
decomposition "leads to fewer wrongly reported issues, influences how subjects
approach and conduct the review activity (by increasing context-seeking), yet
impacts **neither understanding the change nor time to review**."

**The honest claim:** split MRs produce fewer false-positive review comments
and more focused reviewer attention. They don't make reviews faster or improve
comprehension. Don't oversell stacking; reviewers will notice.

### Google's guidance (Grade C)

[Small CLs](https://google.github.io/eng-practices/review/developer/small-cls.html):

> "smallness here refers to the conceptual idea that the CL should be focused
> and is **not a simplistic function on line count**."

Google explicitly sanctions stacking as the remedy for unavoidably large
changes, and exempts machine-generated refactors from the cap entirely. This
is practitioner policy from the org that actually does it — not a peer-
reviewed finding, but editorially maintained and widely regarded.

## The Goodhart guard

GitLab measures MR rate. Splitting inflates the numerator. But GitLab also
tracks Escape Rate (bugs opened / MRs merged), and a false split doesn't
move that needle. If your escape rate climbs after adopting stacking, the
splits are too aggressive or creating integration gaps.

Report MR count alongside escape rate, not alone.

## Summary table

| Number | Source | Grade | Use as |
|---|---|---|---|
| ≤200 LOC target | SmartBear Cisco study | D | Default starting point |
| 300 LOC warn | SmartBear band midpoint | D (interpolated) | Soft prompt |
| 400 LOC hard cap | SmartBear upper bound | D | Override-able policy |
| ≤20 MRs per stack | GitLab 19.1 product limit | **B** | Hard limit |
| Logical > line count | Google engineering practices | C | Primary heuristic |
| Benefit = fewer false positives | PeerJ controlled experiment | **A** | Honest claim to make |
