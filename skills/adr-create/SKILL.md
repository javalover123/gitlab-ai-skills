---
name: adr-create
description: "Creates and manages Architecture Decision Records using MADR 4.0.0 format with Nygard's immutability principles. Handles new ADRs, superseding existing ones, and retroactively documenting past decisions from code analysis. Links decisions to spec requirements and threat model entries. Use when documenting an architecture decision, choosing between technologies, recording why a design choice was made, or backfilling undocumented decisions. Triggers: create ADR, document decision, architecture decision, why did we choose, record decision, backfill ADR."
version: 1.0.1
license: MIT
category: Documentation
compatibility: opencode
metadata:
  audience: developers
  workflow: local
---

# ADR Create

Capture the "why" behind architectural decisions so future you and your team
don't have to guess. ADRs are short, immutable records stored in version control
next to the code they describe. This skill creates new ADRs, supersedes outdated
ones, and retroactively documents decisions that were made but never recorded.

An ADR answers one question: **"Why did we decide X instead of Y?"** Once
accepted it's immutable — new insights get a new ADR that supersedes the old
one. Store them in `docs/adr/` as `NNNN-brief-title.md`.

## When to use

- You chose a technology, framework, or pattern and need to record why.
- You're about to decide and want to structure the thinking.
- A project has undocumented decisions embedded in code needing retroactive ADRs.
- A previous decision needs revisiting (write a new ADR that supersedes it).
- `spec-create` / `threat-model-create` or a code review flagged a missing ADR.

Not for implementation detail (that's a spec) or security analysis (that's a
threat model). ADRs capture *decisions*, not requirements or threats.

## Workflow

### Phase 1 — Discovery

Check for existing ADRs (`ls docs/adr/*.md`). If they exist, learn the numbering
and conventions and find the next number; don't duplicate a recorded decision.
If none exist, `mkdir -p docs/adr` and start with the ADR-0001 bootstrap (below)
using [assets/adr-full-template.md](assets/adr-full-template.md). Scan related
artifacts for undocumented decisions: the spec (assumptions it doesn't state),
the threat model (security decisions), README/design docs, and git history
(major structural changes).

### Phase 2 — Identify the decision

**New decisions:** ask (via the `question` tool / `AskUserQuestion`) the specific
decision point ("which database?", not "how to build the app"), the driving
constraints, who's involved, and how reversible it is. Pre-populate with
candidates found in Phase 1.

**Retroactive:** mine the codebase — every dependency (`Cargo.toml`,
`package.json`, `go.mod`, `Gemfile`) is a decision; infra files (Dockerfile,
Terraform, Nix) are deployment choices; `git log --oneline --diff-filter=A --
'*.toml' '*.json' '*.yaml'` surfaces structural changes; CI config is often an
undocumented choice.

**Superseding:** don't modify the original (immutable) — write a new ADR that
references and supersedes it, and set the old one's status to "Superseded by
ADR-NNNN".

### Phase 3 — Analyze options

Document at least **two** options, each with a one-line description, concrete
pros, and real cons (no strawmen). If only one is viable, document why the
alternatives were ruled out — "we didn't consider alternatives" is a red flag.
Be honest about trade-offs: every option has cons.

### Phase 4 — Write the ADR

Use MADR 4.0.0 — full template in
[references/madr-template.md](references/madr-template.md). Every ADR needs
frontmatter (`status`, `date`, `decision-makers`), a noun-phrase title
(`ADR-NNNN: …`), a value-neutral **Context and Problem Statement**, **Decision
Drivers** (the forces), **Considered Options**, a **Decision Outcome** naming the
chosen option and justifying it against the drivers, and **Consequences** split
into good / bad / neutral.

### Phase 5 — Cross-reference and validate

Link the decision to what it implements or is driven by, in a **More
Information** section:

```markdown
- Implements: [SPEC-003: Session Storage](../specs/auth-spec.md#fr-003)
- Driven by: [TM-AUTH-003: Session Hijacking](../threat-models/auth-threat-model.md#tm-auth-003)
- Supersedes: [ADR-0003](0003-use-memcached.md)
```

If the decision implies requirements or threats that aren't documented, flag it
inline (`> Action needed: run spec-create for FR-XXX` / `run threat-model-create
for the new trust boundary`).

Validate: status set; date present; context describes forces not conclusions;
≥2 options; chosen option justified against the drivers; consequences include
good *and* bad; title is a noun phrase; cross-references present or flagged.

## ADR-0001 bootstrap

Every project's first ADR records the decision to use ADRs (MADR in version
control vs. a wiki → chosen: Markdown in VCS, so decisions stay next to the
code, get reviewed in MRs, and have git history). The full starter is in
[assets/adr-full-template.md](assets/adr-full-template.md).

## Status lifecycle

`proposed → accepted → [deprecated | superseded by ADR-NNNN]`; or `proposed → rejected`. These are the
**only** valid `status:` values. Full detail:
[references/status-lifecycle.md](references/status-lifecycle.md).

| Status | Meaning | Set when |
|---|---|---|
| `proposed` | Under discussion | First drafted, before agreement |
| `accepted` | In effect (immutable) | Team agrees via MR merge/review |
| `rejected` | Considered but not adopted | Decision explicitly declined |
| `deprecated` | No longer relevant | Feature removed / constraint gone |
| `superseded` | Replaced by a newer ADR | New ADR written with a different decision |

For an `accepted` ADR, an optional `## Implementation Location` section
referencing code files lets a completion-checking skill (e.g. `iterate` via its
`hooks.json` checker) verify those files exist and flag a decision that's
documented but not yet coded.

## Retroactive workflow

Identify the decision from code/config/git → reconstruct the context that was
true when it was made → infer the alternatives and why they lost → write the ADR
(with the original date if known) → set status `accepted` (it was accepted
implicitly by being implemented) → note "Retroactively documented on [date]" in
More Information.

## Style

ADRs should read like a thoughtful memo from a colleague, not a legal contract —
the context should tell the story of the situation and pressures. Be direct
about trade-offs: "we accepted slower hash times for better security" beats "the
solution was deemed appropriate".

## Resources

- [references/madr-template.md](references/madr-template.md) — full MADR 4.0.0 template
- [references/status-lifecycle.md](references/status-lifecycle.md) — status transitions and rules
- [assets/adr-full-template.md](assets/adr-full-template.md) — copy-paste starter, all sections
- [assets/adr-minimal-template.md](assets/adr-minimal-template.md) — bare-minimum ADR
