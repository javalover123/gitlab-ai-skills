# ADR Status Lifecycle

## Status Values

| Status | Meaning | Can transition to |
|---|---|---|
| **Proposed** | Under discussion, not yet agreed | Accepted, Rejected |
| **Accepted** | Decision is in effect | Deprecated, Superseded |
| **Rejected** | Considered but not adopted | (terminal) |
| **Deprecated** | No longer relevant | (terminal) |
| **Superseded** | Replaced by a newer ADR | (terminal) |

## Transition Rules

### Proposed → Accepted

The decision has been agreed upon by the decision-makers listed in frontmatter. In practice, this often happens through PR review — when the PR adding the ADR is merged, the status changes from Proposed to Accepted.

### Proposed → Rejected

The decision-makers considered the proposal and chose not to adopt it — a different option won, or the problem turned out not to need a decision at all. A rejected ADR still records real value: it stops the same option from being re-proposed and re-debated later without anyone remembering why it was turned down.

**How:** Update the frontmatter to `status: rejected` and add a "Rejection Rationale" note (or fold the reasoning into "More Information") explaining why the proposal wasn't adopted. Unlike Accepted → Deprecated/Superseded, this is a terminal transition straight from Proposed — there's no further status change once an ADR is rejected.

### Accepted → Deprecated

The system or feature the ADR applies to has been removed or fundamentally changed, making the decision irrelevant. The decision isn't *wrong* — it just doesn't apply anymore.

**When to deprecate:**
- Feature was removed entirely
- System was decommissioned
- External constraint that drove the decision no longer exists

**How:** Add to the frontmatter: `status: deprecated` and note the reason in "More Information."

### Accepted → Superseded

A new ADR makes a different decision about the same topic. The old decision was reasonable at the time but circumstances changed.

**How:**
1. Create the new ADR (e.g., ADR-0015)
2. Update the old ADR's frontmatter: `status: "superseded by [ADR-0015](0015-new-title.md)"`
3. In the new ADR, reference the old one: `Supersedes [ADR-0007](0007-old-title.md)`

## Immutability Principle

**Accepted ADRs don't get edited.** Once an ADR is accepted:

- Don't change the Context, Decision, or Consequences sections
- Don't update it to reflect new information
- The only change allowed is updating the Status field (to deprecated or superseded)

This feels counterintuitive — shouldn't we keep docs up to date? No. The value of an ADR is that it captures what was known and decided *at that point in time*. If you edit accepted ADRs, you lose the decision history.

**If the decision was wrong:** Write a new ADR explaining what changed and why a different decision is now appropriate. Supersede the old one.

**If you want to add information:** Add it to the "More Information" section, clearly dated, or reference it from a new ADR.

## Example Lifecycle

```
ADR-0003: Use Memcached for Session Cache (Accepted, 2023-06-01)
  ↓
  [8 months pass, team discovers Memcached lacks persistence needed for failover]
  ↓
ADR-0012: Use Redis for Session Cache (Accepted, 2024-02-15)
  - Supersedes ADR-0003
  - ADR-0003 status updated to "Superseded by ADR-0012"
```

Both ADRs remain in the repository. A new team member reading ADR-0003 sees it was superseded, reads ADR-0012 for the current decision, and understands the full history — why Memcached was chosen initially, what changed, and why Redis replaced it.
