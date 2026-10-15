# Commit messages and PR description for nixpkgs

Copy the block that matches your change. The rules behind these formats, and the CI checks that enforce them, are in `references/upstreaming-and-prs.md`. Replace `foo`, versions, and URLs; delete lines you can't fill with something true.

## Commit subjects

Subject lines have no trailing period, no `fixup!`/`squash!` prefix, and no Conventional Commits prefix (`feat:`, `fix:`, `chore:`). The `attr:` prefix is functional: CI reads it to queue builds.

| Change | Subject |
|---|---|
| New package | `foo: init at 1.2.3` |
| Update | `foo: 1.2.2 -> 1.2.3` |
| Other package change | `foo: fix build with gcc 15` |
| Package set member | `python3Packages.foo: 1.0 -> 2.0` |
| Several in one set | `python3Packages.{foo,bar}: fix build` |
| New module | `nixos/foo: init module` |
| Module change | `nixos/foo: add bar option` |
| Maintainer entry | `maintainers: add yourhandle` |
| Removal | `foo: remove` |
| Backport | same subject as master |

## New package

Two commits when you're also a new maintainer. The maintainer commit goes first and touches only `maintainers/maintainer-list.nix`.

```
maintainers: add yourhandle
```

```
foo: init at 1.2.3

Foo is a tool that does a thing. https://example.org/foo

Builds from source with cmake. The test suite needs network access, so
tests X and Y are skipped (see the comment in package.nix).
```

Add an `Assisted-by:` trailer when an LLM tool wrote or shaped the commit. `Co-authored-by:` doesn't satisfy the policy.

```
Assisted-by: example-tool (example-model 1.0)
```

## Update

A plain bump needs the attribute, both versions, and a changelog link. Explain why in the body when the change is larger than a bump.

```
foo: 1.2.2 -> 1.2.3

https://example.org/foo/releases/tag/v1.2.3
```

## New module

Module work is a separate commit from the package that backs it. Add the module, its test, the `module-list.nix` entry, and the release-note entry together.

```
nixos/foo: init module

Adds services.foo, a systemd service with a RFC 42 settings option.
Secrets go through tokenFile and LoadCredential. Includes a NixOS test.
```

## Module change

```
nixos/foo: add bar option

Needed to ... (why, not what). Existing configurations keep working
because the default matches the previous behaviour.
```

A rename or removal also needs `mkRenamedOptionModule` or `mkRemovedOptionModule` and a "Backward Incompatibilities" release note.

## Removal

```
foo: remove

Upstream archived the repository in 2026 and the last release doesn't
build against current dependencies. Link the evidence here.
```

Add a throwing alias to `pkgs/top-level/aliases.nix` in the same commit.

## Backport

Cherry-pick from `master` with `-x` so the hash trailer appears. Use `-xe` to add why the backport is needed.

```
git fetch upstream
git switch --create backport-foo upstream/release-YY.MM
git cherry-pick -x <commit-on-master>
```

```
foo: 1.2.2 -> 1.2.3

https://example.org/foo/releases/tag/v1.2.3

(cherry picked from commit 0123456789abcdef0123456789abcdef01234567)
```

The PR title carries `[YY.MM]` and the description links the master PR. If you can't cherry-pick, add `Not-cherry-picked-because: <reason>` as a footer. Target `release-YY.MM`, never `nixos-YY.MM`.

## PR description skeleton

Keep `.github/PULL_REQUEST_TEMPLATE.md` intact and put your own summary above it. Tick only what you did, and give the command or output behind each tick; the boxes are information for reviewers.

```markdown
## Summary

New package: foo 1.2.3, a tool that does a thing (https://example.org/foo).
Why it belongs in nixpkgs: ... (users, upstream maintenance, license).
For an update: changelog https://example.org/foo/releases/tag/v1.2.3, and
anything breaking in it.

Related: searched open and closed PRs and `pkgs/top-level/aliases.nix`;
no competing PR found. (Link any you did find and say how this differs.)

Smoke test a reviewer can run:

    nix-build -A foo && ./result/bin/foo --version

## Things done

- Built on platform:
  - [x] x86_64-linux
  - [ ] aarch64-linux
  - [ ] aarch64-darwin
- Tested, as applicable:
  - [x] Basic functionality of all binary files: ran `./result/bin/foo --help`
        and `./result/bin/foo run sample.txt` (output: ...).
  - [x] Ran `nixpkgs-review wip`; dependents that fail also fail on the base
        branch (or: no dependents).
  - [x] Package tests: `nix-build -A foo.tests`.
  - [ ] NixOS tests: `nix-build -A nixosTests.foo` (modules only).
  - [ ] Tests in lib/tests or pkgs/test (functions and core changes only).
- Nixpkgs release notes
  - [ ] Package update: when the change is major or breaking.
- NixOS release notes
  - [ ] Module addition: when adding a new NixOS module.
  - [ ] Module update: when the change is significant.
- Rebuild count (from CI, or `nixpkgs-review`): N packages, base branch
  `master`. At 500 or more, consider `staging`; at 1000 or more, use it.
- Disabled tests, patches, and pinned versions are explained in comments.
- AI assistance disclosed per CONTRIBUTING.md; commits carry `Assisted-by:`.
```

Evidence checklist before you push:

- Commit subjects match the table, with no trailing period.
- One logical change per commit; `maintainers: add` is its own commit and comes first.
- `nix fmt` is clean, and `./ci/nixpkgs-vet.sh master` passes for new by-name packages.
- You built on every platform you ticked, and ran every installed binary.
- `passthru.tests` and `nixosTests` ran when they exist (`nixpkgs-review` skips `passthru.tests` unless you pass `--tests`).
- A release-note entry exists for a new module or a breaking change.
- The PR targets the base branch the rebuild count calls for.
