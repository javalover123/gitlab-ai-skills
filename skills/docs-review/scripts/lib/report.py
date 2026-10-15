"""Markdown pieces that report.md (combine_findings.py) and the MR summary
note and inline comments (post_review.py) share.

Every function that renders finding text takes `escape`: post_review.py
passes its `untrusted()` neutralizer, combine_findings.py the identity.

Python 3.9+, stdlib only.
"""

import re

from . import findings as F
from . import importance as IMP



def code(text):
    """`text` as a Markdown code span that its own backticks cannot close."""
    text = str(text if text is not None else "")
    ticks = max((len(m) for m in re.findall(r"`+", text)), default=0) + 1
    pad = " " if text.startswith("`") or text.endswith("`") else ""
    return "`" * ticks + pad + text + pad + "`" * ticks

def same(text):
    """The identity `escape`, for text that stays in the job report."""
    return "" if text is None else str(text)


def one_line(text, escape=same):
    """Escaped text with every run of whitespace, newlines included, as one space."""
    return " ".join(escape(text).split())


def fence_for(text):
    """A backtick fence longer than any backtick run in the text."""
    runs = [len(r) for r in re.findall(r"`{3,}", text or "")]
    return "`" * max([3] + [n + 1 for n in runs])


def fenced(text, info="", indent="", fence=None):
    """`text` in a fenced block with `info` after the opening fence. Each line
    gets `indent`; blank lines stay blank."""
    fence = fence or fence_for(text)
    body = [indent + line if line else "" for line in (text or "").split("\n")]
    return [indent + fence + info] + body + [indent + fence]


def suggestion_block(text, rng, indent=""):
    """A GitLab ```suggestion:-0+N block that replaces the lines in `rng`."""
    return fenced(text, "suggestion:-0+{}".format(rng[1] - rng[0]), indent)


def span(f):
    """`line 3` or `lines 3-5`, or "" when the finding has no line."""
    rng = F.line_range(f)
    if not rng:
        return ""
    return "line {}".format(rng[0]) if rng[0] == rng[1] else "lines {}-{}".format(*rng)


def loc(f):
    """`file`, `file:3`, or `file:3-5`."""
    rng = F.line_range(f)
    if not rng:
        return f["file"]
    return "{}:{}".format(f["file"], rng[0]) if rng[0] == rng[1] else "{}:{}-{}".format(f["file"], *rng)


def cell(text, escape=same):
    """Text safe in one Markdown table cell."""
    return escape(text).replace("|", "\\|").replace("\n", " ")


def preservation_table(rows, escape=same, indent=""):
    """The editor's `preservation` facts (what a cut must keep) as table
    lines, or [] when there are none."""
    if not isinstance(rows, list) or not rows:
        return []
    out = [indent + "| Fact | Status | Where |", indent + "|---|---|---|"]
    for r in rows:
        cells = [r.get("fact"), r.get("status"), r.get("where")] if isinstance(r, dict) else [r, "", ""]
        out.append(indent + "| " + " | ".join(cell(c, escape) for c in cells) + " |")
    return out


def final_pass(findings, key, unverified, sme_lines, deferred, deferred_text, left_alone, tasks=(),
               escape=same, note=False, limit=None, deferred_other=None):
    """The "For the final human pass" section.

    - Fix first: `findings` of importance 4 and 5 sorted by `key`, one per
      merge group; at most `limit`. The caller leaves out what must not be
      listed (the note leaves out existing issues).
    - Unverified facts, questions for subject matter experts, and the reader
      walk-through (`tasks`), each when there is any. The caller picks and
      caps `unverified` and builds `sme_lines`, which are not escaped: the
      note's lines carry the mentions that its budget allowed.
    - Left alone on purpose: `deferred` counted by `deferred_text` (unknown
      reasons as `deferred_other`, else the reason), then `left_alone`.

    `note` renders for the MR summary note: an h3 title, bold labels, and
    `loc: message` items. Otherwise h2 and h3 for report.md, and items with
    importance, rule id, and the group size."""
    if note:
        out = ["### For the final human pass", ""]

        def sub(title):
            return ["**{}:**".format(title), ""]
    else:
        out = ["## For the final human pass", ""]

        def sub(title):
            return ["### " + title, ""]

    top, seen, same, files = [], set(), {}, {}
    for f in sorted(findings, key=key):
        if IMP.level(f) < 4:
            continue
        g = f.get("group")
        if g and g in seen:
            continue
        if g:
            seen.add(g)
        point = (f.get("id"), " ".join((f.get("message") or "").split()))
        if point in same:  # the same point in another file: count it, list it once
            files[point].add(f.get("file"))
            continue
        same[point], files[point] = f, {f.get("file")}
        top.append(f)
    out += sub("Fix first (importance 4 and 5)")
    for f in top[:limit]:
        point = (f.get("id"), " ".join((f.get("message") or "").split()))
        others = len(files[point]) - 1
        elsewhere = " (also in {} more file{})".format(others, "" if others == 1 else "s") if others else ""
        if note:
            out.append("- {}: {}{}".format(code(escape(loc(f))), one_line(f["message"], escape), elsewhere))
        else:
            more = " (and {} more lines)".format(f["group_size"] - 1) if f.get("group") else ""
            out.append("- **{}** {} ({}): {}{}{}".format(IMP.level(f), code(escape(f["id"])), code(escape(loc(f))),
                                                           one_line(f["message"], escape), more, elsewhere))
    if not top:
        out.append("- None.")
    out.append("")
    if unverified:
        out += sub("Unverified facts")
        out += ["- {}: {}".format(code(escape(loc(f))), one_line(f["message"], escape)) for f in unverified] + [""]
    if sme_lines:
        out += sub("Questions for subject matter experts") + ["- " + s for s in sme_lines] + [""]
    tasks = [t for t in tasks or [] if isinstance(t, dict)]
    if tasks:
        out += sub("Reader walk-through")
        for t in tasks:
            stuck = " Stuck at line {}.".format(t["stuck_at"]) if isinstance(t.get("stuck_at"), int) else ""
            out.append("- {}: {}.{}".format(code(escape(t.get("task") or t.get("heading") or "?")),
                                             escape(t.get("result") or "?"), stuck))
        out.append("")
    reasons = {}
    for f in deferred or []:
        if isinstance(f, dict):
            r = f.get("deferred_reason")
            text = deferred_text.get(r, str(r) if deferred_other is None else deferred_other)
            reasons[text] = reasons.get(text, 0) + 1
    left = ["{} finding(s) {}.".format(n, r) for r, n in sorted(reasons.items())]
    left += [one_line(x, escape) for x in left_alone or [] if isinstance(x, str)]
    out += sub("Left alone on purpose") + (["- " + x for x in left] if left else ["- Nothing."]) + [""]
    return out
