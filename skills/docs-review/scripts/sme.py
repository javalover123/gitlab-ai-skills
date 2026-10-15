#!/usr/bin/env python3
"""Name subject matter experts (SMEs) for source files in a GitLab project.

Ranks people by recency-weighted commits to the files, approvals of the MRs
that introduced those commits, and CODEOWNERS rules that are not too broad.
--as-of counts only history from before that date. Read-only (`glab api`
GETs; glab from $DOCS_REVIEW_GLAB or PATH). Python 3.9+, stdlib only.

Usage: sme.py --project GROUP/PROJECT [--as-of YYYY-MM-DD] [--json] FILE...

Exit codes: 0 success (even with no candidates), 2 usage or environment error.
"""

import argparse
import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib import gitlab_api  # noqa: E402
from lib import codeowners  # noqa: E402

# One recent commit scores 1.0, an approval half that. CODEOWNERS is a fixed
# bonus because ownership does not decay.
W_COMMIT, W_APPROVAL, W_CODEOWNER = 1.0, 0.5, 1.0
HALF_LIFE_DAYS = 90.0
WINDOW_DAYS = 365
LIMIT = 10
MAX_COMMITS = 300  # per file
MAX_LOOKUPS = 20  # commit -> MR username lookups
MAX_APPROVAL_LOOKUPS = 8
BROAD_FILES = 500  # a CODEOWNERS rule matching more files names no SMEs
TREE_PAGES = 6  # API tree pages (100 entries each) read to count a rule's files
# GitLab reads the first of these that exists.

BOT_USER_RE = re.compile(r"(^|[-_.])bot($|[-_.\d])|^project_\d+_bot|^group_\d+_bot|^ghost$|renovate|dependabot|"
                         r"^gitlab-(bot|crowdin|release-tools)", re.I)
BOT_NAME_RE = re.compile(r"\bbot\b|renovate|dependabot|^gitlab$|release tools", re.I)


def warn(msg):
    sys.stderr.write("sme: {}\n".format(msg))


def is_bot(username=None, name=None, email=None):
    if username and BOT_USER_RE.search(username):
        return True
    if name and BOT_NAME_RE.search(name):
        return True
    return bool(email and re.search(r"(bot|noreply)@|@noreply\.|\+bot@", email, re.I)
                and not re.search(r"users\.noreply", email, re.I))


def parse_date(value):
    """ISO date or datetime -> aware datetime (UTC midnight for a date), or None."""
    if not value:
        return None
    if re.match(r"^\d{4}-\d{2}-\d{2}$", value):
        value += "T00:00:00Z"
    try:
        dt = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=datetime.timezone.utc)


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def recency(dt, now):
    if dt is None:
        return 0.25
    return 0.5 ** (max((now - dt).total_seconds() / 86400.0, 0.0) / HALF_LIFE_DAYS)


# ---------------------------------------------------------------- CODEOWNERS





def literal_dirs(pattern):
    """The literal path segments before the first wildcard, and whether the
    whole pattern is literal."""
    lit = []
    for seg in [x for x in pattern.strip().strip("/").split("/") if x]:
        if any(c in seg for c in "*?["):
            return lit, False
        lit.append(seg)
    return lit, True


def structurally_broad(pattern):
    """`*`, a leading wildcard, a top-level directory, or one literal directory
    and a wildcard."""
    lit, all_literal = literal_dirs(pattern)
    if not lit:
        return True
    if len(lit) > 1:
        return False
    if not all_literal or pattern.rstrip().endswith("/"):
        return True
    return pattern.strip().startswith("/") and "." not in lit[0]  # /doc is a directory


def broad_reason(api, project, ref, pattern, regex):
    """Why a CODEOWNERS rule is too broad to name SMEs, or None. Files are
    counted from the API tree under the pattern's literal directory."""
    if structurally_broad(pattern):
        return "broad pattern"
    ep = "projects/{}/repository/tree?path={}&recursive=true&ref={}".format(
        gitlab_api.enc(project), gitlab_api.enc("/".join(literal_dirs(pattern)[0])), gitlab_api.enc(ref))
    try:
        items, truncated = api.get_pages(ep, per_page=100, max_pages=TREE_PAGES)
    except gitlab_api.GlabError:
        items, truncated = [], True
    n = sum(1 for i in items if isinstance(i, dict) and i.get("type") == "blob" and regex.match(i.get("path") or ""))
    if n > BROAD_FILES:
        return "matches {} files".format(n)
    if truncated:
        return "matches more files than could be counted"
    return None


def codeowners_ref(api, project, branch, as_of, notes):
    """The last default-branch commit before --as-of, else the default branch."""
    if not as_of:
        return branch
    try:
        data = api.get("projects/{}/repository/commits?ref_name={}&until={}&per_page=1".format(
            gitlab_api.enc(project), gitlab_api.enc(branch), gitlab_api.enc(iso(as_of))))
        if isinstance(data, list) and data and data[0].get("id"):
            return data[0]["id"]
    except gitlab_api.GlabError as exc:
        notes.append("as-of commit lookup failed: {}".format(str(exc)[:120]))
    notes.append("CODEOWNERS could not be read as of {}".format(as_of.date().isoformat()))
    return None


def add_codeowners(api, cands, project, branch, files, as_of, notes):
    """Add CODEOWNERS users to cands; return the owner groups found."""
    ref = codeowners_ref(api, project, branch, as_of, notes)
    if ref is None:
        return []
    text = None
    for rel in codeowners.LOCATIONS:
        try:
            data = api.get("projects/{}/repository/files/{}/raw?ref={}".format(
                gitlab_api.enc(project), gitlab_api.enc(rel), gitlab_api.enc(ref)))
        except gitlab_api.GlabError:
            continue
        if isinstance(data, str):
            text = data
            notes.append("CODEOWNERS read from {} at {}".format(rel, ref))
            break
    if text is None:
        notes.append("no CODEOWNERS file found")
        return []
    rules = codeowners.parse(text)
    regex_of = {pattern: regex for _, _, pattern, regex, _ in rules}
    broad, groups = {}, []
    for path in files:
        for name, pattern, owners in codeowners.owners_for(rules, path).values():
            label = "CODEOWNERS `{}`{} ({})".format(pattern, " [{}]".format(name) if name else "", path)
            for owner in owners:
                handle = owner[1:]
                if "/" in handle:
                    groups.append({"group": handle, "reason": label})
                    continue
                if pattern not in broad:
                    broad[pattern] = broad_reason(api, project, ref, pattern, regex_of[pattern])
                if broad[pattern] or is_bot(username=handle):
                    continue
                p = cands.by_username(handle) or cands.get("user:" + handle)
                p["username"] = handle
                if not p["codeowner"]:
                    p["score"] += W_CODEOWNER
                p["codeowner"] = True
                p["files"].add(path)
                p["reasons"].append(label)
    skipped = sorted(p for p, why in broad.items() if why)
    if skipped:
        notes.append("CODEOWNERS owners not used, rule too broad: {}".format(
            "; ".join("`{}` ({})".format(p, broad[p]) for p in skipped)))
    return groups


# ---------------------------------------------------------------- history

class Candidates(object):
    def __init__(self):
        self.people = {}

    def get(self, key, name=None):
        p = self.people.setdefault(key, {"username": None, "name": name, "emails": set(), "score": 0.0,
                                         "reasons": [], "commits": 0, "approvals": 0, "codeowner": False,
                                         "last_activity": None, "files": set(), "commit_files": set()})
        p["name"] = p["name"] or name
        return p

    def by_username(self, username):
        return next((p for p in self.people.values() if p["username"] == username), None)


def names_match(mr_name, commit_name, username, emails):
    if mr_name and commit_name and mr_name.strip().lower() == commit_name.strip().lower():
        return True
    for e in emails:
        local = e.split("@", 1)[0]
        if username and local and username.lower() in (local, local.split("+")[-1]):
            return True
    return False


def collect(api, project, project_id, files, since, as_of, notes):
    pid = gitlab_api.enc(project)
    now = as_of or datetime.datetime.now(datetime.timezone.utc)
    cands, commits_by_author = Candidates(), {}
    for path in files:
        endpoint = "projects/{}/repository/commits?{}".format(pid, gitlab_api.query(
            {"path": path, "since": since, "until": iso(as_of) if as_of else None}))
        try:
            commits, truncated = api.get_pages(endpoint, per_page=100, max_pages=(MAX_COMMITS + 99) // 100)
        except gitlab_api.GlabError as exc:
            notes.append("commits for {} failed: {}".format(path, str(exc)[:160]))
            continue
        if truncated:
            notes.append("{}: commit history capped at {} commits".format(path, len(commits)))
        for c in commits:
            name, email = c.get("author_name"), (c.get("author_email") or "").lower()
            if is_bot(name=name, email=email) or re.match(r"^Merge branch ", c.get("title") or ""):
                continue
            dt = parse_date(c.get("authored_date") or c.get("committed_date"))
            if as_of and dt and dt >= as_of:
                continue  # the API filters by committed date; authored date can differ
            key = email or (name or "").lower()
            p = cands.get(key, name)
            p["emails"].add(email)
            p["score"] += W_COMMIT * recency(dt, now)
            p["commits"] += 1
            p["files"].add(path)
            p["commit_files"].add(path)
            if dt and (p["last_activity"] is None or dt > p["last_activity"]):
                p["last_activity"] = dt
            commits_by_author.setdefault(key, []).append((dt, c.get("id"), path))
    # Map authors to usernames through the MRs of their most recent commits.
    lookups, mrs_seen = 0, {}
    for key, p in sorted(cands.people.items(), key=lambda kv: -kv[1]["score"]):
        if lookups >= MAX_LOOKUPS:
            notes.append("username lookup stopped after {} calls".format(lookups))
            break
        for _, sha, cpath in sorted(commits_by_author.get(key, []), key=lambda x: x[0] or now, reverse=True)[:3]:
            lookups += 1
            try:
                mrs = api.get("projects/{}/repository/commits/{}/merge_requests".format(pid, sha)) or []
            except gitlab_api.GlabError as exc:
                notes.append("MR lookup for {} failed: {}".format(sha[:12], str(exc)[:120]))
                continue
            for mr in mrs if isinstance(mrs, list) else []:
                if mr.get("project_id") not in (None, project_id):
                    continue
                merged = parse_date(mr.get("merged_at"))
                # A later MR still maps the author, but its approvals do not count.
                if not (as_of and merged and merged >= as_of):
                    mrs_seen.setdefault(mr.get("iid"), (mr, cpath))
                author = mr.get("author") or {}
                if author.get("username") and names_match(author.get("name"), p["name"], author["username"],
                                                          p["emails"]):
                    p["username"] = author["username"]
            if p["username"]:
                break
    recent = sorted(mrs_seen.items(), key=lambda kv: kv[1][0].get("merged_at") or "", reverse=True)
    for iid, (mr, mpath) in recent[:MAX_APPROVAL_LOOKUPS]:
        try:
            data = api.get("projects/{}/merge_requests/{}/approvals".format(pid, iid)) or {}
        except gitlab_api.GlabError as exc:
            notes.append("approvals for !{} failed: {}".format(iid, str(exc)[:120]))
            continue
        dt = parse_date(mr.get("merged_at") or mr.get("updated_at"))
        if as_of and dt and dt >= as_of:
            continue
        for a in data.get("approved_by") or []:
            user = a.get("user") or {}
            uname = user.get("username")
            if not uname or is_bot(username=uname, name=user.get("name")):
                continue
            p = cands.by_username(uname) or cands.get("user:" + uname, user.get("name"))
            p["username"] = uname
            p["score"] += W_APPROVAL * recency(dt, now)
            p["approvals"] += 1
            p["files"].add(mpath)
    return cands


def finalize(cands):
    merged = {}
    for p in cands.people.values():
        if not p["username"] or is_bot(username=p["username"]):
            continue
        reasons = []
        if p["commits"]:
            last = p["last_activity"].date().isoformat() if p["last_activity"] else "unknown"
            reasons.append("{} commit(s) to {} (latest {})".format(
                p["commits"], ", ".join(sorted(p["commit_files"])), last))
        if p["approvals"]:
            reasons.append("approved {} MR(s) touching these files".format(p["approvals"]))
        reasons.extend(p["reasons"])
        m = merged.get(p["username"])
        if m is None:  # an author with two emails merges into one entry
            merged[p["username"]] = {"username": p["username"], "name": p["name"], "score": p["score"],
                                     "reasons": reasons, "commits": p["commits"], "approvals": p["approvals"],
                                     "codeowner": p["codeowner"], "files": set(p["files"])}
            continue
        m["score"] += p["score"]
        m["commits"] += p["commits"]
        m["approvals"] += p["approvals"]
        m["codeowner"] = m["codeowner"] or p["codeowner"]
        m["reasons"] += [r for r in reasons if r not in m["reasons"]]
        m["files"] |= p["files"]
    for m in merged.values():
        m["score"], m["files"] = round(m["score"], 3), sorted(m["files"])
    return sorted(merged.values(), key=lambda c: (-c["score"], c["username"]))[:LIMIT]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+", help="file paths in the project")
    ap.add_argument("--project", required=True, help="project path, such as gitlab-org/gitlab")
    ap.add_argument("--as-of", help="ISO date: count only history before it, and measure recency from it")
    ap.add_argument("--json", action="store_true", help="print the candidates as JSON")
    args = ap.parse_args(argv)
    as_of = parse_date(args.as_of)
    if args.as_of and as_of is None:
        warn("--as-of must be an ISO date such as 2026-05-01")
        return 2
    api = gitlab_api.GitLab(None)
    try:
        project = api.get("projects/{}".format(gitlab_api.enc(args.project))) or {}
    except gitlab_api.GlabError as exc:
        warn(str(exc))
        return 2
    notes = []
    if as_of:
        notes.append("as of {}: later commits, merges, and approvals are ignored".format(as_of.date().isoformat()))
    since = iso((as_of or datetime.datetime.now(datetime.timezone.utc)) - datetime.timedelta(days=WINDOW_DAYS))
    cands = collect(api, args.project, project.get("id"), args.files, since, as_of, notes)
    groups = add_codeowners(api, cands, args.project, project.get("default_branch") or "main", args.files, as_of,
                            notes)
    unmapped = sum(1 for p in cands.people.values() if not p["username"] and p["commits"])
    if unmapped:
        notes.append("{} commit author(s) could not be mapped to a username".format(unmapped))
    ranked = finalize(cands)
    if args.json:
        sys.stdout.write(json.dumps(ranked, indent=2) + "\n")
    else:
        sys.stdout.write("SME candidates for {} ({} file(s), commits since {}):\n".format(
            args.project, len(args.files), since[:10]))
        for c in ranked:
            sys.stdout.write("  {:<24} {:>6.2f}  {}\n".format(c["username"], c["score"], "; ".join(c["reasons"])))
        if not ranked:
            sys.stdout.write("  none found\n")
        for g in groups:
            sys.stdout.write("  group @{}: {}\n".format(g["group"], g["reason"]))
    for n in notes:
        warn(n)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, UnicodeError, ValueError, RuntimeError) as exc:  # a one-line error, not a traceback
        if os.environ.get("DOCS_REVIEW_DEBUG"):
            raise
        sys.stderr.write("{}: error: {}\n".format(sys.argv[0].rsplit("/", 1)[-1], exc))
        sys.exit(2)
