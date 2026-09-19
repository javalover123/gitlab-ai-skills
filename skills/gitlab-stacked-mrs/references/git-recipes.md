# Git Recipes for Stacked MRs

Splitting, restacking, absorbing fixups, and verifying parity.

## Splitting a feature branch

### Interactive rebase — commit-by-commit

```bash
# Split the branch into logical commits first
git rebase -i "$(git merge-base HEAD origin/main)"
# Use 'edit' on commits you want to split
# Then: git reset HEAD~, stage partial hunks, commit
```

### Partial staging

```bash
git checkout -p           # interactive hunk selection
git restore -p <file>     # same, file-scoped
git checkout <feature-branch> -- <path>   # cherry-pick a path wholesale
git cherry-pick -n <sha>  # stage a commit without committing (then stage selectively)
```

### Parallel worktrees for per-branch validation

```bash
git worktree add ../stack-01 stack/feature-01-foundation
git worktree add ../stack-02 stack/feature-02-model
# run CI locally per worktree
```

## Restacking

### `--update-refs` (Git 2.38+)

Rewrites all intermediate branch tips in a single pass:

```bash
git rebase origin/main --update-refs
# Or set globally:
git config --global rebase.updateRefs true
```

**Caveat:** won't update a branch checked out in another worktree. Detach or
remove the worktree first.

### Force-push with safety net

```bash
# After restack, push all branches
for branch in $(git branch -l 'stack/*' | tr -d ' *'); do
  git push origin "$branch" --force-with-lease
done
```

### Conflict re-use (`rerere`)

```bash
git config --global rerere.enabled true
# git records resolutions; rerere.autoupdate applies them automatically
git config --global rerere.autoupdate true
```

## Absorbing fixups

`git absorb` routes staged hunks to the nearest commit that touched the same
lines, then optionally rebases:

```bash
# After staging your changes:
git absorb --and-rebase

# Recovery if it goes wrong:
git reset --soft PRE_ABSORB_HEAD  # git-absorb prints this ref
```

Without `git absorb`:

```bash
git commit --fixup=<sha-of-target-commit>
git rebase -i --autosquash --update-refs <base>
```

## Parity verification

Run both checks — they catch different failure modes:

```bash
# Tree check: composed stack must equal feature branch tree
git diff stack/feature-top..feature-branch
# Must produce no output

# Commit correspondence
git range-diff origin/main..stack/feature-top origin/main..feature-branch
```

A non-empty tree diff means a hunk got lost or duplicated during splitting.
Stop and reconcile before opening any MRs.

## Per-language suppression patterns

These are implementation norms, not spec. Confirm they compile in your
version before encoding them in a ledger entry.

### Rust

```rust
// Introduce early — not yet consumed by upper stack entries
#[allow(dead_code)]
pub struct EarlyType { ... }

// Crate-wide suppression (use sparingly)
#![allow(dead_code)]
```

Note: since rustc ~1.80, never-constructed `pub` structs and unused trait
associated constants may trigger `dead_code` warnings despite being `pub`.
Test with `cargo clippy -- -D warnings` on the specific rustc version in CI.

Verify the behaviour against:
- https://doc.rust-lang.org/rustc/lints/listing/warn-by-default.html
- `cargo clippy --help` for the `-D warnings` interaction

### Go

Unused imports and local variables are **compile errors** in Go. Unused
package-level identifiers (functions, vars, consts, fields) are fine.

```go
// Keep scaffolded functions at package level — no suppression needed
func NewHandler() *Handler { ... }

// Suppress staticcheck U1000 for unexported identifiers
//lint:ignore U1000 introduced in stack part 2, consumed in part 3
func internalHelper() { ... }

// Suppress unused import
var _ = pkg.Symbol  // force the import to be "used"

// Build-tag gating (defers compilation entirely)
//go:build future
```

Verify against:
- https://go.dev/doc/faq#unused_variable_and_import
- https://staticcheck.dev/docs/checks/#U1000

### Ruby

```ruby
# autoload defers constant definition until first reference
autoload :NewService, 'services/new_service'

# RuboCop suppression for local variable
result = compute_value  # rubocop:disable Lint/UselessAssignment
```

`Lint/UselessAssignment` applies only to local variables. Class and module
definitions are always safe to introduce early.

Verify against: https://docs.rubocop.org/rubocop/cops_lint.html

### Nix

Nix attribute *values* are lazy — safe to define early. Attribute *names* in
`checks` and `packages` are evaluated strictly by `nix flake check`. Keep
speculative outputs out of `checks` until there's a consuming entry.

```nix
# Safe to define early (lazy value):
myPkg = callPackage ./pkgs/my-pkg.nix {};

# Don't add to checks until the package builds cleanly:
# checks.my-pkg = myPkg;  # add in the consuming stack entry
```

Verify against: https://nix.dev/manual/nix/stable/language/
