#!/usr/bin/env python3
"""Combine docs-review findings from scripts and reviewers into one set and a report.

Validates findings, keeps those about the change (the diff comes from --diff
or from triage.json), calibrates severity and importance, dedupes across
reviewers, groups them into comments, and writes findings.json and report.md.
The full pipeline is in the dev repo: dev/docs/combine-pipeline.md.

Python 3.9+, stdlib only.

Exit codes: 0 no blocker, 1 blockers found, 2 usage error (bad input file).

Example:
  combine_findings.py lint.json impact.json reviewers/*.json --triage triage.json --out-dir out/
"""

import argparse
import difflib
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from lib import findings as F  # noqa: E402
from lib import gitdiff  # noqa: E402
from lib import importance as IMP  # noqa: E402
from lib import lint_config  # noqa: E402
from lib import report as R  # noqa: E402
import triage  # noqa: E402  (shares the formatting classifier with triage)

NON_PUBLIC_REF = "a non-public project"

# Reviewers whose blockers survive calibration even when a model emitted them.
# Script reviewers are listed too, in case a script forgets `deterministic`.
REVIEWERS = ("editor", "facts", "reader")
BLOCKER_REVIEWERS = ("impact", "facts", "lint", "vale", "markdownlint", "docs-preview")
# Findings about content that left the page (or the rendered site) are kept by
# the changed-lines filter, like impact and facts findings.
KEEP_UNCHANGED_IDS = ("lint.vale-rule-disabled",)
KEEP_UNCHANGED_EXTRA_REVIEWERS = ("docs-preview",)
CONF_RANK = {"high": 0, "medium": 1, "low": 2}
CONFIG_NAME = ".docs-review.yml"

# Quotes count as the same text when one contains the other, or when this
# share of the shorter quote's tokens is in the other one.
QUOTE_TOKEN_OVERLAP = 0.8
MIN_QUOTE_CHARS = 4
MIN_QUOTE_TOKENS = 3
# A fix deletes text when it drops at least this share of the quote's words.
# A finding conflicts with a cut when this share of its quote's words is cut.
CUT_SHARE = 0.5
# Findings whose lines overlap share one posted comment (a location group),
# unless one spans more lines than this.
SPOT_MAX_SPAN = 6

UI_NAV_KEYS = ("uinavigation", "navigation", "uitext", "uilabelmatch", "navigationpath")
UI_NAV_FAMILIES = ("lint", "vale")
PRODUCT_KEYS = ("productname", "productnames", "featurename", "offerings", "branding")
PRODUCT_FAMILIES = ("vale", "lint")
# Rules that ask the writer to define a term or an acronym on first use.
DEFINITION_KEYS = ("acronyms", "acronym", "undefinedterm", "undefinedacronym", "defineterm")
LINK_KEYS = ("brokenlink", "brokenanchor", "linkbroken", "anchorbroken")
LINK_FAMILIES = ("lint", "impact", "docs-preview")

# Rules whose findings each state a different problem under one generic id
# (`facts.behavior`). Their repeats form one unit only when the message or
# the fix is the same.
CLAIM_FAMILIES = ("facts", "impact", "reader")
CLAIM_IDS = ("editor.consistency.contradiction",)
VALE_WORD_RULE = re.compile(r"(Substitution|Spelling|Wordy|Simplicity|LatinTerms)", re.I)

# At most this many posted comments per run: a runaway alarm, not a target.
DEFAULT_SAFETY_CAP = 50
# For an author who is not a first-time writer, reader findings below this
# importance go to the summary instead of inline. In replays, these were half
# debatable and rarely matched a technical writer comment; for first-time
# writers the reader keeps its full inline share.
READER_INLINE_MIN_IMPORTANCE = 4
# Scope (references/findings-schema.md#scope). `introduced`: on a changed line.
# `broken`: on an unchanged line the change made wrong; the finding names the
# changed line in `caused_by_line`, or it comes from a check that only finds
# breakage (impact, facts.impact). `existing`: anything else; it goes in the
# summary's "Existing issues" list, never inline, never a blocker.
SCOPE_BROKEN_FAMILIES = ("impact",)
SCOPE_BROKEN_PREFIXES = ("facts.impact.", "lint.anchor", "lint.redirect")
HEADING_RE = re.compile(r"^(#{1,6})\s")
# Findings this close (in lines) to a kept comment that make the same point
# join it.
ADJACENT_LINES = 2
ADJACENT_MESSAGE_OVERLAP = 0.6

FENCE_RE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")


def warn(msg):
    sys.stderr.write("combine_findings: {}\n".format(msg))


# ---------------------------------------------------------------- diff


def diff_from_git(repo, spec):
    base, head, dots = gitdiff.split_range(spec)
    try:
        return gitdiff.run(repo, ["diff", "-U0", "-M", base + dots + head]).stdout
    except gitdiff.GitError as exc:
        raise ValueError(str(exc))


def heading_sections(text):
    """{heading line: last line of its section}, outside code fences. A
    section ends before the next heading of the same or a higher level."""
    lines = (text or "").split("\n")
    heads, fence = [], None
    for i, line in enumerate(lines, 1):
        m = FENCE_RE.match(line)
        if fence:
            if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence):
                fence = None
            continue
        if m:
            fence = m.group(1)
            continue
        h = HEADING_RE.match(line)
        if h:
            heads.append((i, len(h.group(1))))
    out = {}
    for idx, (line, level) in enumerate(heads):
        end = len(lines)
        for nline, nlevel in heads[idx + 1:]:
            if nlevel <= level:
                end = nline - 1
                break
        out[line] = end
    return out


class HeadText(object):
    """Reads files at the reviewed head, for heading sections. Uses
    `git show <head>:<path>` when a head revision is known, else the file in
    the checkout. Missing files return None."""

    def __init__(self, repo, head_rev):
        self.repo = repo
        self.head_rev = head_rev
        self.cache = {}
        self.texts = {}

    def text(self, path):
        if path not in self.texts:
            text = None
            if self.head_rev:
                try:
                    proc = gitdiff.run(self.repo, ["show", "{}:{}".format(self.head_rev, path)], check=False)
                except gitdiff.GitError:
                    proc = None
                if proc is not None and proc.returncode == 0:
                    text = proc.stdout
            if text is None:
                full = os.path.join(self.repo, path)
                if os.path.isfile(full):
                    with open(full, encoding="utf-8", errors="replace") as fh:
                        text = fh.read()
            self.texts[path] = text
        return self.texts[path]

    def lines(self, path, rng):
        """The head text of lines rng[0]..rng[1], or None."""
        text = self.text(path)
        if text is None:
            return None
        lines = text.split("\n")
        if rng[1] > len(lines):
            return None
        return "\n".join(lines[rng[0] - 1:rng[1]])

    def sections(self, path):
        if path not in self.cache:
            text = self.text(path)
            self.cache[path] = heading_sections(text) if text is not None else {}
        return self.cache[path]


def formatting_lines(text):
    """{new_path: set(new-side lines)} in hunks that only rewrap or reindent
    text, with the classifier triage.py uses for `formatting`."""
    out = {}
    for fd in triage.parse_unified_diff(text):
        for removed, added in fd.groups:
            if added and triage.is_formatting_only([t for _, t in removed], [t for _, t in added]):
                out.setdefault(fd.new_path, set()).update(n for n, _ in added)
    return out


def exempt_from_line_filter(f):
    if f.get("reviewer") in F.KEEP_UNCHANGED_REVIEWERS or F.rule_family(f.get("id")) in F.KEEP_UNCHANGED_REVIEWERS:
        return True
    return f.get("id") in KEEP_UNCHANGED_IDS or f.get("reviewer") in KEEP_UNCHANGED_EXTRA_REVIEWERS


def touches_change(f, changed, head_text=None):
    """True when the finding's lines, or its page for a page-level finding,
    are in the change. No reviewer exemptions (on_changed_lines adds them)."""
    lines = changed.get(f.get("file"), "missing")
    if lines == "missing":
        return False
    if lines is None:
        return True
    rng = F.line_range(f)
    if rng is None or f.get("scope") == "page":
        return True  # a page-level finding on a changed page
    if any(n in lines for n in range(rng[0], rng[1] + 1)):
        return True
    # A heading line counts as changed when any line of its section changed:
    # a TW comments on the heading to cut or retitle the topic.
    sections = head_text.sections(f["file"]) if head_text is not None else {}
    for n in range(rng[0], rng[1] + 1):
        end = sections.get(n)
        if end is not None and any(m in lines for m in range(n + 1, end + 1)):
            return True
    return False


def on_changed_lines(f, changed, head_text=None):
    """True when the finding is on a changed line. `summary_only` findings
    are checked like the others when they have a line: a page-level note
    anchored on an unchanged intro is not about this change."""
    if exempt_from_line_filter(f):
        return True
    cause = f.get("caused_by_line")
    if isinstance(cause, int) and not isinstance(cause, bool):
        cause_lines = changed.get(f.get("caused_by_file") or f.get("file"), "missing")
        if cause_lines != "missing" and (cause_lines is None or cause in cause_lines):
            return True  # an unchanged line that the change made wrong
    return touches_change(f, changed, head_text)


# ---------------------------------------------------------------- merge

class Inputs(object):
    def __init__(self):
        self.findings, self.praise, self.dropped, self.targets = [], [], [], []
        self.phases, self.verified, self.statuses, self.coerced = [], [], [], []
        self.left_alone = []  # what the reviewers chose not to flag
        self.tasks = []  # the tasks the reader walked


def load_inputs(paths):
    """Read and validate every input file. Returns an Inputs object."""
    res = Inputs()
    findings, praise, dropped, targets, phases, verified = (res.findings, res.praise, res.dropped, res.targets,
                                                            res.phases, res.verified)
    for path in paths:
        try:
            doc = F.load_doc(path)
        except (OSError, ValueError) as exc:
            raise ValueError(str(exc))
        status_errs = F.validate_status(doc)
        for e in status_errs:
            warn("{}: {}".format(path, e))
        if "status" in doc or doc.get("reviewer"):
            res.statuses.append({"source": path, "reviewer": doc.get("reviewer"), "status": doc.get("status"),
                                 "notes": doc.get("notes") or "", "valid": not status_errs})
        targets.append(doc.get("target") or {})
        for p in doc.get("praise") or []:
            if isinstance(p, str) and p.strip() and p.strip() not in praise:
                praise.append(p.strip())
        for v in doc.get("verified") or []:
            if v and v not in verified:
                verified.append(v)
        for x in doc.get("left_alone") or []:
            if isinstance(x, str) and x.strip() and x.strip() not in res.left_alone:
                res.left_alone.append("{}: {}".format(doc.get("reviewer") or "reviewer", x.strip())
                                      if doc.get("reviewer") else x.strip())
        for t in doc.get("tasks") or []:
            if isinstance(t, dict):
                res.tasks.append(t)
        for ph in doc.get("phases") or []:
            if isinstance(ph, str):
                phases.append(ph)
        for i, f in enumerate(doc["findings"]):
            if isinstance(f, dict):
                f = dict(f)
                for note in F.coerce_finding(f):
                    res.coerced.append({"source": path, "index": i, "id": f.get("id"), "note": note})
                    warn("coerced {} #{} ({}): {}".format(path, i, f.get("id") or "no id", note))
            errs = F.validate_finding(f)
            if errs:
                dropped.append({"source": path, "index": i, "id": f.get("id") if isinstance(f, dict) else None,
                                "errors": errs})
                continue
            f = dict(f)
            f.setdefault("line", None)
            f.setdefault("end_line", f.get("line"))
            f.setdefault("quote", None)
            f.setdefault("suggestion", None)
            f.setdefault("source", None)
            f.setdefault("deterministic", False)
            f["_input"] = path
            findings.append(f)
    return res


def overlaps(a, b):
    ra, rb = F.line_range(a), F.line_range(b)
    if ra is None or rb is None:
        return ra is None and rb is None
    return ra[0] <= rb[1] and rb[0] <= ra[1]


def same_rule(a, b):
    """The same rule: the same id, or the same normalized rule name in the
    same reviewer family, or the same word in a word rule and a rule named
    after it (`lint.word-list.utilize`, `vale.gitlab_base.Utilize`). Generic
    names in different families (`editor.duplicate`, `reader.duplicate`) are
    different rules."""
    if a["id"] == b["id"]:
        return True
    ka, kb = F.rule_key(a["id"]), F.rule_key(b["id"])
    if not ka or ka != kb:
        return False
    return F.rule_family(a["id"]) == F.rule_family(b["id"]) or _is_word_rule(a["id"]) or _is_word_rule(b["id"])


def _norm(text):
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def _tokens(text):
    return set(re.findall(r"[a-z0-9]+", (text or "").lower()))


def quotes_overlap(a, b):
    """One quote contains the other, or most of the shorter one's tokens are
    in the other. Very short quotes (`---`, one word under 4 characters)
    never match on containment alone. Two short quotes (fewer than
    MIN_QUOTE_TOKENS tokens, such as a flagged term) overlap when they share
    a word of 3 or more characters: `normal activity` and `Baseline normal`."""
    qa = " ".join((a.get("quote") or "").split())
    qb = " ".join((b.get("quote") or "").split())
    if not qa or not qb:
        return False
    if qa.lower() == qb.lower():
        return True
    short, long_ = sorted((qa, qb), key=len)
    if len(short.replace(" ", "")) >= MIN_QUOTE_CHARS and short in long_:
        return True
    ta, tb = _tokens(qa), _tokens(qb)
    if min(len(ta), len(tb)) < MIN_QUOTE_TOKENS:
        return any(len(t) >= 3 for t in ta & tb)
    return len(ta & tb) / float(min(len(ta), len(tb))) >= QUOTE_TOKEN_OVERLAP


def _is_word_rule(rid):
    return rid.startswith("lint.word-list") or (F.rule_family(rid) == "vale" and bool(VALE_WORD_RULE.search(rid)))


def rule_class(f):
    """Explicit equivalence group of a rule across reviewers, or None. Only
    rules in one group (or the same rule) can fold into one finding."""
    rid = f.get("id") or ""
    fam, key = F.rule_family(rid), F.rule_key(rid)
    if rid == "lint.redirect-target-missing" or (
            rid == "impact.broken-link" and (f.get("quote") or "").lstrip().startswith("redirect_to:")):
        return "redirect-target"
    if f.get("word_list_rule") == "W1":
        return "product-name"
    if key in DEFINITION_KEYS:
        return "definition"
    if fam in PRODUCT_FAMILIES and (key in PRODUCT_KEYS or (_is_word_rule(rid) and fam != "vale"
                                                            and key.startswith("gitlab") and len(key) > 6)):
        return "product-name"
    if fam in UI_NAV_FAMILIES and key in UI_NAV_KEYS:
        return "ui-navigation"
    if fam in LINK_FAMILIES and key in LINK_KEYS:
        return "broken-link"
    if _is_word_rule(rid):
        return "word"
    return None


def word_terms(f):
    """Normalized terms a word rule is about: the last id segment for word-list
    rules (`lint.word-list.i-3` -> `i`), quoted words in a Vale message."""
    rid = f.get("id") or ""
    if F.rule_family(rid) == "vale":
        terms = re.findall(r"'([^'\n]{1,40})'|\"([^\"\n]{1,40})\"", f.get("message") or "")
        return set(_norm(a or b) for a, b in terms if _norm(a or b))
    last = re.sub(r"-\d+$", "", rid.rsplit(".", 1)[-1])
    return set([_norm(last)]) if _norm(last) else set()


def equivalent_rules(a, b):
    ca, cb = rule_class(a), rule_class(b)
    if ca is None or ca != cb:
        return False
    if ca != "word":
        return True
    ta, tb = word_terms(a), word_terms(b)
    for x in ta:
        for y in tb:
            if x == y or (min(len(x), len(y)) >= 3 and (x in y or y in x)):
                return True
    return False


def _words(text):
    """Content words (3 or more characters) of a text, for the cut check."""
    return set(t for t in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(t) >= 3)


def cut_words(f):
    """The words a finding's fix deletes, or None when the fix keeps the
    text. A fix deletes when the suggestion is empty; when it drops at least
    CUT_SHARE of the quote's words and is less than half as long (a word
    swap or a rewrite is not a cut)."""
    quote = _words(f.get("quote"))
    sugg = f.get("suggestion")
    if sugg is None:
        return None
    if not sugg.strip():
        return quote or set(["<all>"])
    if not quote:
        return None
    after = _words(sugg)
    removed = quote - after
    if len(removed) >= CUT_SHARE * len(quote) and len(after) < (1 - CUT_SHARE) * len(quote):
        return removed
    return None


def conflict(a, b):
    """True when one finding's fix deletes the text that the other finding's
    fix keeps (for example, a cut of lines 15-19 and a request to spell out
    an acronym on line 16). Such findings never fold; both get
    `conflicts_with`."""
    if a["file"] != b["file"] or not overlaps(a, b) or F.line_range(a) is None:
        return False
    for d, k in ((a, b), (b, a)):
        gone = cut_words(d)
        if gone is None or cut_words(k) is not None:
            continue
        kept = _words(k.get("quote"))
        if "<all>" in gone or not kept or len(kept & gone) >= CUT_SHARE * len(kept):
            return True
    return False


def same_issue(a, b):
    """True when a and b report one issue: the same file, the same rule (or
    rules in one equivalence group), overlapping lines, and overlapping
    quotes. A fix that keeps the text never folds into one that deletes it.
    Findings with different rules on the same lines stay separate."""
    if a["file"] != b["file"] or conflict(a, b):
        return False
    if not (same_rule(a, b) or equivalent_rules(a, b)):
        return False
    if a.get("fingerprint") and a.get("fingerprint") == b.get("fingerprint") and \
            (overlaps(a, b) or F.line_range(a) is None or F.line_range(b) is None):
        return True
    return overlaps(a, b) and quotes_overlap(a, b)


def nav_key(f):
    """The nav entry a finding is about, or None: impact findings on the
    global nav file target one entry list, so they fold into one finding
    across files."""
    rid = f.get("id") or ""
    if F.rule_family(rid) == "impact" or rid.startswith("facts.impact."):
        m = re.search(r"[\w./-]*navigation\.ya?ml", f.get("file") or "") or \
            (re.search(r"[\w./-]*navigation\.ya?ml", f.get("message") or "") if "nav" in (f.get("message") or "").lower() else None)
        if m:
            return "nav:" + os.path.basename(m.group(0))
    return None


def keep_preference(f):
    """Which finding of a duplicate group to keep: the most important, then
    most severe, then most confident, then deterministic."""
    return (-IMP.level(f), F.severity_rank(f.get("severity")), CONF_RANK.get(f.get("confidence"), 3),
            0 if f.get("deterministic") else 1)


def alternative(f):
    """Compact copy of a merged finding, kept on the winner as `alternatives`."""
    alt = {"id": f["id"], "reviewer": f.get("reviewer"), "severity": f.get("severity"),
           "line": f.get("line"), "end_line": f.get("end_line"), "message": f.get("message"),
           "suggestion": f.get("suggestion"), "fixable": f.get("fixable"), "fingerprint": f.get("fingerprint")}
    return alt


def add_alternative(winner, alt):
    alts = winner.setdefault("alternatives", [])
    if any(a.get("fingerprint") == alt.get("fingerprint") for a in alts):
        return
    if alt["id"] == winner["id"] and (alt.get("suggestion") in (None, winner.get("suggestion"))):
        return  # the same rule with nothing new to offer
    alts.append(alt)


def dedupe(findings):
    """Group findings that report the same issue (`same_issue`), across
    reviewers. Returns (kept, merged_count). The input order breaks ties, so
    output is stable."""
    for f in findings:
        f["fingerprint"] = F.fingerprint(f)
    order = sorted(range(len(findings)), key=lambda i: (keep_preference(findings[i]), i))
    groups = []  # [[winner, member, ...]]
    for i in order:
        f = findings[i]
        home = None
        for g in groups:
            if g[0]["file"] != f["file"] or any(conflict(m, f) for m in g):
                continue
            if any(same_issue(m, f) for m in g):
                home = g
                break
        if home is None:
            groups.append([f])
        else:
            home.append(f)
    kept, merged_count = [], 0
    for g in groups:
        winner = g[0]
        reporters = set(winner.get("also_reported_by") or [])
        for m in g[1:]:
            merged_count += 1
            reporters.add(m["reviewer"])
            reporters.update(m.get("also_reported_by") or [])
            # A product-name fix is copied only from the same rule: Vale's
            # substitution is often not the form a W1 reviewer finding asks for.
            copy_ok = rule_class(winner) != "product-name" or same_rule(winner, m)
            if copy_ok and not winner.get("suggestion") and m.get("suggestion") \
                    and F.line_range(m) == F.line_range(winner):
                winner["suggestion"] = m["suggestion"]
                winner["fixable"] = m["fixable"]
                winner["suggestion_from"] = m["id"]
                if m["id"] == winner["id"]:
                    continue
                m = dict(m, suggestion=None)
            add_alternative(winner, alternative(m))
        reporters.discard(winner["reviewer"])
        if reporters:
            winner["also_reported_by"] = sorted(reporters)
        if not winner.get("alternatives"):
            winner.pop("alternatives", None)
        kept.append(winner)
    kept, nav_merged = fold_nav(kept)
    mark_conflicts(kept)
    return kept, merged_count + nav_merged


def mark_conflicts(findings):
    """Set `conflicts_with` (fingerprints) on both findings of every pair
    whose fixes conflict (`conflict`). Returns the number of pairs."""
    pairs = 0
    for i, a in enumerate(findings):
        for b in findings[i + 1:]:
            if conflict(a, b):
                pairs += 1
                for x, y in ((a, b), (b, a)):
                    fps = x.setdefault("conflicts_with", [])
                    if y["fingerprint"] not in fps:
                        fps.append(y["fingerprint"])
    return pairs


def fold_nav(findings):
    """Fold findings about the same nav entry list across files into one."""
    by_key, out, merged = {}, [], 0
    for f in findings:
        k = nav_key(f)
        if k is None:
            out.append(f)
            continue
        by_key.setdefault(k, []).append(f)
    for k, group in by_key.items():
        group.sort(key=keep_preference)
        winner = group[0]
        reporters = set(winner.get("also_reported_by") or [])
        files = []
        for m in group[1:]:
            merged += 1
            reporters.add(m["reviewer"])
            reporters.update(m.get("also_reported_by") or [])
            if m["file"] != winner["file"] and m["file"] not in files:
                files.append(m["file"])
            alt = alternative(m)
            alt["file"] = m["file"]
            add_alternative(winner, alt)
        reporters.discard(winner["reviewer"])
        if reporters:
            winner["also_reported_by"] = sorted(reporters)
        if files:
            winner["also_files"] = files
        if not winner.get("alternatives"):
            winner.pop("alternatives", None)
        out.append(winner)
    return out, merged


def resolve_suggestion_conflicts(findings):
    """Never two suggestions for the same lines: the higher-ranked finding
    keeps its suggestion, the others move to its `alternatives`."""
    moved = 0
    with_sugg = [f for f in sorted(findings, key=rank_key) if f.get("suggestion") is not None and F.line_range(f)]
    owners = []
    for f in with_sugg:
        owner = next((o for o in owners if o["file"] == f["file"] and overlaps(o, f)), None)
        if owner is None:
            owners.append(f)
            continue
        add_alternative(owner, alternative(f))
        f["suggestion"] = None
        if f.get("fixable") in ("auto", "suggest"):
            f["fixable"] = "manual"
        f["suggestion_moved_to"] = owner["fingerprint"]
        moved += 1
    return moved


def is_impact(f):
    """An impact finding: from impact.py, or the impact part of the facts
    reviewer (`facts.impact.*`)."""
    rid = f.get("id") or ""
    return F.rule_family(rid) == "impact" or f.get("reviewer") == "impact" or rid.startswith("facts.impact.")


def only_withheld_evidence(f):
    """An impact finding whose only evidence is a non-public project (path
    withheld): nobody reading the review can check it."""
    if not is_impact(f):
        return False
    ev = [e for e in (f.get("evidence") or []) if isinstance(e, dict)]
    return bool(ev) and all(str(e.get("ref") or "").strip().lower() == NON_PUBLIC_REF for e in ev)


def calibrate(f):
    sev, notes = f["severity"], []
    reviewer = f.get("reviewer")
    if sev == "blocker" and not f.get("deterministic") and reviewer not in BLOCKER_REVIEWERS \
            and not (f.get("id") or "").startswith(("editor.metadata.", "editor.correctness.")):
        sev = "major"
        notes.append("blocker is reserved for deterministic checks and the impact and facts reviewers")
    if reviewer == "facts" and f.get("verdict") == "unverified" and F.severity_rank(sev) < F.severity_rank("minor"):
        sev = "minor"
        notes.append("unverified claim: ask, do not block")
    if f.get("confidence") == "low" and not f.get("deterministic") and sev != "nit":
        sev = F.lower_severity(sev)
        notes.append("low confidence")
    if rule_class(f) == "product-name" and F.severity_rank(f["severity"]) <= F.severity_rank("major") \
            and F.severity_rank(sev) > F.severity_rank("major"):
        sev = "major"  # a W1 product-name rule is a legal naming rule: never below major
        notes.append("product-name rule stays major")
    if sev != f["severity"]:
        f["calibrated_from"] = f["severity"]
        f["severity"] = sev
        f["calibration"] = "; ".join(notes)
    return f


def sort_key(f):
    return (f["file"], F.severity_rank(f["severity"]), brevity_first(f), f.get("line") or 0, f["id"])


def rank_key(f):
    """Priority: importance, severity, confidence, then deterministic first
    and editor brevity first."""
    return (-IMP.level(f), F.severity_rank(f["severity"]), CONF_RANK.get(f.get("confidence"), 3),
            0 if f.get("deterministic") else 1, brevity_first(f), f["file"], f.get("line") or 0, f["id"])


QUOTED_BITS = re.compile(r"\"[^\"]*\"|'[^'\n]*'|`[^`]*`|“[^”]*”|\[[^\]]*\]\([^)]*\)|\d+")


def message_pattern(f):
    """The message with quoted text, code, links, and numbers removed, so
    repeats of one rule on other lines compare equal."""
    return " ".join(QUOTED_BITS.sub("", f.get("message") or "").lower().split())


def fix_pattern(f):
    """The transform a suggestion applies to its quote, or None: `case` for a
    case-only change, else the changed token pairs (at most 3)."""
    sugg, quote = f.get("suggestion"), f.get("quote") or ""
    if sugg is None or not quote or sugg == quote:
        return None
    if sugg.lower() == quote.lower():
        return ("case",)
    a, b = re.findall(r"\w+|[^\w\s]", quote), re.findall(r"\w+|[^\w\s]", sugg)
    ops = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if op != "equal":
            ops.append((" ".join(a[i1:i2]), " ".join(b[j1:j2])))
    if not ops or len(ops) > 3:
        return None
    if all(x.lower() == y.lower() for x, y in ops):
        return ("case",)
    return tuple(ops)


def comment_units(findings):
    """Group findings into units: repeats of one rule id in one file are one
    unit, posted or deferred together, even when the suggestion
    differs on each line. Rules whose findings each state a different
    problem under one id (CLAIM_FAMILIES, CLAIM_IDS) group only when the fix pattern
    (same suggestion transform) or the message pattern is the same. Returns a
    list of lists, each ranked."""
    parent = list(range(len(findings)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    seen = {}
    for i, f in enumerate(findings):
        if F.rule_family(f["id"]) in CLAIM_FAMILIES or f["id"] in CLAIM_IDS:
            keys = [("msg", f["id"], f["file"], message_pattern(f))]
            fp = fix_pattern(f)
            if fp is not None:
                keys.append(("fix", f["id"], f["file"], fp))
        else:
            keys = [("rule", f["id"], f["file"])]
        for k in keys:
            if k in seen:
                parent[find(i)] = find(seen[k])
            else:
                seen[k] = i
    groups = {}
    for i in range(len(findings)):
        groups.setdefault(find(i), []).append(findings[i])
    units = [sorted(g, key=rank_key) for g in groups.values()]
    for u in units:
        if len(u) > 1:
            gid = u[0]["fingerprint"][:12]
            for f in u:
                f["group"] = gid
                f["group_size"] = len(u)
    units.sort(key=lambda u: rank_key(u[0]))
    return units


def unit_anchor(u):
    """The finding a unit is posted at: its first line in the file (a
    repeat group is one comment on its first occurrence)."""
    with_line = [f for f in u if F.line_range(f)]
    return min(with_line, key=lambda f: F.line_range(f)) if with_line else u[0]


def spot_of(u):
    """(file, (start, end)) of the comment a unit is posted as, or None
    (no line). A range over SPOT_MAX_SPAN lines is a spot of its own: a
    section-level finding does not take in every line-level one."""
    a = unit_anchor(u)
    rng = F.line_range(a)
    return (a["file"], rng) if rng else None


def same_spot(x, y):
    if x is None or y is None or x[0] != y[0]:
        return False
    (a0, a1), (b0, b1) = x[1], y[1]
    if a1 - a0 + 1 > SPOT_MAX_SPAN or b1 - b0 + 1 > SPOT_MAX_SPAN:
        return x[1] == y[1]
    return a0 <= b1 and b0 <= a1


def near_spot(x, y, gap):
    """Two spots in one file whose line ranges are at most `gap` lines apart,
    neither longer than SPOT_MAX_SPAN."""
    if x is None or y is None or x[0] != y[0]:
        return False
    (a0, a1), (b0, b1) = x[1], y[1]
    if a1 - a0 + 1 > SPOT_MAX_SPAN or b1 - b0 + 1 > SPOT_MAX_SPAN:
        return False
    return a0 <= b1 + gap and b0 <= a1 + gap


STOP_WORDS = set("this that with from have your these those when then than they them their there here which "
                 "what into also only make makes made does should would could must about".split())


def _message_words(f):
    return set(w for w in re.findall(r"[a-z]{4,}", message_pattern(f)) if w not in STOP_WORDS)


def same_point(a, b):
    """Two findings that make the same point: the same or an equivalent rule,
    the same rule name in any family, or messages that share most words."""
    if a.get("file") != b.get("file"):
        return False
    if same_rule(a, b) or equivalent_rules(a, b):
        return True
    ka, kb = F.rule_key(a.get("id")), F.rule_key(b.get("id"))
    if ka and ka == kb and len(ka) >= 4:
        return True
    wa, wb = _message_words(a), _message_words(b)
    if min(len(wa), len(wb)) < 3:
        return False
    return len(wa & wb) / float(min(len(wa), len(wb))) >= ADJACENT_MESSAGE_OVERLAP


class Spots(object):
    """The comments a review posts. A unit whose anchor overlaps a kept
    comment's lines joins that comment (a location group). A unit within
    ADJACENT_LINES of a kept comment that makes the same point (same_point)
    joins it too."""

    def __init__(self):
        self.spots = []  # [{"spot", "owner", "members"}]
        self.adjacent = ADJACENT_LINES

    def _find(self, u):
        sp = spot_of(u)
        for s in self.spots:
            if same_spot(s["spot"], sp):
                return s, False
        if self.adjacent:
            a = unit_anchor(u)
            for s in self.spots:
                if near_spot(s["spot"], sp, self.adjacent) and any(same_point(a, m) for m in s["members"]):
                    return s, True
        return None, False

    def find(self, u):
        s, _ = self._find(u)
        return s["owner"] if s else None

    def add(self, u):
        """Keep u. Returns True when it starts a new comment."""
        s, adjacent = self._find(u)
        a = unit_anchor(u)
        if s is not None:
            a["spot"] = s["owner"]["spot"]
            s["members"].append(a)
            if adjacent:
                a["joined"] = "adjacent"
            return False
        a["spot"] = a["fingerprint"][:12]
        self.spots.append({"spot": spot_of(u), "owner": a, "members": [a]})
        return True


def unit_importance(u):
    return max(IMP.level(f) for f in u)


def apply_safety_cap(findings, safety_cap=DEFAULT_SAFETY_CAP):
    """(kept, deferred, stats). Every unit (see comment_units) posts, best
    first, as one comment or by joining a kept comment (Spots), until the
    comments reach `safety_cap` (None or 0: no cap). Blockers are never cut.
    Importance-1 units never post inline (`importance-1`). `summary_only`
    findings stay in `findings` and never take a comment."""
    outside = [f for f in findings if f.get("summary_only") is True]
    inside = [f for f in findings if f.get("summary_only") is not True]
    units = comment_units(inside)
    spots = Spots()
    blocker_of = lambda u: any(f["severity"] == "blocker" for f in u)  # noqa: E731
    report_only = [u for u in units if unit_importance(u) <= 1 and not blocker_of(u)]
    units = [u for u in units if not (unit_importance(u) <= 1 and not blocker_of(u))]
    kept_units, over_cap = [], []
    for u in units:
        if safety_cap and not blocker_of(u) and len(spots.spots) >= safety_cap and spots.find(u) is None:
            over_cap.append(u)
            continue
        spots.add(u)
        kept_units.append(u)
    deferred_units = [(u, "safety-cap") for u in over_cap] + [(u, "importance-1") for u in report_only]
    keep = set(id(f) for u in kept_units for f in u)
    kept = [f for f in findings if id(f) in keep or f.get("summary_only") is True]
    deferred = []
    for u, reason in sorted(deferred_units, key=lambda x: rank_key(x[0][0])):
        for f in u:
            f["deferred_reason"] = reason
            deferred.append(f)
    stats = {"units": len(units) + len(report_only), "units_kept": len(kept_units),
             "units_deferred": len(deferred_units), "summary_only": len(outside), "slots": len(spots.spots),
             "safety_capped": len(over_cap), "importance_1": len(report_only),
             "adjacent_joined": sum(1 for f in kept if f.get("joined") == "adjacent")}
    return kept, deferred, stats


def expand_occurrences(findings, head_text=None):
    """A finding with `occurrences` (a repeated issue reported once) becomes
    one finding per occurrence, with the same id and message, so the repeats
    group as one comment and writers still see each line. An occurrence may
    be {line, quote}, {line} or a bare line number: without a quote, the
    quote is that line of the file at the head (stripped). Returns (findings,
    notes)."""
    out, notes = [], []
    for f in findings:
        occ = f.pop("occurrences", None)
        out.append(f)
        if occ is None:
            continue
        f["occurrence_root"] = f.get("fingerprint") or F.fingerprint(f)
        if not isinstance(occ, list):
            notes.append("{}: `occurrences` is not a list of lines; ignored".format(f["id"]))
            continue
        for i, o in enumerate(occ):
            if isinstance(o, int) and not isinstance(o, bool):
                o = {"line": o}
            if not isinstance(o, dict) or not isinstance(o.get("line"), int) or isinstance(o.get("line"), bool) \
                    or o["line"] < 1:
                notes.append("{}: occurrence #{} needs a `line`; dropped".format(f["id"], i))
                continue
            path = o.get("file") if isinstance(o.get("file"), str) and o.get("file") else f["file"]
            quote = o.get("quote") if isinstance(o.get("quote"), str) and o.get("quote") else None
            if quote is None:
                quote = line_of(head_text, path, o["line"])
                if not quote:
                    notes.append("{}: occurrence #{} has no `quote` and line {} of {} is empty or unknown; dropped".format(
                        f["id"], i, o["line"], path))
                    continue
                notes.append("{}: occurrence #{} had no `quote`; used line {} of {}".format(f["id"], i, o["line"], path))
            g = dict(f)
            g["file"] = path
            g["line"] = o["line"]
            end = o.get("end_line")
            g["end_line"] = end if isinstance(end, int) and end >= o["line"] else o["line"]
            g["quote"] = quote
            sugg = o.get("suggestion")
            g["suggestion"] = sugg if isinstance(sugg, str) else None
            if g["suggestion"] is None and g.get("fixable") in ("auto", "suggest"):
                g["fixable"] = "manual"
            # The primary's details describe its own lines: an occurrence keeps
            # them only when it says so, or another page gets the wrong advice.
            msg = o.get("message")
            if isinstance(msg, str) and msg.strip():
                # The shared message is true of every occurrence; this adds what differs here.
                g["message"] = "{} On this page: {}".format(f["message"].rstrip(), msg.strip())
            g["occurrence_root"] = f.get("fingerprint") or F.fingerprint(f)
            g["preservation"] = o.get("preservation") if isinstance(o.get("preservation"), list) else None
            if g["preservation"] is None:
                g.pop("preservation")
            g["occurrence_of"] = f["id"]
            out.append(g)
    return out, notes


def line_of(head_text, path, n):
    """Line n of path at the head, stripped, or None."""
    text = head_text.text(path) if head_text is not None else None
    if text is None:
        return None
    lines = text.split("\n")
    return lines[n - 1].strip() or None if 0 < n <= len(lines) else None


def disambiguate_fingerprints(findings):
    """Identical quotes on different lines (one sentence repeated on a page)
    must not share a fingerprint: the fingerprint keys dedupe, plans, and
    already-posted markers. The first occurrence keeps the plain fingerprint,
    so it stays stable across rebases; later ones get `#2`, `#3`, in line
    order. Returns the number changed."""
    by_fp = {}
    for f in findings:
        by_fp.setdefault(f["fingerprint"], []).append(f)
    changed = 0
    for fp, group in by_fp.items():
        if len(group) < 2:
            continue
        group.sort(key=lambda x: (F.line_range(x) or (0, 0)))
        for n, f in enumerate(group[1:], 2):
            f["fingerprint"] = hashlib.sha1("{}#{}".format(fp, n).encode("utf-8")).hexdigest()
            changed += 1
    return changed


def fold_covered(findings):
    """`covers`: ids of other findings on the same lines that this
    finding's suggestion also fixes. Those findings fold into it, as one
    comment with one suggestion. Blockers never fold. Returns (findings,
    folded count)."""
    gone, folded = set(), 0
    for f in findings:
        f.setdefault("fingerprint", F.fingerprint(f))
    for f in findings:
        covers = f.get("covers")
        if id(f) in gone or not isinstance(covers, list) or not covers or f.get("suggestion") is None:
            continue
        keys = set(F.rule_key(c) for c in covers if isinstance(c, str))
        ids = set(c for c in covers if isinstance(c, str))
        for g in findings:
            if g is f or id(g) in gone or g["file"] != f["file"] or g["severity"] == "blocker":
                continue
            if not overlaps(f, g) or not (g["id"] in ids or (F.rule_key(g["id"]) in keys and g.get("deterministic"))):
                continue
            gone.add(id(g))
            folded += 1
            rep = set(f.get("also_reported_by") or [])
            rep.add(g["reviewer"])
            rep.discard(f["reviewer"])
            f["also_reported_by"] = sorted(rep)
            alt = alternative(g)
            alt["suggestion"] = None
            alt["reason"] = "covered"
            add_alternative(f, alt)
    return [f for f in findings if id(f) not in gone], folded


def resolve_contradictions(findings):
    """Of two findings whose fixes conflict (`conflicts_with`), keep the
    higher-ranked one (importance first). The other becomes its alternative
    and leaves the posted set (`deferred_reason: "alternative"`). A blocker
    always beats a non-blocker; two blockers both stay. Returns (kept,
    alternatives)."""
    by_fp = dict((f["fingerprint"], f) for f in findings)
    losers = {}
    for f in sorted(findings, key=lambda x: (0 if x["severity"] == "blocker" else 1, rank_key(x))):
        if f["fingerprint"] in losers:
            continue
        for fp in list(f.get("conflicts_with") or []):
            o = by_fp.get(fp)
            if o is None or fp in losers:
                continue
            if f["severity"] == "blocker" and o["severity"] == "blocker":
                continue
            losers[fp] = f
            alt = alternative(o)
            alt["reason"] = "conflict"
            add_alternative(f, alt)
            o["deferred_reason"] = "alternative"
            o["alternative_of"] = f["fingerprint"]
    kept = []
    for f in findings:
        if f["fingerprint"] in losers:
            continue
        cw = [fp for fp in f.get("conflicts_with") or [] if fp not in losers]
        if cw:
            f["conflicts_with"] = cw
        else:
            f.pop("conflicts_with", None)
        kept.append(f)
    alts = [by_fp[fp] for fp in losers]
    for o in alts:
        o.pop("conflicts_with", None)
    return kept, alts


# ---------------------------------------------------------------- report

IMPORTANCE_TITLES = {5: "the reader fails or gets a wrong result", 4: "the reader is likely confused or misled",
                     3: "noticeable friction", 2: "slower to scan", 1: "cosmetic, report only"}
DEFERRED_TEXT = {"safety-cap": "over the safety cap", "importance-1": "importance 1, report only",
                 "alternative": "an alternative to a higher-importance finding"}


def final_pass_lines(findings, deferred, info):
    """The "For the final human pass" section: what a person must still look
    at, and what the review left alone on purpose."""
    unverified = [f for f in findings + deferred if f.get("verdict") == "unverified"
                  and f.get("deferred_reason") != "alternative"]
    sme = []
    for f in findings:
        if f.get("sme") and (f.get("verdict") == "contradicted" or f.get("confidence") == "low"):
            people = ", ".join("`{}`".format(s["username"]) for s in f["sme"][:2] if isinstance(s, dict))
            sme.append("{} (`{}`): {}".format(people, R.loc(f), f["message"]))
    return R.final_pass(findings, rank_key, unverified[:20], sme, deferred, DEFERRED_TEXT, info.get("left_alone"),
                        tasks=(info.get("tasks") or [])[:20])


def render_report(findings, praise, dropped, merged_count, phases, target, verified=None, info=None):
    """report.md: findings by importance, with the final human pass section
    first."""
    info = info or {}
    deferred = info.get("deferred") or []
    by_fp = dict((f.get("fingerprint"), f) for f in list(findings) + list(deferred))
    out = ["# Docs review report", ""]
    t = target or {}
    bits = []
    if t.get("mr"):
        bits.append("MR !{}".format(t["mr"]))
    if t.get("project"):
        bits.append(t["project"])
    if t.get("base") and t.get("head"):
        bits.append("{}..{}".format(str(t["base"])[:12], str(t["head"])[:12]))
    if t.get("tier"):
        bits.append("tier {}".format(t["tier"]))
    if bits:
        out += ["Target: " + ", ".join(bits), ""]
    if t.get("first_time_writer"):
        out += ["First-time docs writer: every editor and reader finding says why it matters and links the rule.", ""]

    levels = [5, 4, 3, 2, 1]
    counts = {}
    for f in findings:
        counts.setdefault(f["reviewer"], dict((n, 0) for n in levels))[IMP.level(f)] += 1
    out += ["## Summary", ""]
    if not findings:
        out += ["No findings.", ""]
    else:
        cols = [n for n in levels if any(c[n] for c in counts.values())]
        out.append("| Reviewer | " + " | ".join("Importance {}".format(n) for n in cols) + " | Total |")
        out.append("|---|" + "---|" * (len(cols) + 1))
        for reviewer in sorted(counts):
            c = counts[reviewer]
            out.append("| {} | {} | {} |".format(reviewer, " | ".join(str(c[n]) for n in cols), sum(c.values())))
        totals = [sum(counts[r][n] for r in counts) for n in cols]
        out.append("| **Total** | {} | **{}** |".format(" | ".join(str(x) for x in totals), len(findings)))
        out.append("")
    extra = summary_extras(findings, dropped, merged_count, info)
    if extra:
        out += ["- " + e for e in extra] + [""]
    out += final_pass_lines(findings, deferred, info)
    if praise:
        out += ["## What is done well", ""] + ["- " + p for p in praise] + [""]
    if findings:
        out += ["## Findings by importance", ""]
        for lvl in levels:
            fs = sorted([f for f in findings if IMP.level(f) == lvl], key=rank_key)
            if not fs:
                continue
            out += ["### Importance {}: {}".format(lvl, IMPORTANCE_TITLES[lvl]), ""]
            for f in fs:
                out += finding_detail_lines(f, findings, by_fp)
            out.append("")
    if verified:
        out += ["## Verified claims", ""] + render_verified(verified)
    out += render_tail(dropped, phases, info, deferred)
    return "\n".join(out).rstrip() + "\n"


# ---------------------------------------------------------------- config

def _int_value(raw):
    raw = (raw or "").strip().strip("'\"")
    if re.match(r"^\d+$", raw):
        return int(raw)
    return None


def resolve_safety_cap(cli, config):
    if cli is not None:
        return cli or None
    n = _int_value(str(config.get("safety_cap") if config.get("safety_cap") is not None else ""))
    return DEFAULT_SAFETY_CAP if n is None else (n or None)


# ---------------------------------------------------------------- scope

def normalize_scope(f):
    """`scope` and `action` (findings-schema.md): a page-scope finding is
    summary-only, and the only `action` is `fix`. Returns a note or None."""
    note = None
    if f.get("scope") not in (None, "line", "section", "page"):
        note = "`scope` {!r} ignored".format(f.get("scope"))
        f.pop("scope")
    if f.get("action") not in (None, "fix"):
        note = "`action` {!r} ignored".format(f.get("action"))
        f.pop("action")
    if f.get("scope") == "page":
        f["summary_only"] = True
    return note


# Word-list substitutions that do not apply: the term is a bold UI label
# (UI text in the docs must match the UI), or the term is the acronym being
# defined right after its expansion ("GitLab Duo Agent Platform (DAP)").
SUBST_TERM_RE = re.compile(r"instead of '([^']+)'")
PLURAL_S_RE = re.compile(r"\w+\(s\)", re.I)
BOLD_RE = re.compile(r"\*\*(.+?)\*\*")


def substitution_term(f):
    """The word a deterministic word-list or Vale finding wants replaced, or None."""
    if not f.get("deterministic") or not str(f.get("id", "")).startswith(("vale.", "lint.word-list")):
        return None
    m = SUBST_TERM_RE.search(f.get("message") or "")
    if m:
        return m.group(1)
    if f["id"].endswith("BadPlurals"):
        m = PLURAL_S_RE.search(f.get("quote") or "")
        return m.group(0) if m else None
    return None


def substitution_not_applicable(f):
    """'ui-label', 'acronym-definition', or None (references/vocabulary.md)."""
    term = substitution_term(f)
    quote = f.get("quote") or ""
    if not term or term.lower() not in quote.lower():
        return None
    low, t = quote.lower(), term.lower()
    spans = [(m.start(1), m.end(1)) for m in BOLD_RE.finditer(quote)]
    hits = [i for i in range(len(low)) if low.startswith(t, i)]
    if hits and all(any(a <= i and i + len(t) <= b for a, b in spans) for i in hits):
        return "ui-label"
    repl = None
    m = re.search(r"Use '([^']+)' instead of", f.get("message") or "")
    if m:
        repl = m.group(1).lower()
    if repl and hits and all(low[max(0, i - 1):i] == "(" and low[:max(0, i - 2)].rstrip().endswith(repl) for i in hits):
        return "acronym-definition"
    return None


def scope_class(f, changed, head_text):
    """`introduced`, `broken`, or `existing` (see SCOPE_BROKEN_*)."""
    if f.get("old_text") is True and not f.get("caused_by_line"):
        return "existing"  # the reviewer says the old version had this problem too
    if touches_change(f, changed, head_text):
        return "introduced"
    rid = f.get("id") or ""
    if F.rule_family(rid) in SCOPE_BROKEN_FAMILIES or f.get("reviewer") in SCOPE_BROKEN_FAMILIES \
            or rid.startswith(SCOPE_BROKEN_PREFIXES):
        return "broken"
    cause = f.get("caused_by_line")
    cause_file = f.get("caused_by_file") or f.get("file")
    lines = changed.get(cause_file, "missing")
    if isinstance(cause, int) and not isinstance(cause, bool) and lines != "missing" \
            and (lines is None or cause in lines):
        return "broken"
    return "existing"


def apply_scope(findings, changed, head_text):
    """Label each finding with `scope_class`. Existing issues go to the
    summary only and never block. Returns counts by class."""
    counts = {"introduced": 0, "broken": 0, "existing": 0}
    for f in findings:
        c = scope_class(f, changed, head_text)
        f["scope_class"] = c
        counts[c] += 1
        if c == "existing":
            f["summary_only"] = True
            f["summary_reason"] = "existing"
            if f["severity"] == "blocker":
                f["severity"] = "major"
                f["blocker_downgraded"] = "existing issue, not caused by this change"
    return counts


GENERIC_SOURCE_RE = re.compile(r"^https?://docs\.gitlab\.com/development/documentation(/styleguide)?/?$")


def is_taste(f):
    """An editor or reader finding with no specific rule behind it: no
    source, or only the style guide or documentation root with no section.
    A guideline page (topic types, metadata, navigation) is a specific rule."""
    if f.get("reviewer") not in ("editor", "reader") or f["severity"] == "blocker":
        return False
    src = (f.get("source") or "").strip()
    return not src or bool(GENERIC_SOURCE_RE.match(src))


# ---------------------------------------------------------------- report helpers

def brevity_first(f):
    return 0 if (f.get("id") or "").startswith("editor.brevity.") else 1


def render_preservation(rows):
    """`preservation` (editor): facts a cut must keep, as a table."""
    table = R.preservation_table(rows, indent="  ")
    return ["", *table, ""] if table else []


def render_verified(items):
    out = ["<details><summary>Verified claims ({})</summary>".format(len(items)), ""]
    for v in items:
        if isinstance(v, dict):
            claim = v.get("claim") or v.get("quote") or v.get("message") or json.dumps(v, ensure_ascii=False)
            where = v.get("file")
            if where and v.get("line"):
                where = "{}:{}".format(where, v["line"])
            ev = v.get("evidence")
            if isinstance(ev, list) and ev:
                ev = ev[0].get("ref") if isinstance(ev[0], dict) else ev[0]
            bits = [str(claim)]
            if where:
                bits.append("({})".format(where))
            if ev:
                bits.append("- evidence: {}".format(ev))
            out.append("- " + " ".join(bits))
        else:
            out.append("- {}".format(v))
    out += ["", "</details>", ""]
    return out


def render_alternatives(alts):
    """Other reviewers' findings and suggestions merged into this one."""
    if not alts:
        return []
    out = ["  - Also on these lines:"]
    for a in alts:
        rng = ""
        if a.get("line"):
            rng = " (line {})".format(a["line"]) if a.get("end_line") in (None, a["line"]) else \
                " (lines {}-{})".format(a["line"], a["end_line"])
        out.append("    - `{}` from {}{}: {}".format(a["id"], a.get("reviewer") or "?", rng, a.get("message") or ""))
        if a.get("suggestion"):
            out += [""] + R.fenced(a["suggestion"], "markdown", "      ") + [""]
    return out


def finding_line(f):
    return "- **{}** `{}` (`{}`): {}".format(f["severity"], f["id"], R.loc(f), f["message"])


def finding_ref(f):
    """`id` (line n) or `id` (lines a-b), for cross-references."""
    where = R.span(f)
    return "`{}` ({})".format(f["id"], where) if where else "`{}`".format(f["id"])


def coverage_gaps(target, statuses):
    """What did not run: skipped tools from the script inputs and missing reviewers."""
    gaps = ["{} {} ({})".format(name, "skipped" if t.get("skipped") else "failed", t.get("skipped") or t.get("error"))
            for name, t in sorted((target.get("tools") or {}).items())
            if isinstance(t, dict) and (t.get("skipped") or t.get("error"))]
    ran = {st.get("reviewer") for st in statuses or []}
    if ran:  # reviewers ran as subagents: name any that did not report
        gaps += ["reviewer `{}` did not report".format(r) for r in REVIEWERS if r not in ran]
    return gaps


def summary_extras(findings, dropped, merged_count, info):
    """The notes under the summary table."""
    deferred = info.get("deferred") or []
    extra = []
    if info.get("coverage"):
        extra.append("Not covered: " + "; ".join(info["coverage"]))
    if deferred:
        units = info.get("units") or {}
        extra.append("Showing {} finding(s) in {} comment(s). Repeats of one rule in a file are one comment, "
                     "findings on overlapping lines share one comment, and summary-only findings take no "
                     "comment".format(len(findings), units.get("slots", len(findings))))
    if info.get("withheld"):
        extra.append("{} impact finding(s) dropped: their only evidence is in a non-public project "
                     "(path withheld)".format(info["withheld"]))
    if info.get("rewrap"):
        extra.append("{} finding(s) dropped on lines that were only rewrapped or reindented".format(info["rewrap"]))
    if info.get("safety_capped"):
        extra.append("{} group(s) were deferred by the safety cap of {} comments".format(
            info["safety_capped"], info.get("safety_cap")))
    if deferred:
        extra.append("{} lower-priority finding(s) deferred (see the end of this report)".format(len(deferred)))
    if merged_count:
        extra.append("{} duplicate finding(s) merged".format(merged_count))
    if info.get("conflicts"):
        extra.append("{} overlapping suggestion(s) moved to the higher-ranked finding's alternatives".format(
            info["conflicts"]))
    if info.get("conflict_pairs"):
        extra.append("{} pair(s) of findings conflict: one cuts text that the other keeps. Both are listed, "
                     "with `conflicts_with`".format(info["conflict_pairs"]))
    if info.get("contradictions"):
        extra.append("{} contradicting finding(s) resolved: the higher-importance one is posted, the other is "
                     "its alternative".format(info["contradictions"]))
    if info.get("covered"):
        extra.append("{} finding(s) folded into a suggestion that also fixes them (`covers`)".format(info["covered"]))
    if info.get("coaching_missing"):
        extra.append("{} editor or reader finding(s) have no coaching note (`why`)".format(info["coaching_missing"]))
    if info.get("coerced"):
        extra.append("{} finding shape problem(s) repaired".format(len(info["coerced"])))
    if dropped:
        extra.append("{} invalid finding(s) dropped".format(len(dropped)))
    return extra


def finding_detail_lines(f, findings, by_fp):
    """One finding in the report, with its quote, evidence, notes, the
    suggestion block, and alternatives."""
    out = []
    rng = F.line_range(f)
    loc = R.span(f)
    head = "- **{}** {} `{}` (`{}`{}): {}".format(IMP.level(f), f["severity"], f["id"], f["file"],
                                                  ", " + loc if loc else "", f["message"])
    if f.get("source"):
        head += " ([source]({}))".format(f["source"])
    out.append(head)
    if f.get("importance_why"):
        out.append("  - Why it matters: {}".format(f["importance_why"]))
    if f.get("why"):
        out.append("  - Coaching: {}".format(f["why"]))
    if f.get("quote"):
        out.append("  - Quote: `{}`".format(f["quote"].replace("`", "'")[:300]))
    if f.get("verdict"):
        out.append("  - Verdict: {} (confidence {})".format(f["verdict"], f["confidence"]))
    for ev in (f.get("evidence") or [])[:5]:
        out.append("  - Evidence ({}): {}{}".format(ev.get("kind"), ev.get("ref"),
                                                    " - " + ev["note"] if ev.get("note") else ""))
    if f.get("summary_only"):
        out.append("  - Page-level: summary only, never posted inline")
    if f.get("also_reported_by"):
        out.append("  - Also reported by: {}".format(", ".join(f["also_reported_by"])))
    if f.get("also_files"):
        out.append("  - Same entry also reported for: {}".format(
            ", ".join("`{}`".format(p) for p in f["also_files"])))
    if f.get("group_size", 1) > 1:
        out.append("  - One of {} findings of this rule (group `{}`)".format(f["group_size"], f["group"]))
    mates = [m for m in findings if f.get("spot") and m is not f and m.get("spot") == f["spot"]]
    if mates:
        out.append("  - Posted in one comment with {}".format(", ".join(finding_ref(m) for m in mates)))
    for fp in f.get("conflicts_with") or []:
        other = by_fp.get(fp)
        if other is not None:
            out.append("  - Conflicts with {}: one cuts text that the other keeps. Pick one.".format(
                finding_ref(other)))
    out += render_preservation(f.get("preservation"))
    if f.get("calibration"):
        out.append("  - Severity lowered from {} ({})".format(f["calibrated_from"], f["calibration"]))
    if f.get("suggestion") is not None and rng:
        out += [""] + R.suggestion_block(f["suggestion"], rng, "  ") + [""]
    out += render_alternatives(f.get("alternatives"))
    return out


def render_tail(dropped, phases, info, deferred):
    """Deferred findings, reviewer status, dropped findings, and the phase
    lines."""
    out = []
    if deferred:
        out += ["<details><summary>More findings (lower priority) ({})</summary>".format(len(deferred)), ""]
        shown = set()
        for f in deferred:
            gid = f.get("group")
            if gid and gid in shown:
                continue
            line = finding_line(f).replace("- **", "- **{}** **".format(IMP.level(f)), 1)
            if gid:
                shown.add(gid)
                line += " (and {} more of this rule)".format(f["group_size"] - 1)
            if f.get("deferred_reason") == "safety-cap":
                line += " (safety cap)"
            elif f.get("deferred_reason") in ("importance-1", "alternative"):
                line += " ({})".format(DEFERRED_TEXT[f["deferred_reason"]])
            out.append(line)
        out += ["", "</details>", ""]

    bad_status = [st for st in info.get("statuses") or [] if not st["valid"] or st.get("status") in ("partial", "blocked")]
    if bad_status:
        out += ["## Reviewer status", ""]
        for st in bad_status:
            note = " ({})".format(st["notes"]) if st.get("notes") else ""
            flag = "" if st["valid"] else " - invalid status, expected complete, partial, or blocked"
            out.append("- {}: `{}`{}{}".format(st.get("reviewer") or st["source"], st.get("status"), flag, note))
        out.append("")

    if dropped:
        out += ["## Dropped (invalid) findings", ""]
        for d in dropped:
            out.append("- {} #{} ({}): {}".format(d["source"], d["index"], d.get("id") or "no id", "; ".join(d["errors"])))
        out.append("")

    if phases:
        out += ["---", ""] + ["`{}`".format(p) for p in phases] + [""]
    return out


# ---------------------------------------------------------------- main

def parse_args(argv):
    p = argparse.ArgumentParser(
        description="Combine docs-review findings: validate, filter to changed lines, calibrate, dedupe "
                    "across reviewers, group into comments, and render report.md.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Exit codes: 0 no blocker, 1 blockers found, 2 usage error.")
    p.add_argument("inputs", nargs="+", help="findings JSON files (scripts and reviewers)")
    p.add_argument("--diff", help="BASE..HEAD: keep only findings on changed lines (impact and facts exempt)")
    p.add_argument("--diff-file", help="unified diff file to use instead of --diff")
    p.add_argument("--repo", default=".", help="git checkout for --diff, heading sections, and the config (default: .)")
    p.add_argument("--safety-cap", type=int, help="most comments one run posts (default {}; `safety_cap:`; 0 turns "
                                                  "it off). Blockers are never cut".format(DEFAULT_SAFETY_CAP))
    p.add_argument("--config", help="config file with `safety_cap:` and `importance:` (default: "
                                    "<repo>/{})".format(CONFIG_NAME))
    p.add_argument("--triage", help="triage.py output: tier, reader scope, and first-time writer")
    p.add_argument("--first-time-writer", action="store_true", help="the MR author is a first-time docs writer: "
                                                                     "check coaching notes (`why`)")
    p.add_argument("--reader-scope", choices=("full", "changed"), help="`full` keeps reader findings on any line "
                                                                       "of a changed page (default: the triage "
                                                                       "file's reader.scope)")
    p.add_argument("--tier", help="triage tier to record in the target (default: target.tier)")
    p.add_argument("--out-dir", help="write findings.json and report.md here")
    p.add_argument("--out", help="write the combined findings JSON to this file")
    p.add_argument("--json", action="store_true", help="print the combined findings JSON to stdout")
    return p.parse_args(argv)


def load_triage(path):
    """triage.py output, or {}."""
    if not path:
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        raise ValueError("cannot read --triage {}: {}".format(path, exc))
    return data if isinstance(data, dict) else {}


def read_config(args, base=None):
    """`.docs-review.yml` as a dict, read at the base of the change, so the MR
    under review cannot change its own importance or safety cap. `--config`
    is an explicit local override. A config that does not parse is a warning:
    triage already failed on it, and the review should still finish."""
    if args.config:
        if not os.path.isfile(args.config):
            raise ValueError("cannot read --config {}".format(args.config))
        with open(args.config, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        try:
            return lint_config.parse(text)
        except lint_config.ConfigError as exc:
            warn("{}: {}; using defaults".format(args.config, exc))
            return {}
    if base is None and (args.diff or args.diff_file):
        warn("{} read from the working tree: the base of the change is unknown".format(CONFIG_NAME))
    try:
        return lint_config.load_at(args.repo, base, warn)
    except lint_config.ConfigError as exc:
        warn("{}: {}; using defaults".format(CONFIG_NAME, exc))
        return {}


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    if args.safety_cap is not None and args.safety_cap < 0:
        warn("--safety-cap must be 0 or more")
        return 2
    try:
        inp = load_inputs(args.inputs)
        triage_doc = load_triage(args.triage)
    except (OSError, ValueError) as exc:
        warn(str(exc))
        return 2
    if not (args.diff or args.diff_file) and triage_doc.get("base"):
        # Scope needs the diff: take it from triage, so a run cannot skip the changed-line filter.
        args.diff = "{}...{}".format(triage_doc["base"], triage_doc.get("head") or "HEAD")  # from the merge base
    if not (args.diff or args.diff_file):
        warn("no --diff and no base in --triage: findings are not filtered to changed lines")
    elif args.diff and not args.diff_file:
        try:
            gitdiff.split_range(args.diff)
        except ValueError as exc:
            warn(str(exc))
            return 2
    base = triage_doc.get("base") or (lint_config.base_of(args.repo, args.diff) if args.diff else None)
    try:
        config = read_config(args, base)
    except (OSError, ValueError) as exc:
        warn(str(exc))
        return 2
    findings, praise, dropped, targets = inp.findings, inp.praise, inp.dropped, inp.targets
    phases, verified = inp.phases, inp.verified
    for d in dropped:
        warn("dropped {} #{} ({}): {}".format(d["source"], d["index"], d.get("id") or "no id", "; ".join(d["errors"])))

    target = {}
    for t in targets:
        for k, v in t.items():
            if v is not None and k not in target:
                target[k] = v
    if args.tier:
        target["tier"] = args.tier
    elif triage_doc.get("tier") and not target.get("tier"):
        target["tier"] = triage_doc["tier"]
    if triage_doc.get("technical_writer") and not target.get("technical_writer"):
        target["technical_writer"] = triage_doc["technical_writer"]
    ftw = triage_doc.get("first_time_writer")
    first_time = bool(args.first_time_writer or target.get("first_time_writer")
                      or (isinstance(ftw, dict) and ftw.get("value") is True) or ftw is True)
    if first_time:
        target["first_time_writer"] = True

    occ_rev = gitdiff.split_range(args.diff)[1] if (args.diff and not args.diff_file) else None
    findings, occ_notes = expand_occurrences(findings, HeadText(args.repo, occ_rev))
    for n in occ_notes:
        warn(n)
        inp.coerced.append({"source": "occurrences", "index": None, "id": n.split(":", 1)[0], "note": n})

    for i, f in enumerate(findings):
        note = normalize_scope(f)
        if note:
            inp.coerced.append({"source": f["_input"], "index": i, "id": f["id"], "note": note})
            warn("{} ({}): {}".format(f["_input"], f["id"], note))

    filtered = rewrap = 0
    changed = None
    head_text = HeadText(args.repo, None)
    if args.diff or args.diff_file:
        try:
            if args.diff_file:
                with open(args.diff_file, encoding="utf-8", errors="replace") as fh:
                    text = fh.read()
                head_rev = None
            else:
                text = diff_from_git(args.repo, args.diff)
                head_rev = gitdiff.split_range(args.diff)[1]
        except (OSError, ValueError) as exc:
            warn(str(exc))
            return 2
        changed = gitdiff.parse_unified(text)
        head_text = HeadText(args.repo, head_rev)
        before = len(findings)
        reader_full = args.reader_scope == "full" or (
            args.reader_scope is None and ((triage_doc.get("reader") or {}).get("scope") == "full"))

        def reader_page(f):
            # A full reader walk may quote any line of a changed page.
            return reader_full and f.get("reviewer") == "reader" and f.get("file") in changed

        findings = [f for f in findings if on_changed_lines(f, changed, head_text) or reader_page(f)]
        filtered = before - len(findings)
        # Lines that a hunk only rewrapped or reindented are not changed text.
        fmt = formatting_lines(text)
        if fmt:
            real = dict((p, (None if lines is None else lines - fmt.get(p, set()))) for p, lines in changed.items())
            before = len(findings)
            findings = [f for f in findings if exempt_from_line_filter(f) or F.line_range(f) is None
                        or on_changed_lines(f, real, head_text) or reader_page(f)]
            rewrap = before - len(findings)

    scope_counts = apply_scope(findings, changed, head_text) if changed is not None else None
    withheld = [f for f in findings if only_withheld_evidence(f)]
    findings = [f for f in findings if not only_withheld_evidence(f)]
    not_applicable = []
    for f in findings:
        why = substitution_not_applicable(f)
        if why:
            not_applicable.append({"fingerprint": f.get("fingerprint"), "id": f["id"], "file": f.get("file"),
                                   "line": f.get("line"), "reason": why})
    skip = set(id(f) for f in findings if substitution_not_applicable(f))
    findings = [f for f in findings if id(f) not in skip]
    findings = [calibrate(f) for f in findings]
    overrides, imp_warnings = IMP.parse_overrides(config.get("importance"))
    for w in imp_warnings:
        warn("{}: {}".format(CONFIG_NAME, w))
    for f in findings:
        IMP.resolve(f, overrides)
    findings, covered = fold_covered(findings)
    findings, merged_count = dedupe(findings)
    fingerprints_split = disambiguate_fingerprints(findings)
    conflict_pairs = sum(len(f.get("conflicts_with") or []) for f in findings) // 2
    findings, alternatives = resolve_contradictions(findings)
    conflicts = resolve_suggestion_conflicts(findings)
    coaching_missing = 0
    if first_time:
        for f in findings:
            if f.get("reviewer") in ("editor", "reader") and not (f.get("why") or "").strip():
                if f.get("importance_why"):
                    f["why"] = f["importance_why"]
                else:
                    coaching_missing += 1
    findings.sort(key=sort_key)
    safety_cap = resolve_safety_cap(args.safety_cap, config)
    reader_to_summary = 0
    if not first_time:
        for f in findings:
            imp = f.get("importance")
            if f.get("reviewer") == "reader" and f["severity"] != "blocker" and f.get("summary_only") is not True \
                    and isinstance(imp, int) and imp < READER_INLINE_MIN_IMPORTANCE:
                f["summary_only"] = True
                f["summary_reason"] = "reader"
                reader_to_summary += 1
    polish_to_summary = 0
    for f in findings:
        if f.get("summary_only") is True:
            continue
        if is_taste(f):
            f["summary_only"] = True
            f["summary_reason"] = "polish"
            polish_to_summary += 1
    findings, deferred, unit_stats = apply_safety_cap(findings, safety_cap)
    deferred = deferred + sorted(alternatives, key=rank_key)
    findings.sort(key=rank_key)
    for f in findings + deferred:
        f.pop("_input", None)

    stats = {"input_files": len(args.inputs), "kept": len(findings), "deferred": len(deferred),
             "safety_cap": safety_cap, "dropped_invalid": len(dropped), "filtered_unchanged": filtered,
             "filtered_rewrap": rewrap, "dropped_withheld_evidence": len(withheld),
             "substitution_not_applicable": not_applicable, "merged_duplicates": merged_count,
             "fingerprints_split": fingerprints_split, "suggestion_conflicts": conflicts,
             "conflict_pairs": conflict_pairs, "coerced": len(inp.coerced),
             "reader_to_summary": reader_to_summary, "polish_to_summary": polish_to_summary,
             "scope": scope_counts,
             "contradictions_resolved": len(alternatives), "covered": covered,
             "coaching_missing": coaching_missing, "first_time_writer": first_time}
    stats.update(unit_stats)
    doc = F.new_doc(target, findings, deferred=deferred, praise=praise, verified=verified, phases=phases, stats=stats,
                    dropped=dropped, coerced=inp.coerced, reviewer_status=inp.statuses, left_alone=inp.left_alone,
                    reader_tasks=inp.tasks)
    info = {"deferred": deferred, "conflicts": conflicts, "safety_capped": unit_stats.get("safety_capped"),
            "safety_cap": safety_cap, "conflict_pairs": conflict_pairs, "coerced": inp.coerced,
            "statuses": inp.statuses, "units": unit_stats, "withheld": len(withheld), "rewrap": rewrap,
            "contradictions": len(alternatives), "covered": covered, "coaching_missing": coaching_missing,
            "left_alone": inp.left_alone, "tasks": inp.tasks, "coverage": coverage_gaps(target, inp.statuses)}
    report = render_report(findings, praise, dropped, merged_count, phases, target, verified, info)

    out_json, out_report = args.out, None
    if args.out_dir:
        os.makedirs(args.out_dir, exist_ok=True)
        out_json = out_json or os.path.join(args.out_dir, "findings.json")
        out_report = out_report or os.path.join(args.out_dir, "report.md")
    if out_json:
        F.dump(doc, out_json)
    if out_report:
        with open(out_report, "w", encoding="utf-8") as fh:
            fh.write(report)
    if args.json:
        sys.stdout.write(F.dump(doc))
    elif not out_json and not out_report:
        sys.stdout.write(report)
    else:
        sys.stdout.write("merged {} finding(s) in {} group(s), {} comment(s), from {} file(s): {} deferred in {} "
                         "group(s), {} filtered (unchanged lines), {} rewrap-only, {} withheld-evidence, "
                         "{} duplicates, {} suggestion conflicts, {} invalid\n".format(
                             len(findings), unit_stats.get("units_kept"), unit_stats.get("slots"), len(args.inputs),
                             len(deferred), unit_stats.get("units_deferred"), filtered, rewrap, len(withheld),
                             merged_count, conflicts, len(dropped)))
    return 1 if F.has_blocker(findings) else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, UnicodeError, ValueError, RuntimeError) as exc:  # a one-line error, not a traceback
        if os.environ.get("DOCS_REVIEW_DEBUG"):
            raise
        sys.stderr.write("{}: error: {}\n".format(sys.argv[0].rsplit("/", 1)[-1], exc))
        sys.exit(2)
