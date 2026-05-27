# Grouping heuristics

Decide how to split the captured diff into a 2-4 layer stack. Top of stack = the layer that lands last.

## Plan schema

Emit:

```json
{
  "stack_name": "kebab-case-name",
  "base_branch": "main",
  "groups": [
    {"order": 1, "title": "single-line title", "files": ["path/a", "path/b"], "rationale": "why these go together at this position"}
  ],
  "excluded": [{"file": "path", "reason": "..."}],
  "warnings": []
}
```

## Hard rules

1. `2 ≤ groups ≤ 4` (5 only with explicit `warnings` justification).
2. Each layer with all layers below it must build and pass tests on its own.
3. Tests live in the same layer as the implementation they cover.
4. No file appears in two groups. If a file would need a hunk-level split, put it whole in the layer it most belongs to and add a `warnings` entry naming it.
5. Every captured file is in exactly one of `groups[*].files` or `excluded`.
6. Titles are single-line. Match the project's commit-message style — check `git log --oneline -20`.

## Order (bottom → top)

1. Pure refactors / renames — mechanical, lowest-risk.
2. Type / contract additions — interfaces, schemas, public types.
3. Infrastructure — utilities, fixtures, config plumbing.
4. Feature behaviour — the user-visible change.
5. Docs / changelog ship with the layer they describe, not separately.

A reviewer reading the chain top-to-bottom should see "preparation → feature."

## Together

- Implementation + its tests + its docs.
- A refactor + every file it mechanically touches (don't split a rename across layers).
- A flag + the code that reads it.

## Apart

- Unrelated drive-by changes. Default to `excluded` and suggest the user file them separately.
- Refactors of file A vs refactors of file B done for unrelated reasons.

## Reject these anti-patterns

- Code in layer N, tests for that code in layer N+1.
- Interface added in layer N with no callers; impl added in layer N+1 with no relationship visible.
- 5+ tiny layers where no individual layer is reviewable alone.
- Coupled changes spread across layers, leaving intermediate states broken (e.g. DB column in layer N, writer in layer N+1, reader in layer N+2 for a simple feature).

## Naming

`stack_name` must match `^[a-z][a-z0-9-]{2,39}$`. Describe the outcome, not the current branch.

- Good: `usage-quota-service`, `auth-refactor`, `doctor-diagnostics`.
- Bad: `my-changes`, `wip`, `fix-stuff`.

## Recommend NOT splitting

If no clean ≥2-layer split exists that respects the rules above, tell the user:

> "I couldn't find a sensible split — the change reads as one coherent unit. Recommend submitting as a single MR. Tell me if you want a different angle (e.g. extract tests as prep)."

A bad stack costs the same reviewer attention as one MR and signals less cohesion.

## Pre-presentation self-check

For each layer:

1. Can you state in one sentence why each file is in this layer and not another?
2. If this layer were merged alone today, would the codebase still build?
3. Is the layer ≤1 file or <20 lines? (If yes, merge with its neighbour.)
4. Is the layer >1500 lines? (If yes, look for a sub-split.)

Do the layer titles read as a coherent narrative top-to-bottom? If not, the order is wrong.

If any check fails, revise before presenting.
