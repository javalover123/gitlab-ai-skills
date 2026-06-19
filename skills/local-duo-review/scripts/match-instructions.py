#!/usr/bin/env python3
"""match-instructions.py — Map locally-changed files to GitLab Duo custom review instruction groups.

Reads a project's ``.gitlab/duo/mr-review-instructions.yaml`` (the file GitLab
Duo Code Review uses for custom instructions), computes the set of files changed
locally relative to the fork point with the target branch (committed + staged +
unstaged + untracked work; when no target branch can be detected it falls back
to uncommitted changes vs ``HEAD`` only). The base is the local
``git merge-base`` of HEAD and the target — the commit GitLab uses as an MR's
diff base — resolved without any network access. Reports
which instruction group(s) apply to each changed file — approximating the glob
semantics GitLab Duo uses (a doublestar-style matcher): patterns are anchored at
the repo root, a path-segment ``**`` recurses across directories, ``!`` excludes,
and ``{a,b}`` is a union (GitLab 19.1+). ``*.rb`` matches root-level files only;
``**/*.rb`` matches at any depth. A ``**`` that is not its own path segment
(e.g. ``a**b``) is treated as a single ``*`` within one segment, matching Duo's
doublestar behavior rather than letting it cross directories.

Output is plain text in marker-delimited sections for the agent to read.

YAML parsing uses PyYAML if importable, else falls back to the ``ruby`` CLI
(YAML->JSON). No third-party Python dependency is required if either is present.

Usage:
    match-instructions.py [--instructions PATH]... [--target BRANCH]
                          [--base REF] [--no-untracked] [--no-diff]

  --instructions PATH  Path to an instructions YAML. Repeatable: pass it again
                       to load additional instruction groups from another file
                       (e.g. a group-level template). Groups from every file are
                       collected into one flat list. Defaults to
                       .gitlab/duo/mr-review-instructions.yaml.
  --target BRANCH      Branch to diff against. Default: auto-detect, preferring
                       LOCAL refs (the clone's recorded default branch, then
                       local main/master), falling back to remote-tracking
                       origin/main|master only if no local branch exists. The
                       comparison base is the git merge-base (fork point) of
                       HEAD and the target — the same commit GitLab diffs an MR
                       against. Resolution is purely local; no network access.
  --base REF           Explicit comparison base (used verbatim, no merge-base);
                       overrides --target.
  --no-untracked       Exclude untracked files from the changed set.
  --no-diff            Omit the per-file unified diffs from the output.
"""
import argparse
import functools
import os
import re
import shutil
import subprocess
import sys

DEFAULT_INSTRUCTIONS = ".gitlab/duo/mr-review-instructions.yaml"


def run(cmd, stdin=None):
    """Run a command; return (returncode, stdout). stderr is captured but dropped."""
    proc = subprocess.run(cmd, input=stdin, capture_output=True, text=True)
    return proc.returncode, proc.stdout


def load_yaml(path):
    """Parse a YAML file using PyYAML, falling back to the ruby CLI."""
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    try:
        import yaml  # noqa: WPS433 (optional dependency)

        return yaml.safe_load(text)
    except ImportError:
        pass
    if shutil.which("ruby"):
        rc, out = run(
            ["ruby", "-ryaml", "-rjson", "-e", "print YAML.safe_load(STDIN.read).to_json"],
            stdin=text,
        )
        if rc == 0 and out.strip():
            import json

            return json.loads(out)
        sys.exit(f"error: ruby failed to parse YAML — check that {path} is valid YAML")
    sys.exit(
        "error: cannot parse YAML — install PyYAML (pip install pyyaml) or the ruby CLI"
    )


MAX_BRACE_EXPANSIONS = 1024


def expand_braces(pattern):
    """Expand a single brace group ``{a,b}`` into a list of patterns (recursively).

    Caps the number of alternatives at ``MAX_BRACE_EXPANSIONS`` to avoid
    combinatorial blow-up on adversarial patterns (e.g. deeply nested
    ``{a,{b,{c,...}}}``); beyond the cap the brace is treated literally."""
    open_idx = pattern.find("{")
    if open_idx == -1:
        return [pattern]
    depth = 0
    close_idx = None
    for k in range(open_idx, len(pattern)):
        if pattern[k] == "{":
            depth += 1
        elif pattern[k] == "}":
            depth -= 1
            if depth == 0:
                close_idx = k
                break
    if close_idx is None:
        return [pattern]  # unbalanced — treat literally
    pre, body, post = pattern[:open_idx], pattern[open_idx + 1:close_idx], pattern[close_idx + 1:]
    parts, d, last = [], 0, 0
    for k, ch in enumerate(body):
        if ch == "{":
            d += 1
        elif ch == "}":
            d -= 1
        elif ch == "," and d == 0:
            parts.append(body[last:k])
            last = k + 1
    parts.append(body[last:])
    results = []
    for part in parts:
        results.extend(expand_braces(pre + part + post))
        if len(results) > MAX_BRACE_EXPANSIONS:
            return [pattern]  # blow-up guard — treat the brace literally
    return results


def glob_to_regex(pattern):
    """Translate a brace-free glob into a full-match regex string (root-anchored)."""
    out = ["^"]
    i, n = 0, len(pattern)
    while i < n:
        ch = pattern[i]
        if ch == "*":
            j = i
            while j < n and pattern[j] == "*":
                j += 1
            star_run = j - i
            # ``**`` only crosses directory boundaries when it is its own path
            # segment: at the start of the pattern or preceded by '/', AND at the
            # end or followed by '/'. Otherwise (e.g. ``a**b``) doublestar treats
            # it as a single ``*`` confined to one segment.
            prev_is_sep = i == 0 or pattern[i - 1] == "/"
            next_is_sep = j >= n or pattern[j] == "/"
            if star_run >= 2 and prev_is_sep and next_is_sep:
                if j < n and pattern[j] == "/":
                    out.append("(?:.*/)?")  # **/ -> optional leading dirs
                    i = j + 1
                else:
                    out.append(".*")
                    i = j
            else:  # single * (or non-segment **) — within one path segment
                out.append("[^/]*")
                i = j
        elif ch == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(ch))
            i += 1
    out.append("$")
    return "".join(out)


@functools.lru_cache(maxsize=4096)
def compile_pattern(pattern):
    """Expand brace groups and compile each alternative to a regex (cached)."""
    return [re.compile(glob_to_regex(expanded)) for expanded in expand_braces(pattern)]


def any_match(path, patterns):
    for pat in patterns:
        for regex in compile_pattern(pat):
            if regex.match(path):
                return True
    return False


def file_matches(path, filters):
    """A file matches a group iff it matches >=1 positive filter (or there are
    none) AND matches no ``!`` exclusion filter. Empty filters match everything."""
    if not filters:
        return True
    positives, negatives = [], []
    for raw in filters:
        flt = str(raw).strip()
        if not flt:
            continue
        if flt.startswith("!"):
            negatives.append(flt[1:])
        else:
            positives.append(flt)
    if positives and not any_match(path, positives):
        return False
    if any_match(path, negatives):
        return False
    return True


def _ref_exists(ref):
    rc, _ = run(["git", "rev-parse", "--verify", "--quiet", ref])
    return rc == 0


def detect_target(explicit):
    """Resolve the branch to compare against, preferring *local* refs so the
    result matches what GitLab will diff the MR against — and without ever
    touching the network.

    Order: explicit ``--target`` → the clone's recorded default branch
    (``refs/remotes/origin/HEAD`` if configured) → local ``main``/``master`` →
    only then the remote-tracking ``origin/main``/``origin/master`` as a last
    resort. Returns ``(target_ref, autodetected)``."""
    if explicit:
        return explicit, False
    # The clone's recorded default branch, e.g. "origin/main". Local symbolic
    # ref lookup; no fetch. Map it to the matching *local* branch when present.
    rc, out = run(["git", "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD"])
    if rc == 0 and out.strip():
        remote_default = out.strip().rsplit("/", 1)[-1]  # "main"
        if _ref_exists(remote_default):
            return remote_default, True
        if _ref_exists(f"origin/{remote_default}"):
            return f"origin/{remote_default}", True
    for ref in ("main", "master", "origin/main", "origin/master"):
        if _ref_exists(ref):
            return ref, True
    return None, True


def fork_point(target):
    """Return the merge-base (fork point) of HEAD and ``target`` — the commit
    GitLab uses as the diff base for an MR. Falls back to ``target`` itself when
    no common ancestor is found. Purely local; no network access."""
    rc, out = run(["git", "merge-base", target, "HEAD"])
    if rc == 0 and out.strip():
        return out.strip()
    return target


def changed_files(base, include_untracked):
    """Files changed in the working tree vs ``base`` (committed + staged +
    unstaged, plus untracked when requested). When ``base`` is None there is no
    comparison branch, so this falls back to ``HEAD`` and reports uncommitted
    changes only. Deletions are excluded (``--diff-filter=d``)."""
    ref = base if base else "HEAD"
    # Working-tree-vs-ref misses files staged then reverted in the working tree
    # to match ref; union with the index-vs-ref diff to honor the
    # "committed + staged + unstaged" contract.
    _, worktree_out = run(["git", "diff", "--name-only", "--diff-filter=d", ref])
    _, staged_out = run(["git", "diff", "--cached", "--name-only", "--diff-filter=d", ref])
    seen, tracked = set(), []
    for ln in (worktree_out + staged_out).splitlines():
        ln = ln.strip()
        if ln and ln not in seen:
            seen.add(ln)
            tracked.append(ln)
    untracked = []
    if include_untracked:
        _, unt_out = run(["git", "ls-files", "--others", "--exclude-standard"])
        untracked = [ln for ln in unt_out.splitlines() if ln.strip()]
    return tracked, untracked


def file_diff(path, base, untracked_set):
    # git diff exits 1 when differences exist (the normal case here) and >1 on
    # real errors; only treat >1 as a failure worth surfacing.
    if path in untracked_set:
        rc, out = run(["git", "diff", "--no-index", "--", os.devnull, path])
        # --no-index also exits 1 for some errors and produces no textual diff
        # for binary/unreadable files; surface that rather than emitting silence.
        if rc == 1 and not out.strip():
            return f"(no textual diff for untracked {path} — binary or unreadable?)"
    else:
        ref = base if base else "HEAD"
        rc, out = run(["git", "diff", ref, "--", path])
        # Empty here means the file was staged then reverted in the worktree to
        # match ref (the case changed_files unions in); fall back to the
        # index-vs-ref diff so a matched file is never shown with no diff.
        if not out.strip():
            rc, out = run(["git", "diff", "--cached", ref, "--", path])
    if rc > 1:
        return f"(git diff failed for {path} — exit {rc})"
    return out


def collect_groups(instruction_paths):
    """Return (groups, present_paths, missing_paths). Each group: dict with
    source, name, filters, instructions."""
    groups, present, missing = [], [], []
    for path in instruction_paths:
        if not os.path.isfile(path):
            missing.append(path)
            continue
        present.append(path)
        data = load_yaml(path)
        items = data.get("instructions", []) if isinstance(data, dict) else []
        for idx, item in enumerate(items or []):
            if not isinstance(item, dict):
                continue
            groups.append(
                {
                    "source": path,
                    "name": item.get("name")
                    or f"(unnamed #{idx + 1} in {os.path.basename(path)})",
                    "filters": item.get("fileFilters") or [],
                    "instructions": str(item.get("instructions") or "").rstrip(),
                }
            )
    return groups, present, missing


def main():
    parser = argparse.ArgumentParser(
        description="Map locally-changed files to GitLab Duo custom review instruction groups.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--instructions", action="append", default=None)
    parser.add_argument("--target", default=None)
    parser.add_argument("--base", default=None)
    parser.add_argument("--no-untracked", action="store_true")
    parser.add_argument("--no-diff", action="store_true")
    args = parser.parse_args()

    rc, _ = run(["git", "rev-parse", "--is-inside-work-tree"])
    if rc != 0:
        sys.exit(
            "error: not inside a git repository (or 'git' is not on PATH) — "
            "run this from a git checkout with local changes"
        )

    instruction_paths = args.instructions or [DEFAULT_INSTRUCTIONS]
    groups, present, missing = collect_groups(instruction_paths)

    print("=== INSTRUCTIONS ===")
    if present:
        print("files: " + ", ".join(present))
    if missing:
        print("missing: " + ", ".join(missing))
    print(f"groups: {len(groups)}")
    if not groups:
        print("status: none")
        print(
            "hint: this project has no custom Duo review instructions — "
            "tell the user, and suggest the mr-review skill for a general review"
        )

    target, autodetected = detect_target(args.target)
    if args.base:
        base = args.base
    elif target:
        base = fork_point(target)  # merge-base: the commit GitLab diffs against
    else:
        base = None

    print("\n=== BASE ===")
    print(f"target: {target if target else '(none detected)'}")
    print(f"base: {base if base else '(none — uncommitted changes only)'}")
    print(
        "mode: "
        + ("committed + uncommitted vs base" if base else "uncommitted only (vs HEAD)")
    )
    print("note: base is the local merge-base (fork point) with the target — no network access")
    # Auto-detection fell back to a remote-tracking ref because no local default
    # branch was found. That ref is a cache of the last fetch and may be stale.
    if autodetected and target and target.startswith("origin/"):
        print(
            f"warning: no local default branch found; using remote-tracking "
            f"'{target}' (a cache of the last 'git fetch', possibly stale) — "
            "run 'git fetch' or pass --target/--base for an accurate base"
        )

    tracked, untracked = changed_files(base, not args.no_untracked)
    untracked_set = set(untracked)
    all_changed = sorted(set(tracked) | untracked_set)

    print("\n=== CHANGED_FILES ===")
    for path in all_changed:
        tag = " (untracked)" if path in untracked_set else ""
        print(f"{path}{tag}")
    print(f"count: {len(all_changed)}")

    # Compute matches.
    file_to_groups = {path: [] for path in all_changed}
    group_to_files = {}
    for grp in groups:
        matched = [p for p in all_changed if file_matches(p, grp["filters"])]
        group_to_files[id(grp)] = matched
        for path in matched:
            file_to_groups[path].append(grp["name"])

    print("\n=== MATCHES ===")
    any_matched = False
    for grp in groups:
        matched = group_to_files[id(grp)]
        if not matched:
            continue
        any_matched = True
        print(f"## group: {grp['name']}  (source: {grp['source']})")
        print("instructions: |")
        for line in grp["instructions"].splitlines():
            print(f"  {line}")
        print("files:")
        for path in matched:
            print(f"  - {path}")
        print("")
    if not any_matched:
        print("(no changed file matched any instruction group)")

    empty_groups = [g["name"] for g in groups if not group_to_files[id(g)]]
    if empty_groups:
        print("=== GROUPS_WITHOUT_MATCHES ===")
        for name in empty_groups:
            print(name)
        print("")

    unmatched = [p for p in all_changed if not file_to_groups[p]]
    print("=== UNMATCHED_FILES ===")
    print("(changed files no instruction group applies to — out of scope for custom review)")
    for path in unmatched:
        print(path)

    if not args.no_diff and all_changed:
        print("\n=== DIFFS ===")
        for path in all_changed:
            applicable = file_to_groups[path]
            tag = ", ".join(applicable) if applicable else "(none)"
            print(f"--- file: {path}  | groups: {tag} ---")
            print(file_diff(path, base, untracked_set).rstrip("\n"))
            print("")


if __name__ == "__main__":
    main()
