#!/usr/bin/env python3
"""Post combined docs-review findings to a GitLab MR: inline comments on the
reviewed diff version plus one summary note. Tier, technical writer, and
first-time writer come from `target` in findings.json.

Usage:
  post_review.py out/findings.json --project group/proj --mr 42 --dry-run --out out/post
  post_review.py out/findings.json --project group/proj --mr 42 --mode auto

Exit codes: 0 no blocker, 1 blockers found, 2 usage, environment, or API error.

Guardrails:
  - Every note starts with `:robot: AI-generated docs review`.
  - Interactive mode (default) only previews; it posts with --yes. Auto mode
    (--mode auto or DOCS_REVIEW_MODE=auto) posts. --dry-run never writes.
  - Five writes exist: create a note, update our own summary note
    (`<!-- docs-review:summary -->`), create a discussion, and, on our own
    threads that no person has replied to, add a reply and resolve them.
  - With --applied (auto mode, after a writer step), fixed findings are listed
    in the summary, never posted. Our open threads they fix, or whose line a
    later commit changed and that this review no longer finds, get a short
    reply and are resolved. A new finding that matches one of our open
    threads is not posted again.
  - Inline comments carry `<!-- docs-review:fp=... -->`; a fingerprint already
    in any note, or in a resolved thread, is skipped.
  - Non-public references are withheld (lib/visibility.py, fail closed).
  - SME mentions only for `facts` findings that are contradicted or low
    confidence: at most 2 per finding, 5 per run; never the MR author or us.
  - Finding text is untrusted: `@` handles, HTML comments, and quick action
    lines are neutralized, so it cannot ping, run `/approve`, or spoof markers.
  - Tier `severe` mentions the technical writer; tier `high` names them in
    backticks without a ping.
  - If the reviewed version's diffs are gone and `repository/compare` cannot
    rebuild them, exit 2 instead of moving every finding to the summary.
"""

import argparse
import datetime
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from lib import findings as F  # noqa: E402
from lib import gitlab_api  # noqa: E402
from lib import importance as IMP  # noqa: E402
from lib import report as R  # noqa: E402
from lib import visibility  # noqa: E402

PREFIX = ":robot: AI-generated docs review"
SUMMARY_MARKER = "<!-- docs-review:summary -->"
FP_MARKER = "<!-- docs-review:fp={} -->"
# Our marker is always the last line, so a marker quoted inside a suggestion
# block cannot hide another finding.
FP_RE = re.compile(r"<!-- docs-review:fp=([0-9a-f]{40}(?:,[0-9a-f]{40})*) -->\s*$")
SHA_RE = re.compile(r"^[0-9a-f]{7,40}$")
MAX_MENTIONS = 5
MENTIONS_PER_FINDING = 2
DEFAULT_SAFETY_CAP = 50
MAX_SUMMARY_ITEMS = 50

# The only write endpoints this script may call.
ALLOWED_WRITES = (
    ("POST", re.compile(r"^projects/[^/]+/merge_requests/\d+/notes$")),
    ("PUT", re.compile(r"^projects/[^/]+/merge_requests/\d+/notes/\d+$")),
    ("POST", re.compile(r"^projects/[^/]+/merge_requests/\d+/discussions$")),
    ("POST", re.compile(r"^projects/[^/]+/merge_requests/\d+/discussions/([0-9a-f]+)/notes$")),
    ("PUT", re.compile(r"^projects/[^/]+/merge_requests/\d+/discussions/([0-9a-f]+)$")),
)
MATCH_LINES = 10  # a new finding within this many lines of our open thread, same file and rule, is that thread
QUICK_ACTION_RE = re.compile(r"^(\s*)/(?=[A-Za-z_])", re.M)
MENTION_RE = re.compile(r"(?<![\w`@])@([A-Za-z0-9_][A-Za-z0-9_.\-/]*)")
BOT_RE = re.compile(r"(^|[-_.])bot($|[-_.\d])|^project_\d+_bot|^group_\d+_bot|^ghost$", re.I)


def warn(msg):
    sys.stderr.write("post_review: {}\n".format(msg))


class GuardrailError(RuntimeError):
    pass


# ---------------------------------------------------------------- text safety

def untrusted(text):
    """Make finding text safe to embed: no mentions, markers, or quick actions."""
    if text is None:
        return ""
    text = str(text)
    text = text.replace("<!--", "&lt;!--").replace("-->", "--&gt;")
    # A zero-width space after `@` is not a mention, inside or outside a code span.
    text = MENTION_RE.sub(lambda m: "@\u200b" + m.group(1), text)
    return QUICK_ACTION_RE.sub(lambda m: m.group(1) + "\\/", text)


OPEN_FENCE_RE = re.compile(r"^(`{3,})[^`]*$")  # CommonMark: a backtick fence's info string has no backtick
CLOSE_FENCE_RE = re.compile(r"^(`{3,})[ \t]*$")


def one_line(text):
    """Untrusted text on one line, so it cannot open a fence or start a line."""
    return R.one_line(text, untrusted)


def _code_lines(lines):
    """Indexes of lines inside closed ``` fences that start at column 0: the only
    blocks GitLab's quick action parser skips. A line that only looks like a
    fence, such as ```a`b, is paragraph text, so it is not counted."""
    inside, start, fence = set(), None, None
    for i, line in enumerate(lines):
        if fence is None:
            m = OPEN_FENCE_RE.match(line)
            if m:
                start, fence = i, m.group(1)
            continue
        m = CLOSE_FENCE_RE.match(line)
        if m and len(m.group(1)) >= len(fence):
            inside.update(range(start, i + 1))
            start, fence = None, None
    return inside


def escape_quick_actions(body):
    """Escape lines that start with `/` outside closed fenced code blocks."""
    lines = body.split("\n")
    code = _code_lines(lines)
    return "\n".join(line if i in code else QUICK_ACTION_RE.sub(lambda m: m.group(1) + "\\/", line)
                     for i, line in enumerate(lines))


def check_body(body):
    if not body.startswith(PREFIX):
        raise GuardrailError("note body must start with the AI-generated prefix")
    lines = body.split("\n")
    code = _code_lines(lines)
    for i, line in enumerate(lines):
        if i not in code and re.match(r"^\s*/[A-Za-z_]", line):
            raise GuardrailError("note body contains a quick action line: {!r}".format(line[:60]))


class SafeWriter(object):
    """Allowlisted writes only. In dry-run it records and never calls."""

    def __init__(self, api, dry_run, vis=None, own_threads=()):
        self.api = api
        self.dry_run = dry_run
        self.vis = vis
        self.own_threads = set(own_threads)  # discussions we may reply to or resolve
        self.redacted = 0
        self.planned = []

    def write(self, method, endpoint, body, label):
        match = next((rx.match(endpoint) for m, rx in ALLOWED_WRITES if m == method and rx.match(endpoint)), None)
        if match is None:
            raise GuardrailError("write not allowed: {} {}".format(method, endpoint))
        thread = match.group(1) if match.groups() else None
        if thread is not None and thread not in self.own_threads:
            raise GuardrailError("not our thread, or a person replied to it: {}".format(thread))
        allowed = set(["resolved"]) if (method == "PUT" and thread) else set(["body", "position"])
        if set(body) - allowed or (method == "PUT" and thread and body != {"resolved": True}):
            raise GuardrailError("unexpected body keys: {}".format(sorted(set(body) - allowed) or body))
        if "body" not in body:
            self.planned.append({"method": method, "endpoint": endpoint, "body": body, "label": label})
            return None if self.dry_run else self.api.write(method, endpoint, body)
        if self.vis is not None:
            # The last gate: no rendered text names a reference that is not
            # confirmed public, whatever field it came from.
            text, n = visibility.redact_text(body["body"], self.vis)
            if n:
                body = dict(body, body=text)
                self.redacted += n
        check_body(body["body"])
        self.planned.append({"method": method, "endpoint": endpoint, "body": body, "label": label})
        if self.dry_run:
            return None
        return self.api.write(method, endpoint, body)


# ---------------------------------------------------------------- MR context

def parse_diff_positions(diff):
    """{new_line: old_line or None} for lines a comment can attach to."""
    pos, old, new = {}, 0, 0
    for line in (diff or "").split("\n"):
        m = re.match(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
        if m:
            old, new = int(m.group(1)), int(m.group(2))
            continue
        if not line or line.startswith("\\"):
            continue
        tag = line[0]
        if tag == "+":
            pos[new] = None
            new += 1
        elif tag == "-":
            old += 1
        elif tag == " ":
            pos[new] = old
            new += 1
            old += 1
    return pos


class Context(object):
    def __init__(self):
        self.me = None
        self.author = None
        self.state = None
        self.refs = {}
        self.files = {}          # new_path -> {"old_path", "positions"}
        self.fps = set()         # fingerprints in notes other than our summary note
        self.resolved_fps = set()
        self.summary_note = None  # {"id", "discussion_id"}
        self.read_errors = []
        self.notes = []
        self.version = None       # the MR diff version used for positions
        self.inline_ok = True     # False when the reviewed head is not an MR version
        self.positions_error = None  # set when no diff could be read for positions
        self.visibility = None
        self.project_path = None  # group/project, for same-project references
        self.threads = []         # our inline threads: see load_context


def sha_match(a, b):
    a, b = (a or "").lower(), (b or "").lower()
    if not SHA_RE.match(a) or not SHA_RE.match(b):
        return False
    return a.startswith(b) or b.startswith(a)


def pick_version(versions, head_sha):
    """(version, is_latest). With a head SHA, the version with that head_sha,
    or (None, False). Without one, the latest version."""
    if not versions:
        return None, False
    if not head_sha:
        return versions[0], True
    for i, v in enumerate(versions):
        if sha_match(v.get("head_commit_sha"), head_sha):
            return v, i == 0
    return None, False


def rebuild_diffs(api, base, refs):
    """(diffs, error) from read-only `repository/compare` for a version whose
    diffs GitLab pruned (replays of older MR versions hit this)."""
    b, h = refs.get("base_sha"), refs.get("head_sha")
    if not b or not h:
        return None, "the MR version has no base or head SHA"
    pid = base.split("/merge_requests/")[0]
    try:
        cmp_ = api.get("{}/repository/compare?{}".format(pid, gitlab_api.query({"from": b, "to": h, "straight": "true"})))
    except gitlab_api.GlabError as exc:
        return None, "repository/compare failed: {}".format(str(exc)[:160])
    diffs = cmp_.get("diffs") if isinstance(cmp_, dict) else None
    return (diffs, None) if diffs else (None, "repository/compare returned no diffs")


def load_context(api, project, mr, dry_run, head_sha=None):
    ctx = Context()
    pid = gitlab_api.enc(project)
    base = "projects/{}/merge_requests/{}".format(pid, mr)

    def read(fn, label):
        try:
            return fn()
        except gitlab_api.GlabError as exc:
            if not dry_run:
                raise
            ctx.read_errors.append("{}: {}".format(label, str(exc)[:160]))
            return None

    me = read(lambda: api.get("user"), "current user")
    ctx.me = (me or {}).get("username") if isinstance(me, dict) else None
    info = read(lambda: api.get(base), "merge request")
    if isinstance(info, dict):
        ctx.author = (info.get("author") or {}).get("username")
        full = str((info.get("references") or {}).get("full") or "")
        ctx.project_path = full.rsplit("!", 1)[0] or None
        ctx.state = info.get("state")
        ctx.refs = dict(info.get("diff_refs") or {})
    # Long-lived MRs have many versions: read them all, or the reviewed head is missed.
    versions = read(lambda: api.get_pages(base + "/versions", per_page=100, max_pages=20)[0], "versions")
    diffs = None
    if isinstance(versions, list) and versions:
        v, latest = pick_version(versions, head_sha)
        if v is None:
            ctx.refs = {}
            ctx.inline_ok = False
            ctx.notes.append("The reviewed head {} is not a diff version of this MR, so nothing was posted inline. "
                             "Rerun the review on the current head.".format(str(head_sha)[:12]))
        else:
            ctx.version = v.get("id")
            ctx.refs = {"base_sha": v.get("base_commit_sha"), "start_sha": v.get("start_commit_sha"),
                        "head_sha": v.get("head_commit_sha")}
            if latest:
                diffs = read(lambda: api.get_pages(base + "/diffs", per_page=50, max_pages=20)[0], "diffs")
                pruned = not diffs
            else:
                ver = read(lambda: api.get("{}/versions/{}".format(base, v.get("id"))), "version diffs")
                diffs = ver.get("diffs") if isinstance(ver, dict) else None
                # GitLab prunes the diffs of old versions: `diffs` comes back empty
                # and `state` is no longer `collected`.
                pruned = not diffs or (isinstance(ver, dict) and ver.get("state") not in (None, "collected"))
                ctx.notes.append("Inline positions use MR diff version {} (head {}), not the latest version.".format(
                    v.get("id"), str(v.get("head_commit_sha"))[:12]))
            if pruned:
                diffs, err = rebuild_diffs(api, base, ctx.refs)
                if diffs:
                    ctx.notes.append("The diffs of that version are no longer stored, so positions were rebuilt "
                                     "from repository/compare.")
                else:
                    ctx.positions_error = "MR diff version {} has no stored diffs, and rebuilding them failed: {}".format(
                        v.get("id"), err)
    elif head_sha and ctx.refs.get("head_sha") and not sha_match(ctx.refs.get("head_sha"), head_sha):
        ctx.refs = {}
        ctx.inline_ok = False
        ctx.notes.append("The reviewed head {} is not the MR head, so nothing was posted inline.".format(
            str(head_sha)[:12]))
    elif ctx.refs.get("head_sha"):
        diffs = read(lambda: api.get_pages(base + "/diffs", per_page=50, max_pages=20)[0], "diffs")
    for d in diffs or []:
        if d.get("deleted_file"):
            continue
        ctx.files[d.get("new_path")] = {"old_path": d.get("old_path"), "positions": parse_diff_positions(d.get("diff"))}
    discussions = read(lambda: api.get_pages(base + "/discussions", per_page=100, max_pages=20)[0], "discussions")
    summary_candidates = []
    for disc in discussions or []:
        notes = disc.get("notes") or []
        resolved = any(n.get("resolvable") and n.get("resolved") for n in notes)
        record_thread(ctx, disc, notes, resolved)
        for n in notes:
            body = n.get("body") or ""
            if body.split("\n")[:2] == [PREFIX, SUMMARY_MARKER]:
                owner = (n.get("author") or {}).get("username")
                if ctx.me is None or owner == ctx.me:
                    summary_candidates.append({"id": n.get("id"), "discussion_id": disc.get("id"),
                                               "created_at": n.get("created_at") or ""})
                    continue
            if not body.startswith(PREFIX) or (ctx.me is not None
                                               and (n.get("author") or {}).get("username") != ctx.me):
                continue  # only our own comments count, or anyone could hide a finding
            for group in FP_RE.findall(body.rstrip()):
                for fp in group.split(","):
                    ctx.fps.add(fp)
                    if resolved:
                        ctx.resolved_fps.add(fp)
    if summary_candidates:
        summary_candidates.sort(key=lambda c: (c["created_at"], c["id"] or 0))
        ctx.summary_note = summary_candidates[0]
    return ctx


ID_IN_BODY_RE = re.compile(r"\(`([a-z0-9][a-z0-9_-]*(?:\.[A-Za-z0-9_-]+)+)`\)")


def record_thread(ctx, disc, notes, resolved):
    """Our inline thread, for repeat matching and resolving: its fingerprints,
    rule ids, place, whether a person replied, and whether a later commit
    changed its line (GitLab's "changed this line" system note)."""
    if not notes:
        return
    first = notes[0]
    body = first.get("body") or ""
    if not body.startswith(PREFIX) or SUMMARY_MARKER in body.split("\n")[:2]:
        return
    if ctx.me is not None and (first.get("author") or {}).get("username") != ctx.me:
        return
    m = FP_RE.search(body.rstrip())
    if not m:
        return
    pos = first.get("position") or {}
    human = any(not n.get("system") and (n.get("author") or {}).get("username") != ctx.me for n in notes[1:])
    outdated = any(n.get("system") and "changed this line" in (n.get("body") or "") for n in notes[1:])
    ctx.threads.append({"id": disc.get("id"), "fps": set(m.group(1).split(",")), "ids": ID_IN_BODY_RE.findall(body),
                        "file": pos.get("new_path"), "line": pos.get("new_line"), "resolved": resolved,
                        "human": human, "outdated": outdated,
                        "message": " ".join(re.sub(r"<!--.*?-->|```.*?```", " ", body[len(PREFIX):], flags=re.S).split())[:400],
                        "replied": [n.get("body") or "" for n in notes[1:] if not n.get("system")]})


def thread_for(f, threads):
    """Our thread about the same point: same fingerprint, or the same rule on
    the same file within MATCH_LINES lines."""
    fp, line = f.get("fingerprint"), f.get("line") or 0
    for t in threads:
        if fp and fp in t["fps"]:
            return t
    for t in threads:
        if t["file"] == f.get("file") and f.get("id") in t["ids"] and t["line"] \
                and abs(t["line"] - line) <= MATCH_LINES:
            return t
    return None


def open_threads(ctx):
    return [t for t in ctx.threads if not t["resolved"]]


def resolve_fixed(ctx, writer, endpoint_base, findings, applied, head):
    """Reply to and resolve our open threads that are fixed: an applied
    finding matches them, or a later commit changed their line and this
    review no longer finds them. A thread a person replied to stays open."""
    done = []
    applied_list = (applied or {}).get("applied") or []
    for t in open_threads(ctx):
        if t["human"] or thread_for_any(t, findings):
            continue
        hit = thread_for_any(t, applied_list)
        if hit:
            text = "Applied in {}.".format(head[:12])
        elif t["outdated"]:
            text = "Fixed in {}: a later commit changed this line, and this review no longer finds the problem.".format(
                head[:12])
        else:
            continue
        base = "{}/discussions/{}".format(endpoint_base, t["id"])
        writer.write("POST", base + "/notes", {"body": PREFIX + "\n\n" + text}, "reply " + t["id"])
        writer.write("PUT", base, {"resolved": True}, "resolve " + t["id"])
        done.append(t["id"])
    return done


def thread_for_any(t, items):
    return next((f for f in items if thread_for(f, [t]) is t), None)


# ---------------------------------------------------------------- planning

def mention_eligible(f):
    return f.get("reviewer") == "facts" and (f.get("verdict") == "contradicted" or f.get("confidence") == "low")


class MentionBudget(object):
    """At most MAX_MENTIONS distinct people per run; never anyone in `exclude`."""

    def __init__(self, exclude, limit=MAX_MENTIONS):
        self.limit = limit
        self.people = []
        self.exclude = set(u.lower() for u in exclude if u)

    def take(self, usernames, limit=MENTIONS_PER_FINDING):
        picked = []
        for u in usernames:
            if not u or len(picked) >= limit:
                continue
            u = u.lstrip("@")
            if u.lower() in self.exclude or BOT_RE.search(u) or not re.match(r"^[A-Za-z0-9_][A-Za-z0-9_.\-]*$", u):
                continue
            if u not in self.people:
                if len(self.people) >= self.limit:
                    continue
                self.people.append(u)
            if u not in picked:
                picked.append(u)
        return picked


def sme_question(f, people):
    ev = next((e for e in f.get("evidence") or [] if isinstance(e, dict) and e.get("ref") != "non-public"), {})
    if ev.get("ref"):
        evidence = untrusted(ev.get("ref"))
    elif f.get("withheld_internal"):
        evidence = "internal, withheld from this comment"
    else:
        evidence = "none recorded"
    who = ", ".join("@" + p for p in people)
    claim = " ".join(untrusted(f.get("quote") or f.get("message")).split())
    return "{}, can you confirm whether this is accurate: \"{}\"? Evidence: {}".format(who, claim[:300], evidence)


def preservation_details(rows):
    """Brevity reviewer `preservation` facts as a collapsed table."""
    table = R.preservation_table(rows, untrusted)
    if not table:
        return []
    return ["", "<details><summary>Facts this change must keep ({})</summary>".format(len(rows)), ""] + table + \
        ["", "</details>"]


def plain_block(text):
    """Untrusted suggestion text shown as a plain code block, not a suggestion.
    The fence is longer than any backtick run in the text, so nothing inside can
    close it, and GitLab neither links mentions nor runs quick actions in it."""
    return R.fenced(str(text), "markdown", fence=R.fence_for(text))


def line_label(a):
    where = R.span(a)
    return " ({})".format(where) if where else ""


def conflict_notes(members, by_fp):
    """One line for each conflict (`conflicts_with`) of a finding in this
    comment: a fix that cuts text another fix keeps."""
    out, seen = [], set()
    here = set(m["fingerprint"] for m in members)
    for m in members:
        for fp in m.get("conflicts_with") or []:
            pair = tuple(sorted((m["fingerprint"], fp)))
            other = by_fp.get(fp)
            if pair in seen or other is None:
                continue
            seen.add(pair)
            where = "in this comment" if fp in here else "on{}".format(line_label(other).replace(" (", " ").rstrip(")"))
            out.append("Conflict: `{}` and `{}` ({}) disagree. One cuts text that the other keeps. "
                       "Pick one.".format(untrusted(m["id"]), untrusted(other["id"]), where))
    return ["", "\n".join("- " + o for o in out)] if out else []


def position_for(f, ctx):
    rng = F.line_range(f)
    if f.get("summary_only") is True or not ctx.inline_ok:
        return None
    if rng is None or not ctx.refs.get("head_sha"):
        return None
    info = ctx.files.get(f.get("file"))
    if not info:
        return None
    if rng[0] not in info["positions"]:
        return None
    # A multi-line suggestion needs every line in the diff.
    if f.get("suggestion") is not None and any(n not in info["positions"] for n in range(rng[0], rng[1] + 1)):
        return None
    pos = {"position_type": "text", "base_sha": ctx.refs.get("base_sha"), "start_sha": ctx.refs.get("start_sha"),
           "head_sha": ctx.refs.get("head_sha"), "old_path": info["old_path"] or f["file"], "new_path": f["file"],
           "new_line": rng[0]}
    old_line = info["positions"][rng[0]]
    if old_line is not None:
        pos["old_line"] = old_line
    return pos


IMPORTANCE_LABELS = {5: "Fix first", 4: "Fix first", 3: "Recommended", 2: "Optional", 1: "Optional"}
DEFERRED_TEXT = {"safety-cap": "over the safety cap", "importance-1": "cosmetic (importance 1), kept in the report",
                 "alternative": "alternatives to a more important suggestion"}
DEFERRED_OTHER = "kept in the report"
# The orientation for a first-time docs writer: at most 3 sentences, plain words.
ORIENTATION = ("Thanks for working on the docs. Each comment below says why it matters and links to the rule in "
               "the GitLab documentation style guide. Start with the comments marked **Fix first**, and ask in "
               "the thread if anything is unclear.")
MAX_ALTERNATIVES = 3


def coaching_line(f):
    why = " ".join(untrusted(f.get("why")).split())
    if not why:
        return []
    src = untrusted(f.get("source")) if f.get("source") else ""
    return ["", "Why: {}{}".format(why, " See [the rule]({}).".format(src) if src else "")]


def alternatives_line(members):
    """Other wordings or rules for these lines, one line each, never a second
    suggestion block."""
    alts, here = [], set(m.get("fingerprint") for m in members)
    for m in members:
        for a in m.get("alternatives") or []:
            # A finding already in this comment is not an alternative to it.
            if isinstance(a, dict) and a.get("message") and a.get("fingerprint") not in here \
                    and a.get("reason") != "covered":
                alts.append(a)
    if not alts:
        return []
    out = [""]
    for a in alts[:MAX_ALTERNATIVES]:
        out.append("- Alternative ({}): {}".format(R.code(untrusted(a.get("id"))), " ".join(untrusted(a.get("message")).split())))
    if len(alts) > MAX_ALTERNATIVES:
        out.append("- And {} more in the report.".format(len(alts) - MAX_ALTERNATIVES))
    return out


MAX_ALSO = 12


def repeats_line(f):
    also = [a for a in f.get("_also") or [] if F.line_range(a)]
    if not also:
        return []
    if all(a.get("file") == f.get("file") for a in also):
        return ["", "Also on lines {}.".format(", ".join(str(F.line_range(a)[0]) for a in also))]
    where = [R.code(untrusted("{}:{}".format(a["file"], F.line_range(a)[0]))) for a in also[:MAX_ALSO]]
    more = " and {} more".format(len(also) - MAX_ALSO) if len(also) > MAX_ALSO else ""
    return ["", "Also in {}{}.".format(", ".join(where), more)]


def inline_body(group, mention_lines, by_fp=None, coaching=False):
    """One comment for a position or location group: one suggestion at most, alternatives as one line each, repeats as line
    numbers, and a coaching line for a first-time docs writer."""
    f = group[0]
    parts = [PREFIX, ""]
    parts.append("**{}:** {} (`{}`)".format(IMPORTANCE_LABELS[IMP.level(f)], one_line(f["message"]),
                                           one_line(f["id"])))
    shown = False
    if f.get("suggestion") is not None and f.get("fixable") in ("auto", "suggest"):
        parts += [""] + R.suggestion_block(f["suggestion"], F.line_range(f))
        shown = True
    if coaching and f.get("why"):
        parts += coaching_line(f)
    elif f.get("source"):
        parts += ["", "Source: {}".format(untrusted(f["source"]))]
    parts += preservation_details(f.get("preservation"))
    parts += repeats_line(f)
    primary_rng = F.line_range(f)
    for other in group[1:]:
        rng = F.line_range(other)
        where = " Line {}:".format(rng[0]) if rng and rng != primary_rng else ""
        parts += ["", "**{}:**{} {} (`{}`)".format(IMPORTANCE_LABELS[IMP.level(other)], where,
                                                 one_line(other["message"]), one_line(other["id"]))]
        if other.get("suggestion") is not None and not shown and other.get("fixable") in ("auto", "suggest"):
            parts += ["", "Suggested text:", ""] + plain_block(other["suggestion"])
            shown = True
        if coaching and other.get("why"):
            parts += coaching_line(other)
        parts += repeats_line(other)
    parts += alternatives_line(group)
    parts += conflict_notes(group + [a for g in group for a in g.get("_also") or []], by_fp or {})
    for line in mention_lines:
        parts += ["", line]
    fps = [g["fingerprint"] for g in group] + [a["fingerprint"] for g in group for a in g.get("_also") or []]
    parts += ["", FP_MARKER.format(",".join(fps))]
    return escape_quick_actions("\n".join(parts))


def final_pass_summary(findings, doc, sme_lines):
    """The "For the final human pass" section of the summary note. Existing
    issues are not for this MR, and `deferred` is never posted: only its
    counts appear."""
    current = [f for f in findings if f.get("summary_reason") != "existing"]
    unverified = [f for f in findings if f.get("verdict") == "unverified"]
    left_alone = [x for x in doc.get("left_alone") or [] if isinstance(x, str)][:5]
    return R.final_pass(current, rank, unverified[:MAX_SUMMARY_ITEMS], sme_lines, doc.get("deferred"), DEFERRED_TEXT,
                        left_alone, escape=untrusted, note=True, limit=MAX_SUMMARY_ITEMS, deferred_other=DEFERRED_OTHER)


SUMMARY_SECTIONS = (
    (None, "### Page-level findings and findings outside the diff", None, False),
    ("reader", "### Reader questions", "Lower-importance questions from the first-time-reader pass.", False),
    ("polish", "Optional polish", "Wording ideas without a specific style guide rule. Take them or leave them.",
     True),
    ("generated", "Fix in the generated source",
     "These are in generated blocks. Fix them in the source the block is generated from.", True),
    ("moved", "Questions whose text changed",
     "The text these questions were about changed in the fix commit. Check that the answer still matters.", True),
    ("existing", "Existing issues on this page",
     "These were on the page before this change. They are not blockers for this MR. Fix them here if it is "
     "easy, or in a follow-up.", True),
)


def summary_only_sections(not_inline):
    """The summary-only findings, in sections by `summary_reason`. Optional
    polish and existing issues are collapsed."""
    out = []
    known = set(r for r, _, _, _ in SUMMARY_SECTIONS if r)
    for reason, title, intro, collapsed in SUMMARY_SECTIONS:
        items = [f for f in not_inline if (f.get("summary_reason") if f.get("summary_reason") in known else None)
                 == reason]
        if not items:
            continue
        if collapsed:
            out += ["<details><summary>{} ({})</summary>".format(title, len(items)), ""]
        else:
            out += [title, ""]
        if intro:
            out += [intro, ""]
        for f in sorted(items, key=lambda x: -IMP.level(x))[:MAX_SUMMARY_ITEMS]:
            out.append("- **{}** `{}` in {}: {}".format(IMPORTANCE_LABELS[IMP.level(f)], untrusted(f["id"]),
                                                        R.code(untrusted(R.loc(f))), R.one_line(f["message"], untrusted)))
        if len(items) > MAX_SUMMARY_ITEMS:
            out.append("- And {} more. See the full report in the job output.".format(len(items) - MAX_SUMMARY_ITEMS))
        out.append("")
        if collapsed:
            out += ["</details>", ""]
    return out


MAX_APPLIED_LINES = 40


def applied_section(applied):
    """What the writer step fixed, collapsed: one line for each fix."""
    items = (applied or {}).get("applied") or []
    if not items:
        return []
    out = ["<details><summary>Applied automatically in {} ({})</summary>".format(
        R.code(str(applied.get("head") or "")[:12]), len(items)), ""]
    for a in items[:MAX_APPLIED_LINES]:
        out.append("- `{}` in {}: {}".format(untrusted(a.get("id")), R.code(untrusted(
            "{}:{}".format(a.get("file"), a.get("line")))), R.one_line(a.get("message"), untrusted)))
    if len(items) > MAX_APPLIED_LINES:
        out.append("- And {} more in the job report.".format(len(items) - MAX_APPLIED_LINES))
    out += ["", "</details>", ""]
    wrong = (applied or {}).get("invalid") or []
    if wrong:
        out += ["<details><summary>Not applied: the writer found these findings wrong ({})</summary>".format(len(wrong)), ""]
        out += ["- `{}` in {}: {}".format(untrusted(w.get("id")), R.code(untrusted("{}:{}".format(w.get("file"), w.get("line")))),
                                         R.one_line(w.get("reason"), untrusted)) for w in wrong[:MAX_APPLIED_LINES]]
        out += ["", "</details>", ""]
    return out


def summary_body(findings, posted, not_inline, skipped_dup, skipped_resolved, sme_lines, tier, tw_mention, head,
                 notes=None, deferred=0, doc=None, first_time=False, applied=None):
    doc = doc or {}
    lines = [PREFIX, SUMMARY_MARKER, "", "## Docs review summary", ""]
    if first_time:
        lines += [ORIENTATION, ""]
    if tier in ("high", "severe"):
        ask = "This change is tier **{}**. It needs a review from a human technical writer".format(tier)
        lines += [ask + (", {}.".format(tw_mention) if tw_mention else "."), ""]
    if findings:
        counts = dict((n, 0) for n in (5, 4, 3, 2, 1))
        for f in findings:
            counts[IMP.level(f)] += 1
        cols = [n for n in (5, 4, 3, 2, 1) if counts[n]]
        lines.append("| " + " | ".join("Importance {}".format(n) for n in cols) + " | Total |")
        lines.append("|" + "---|" * (len(cols) + 1))
        lines.append("| " + " | ".join(str(counts[n]) for n in cols) + " | {} |".format(len(findings)))
        lines.append("")
    else:
        lines += ["No findings to post." if deferred else "No findings. Nice work.", ""]
    stats = ["{} new inline comment(s)".format(posted)]
    if skipped_dup:
        stats.append("{} already posted".format(skipped_dup))
    if skipped_resolved:
        stats.append("{} in resolved threads".format(skipped_resolved))
    lines += ["This run: " + ", ".join(stats) + ".", ""]
    for n in notes or []:
        lines += ["- " + untrusted(n)]
    if notes:
        lines.append("")
    lines += applied_section(applied)
    lines += final_pass_summary(findings, doc, sme_lines)
    lines += summary_only_sections(not_inline)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines.append("_Updated {}{}. A rerun updates this note._".format(stamp, " for {}".format(head[:12]) if head else ""))
    return escape_quick_actions("\n".join(lines))


def rank(f):
    return (-IMP.level(f), F.severity_rank(f["severity"]), f["file"], f.get("line") or 0)


def plan_and_post(doc, ctx, writer, args, endpoint_base):
    findings = []
    for f in doc["findings"]:  # only `findings`: `deferred` is never posted
        if isinstance(f, dict):
            f = dict(f)
            F.coerce_finding(f)
        errs = F.validate_finding(f)
        if errs:
            warn("skipping invalid finding {}: {}".format(f.get("id") if isinstance(f, dict) else "?", "; ".join(errs)))
            continue
        f.setdefault("fingerprint", F.fingerprint(f))
        findings.append(f)
    # Never post non-public content: confidential items or private projects
    # that the reviewing account could read (lib/visibility.py).
    vis = ctx.visibility or visibility.Visibility(None)
    gated, withheld = [], False
    for f in findings:
        g, n = visibility.gate(f, vis)
        gated.append(g)
        withheld = withheld or bool(n) or bool(g.get("withheld_internal"))
    findings = gated
    left_alone = []
    for x in doc.get("left_alone") or []:
        y, n = visibility.redact_text(x, vis)
        left_alone.append(y)
        withheld = withheld or bool(n)
    doc = dict(doc, left_alone=left_alone)
    if withheld:
        ctx.notes.append("{} finding(s) rely on internal evidence that is withheld from this comment. A team member "
                         "with access can check them in the job report.".format(
                             sum(1 for f in findings if f.get("withheld_internal"))))
    target = doc.get("target") or {}
    first_time = bool(target.get("first_time_writer"))
    findings.sort(key=rank)

    tier = target.get("tier")
    budget = MentionBudget([ctx.author or target.get("author"), ctx.me], 0 if args.no_mentions else MAX_MENTIONS)
    tw = args.tw or target.get("technical_writer")
    tw_mention = None
    if tier == "severe" and tw:
        # Severe: a technical writer review is required, so mention them.
        picked = budget.take([tw.lstrip("@")], limit=1)
        tw_mention = "@" + picked[0] if picked else R.code(untrusted(tw.lstrip("@")))
    elif tier == "high" and tw:
        # High: name the writer without a notification (triage.md).
        tw_mention = R.code(untrusted(tw.lstrip("@")))

    skipped_dup = skipped_resolved = posted = 0
    not_inline, sme_lines = [], []
    cap = args.safety_cap
    if cap is None:
        stat_cap = (doc.get("stats") or {}).get("safety_cap", DEFAULT_SAFETY_CAP)
        cap = stat_cap if isinstance(stat_cap, int) and stat_cap > 0 else DEFAULT_SAFETY_CAP
    inline_left = 0 if args.summary_only else cap
    by_fp = dict((f["fingerprint"], f) for f in findings)
    pending = []
    still_open = 0
    for f in findings:
        if f["fingerprint"] in ctx.fps:
            if f["fingerprint"] in ctx.resolved_fps:
                skipped_resolved += 1
            else:
                skipped_dup += 1
            continue
        t = thread_for(f, ctx.threads) if f.get("summary_only") is not True else None
        if t is not None:
            # The same point in other words: its thread already says it.
            if t["resolved"]:
                skipped_resolved += 1
            else:
                still_open += 1
            continue
        pending.append(f)
    # One question asked on many pages is one comment: the answer is the same.
    for f in pending:
        if not f.get("group") and F.needs_input(f) and f.get("summary_only") is not True:
            core = str(f.get("message") or "").split(" Not applied automatically:", 1)[0]
            f["group"] = "input:" + (f.get("occurrence_root") or "{}:{}".format(
                f["id"], " ".join(core.lower().split())[:200]))
    # Repeats of one rule (merge `group`) are one comment on their first line.
    carriers, first = [], {}
    for f in sorted(pending, key=lambda x: (x.get("group") or "", x["file"], x.get("line") or 0)):
        g = f.get("group")
        if g and g in first and f.get("summary_only") is not True:
            first[g].setdefault("_also", []).append(f)
            continue
        if g:
            first[g] = f
        carriers.append(f)
    carriers.sort(key=rank)

    def unpack(f):
        return [f] + list(f.get("_also") or [])

    groups, order = {}, []  # comment key -> [(finding, position, mention line)]
    for f in carriers:
        mention_line = None
        for m in unpack(f):
            if mention_eligible(m) and m.get("sme"):
                people = budget.take([s.get("username") for s in m["sme"] if isinstance(s, dict)])
                if people:
                    line = sme_question(m, people)
                    mention_line = line if mention_line is None else mention_line + "\n\n" + line
        # Findings in one location group (merge `spot`) share one comment.
        skey = ("spot", f["file"], f["spot"]) if f.get("spot") and f.get("summary_only") is not True else None
        if skey in groups:
            pos = position_for(f, ctx)
            entry = (f, pos, mention_line)
            if f["fingerprint"][:12] == f["spot"] and pos is not None:
                groups[skey].insert(0, entry)  # the location group's owner leads the comment
            else:
                groups[skey].append(entry)
            continue
        pos = position_for(f, ctx) if (inline_left > 0 or groups) else None
        key = skey or ((pos["new_path"], pos["new_line"]) if pos else None)
        if pos is None or (key not in groups and len(order) >= inline_left):
            not_inline.extend(unpack(f))
            if mention_line:
                sme_lines.append(mention_line)
            continue
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append((f, pos, mention_line))

    folded = 0
    for key in order:
        group = groups[key]
        primary, pos, _ = group[0]
        members = [primary] + [g[0] for g in group[1:]]
        folded += sum(len(unpack(m)) for m in members) - 1
        mentions = [g[2] for g in group if g[2]]
        body = {"body": inline_body(members, mentions, by_fp, first_time), "position": pos}
        label = "inline {} {}:{}".format("+".join(m["id"] for m in members), primary["file"], primary["line"])
        try:
            writer.write("POST", endpoint_base + "/discussions", body, label)
            posted += 1
        except gitlab_api.GlabError as exc:
            warn("inline comment for {} {}:{} failed, moving it to the summary: {}".format(
                primary["id"], primary["file"], primary["line"], str(exc)[:160]))
            writer.planned.pop()
            for m in members:
                not_inline.extend(unpack(m))
            sme_lines.extend(mentions)

    head = ctx.refs.get("head_sha") or args.head_sha or ""
    resolved_now = resolve_fixed(ctx, writer, endpoint_base, findings, args.applied_doc, head) \
        if args.applied_doc is not None else []
    if still_open:
        ctx.notes.append("{} earlier comment(s) still apply. They stay in their threads.".format(still_open))
    if resolved_now:
        ctx.notes.append("Resolved {} earlier comment(s) that are fixed.".format(len(resolved_now)))
    deferred = len(doc.get("deferred") or [])
    body = summary_body(findings, posted, not_inline, skipped_dup, skipped_resolved, sme_lines, tier, tw_mention,
                        head, ctx.notes, deferred, doc, first_time, args.applied_doc)
    if ctx.summary_note and ctx.summary_note.get("id"):
        writer.write("PUT", "{}/notes/{}".format(endpoint_base, ctx.summary_note["id"]), {"body": body}, "update summary")
    else:
        writer.write("POST", endpoint_base + "/notes", {"body": body}, "create summary")
    return {"inline": posted, "folded": folded, "deferred_not_posted": deferred, "skipped_duplicate": skipped_dup,
            "skipped_resolved": skipped_resolved, "mentions": budget.people, "version": ctx.version,
            "notes": ctx.notes, "summary_action": "update" if ctx.summary_note else "create",
            "still_open": still_open, "resolved": resolved_now}


def write_out(out_dir, writer, result, ctx):
    os.makedirs(os.path.join(out_dir, "payloads"), exist_ok=True)
    for i, p in enumerate(writer.planned, 1):
        with open(os.path.join(out_dir, "payloads", "{:03d}.json".format(i)), "w", encoding="utf-8") as fh:
            json.dump(p, fh, indent=2)
            fh.write("\n")
    with open(os.path.join(out_dir, "preview.md"), "w", encoding="utf-8") as fh:
        fh.write(render_preview(writer, result, ctx))


def render_preview(writer, result, ctx):
    lines = ["# Docs review: posting preview", ""]
    lines.append("- Inline comments: {} ({} finding(s) folded into a comment on the same line)".format(
        result["inline"], result.get("folded", 0)))
    lines.append("- Diff version: {}".format(result.get("version") or "latest"))
    if result.get("deferred_not_posted"):
        lines.append("- Deferred findings (report only, not posted): {}".format(result["deferred_not_posted"]))
    for n in result.get("notes") or []:
        lines.append("- Note: {}".format(n))
    lines.append("- Summary note: {}".format(result["summary_action"]))
    lines.append("- Skipped (already posted): {}".format(result["skipped_duplicate"]))
    lines.append("- Skipped (resolved threads): {}".format(result["skipped_resolved"]))
    lines.append("- Mentions: {}".format(", ".join(result["mentions"]) or "none"))
    for e in ctx.read_errors:
        lines.append("- Read error (dry-run continued): {}".format(e))
    lines.append("")
    for p in writer.planned:
        lines.append("## {} {} ({})".format(p["method"], p["endpoint"], p["label"]))
        if p["body"].get("position"):
            pos = p["body"]["position"]
            lines.append("")
            lines.append("Position: `{}` line {}".format(pos["new_path"], pos["new_line"]))
        lines.append("")
        lines += R.fenced(p["body"]["body"], "markdown") + [""]
    return "\n".join(lines)


def parse_args(argv):
    p = argparse.ArgumentParser(
        description="Post docs-review findings to a GitLab MR (summary note + inline suggestions), or preview them.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Exit codes: 0 no blocker, 1 blockers found, 2 usage, environment, or API error.")
    p.add_argument("findings", nargs="?", help="combined findings.json from combine_findings.py (or "
                                               "remaining.json from collect_writers.py)")
    p.add_argument("--project", required=True, help="project path, such as group/project")
    p.add_argument("--mr", required=True, type=int, help="merge request IID")
    p.add_argument("--mode", choices=("interactive", "auto"), help="default: $DOCS_REVIEW_MODE or interactive")
    p.add_argument("--no-mentions", action="store_true", help="name people in backticks; mention nobody "
                                                          "(test copies of real MRs)")
    p.add_argument("--dry-run", action="store_true", help="write payloads and preview.md; never call a write API")
    p.add_argument("--yes", action="store_true", help="interactive mode: post after the user approved the preview")
    p.add_argument("--out", help="output directory for payloads and preview.md (required with --dry-run)")
    p.add_argument("--safety-cap", type=int,
                   help="most inline comments per run (default: stats.safety_cap in findings.json, else {})".format(
                       DEFAULT_SAFETY_CAP))
    p.add_argument("--summary-only", action="store_true", help="post only the summary note")
    p.add_argument("--tw", help="technical writer for tier high or severe (default: target.technical_writer)")
    p.add_argument("--head-sha", help="reviewed head commit; inline positions use the MR diff version with this "
                                      "head (default: target.head in findings.json)")
    p.add_argument("--applied", help="applied.json from collect_writers.py: list the fixes, resolve the threads "
                                     "they fix, and post only what is left")
    p.add_argument("--list-open", metavar="FILE", help="write our open threads as JSON (for the reviewers) and exit; "
                                                       "read-only")
    p.add_argument("--glab", default=None, help="glab binary (default: $DOCS_REVIEW_GLAB or glab)")
    args = p.parse_args(argv)
    args.applied_doc = None
    if args.applied:
        with open(args.applied, encoding="utf-8") as fh:
            args.applied_doc = json.load(fh)
    return args


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    mode = args.mode or os.environ.get("DOCS_REVIEW_MODE") or "interactive"
    if mode not in ("interactive", "auto"):
        warn("DOCS_REVIEW_MODE must be interactive or auto")
        return 2
    if args.list_open:
        api = gitlab_api.GitLab(args.glab)
        try:
            ctx = load_context(api, args.project, args.mr, True)
        except gitlab_api.GlabError as exc:
            warn(str(exc))
            return 2
        rows = [{"file": t["file"], "line": t["line"], "ids": t["ids"], "message": t["message"], "outdated": t["outdated"],
                 "human_reply": t["human"]} for t in open_threads(ctx)]
        with open(args.list_open, "w", encoding="utf-8") as fh:
            json.dump({"open_threads": rows}, fh, indent=2)
        sys.stdout.write("{} open thread(s) written to {}\n".format(len(rows), args.list_open))
        return 0
    if not args.findings:
        warn("give the findings file, or --list-open FILE")
        return 2
    if args.dry_run and not args.out:
        warn("--dry-run needs --out DIR")
        return 2
    if args.safety_cap is not None and args.safety_cap < 0:
        warn("--safety-cap must be 0 or more")
        return 2
    try:
        doc = F.load_doc(args.findings)
    except (OSError, ValueError) as exc:
        warn(str(exc))
        return 2
    blockers = F.has_blocker(doc["findings"])
    if not args.head_sha:
        head = str((doc.get("target") or {}).get("head") or "")
        args.head_sha = head if SHA_RE.match(head.lower()) else None
    preview_only = mode == "interactive" and not args.yes and not args.dry_run
    dry = args.dry_run or preview_only
    api = gitlab_api.GitLab(args.glab)
    try:
        ctx = load_context(api, args.project, args.mr, dry, args.head_sha)
    except gitlab_api.GlabError as exc:
        warn(str(exc))
        return 2
    project_path = ctx.project_path or (args.project if "/" in str(args.project) else None)
    ctx.visibility = visibility.Visibility(api, project_path)
    if ctx.positions_error and not args.summary_only:
        # Never move every finding to the summary without saying so.
        bar = "!" * 72
        warn("\n{}\nNO INLINE POSITIONS: {}.\nNothing was posted. Rerun with --summary-only to post only the "
             "summary.\n{}".format(bar, ctx.positions_error, bar))
        return 2
    if not dry and ctx.state in ("merged", "closed"):
        warn("MR !{} is {}; not posting".format(args.mr, ctx.state))
        return 1 if blockers else 0
    writer = SafeWriter(api, dry, ctx.visibility, [t["id"] for t in ctx.threads if not t["human"]])
    endpoint_base = "projects/{}/merge_requests/{}".format(gitlab_api.enc(args.project), args.mr)
    try:
        result = plan_and_post(doc, ctx, writer, args, endpoint_base)
    except GuardrailError as exc:
        warn("guardrail: {}".format(exc))
        return 2
    except gitlab_api.GlabError as exc:
        warn(str(exc))
        return 2
    if args.out:
        write_out(args.out, writer, result, ctx)
    if preview_only:
        sys.stdout.write(render_preview(writer, result, ctx))
        sys.stdout.write("\nNothing was posted. Review the text above, then rerun with --yes to post.\n")
    else:
        verb = "would post" if dry else "posted"
        sys.stdout.write("{} {} inline comment(s) and {} the summary note; skipped {} duplicate(s), {} resolved; "
                         "mentions: {}\n".format(verb, result["inline"], ("would " if dry else "") + result["summary_action"]
                                                 + ("" if dry else "d"), result["skipped_duplicate"],
                                                 result["skipped_resolved"], ", ".join(result["mentions"]) or "none"))
        if args.dry_run:
            sys.stdout.write("payloads and preview.md written to {}\n".format(args.out))
    return 1 if blockers else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, UnicodeError, ValueError, RuntimeError) as exc:  # a one-line error, not a traceback
        if os.environ.get("DOCS_REVIEW_DEBUG"):
            raise
        sys.stderr.write("{}: error: {}\n".format(sys.argv[0].rsplit("/", 1)[-1], exc))
        sys.exit(2)
