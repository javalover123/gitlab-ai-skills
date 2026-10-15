"""Changed lines from git, for `--changed-only` and `--diff`.

Python 3.9+, stdlib only. Lines are numbered in the new (head) version.
Read-only: runs `git diff`, `git ls-files`, and `git rev-parse` only.
"""

import os
import re
import subprocess

HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


class GitError(RuntimeError):
    pass


# User config must not change what the scripts parse: quoted non-ASCII paths,
# no a/ b/ prefixes, color codes, or an external diff tool.
SAFE_CONFIG = ["-c", "core.quotePath=false", "-c", "diff.noprefix=false", "-c", "diff.mnemonicPrefix=false",
               "-c", "diff.srcPrefix=a/", "-c", "diff.dstPrefix=b/", "-c", "color.ui=never"]
DIFF_COMMANDS = ("diff", "show", "log")


def run(repo, args, check=True):
    """`git -C repo <args>` with SAFE_CONFIG. Output is decoded leniently.
    Raises GitError when git is missing, or when `check` and git fails."""
    args = list(args)
    if args and args[0] in DIFF_COMMANDS:
        args = args[:1] + ["--no-color", "--no-ext-diff"] + args[1:]
    try:
        res = subprocess.run(["git", "-C", repo] + SAFE_CONFIG + args, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
    except OSError as exc:
        raise GitError("cannot run git: {} (install git)".format(exc))
    res.stdout = res.stdout.decode("utf-8", errors="replace")
    res.stderr = res.stderr.decode("utf-8", errors="replace")
    if check and res.returncode != 0:
        raise GitError("git {} failed: {}".format(" ".join(args[:3]), res.stderr.strip()[:300]))
    return res


def _git(repo, args):
    return run(repo, args).stdout


def repo_root(path):
    start = path if os.path.isdir(path) else os.path.dirname(os.path.abspath(path)) or "."
    try:
        return _git(start, ["rev-parse", "--show-toplevel"]).strip()
    except GitError:
        return None


def split_range(spec):
    """(base, head, dots) from `BASE..HEAD` or `BASE...HEAD`; head defaults to HEAD."""
    m = re.match(r"^(.*?)(\.\.\.?)(.*)$", spec or "")
    if not m or not m.group(1):
        raise ValueError("a range must look like BASE..HEAD or BASE...HEAD, got {!r}".format(spec))
    return m.group(1), m.group(3) or "HEAD", m.group(2)


def parse_unified(text):
    """{path: set(lines)} from `git diff -U0` output. Deleted files are skipped."""
    changed = {}
    current = None
    for line in text.splitlines():
        if line.startswith("+++ "):
            target = line[4:].strip()
            if target == "/dev/null":
                current = None
            else:
                current = target[2:] if target.startswith("b/") else target
                changed.setdefault(current, set())
            continue
        m = HUNK_RE.match(line)
        if m and current is not None:
            start = int(m.group(1))
            count = int(m.group(2)) if m.group(2) is not None else 1
            changed[current].update(range(start, start + count))
    return changed


def changed_lines(repo, rev_range=None, paths=None):
    """Changed lines per repo-relative path.

    rev_range: `BASE..HEAD` or `BASE...HEAD`; None means the working tree
    (staged and unstaged) against HEAD, plus untracked files in full.
    """
    args = ["diff", "-U0", "--no-color", "--no-ext-diff", "--find-renames"]
    if rev_range:
        args.append(rev_range)
    else:
        args.append("HEAD")
    args.append("--")
    args.extend(paths or [])
    changed = parse_unified(_git(repo, args))
    if not rev_range:
        others = _git(repo, ["ls-files", "--others", "--exclude-standard", "--"] + list(paths or []))
        for rel in others.splitlines():
            full = os.path.join(repo, rel)
            try:
                with open(full, encoding="utf-8", errors="replace") as fh:
                    count = len(fh.read().split("\n"))
            except OSError:
                continue
            changed[rel] = set(range(1, count + 1))
    return changed
