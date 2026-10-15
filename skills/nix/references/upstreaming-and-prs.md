# Upstreaming to nixpkgs: inclusion, commits, branches, backports, review

Load this when a change is headed for a nixpkgs pull request: deciding whether it belongs there, writing commits, picking the base branch, opening and shepherding the PR, backporting. Verified against nixpkgs master (26.11 development, Oct 2026). The old `doc/contributing/` chapters no longer exist; their content now lives in `CONTRIBUTING.md`, `pkgs/README.md`, `nixos/README.md`, `maintainers/README.md` and `ci/README.md`, and `doc/contributing.md` only keeps legacy anchors pointing there.

Companion files: [upstreamable-checklist](upstreamable-checklist.md) for the code-level checklist, [versioning-and-updates](versioning-and-updates.md) for bump mechanics, [nixos-modules](nixos-modules.md) for module content, [gates-and-tooling](gates-and-tooling.md) for local gates, [review-evidence](review-evidence.md) for how to read the review corpus.

**Contents:** [Does it belong in nixpkgs?](#does-it-belong-in-nixpkgs) · [Before you start: search for existing work](#before-you-start-search-for-existing-work) · [Commit messages](#commit-messages) · [Choosing the target branch](#choosing-the-target-branch) · [Backporting](#backporting) · [Removing packages](#removing-packages) · [CI and automated checks](#ci-and-automated-checks) · [Who merges, and how](#who-merges-and-how) · [PR title, description and evidence](#pr-title-description-and-evidence) · [Release notes and documentation](#release-notes-and-documentation) · [Responding to review](#responding-to-review) · [Stale and abandoned PRs](#stale-and-abandoned-prs) · [Pitfalls that stall PRs](#pitfalls-that-stall-prs) · [PR readiness checklist](#pr-readiness-checklist) · [Evidence](#evidence) · [Dated advice to ignore](#dated-advice-to-ignore)

## Does it belong in nixpkgs?

The "adding a package" section of `pkgs/README.md` sets the bar. If the answer to any of these is no, don't send the package:

| Question | What the docs say |
|----------|-------------------|
| Is it ready for general use? | Too-immature or soon-abandoned projects don't belong. Ask upstream when unsure. |
| Is the license clear? | Software is unfree by default. Source availability alone doesn't grant redistribution. |
| Will other people use it? | Niches are fine, "a niche of 5 people" is too small. Upstream issues and other distros' repos are a usable signal. |
| Is it maintained upstream? | Security-critical, fast-moving-dependency, or data-integrity software needs regular upstream maintenance. |
| Will you maintain it? | Commit to at least one full Nixpkgs release cycle, or find someone to adopt it. |
| Library? | It needs at least one dependent. Package the dependent in the same PR, or add a minimal `passthru.tests` program. |
| Would it need `meta.knownVulnerabilities` on day one? | Unlikely to be accepted. |

An upstream author submitting their own project is described as often a sign the userbase isn't there yet; the docs suggest waiting for another user to submit it.

Where else things go:

| Content | Place | Source |
|---------|-------|--------|
| Hardware profiles, firmware workarounds, extra kernel flavours | `nixos-hardware` | `README.md`; `doc/packages/linux.section.md` ("No new downstream kernels are accepted") |
| Immature or niche packages | Your own flake, an overlay, or a community repository such as NUR | NUR appears in review history only. The nixpkgs tree never mentions it, so don't cite it as policy. |
| Project-specific build glue, internal tools | Your own flake | See [flake-layout](flake-layout.md) |
| Local patches or overrides of an existing package | An overlay in your own flake | `pkgs/README.md` says `overrideAttrs` suits out-of-tree code; inside nixpkgs, fix the package itself |

## Before you start: search for existing work

Duplicate and competing PRs are the most frequently closed category in the review corpus. Spend the search time up front:

- Search open and closed PRs and issues for the package or option name. `gh search prs --repo NixOS/nixpkgs "foo"` works; so does the GitHub UI.
- For updates, check whether the update bot (`r-ryantm`, running `nixpkgs-update`) already opened a PR for that version. The bot is exempt from the AI policy and its PRs are the expected path for plain bumps.
- Grep `pkgs/top-level/aliases.nix` for the name. A `throw` alias means the package was removed on purpose, and the message says why.
- For a backport, search for an existing `backport` PR on the same release branch.
- Don't open a package-request issue instead of a PR: the bot auto-closes issues labeled `0.kind: packaging request` and asks for a PR.
- For a large or cross-cutting change, ask the relevant maintainers or the Staging room before you write code.

If you find a competing PR, review or build it, say what's different about yours, or close yours.

## Commit messages

`CONTRIBUTING.md` ("Commit conventions") applies everywhere, and the area READMEs add formats.

| Change | Subject | Where defined |
|--------|---------|---------------|
| New package | `foo: init at 1.2.3` | `pkgs/README.md` |
| Update | `foo: 1.2.2 -> 1.2.3` (`→` is also accepted) | `pkgs/README.md` |
| Other package change | `foo: fix build with gcc 15` | `pkgs/README.md` |
| Package set member | `python3Packages.foo: 1.0 -> 2.0`; several at once: `python3Packages.{foo,bar}: fix build` | `pkgs/README.md` |
| NixOS module | `nixos/foo: init module`, `nixos/foo: add bar option`, `nixos/foo: refactor config generation` | `nixos/README.md` |
| Docs only | `doc/stdenv: update kernel config documentation` | `doc/README.md` |
| Library | `lib.fileset: add an additional argument` | `lib/README.md` |
| Maintainer list | `maintainers: add <handle>` | `CONTRIBUTING.md`, `maintainers/README.md` |
| Package removal | `foo: remove`, body says why and links the evidence | `pkgs/README.md` |
| Backport | Same subject as master plus `(cherry picked from commit <40-hex>)` trailer from `-x` | `CONTRIBUTING.md` |

The `pkg-name:` prefix is functional, not cosmetic: CI reads it to queue builds. For package sets with several versions (`python3Packages`, `perlPackages`), use the unversioned attribute unless the change is version-specific. The label bot also pattern-matches subjects: `<attr>: init at <version>` earns `8.has: package (new)` and `<attr>: <old> -> <new>` earns `8.has: package (update)`; `nixos/...` subjects are excluded from both.

Body rules from `CONTRIBUTING.md`: explain why, not what; a simple version bump needs the attribute, old and new versions, and a link to the release notes or changelog; larger upgrades need a longer message. Leave a blank line after the subject.

```
foo: 1.2.2 -> 1.2.3

https://example.org/foo/releases/tag/v1.2.3
```

`ci/github-script/lint-commits.ts` fails a PR when a commit subject:

- doesn't contain `: `
- ends with a period
- starts with `fixup!`, `squash!` or `amend!` (run `git rebase -i --autosquash` first)
- looks like a Conventional Commits prefix (`feat:`, `fix:`, `chore:`, `refactor:`, `style:`, `test:`, `build:`, `ci:`, `perf:`, `update:`, `services:`, optionally with scope or `!`). A type is skipped when the commit touches a path segment of the same name, which is why `doc: ...` passes for commits under `doc/`. Prefer `doc/component:` anyway.

It also fails commits with an empty or malformed author or committer name or email. A GitHub noreply address is acceptable.

### One logical change per commit

- Create one commit per logical unit and squash `oops, whitespace` fixups. `CONTRIBUTING.md` also warns that over-fragmentation causes friction, so a package init plus its module should be two commits, not ten.
- Order matters when you're also a new maintainer: the `maintainers: add <handle>` commit goes first, before the package or module commits, and contains only the `maintainer-list.nix` entry.
- Keep each commit buildable. A reviewer bisecting later needs every step to evaluate.
- Mechanical churn, such as reformatting files you didn't otherwise touch, goes in its own commit or PR so the behavior change stays reviewable.
- Security fixes stay out of unrelated PRs so they can be backported on their own.
- Don't rewrite or reorder shared history on a branch others are testing without saying so in the PR.

### Automation and AI disclosure

`CONTRIBUTING.md` ("Automation/AI policy") requires a responsible human who has reviewed the contribution, and disclosure of non-trivial automation. For LLM-based tools the commit must carry an `Assisted-by:` trailer naming at least the tool and the primary model and version. `Co-authored-by:` doesn't satisfy the policy. PR descriptions and review comments are disclosed separately from commits. The label bot adds `llm-assisted` when a commit has an `Assisted-by:` trailer (except for `nix-init`). Deterministic formatters, `nix-update`, and the official bots are exempt. If you're an agent producing commits for a user, add the trailer and tell the user it's required.

```
Assisted-by: example-tool (example-model 1.0)
```

## Choosing the target branch

Default to `master`. The decision process in `CONTRIBUTING.md` ("Branch conventions"):

| Situation | Base branch |
|-----------|-------------|
| Not for a release, or the same change works on master and release | `master`, then backport after merge |
| The change can't be the same on both (for example differing major versions) | Two PRs: `master` and `release-YY.MM` |
| Rebuilds roughly 500-999 packages | `master` or `staging`; CI flags a "possible mass rebuild" and the author judges |
| Rebuilds 1000 or more | `staging` (`staging-YY.MM` for a release branch) |
| Rebuilds all NixOS tests (`10.rebuild-nixos-tests`) but isn't a mass rebuild | `staging-nixos` |
| Linux kernel changes | `staging-nixos` (CI exempts single-file kernel pins) |
| Critical security fix, not a mass rebuild | `master` |
| Critical security fix that is a mass rebuild | `staging-next` (`staging-next-YY.MM`), per the branch table |
| Fix for a Hydra failure on the staging train | `staging-next`, after asking the Staging room |

Never target `nixos-YY.MM` or `nixpkgs-*` channel branches; PRs there are disallowed (`ci/README.md`, "Branch classification"). Don't push other work to `staging-next`: it "should only receive changes that fix Hydra builds".

### Thresholds and the review folklore

The tree and CI agree on two numbers. `CONTRIBUTING.md` says "500 or more, consider targeting `staging`; 1000 or more is a mass rebuild and should target `staging`." `ci/github-script/check-target-branch-policy.ts` implements them (`maxRebuildCount >= 500` is a possible mass rebuild, `>= 1000` a mass rebuild), and its tests pin the same values. The rebuild labels bucket the count per platform kernel as `1`, `1-10`, `11-100`, `101-500`, `501-1000`, `1001-2500`, `2501-5000` and `5001+`. Review comments sometimes say "100+ goes to staging". That threshold appears in the corpus but not in the docs or CI; use 500 and 1000. Mass rebuilds aren't formally defined, so look at previously merged PRs to a staging branch when the count sits near a boundary.

You won't see the count until the PR's eval job runs. CI then posts a review: at 1000 or more on `master` or a release branch it requests changes and names the likely staging branch; at 500-999 it asks you to judge, and says the message can be ignored when the change isn't a mass rebuild. Rebuilding all NixOS tests triggers a separate message pointing at `staging-nixos`. Estimate beforehand with `nixpkgs-review wip` or by checking what depends on the changed attribute, and retarget as soon as the review appears.

### Retargeting a PR

Rebase onto the merge base so you don't rebuild the world locally, force-push, change the base in the GitHub UI, then rebase onto the new base to settle conflicts:

```
git rebase --onto upstream/staging... upstream/master
git push origin feature --force-with-lease
# change the base branch in the GitHub PR, then:
git rebase upstream/staging
git push origin feature --force-with-lease
```

## Backporting

Only merged changes are backported, and only to supported releases. Find the oldest supported release with `nix-instantiate --eval -A lib.trivial.oldestSupportedRelease` (it printed `2605` against this tree).

Eligible, per `CONTRIBUTING.md` ("Changes acceptable for releases"): new packages, modules and functions; security fixes; patch-level version updates; minor updates with new functionality but no breaking changes. Major updates with breaking changes are acceptable only for services that break without a current client and for security-critical applications. Release branches should only receive backwards-compatible changes. Mass rebuilds go to `staging-YY.MM`. Kernel PRs from `staging-nixos` need manual backports.

Automatic route (needs maintainer status): add the label `backport release-YY.MM` to the master PR, open or merged. `.github/workflows/backport.yml` opens the backport PR and labels it `8.has: port to stable`, or `8.has: failed backport` on conflict. The bot's PR description reminds the reviewer to check acceptability. Plain PRs from non-maintainers need the manual route.

Manual route:

```
git fetch upstream
git switch --create backport-foo upstream/release-26.05
git cherry-pick -x <commit-on-master>
```

- Base branch is `release-YY.MM`, never `nixos-YY.MM` (that tracks the last tested channel commit).
- `git cherry-pick -x <commit>` when the reason is obvious (minor bumps, fixes). `git cherry-pick -xe <commit>` to add the reason for the backport.
- The commit must exist on `master`. After a squash or rebase merge the hash changes; find the new one in the merge message at the bottom of the master PR.
- PR title includes `[YY.MM]`; description links the master PR.
- If you really can't cherry-pick (for example master has already moved to the next major), add a `Not-cherry-picked-because: <reason>` footer. CI flags it for manual review.
- A security fix that needs different patches on master and the release gets two PRs.

On PRs that target stable branches, the commits job of the `Check` workflow looks for the cherry-pick hash: an error when the original SHA isn't on a development branch, a warning when `git range-diff` shows differences from the original.

## Removing packages

Follow `pkgs/README.md` ("Steps to remove a package"): delete the directory, drop the `all-packages.nix` entry if present, and add a throwing alias in `pkgs/top-level/aliases.nix` (kept in ASCIIbetical order). Package removals get no release note; the alias message does the job.

```nix
{
  foo = throw "foo has been removed because upstream abandoned it in 2026"; # Added 2026-10-14
  bar = throw "'bar' has been renamed to/replaced by 'baz'"; # Converted to throw 2026-10-14
}
```

The commit body explains why and links evidence. Mention the maintainers in the PR. There's no stated policy on when to remove; the docs say to look for a new maintainer or fix small issues first. Test with `nix-env -qaP -f . --show-trace`.

## CI and automated checks

`ci/README.md` and `.github/workflows/` describe what runs. Merge requires the single status `no PR failures`, aggregated from the jobs below; the name is fixed because the branch ruleset references it (`.github/workflows/README.md`). `CONTRIBUTING.md` states "Ofborg is not required by the checks", yet ofborg builds and `@ofborg test <module>` still exist and are how reviewers run NixOS module tests. Stuck ofborg builds (Darwin, `staging` PRs) are normal.

| Check | What it enforces | Run locally |
|-------|------------------|-------------|
| `Lint` / treefmt | `nixfmt`, `nixf-diagnose --auto-fix`, `keep-sorted` blocks, editorconfig, `biome` for JS/TS, `yamlfmt`, `actionlint`, `zizmor` | `nix fmt`, `nix develop --command treefmt`, or `nix-shell --run treefmt` |
| `Lint` / parse | Every Nix file parses | `nix-instantiate --parse` per file |
| `Lint` / nixpkgs-vet | `pkgs/by-name` layout and related structure rules; no `<nixpkgs/...>` self-references; no case-colliding paths | `./ci/nixpkgs-vet.sh master` |
| `Lint` / commits | Commit message rules listed above | Read the list; no local script |
| `Check` / commits | Cherry-pick traceability on stable-targeting PRs | Use `-x` |
| `Check` / manual-file-edits | Review request when `maintainers/github-teams.json` is edited by hand | Don't edit it |
| `Eval` | Evaluates changed outpaths, computes the per-platform rebuild count and its labels, and drives the target-branch review | `nixpkgs-review wip` approximates it |
| `Build` | NixOS and Nixpkgs manuals, `lib` tests, tarball | `nix-build -A tests.<name>` for the relevant test |

Also automated: `CODEOWNERS`-style review requests from `ci/OWNERS` and package maintainers; labels such as `9.needs: reviewer`, `2.status: merge conflict`, `12.approvals: N`; merge queue (`merge-group.yml`) re-runs the checks before the final merge. Unused-binding diagnostics are explicitly ignored in the CI formatter config, so unused code is a reviewer catch, not a CI failure.

## Who merges, and how

- Committers merge. A non-committer needs at least one committer who is confident about intention, code quality and the artifacts.
- Package maintainers can merge through the merge bot by commenting `@NixOS/nixpkgs-merge-bot merge`. The bot lives in `ci/github-script/merge.ts`. Constraints from `ci/README.md`: the PR targets a development branch; it touches only `pkgs/by-name/*`; it's approved by a committer, backported by label, or opened by a committer or `r-ryantm`; the invoker is in `@NixOS/nixpkgs-maintainers` and maintains every touched package; no committer has an outstanding "changes requested" review. With green CI it queues the merge, with pending CI it enables auto-merge, with failing CI it refuses until CI is green and you comment again.
- Non-maintainer-endorsed changes: committers should wait at least a week before merging, longer for critical packages (mass-rebuild or listed in `ci/OWNERS`). Security-team overrides apply for critical fixes (`maintainers/README.md`).
- Comments are non-blocking unless the reviewer uses GitHub's "Request Changes". Every suggestion, blocking or not, should be acknowledged before merge: apply it or reject it explicitly.
- Committers may push small fixes to your branch unless you untick "Allow edits and access to secrets by maintainers".
- Merges go through a merge queue (`merge-group.yml`) that re-runs the required checks, so a PR that was green earlier can still bounce when the base branch moved.

An agent shouldn't invoke the merge bot or merge for the user unless the user is a listed maintainer and has asked for it.

## PR title, description and evidence

`.github/PULL_REQUEST_TEMPLATE.md` is pre-populated. Don't delete it, even with nothing ticked. Put what the template doesn't cover at the top.

- Title: short and descriptive, in sync with the commit subject. For multi-commit PRs, a summary of the commits. A title starting with `WIP:` or containing `[WIP]` stops automatic package builds; draft status does not.
- Summary: what changed and why. For updates, link the changelog or describe the changes so maintainers spot breakage. For new packages, describe the package or link its homepage and say why it should be in nixpkgs. Link related issues and competing PRs.
- Reviewability: provide a smoke test a reviewer can run without research, such as a command that shows the thing works, or a NixOS test.
- Tick only what you did. The template says the boxes are information, not hard requirements.

| Template item | Evidence to give |
|---------------|------------------|
| Built on platform | List only platforms you built on. The supported Hydra systems are `x86_64-linux`, `aarch64-linux`, `aarch64-darwin` (`pkgs/top-level/release-supported-systems.json`). Not testing all isn't a merge blocker. |
| Basic functionality of all binary files | Say which of `./result/bin/*` you ran, and with what arguments. |
| `nixpkgs-review` | `nixpkgs-review pr <N>`, `nixpkgs-review wip` or `nixpkgs-review rev HEAD`; note any dependents that fail and whether they fail on the base too. |
| Package tests at `passthru.tests` | `nix-build -A foo.tests`. `nixpkgs-review` and Hydra don't build `passthru.tests` by default, so say you ran them. |
| NixOS tests | `nix-build -A nixosTests.foo`. Linux only. |
| Tests in `lib/tests` or `pkgs/test` | For function and core changes. |
| Nixpkgs release notes | For a major or breaking package update. |
| NixOS release notes | For a new module, or a significant module change. |

Sandboxing: Linux builds are sandboxed by default; on other platforms set `sandbox = true` in `nix.conf` before testing, since Hydra sandboxes.

## Release notes and documentation

- A new, removed or significantly changed NixOS module needs an entry in `nixos/doc/manual/release-notes/rl-YYMM.section.md` for the release in development (currently `rl-2611`). Sections: Highlights, New Modules, Backward Incompatibilities, Other Notable Changes. The files say to add at an arbitrary position to avoid merge conflicts. A new-module entry links to the program and to the option:

  ```
  - [Foo](https://example.org/foo), a thing that does something. Available as [services.foo](#opt-services.foo.enable).
  ```

- A major or breaking package change (other than removal) goes in `doc/release-notes/rl-YYMM.section.md`. Sections: Highlights, Backward Incompatibilities, Other Notable Changes, Nixpkgs Library.
- Backward-incompatible module changes need a migration path: `mkRenamedOptionModule` or `mkRemovedOptionModule`, and `lib.versionAtLeast config.system.stateVersion "..."` when a change could corrupt existing state (`nixos/README.md`). See [nixos-modules](nixos-modules.md).
- Module options need a description, type, default and example; the module itself needs `meta.maintainers`, and documentation lives in `meta.doc`.
- Manual changes follow `doc/README.md` and `doc/styleguide.md`; ping `@NixOS/documentation-team` for structural changes. Preserve legacy anchors when moving content.
- Explain special packaging choices in a comment or patch name: pinned versions, opinionated patches or `substituteInPlace`, non-default flags, disabled checks (`pkgs/README.md`, "Reviewing contributions").

## Responding to review

- Answer all feedback in one round. `CONTRIBUTING.md` ("Aim to reduce cycles") says waiting days for a reminder wastes everyone's time.
- Acknowledge every suggestion, applied or declined, with a short reason.
- Treat comments marked nitpick as optional, but read them; they often reveal unwritten rules. If a request looks like personal preference, ask whether it's critical to the PR. Unless a written standard or a real maintainability problem backs it, you may decline politely.
- Re-request review after pushing. GitHub doesn't always notify earlier reviewers about new commits or force-pushes (`.github/STALE-BOT.md`), and an approval of older commits doesn't cover your new ones.
- Rewrite history with `git push --force-with-lease` only. Say in a comment what changed in the force-push, because GitHub's diff of a rewritten branch is hard to read. Don't leave `fixup!` commits in the pushed branch; CI rejects them.
- Keep the PR mergeable: rebase onto the base branch (not merge commits from master) when conflicts appear.
- Follow up after about a week of silence with a polite mention. Reviewers are unpaid volunteers. For a longer wait, the channels are the review-request threads on NixOS Discourse, the Review Requests Matrix room, or the "PRs in distress" thread, once you've made a serious attempt first.

## Stale and abandoned PRs

The bot labels a PR `2.status: stale` after 180 days with no assignment, comment, commit, force-push, review or review request (`ci/github-script/bot.ts`). It never closes PRs. Any new comment or push clears the label. Auto-close applies only to issues carrying `4.workflow: auto-close`.

From `.github/STALE-BOT.md`: mark unfinished work as a draft; close with a short comment if you won't return, so someone else can pick it up; to revive, rebase, address valid comments and request review. Close your own PR when a competing one superseded it.

## Pitfalls that stall PRs

These are patterns reviewers commonly raise, with corpus support counts from `find-rules.py`. They describe reviewer tendencies and aren't a causal claim about merging.

- Duplicate or competing PRs (support in the thousands; nearly all closed unmerged). Reviewers redirect to the first PR or the maintainer's.
- Unresolved merge conflicts or failing CI left open; reviewers often ask to fix or close. Docs: "Your PR will not be merged while CI is still failing."
- Mixed unrelated changes in one commit or PR (243 PRs with formal changes-requested on commit separation).
- Maintainer-list edits mixed with package changes (108 PRs with changes-requested on this alone).
- Missing release notes for a new NixOS module (52 PRs backing the rule, 17 with changes-requested).
- Large rebuilds aimed at `master`; reviewers ask to retarget `staging` (1135 PRs back the 500+ rule, 67 with changes-requested).
- Backports that aren't cherry-picks, that carry breaking changes, or that target an unsupported release.
- Approval given earlier on different commits; reviewers commonly ask for a fresh look after substantial pushes.
- Undisclosed automation or a missing `Assisted-by:` trailer on AI-assisted commits (policy in `CONTRIBUTING.md`; reviewers may close or hide the PR).
- Proposing new metadata fields, governance structures or patterns without maintainer discussion first.

## PR readiness checklist

- The package or module passes the inclusion questions, and you searched open and closed PRs, issues and `aliases.nix`.
- Every commit subject matches the area format, has no trailing period, and carries no `fixup!` prefix or Conventional Commits prefix.
- One logical change per commit; `maintainers: add <handle>` is its own commit and comes first.
- Update commits include a changelog or release-notes link; new packages explain why they belong.
- Base branch matches the rebuild count (500/1000) and change type; you retargeted if CI posted a mass-rebuild label.
- `treefmt` is clean and `./ci/nixpkgs-vet.sh master` passes for new top-level packages.
- You built on the platforms you'll tick, ran the binaries, ran `nixpkgs-review` for packages with dependents, and ran `passthru.tests` or `nixosTests`.
- Release notes are written for new, removed or significantly changed modules and for major package changes.
- Special packaging choices, disabled tests and patches have comments saying why.
- AI-assisted commits carry the `Assisted-by:` trailer, and the PR template is intact with only true boxes ticked.
- Backport PRs target `release-YY.MM`, use `git cherry-pick -x`, include `[YY.MM]` in the title and link the master PR.

## Evidence

Counts from `find-rules.py` (support PRs, cr = formal changes-requested); correlation only.

| Rule | Support | cr |
|------|---------|----|
| Separate logically distinct changes into individual commits | 1161 | 243 |
| Maintainer-list change in its own commit | 245 | 108 |
| `<package>: <action>` commit subject format | 632 | 92 |
| Address all reviewer feedback before merge | 255 | 71 |
| Route 500+ rebuilds to `staging` | 1135 | 67 |
| Document breaking changes in release notes | 1177 | 138 |
| `git cherry-pick -x` for backports | 225 | 12 |
| Search for existing PRs before submitting | 1708 | 46 |

## Dated advice to ignore

- "Rebuilds of 100+ packages go to staging": the docs and CI use 500 (consider) and 1000 (mass rebuild).
- "Test on x86_64-darwin": it isn't in `release-supported-systems.json` or the PR template; use `aarch64-darwin`.
- "Format with `nixfmt-rfc-style`": that attribute is now a warning alias for `nixfmt`.
- "Wrap documentation text with `mdDoc`": `lib.mdDoc` is gone; the markup is Markdown by default.
- "Changelog or version dates as `unstable-YYYY-MM-DD`": the tree requires a leading digit, so `0-unstable-YYYY-MM-DD` or `<release>-unstable-YYYY-MM-DD`.
- "Ofborg must pass": ofborg isn't a required check any more; the required status is `no PR failures`.
- "The merge bot is a Python web app": it's now part of `ci/github-script`.
- "Backports need an attestation that they meet the backport policy": the current template has no such box. The bot's PR text asks the reviewer to confirm acceptability.
- "The stale bot closes PRs": it only labels them.
- `doc/contributing/` chapters (`submitting-changes`, `reviewing-contributions`) and their anchors: replaced by `CONTRIBUTING.md`.
