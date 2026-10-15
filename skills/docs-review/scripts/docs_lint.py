#!/usr/bin/env python3
"""Deterministic GitLab docs checks. Emits the docs-review findings schema as JSON
(references/findings-schema.md) plus a `vocabulary` array (references/vocabulary.md).
Python 3.9+, stdlib only, read-only on the target repository.

Usage:
  docs_lint.py --diff origin/main...HEAD [--out findings.json]
  docs_lint.py doc/user/project/settings.md
  docs_lint.py --list-checks

Checks:
  1. Vale with GitLab's rules and .vale.ini from gitlab-org/gitlab (cached, refreshed
     weekly; DOCS_REVIEW_OFFLINE=1 never fetches), merged with the project's .vale.ini.
     Known misfires are dropped and counted in `target.tools.vale.suppressed`.
  2. markdownlint-cli2 with the project config, else GitLab's .markdownlint-cli2.yaml.
  3. Built-in `lint.*` checks Vale cannot do: front matter structure, availability
     details, history blocks, feature flag notes, redirects, alerts, product terms,
     headings, links and anchors, code fences, and Vale rules turned off in a changed
     Vale config. `--list-checks` prints them.

Exit codes: 0 no blocker, 1 at least one blocker, 2 usage or environment error.
"""

import argparse
import datetime
import difflib
import fnmatch
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from lib import dates  # noqa: E402
from lib import findings as F  # noqa: E402
from lib import gitdiff  # noqa: E402
from lib import lint_config  # noqa: E402
from lib import mdparse  # noqa: E402
from lib import page_class  # noqa: E402

GITLAB_PROJECT = "278964"  # gitlab-org/gitlab
GITLAB_API = "https://gitlab.com/api/v4/projects/" + GITLAB_PROJECT
CACHE_DIR = os.path.join(os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache"),
                         "docs-review", "vale")
VALE_MIN_LEVEL = "warning"
# Fetched from gitlab-org/gitlab next to doc/.vale, at the cache's <sha>/ root.
UPSTREAM_FILES = (".vale.ini", ".markdownlint-cli2.yaml")

DOCS = "https://docs.gitlab.com/development/documentation/"
SG = DOCS + "styleguide/"
WL = SG + "word_list/"
AD = SG + "availability_details/"
META = DOCS + "metadata/"
FF = DOCS + "feature_flags/"
RD = DOCS + "redirects/"
TT = DOCS + "topic_types/"
VALE_DOC = DOCS + "testing/vale/"
MDL_DOC = DOCS + "testing/markdownlint/"

# Built-in checks: id -> (reviewer area for humans, default severity, source).
CHECKS = {
    "lint.front-matter-missing": ("metadata", "major", META + "#title-metadata", 3),
    "lint.front-matter-key": ("metadata", "major", META + "#stage-and-group-metadata", 2),
    "lint.front-matter-description": ("metadata", "minor", META + "#description-metadata", 2),
    "lint.front-matter-group": ("metadata", "major", META + "#stage-and-group-metadata", 2),
    "lint.front-matter-unknown-key": ("metadata", "minor", META + "#additional-metadata", 1),
    "lint.details-unclosed": ("metadata", "blocker", AD, 4),
    "lint.details-tier": ("metadata", "major", AD + "#tier", 3),
    "lint.details-status": ("metadata", "major", AD + "#status", 3),
    "lint.details-unknown-key": ("metadata", "minor", AD + "#available-options", 2),
    "lint.details-placement": ("metadata", "minor", AD, 2),
    "lint.history-unclosed": ("metadata", "blocker", AD + "#history", 4),
    "lint.history-format": ("metadata", "major", AD + "#history", 2),
    "lint.history-link": ("metadata", "minor", AD + "#history", 2),
    "lint.history-version": ("metadata", "minor", AD + "#history", 2),
    "lint.history-flag-format": ("metadata", "major", FF + "#add-history-text", 2),
    "lint.flag-note-missing": ("metadata", "major", FF + "#add-a-flag-note", 3),
    "lint.flag-note-without-flag": ("metadata", "major", FF + "#add-a-flag-note", 3),
    "lint.flag-note-after-removal": ("metadata", "major", FF + "#history-examples", 3),
    "lint.flag-note-placement": ("metadata", "minor", FF + "#add-a-flag-note", 2),
    "lint.flag-note-text": ("metadata", "minor", FF + "#add-a-flag-note", 2),
    "lint.redirect-target-missing": ("metadata", "blocker", RD + "#redirect-to-a-page-that-already-exists", 5),
    "lint.redirect-chain": ("metadata", "major", RD, 3),
    "lint.redirect-remove-date": ("metadata", "major", RD + "#redirect-to-a-page-that-already-exists", 2),
    "lint.redirect-remove-date-window": ("metadata", "minor", RD + "#redirect-to-a-page-that-already-exists", 2),
    "lint.redirect-comment-date": ("metadata", "major", RD + "#redirect-to-a-page-that-already-exists", 2),
    "lint.redirect-body": ("metadata", "minor", RD + "#redirect-to-a-page-that-already-exists", 2),
    "lint.redirect-extra-key": ("metadata", "minor", RD + "#redirect-to-a-page-that-already-exists", 1),
    "lint.alert-type": ("style", "major", SG + "#alert-boxes", 2),
    "lint.alert-case": ("style", "nit", SG + "#alert-boxes", 1),
    "lint.alert-legacy": ("style", "major", SG + "#alert-boxes", 2),
    "lint.alert-consecutive": ("style", "minor", SG + "#alert-boxes", 2),
    "lint.product-term": ("consistency", "major", WL, 3),
    "lint.heading-length": ("structure", "minor", TT + "#topic-title-guidelines", 2),
    "lint.heading-step-number": ("structure", "minor", TT + "#topic-title-guidelines", 2),
    "lint.heading-duplicate": ("structure", "minor", SG + "#heading-levels-in-markdown", 3),
    "lint.heading-h1": ("structure", "major", SG + "#heading-levels-in-markdown", 3),
    "lint.heading-task-verb": ("structure", "nit", TT + "task/#task-topic-titles", 1),
    "lint.link-broken": ("style", "blocker", SG + "#links", 4),
    "lint.image-missing": ("style", "blocker", SG + "#images", 4),
    "lint.anchor-broken": ("style", "blocker", SG + "#anchor-links", 4),
    "lint.link-outside-docs": ("style", "major", SG + "#links-to-external-documentation", 2),
    "lint.link-to-redirect": ("style", "minor", RD, 2),
    "lint.code-fence-language": ("code-examples", "minor", SG + "#code-blocks", 1),
    "lint.code-fence-unclosed": ("code-examples", "major", SG + "#code-blocks", 4),
    "lint.vale-rule-disabled": ("style", "minor", VALE_DOC + "#disable-vale-tests", 2),
}

FRONT_MATTER_KEYS = {
    "title", "description", "stage", "group", "info", "redirect_to", "remove_date",
    "gitlab_dedicated", "availability_details", "ignore_in_report", "feedback", "noindex",
    "toc", "type", "source", "layout", "aliases", "weight", "date", "draft", "summary",
}
REQUIRED_KEYS = ("title", "description", "stage", "group", "info")

TIER_ORDER = ("Free", "Premium", "Ultimate")
STATUSES = ("Beta", "Experiment", "Limited availability")
STATUS_FIX = {"beta": "Beta", "experiment": "Experiment", "experimental": "Experiment",
              "limited availability": "Limited availability"}
DETAILS_KEYS = ("Tier", "Add-on", "Offering", "Status", "LLM", "Model")
ALERT_TYPES = ("note", "warning", "flag", "disclaimer")
ALERT_FIX = {"tip": "note", "info": "note", "important": "note", "caution": "warning", "danger": "warning"}

# -ing words that are nouns in topic titles (not gerund task titles).
ING_NOUNS = {
    "troubleshooting", "billing", "pricing", "logging", "tracing", "indexing", "caching", "routing",
    "networking", "licensing", "monitoring", "testing", "scheduling", "clustering", "sharding",
    "hosting", "mapping", "rendering", "streaming", "ranking", "encoding", "filtering", "sorting",
    "branching", "mirroring", "versioning", "signing", "tagging", "labeling", "debugging",
    "profiling", "onboarding", "packaging", "naming", "nothing", "something", "string",
    "building", "setting", "settings", "spring", "pending", "existing", "missing",
    "incoming", "outgoing", "upcoming", "polling", "batching", "paging", "pagination", "throttling",
    "permissions", "planning", "learning", "reporting", "alerting", "auditing", "ordering",
    "matching", "parsing", "scoring", "sampling", "rating", "funding", "listing", "heading",
    "padding", "warning", "meaning", "morning", "evening", "wording", "spacing", "timing",
}
VOCAB_RULES = re.compile(r"(^|\.)(Spelling|British|Substitutions|SubstitutionWarning)$")

DETAILS_OPEN = re.compile(r"\{\{<\s*details\s*>\}\}")
DETAILS_CLOSE = re.compile(r"\{\{<\s*/details\s*>\}\}")
HISTORY_OPEN = re.compile(r"\{\{<\s*history\s*>\}\}")
HISTORY_CLOSE = re.compile(r"\{\{<\s*/history\s*>\}\}")
COLLAPSIBLE_OPEN = re.compile(r"\{\{<\s*collapsible\b")
COLLAPSIBLE_CLOSE = re.compile(r"\{\{<\s*/collapsible\s*>\}\}")
ALERT_RE = re.compile(r"^\s*>\s*\[!([A-Za-z]+)\]")


def info(msg):
    sys.stderr.write("docs_lint: " + msg + "\n")


class Context(object):
    def __init__(self, args):
        self.args = args
        self.repo = None
        self.docs_root = None  # absolute
        self.config = {}
        self.config_path = None
        self.today = datetime.date.today()
        self.findings = []
        self.vocab_hits = []
        self.tools = {}
        self.layout = "standalone"
        self.doc_cache = {}
        self.disabled_ids = []
        self.vale_seen = set()
        self.page_classes = {}  # repo-relative path -> page class, for linted pages
        self.rules = None  # (doc/.vale dir, label), see gitlab_rules()

    def rel(self, path):
        base = self.repo or os.getcwd()
        r = os.path.relpath(os.path.abspath(path), base)
        return r.replace(os.sep, "/")

    def parsed(self, abspath):
        abspath = os.path.normpath(abspath)
        if abspath not in self.doc_cache:
            try:
                self.doc_cache[abspath] = mdparse.parse_file(abspath, self.rel(abspath))
            except OSError:
                self.doc_cache[abspath] = None
        return self.doc_cache[abspath]

    def is_disabled_rule(self, rule):
        return any(rule == d or (d.endswith("*") and rule.startswith(d[:-1])) or rule.startswith(d + ".")
                   for d in self.disabled_ids)


class Emitter(object):
    """Builds findings for one document, honoring disable regions and config."""

    def __init__(self, ctx, doc, abspath):
        self.ctx = ctx
        self.doc = doc
        self.abspath = abspath
        self.file = ctx.rel(abspath)

    def __call__(self, rule, line, message, severity=None, confidence="high", suggestion=None,
                 fixable="manual", end_line=None, kind="meta", source=None, reviewer="lint", importance=None):
        if rule in CHECKS:
            _, default_sev, default_src, default_imp = CHECKS[rule]
        else:
            base = rule.rsplit(".", 1)[0]
            default_sev, default_src, default_imp = CHECKS.get(base, ("lint", "minor", SG, 2))[1:]
        if self.ctx.is_disabled_rule(rule):
            return
        line = max(1, min(line, len(self.doc.lines))) if self.doc.lines else None
        if line is None:
            return
        end = end_line or line
        if kind in ("prose", "markdown") and self.doc.is_disabled(line, rule, kind):
            return
        if self.doc.is_disabled(line, rule, "ids"):
            return
        quote = "\n".join(self.doc.lines[line - 1:end])
        if not quote.strip():
            return  # Every finding must quote text from the file.
        self.ctx.findings.append(F.make_finding(
            rule, reviewer, severity or default_sev, self.file, message, confidence=confidence,
            line=line, end_line=end, quote=quote, suggestion=suggestion, fixable=fixable,
            source=source or default_src, deterministic=True))
        self.ctx.findings[-1]["importance"] = importance or default_imp


# ---------------------------------------------------------------------------
# Front matter
# ---------------------------------------------------------------------------

def _norm_words(s):
    return [w for w in re.findall(r"[a-z0-9]+", (s or "").lower())]


def check_front_matter(doc, emit, ctx):
    fm = doc.front_matter
    if doc.front_matter_range is None or "redirect_to" in fm:
        return  # Vale's gitlab_docs.FrontMatter flags a page without front matter
    start = doc.front_matter_range[0]
    # Release notes follow their own templates: no `info`, and `stage` and
    # `group` are not product values (lib/page_class.py).
    release_notes = getattr(doc, "page_class", None) == page_class.RELEASE_NOTES
    for key in (("title",) if release_notes else REQUIRED_KEYS):
        val = fm.get(key)
        if val is None or not str(val).strip():
            line = doc.front_matter_lines.get(key, start)
            emit("lint.front-matter-key", line,
                 "Add a non-empty `{}` to the front matter.".format(key),
                 severity="blocker" if key == "title" and ctx.layout == "gitlab" else None)
    title, desc = fm.get("title", ""), fm.get("description", "")
    if title and desc:
        tw, dw = _norm_words(title), _norm_words(desc)
        stop = {"a", "an", "the", "and", "or", "of", "for", "to", "in", "on", "with", "gitlab", "about", "how"}
        if dw == tw or (dw and set(dw) - stop <= set(tw) - stop):
            emit("lint.front-matter-description", doc.front_matter_lines["description"],
                 "The `description` repeats the title. Describe what the reader can do on the page.",
                 confidence="medium")
    group = fm.get("group", "")
    if group and re.search(r"[,;]", group) and not release_notes:
        emit("lint.front-matter-group", doc.front_matter_lines["group"],
             "Use one `group` value. Tooling such as CODEOWNERS and docs metrics reads it.")
    for key, num in sorted(doc.front_matter_lines.items(), key=lambda kv: kv[1]):
        if key not in FRONT_MATTER_KEYS and not (release_notes and key in page_class.RELEASE_NOTE_KEYS):
            emit("lint.front-matter-unknown-key", num,
                 "Front matter key `{}` is not a documented metadata key.".format(key), confidence="medium")
    if title:
        line = doc.front_matter_lines["title"]
        if len(title) > 70:
            emit("lint.heading-length", line,
                 "Shorten the title to fewer than 70 characters ({} now).".format(len(title)))


# ---------------------------------------------------------------------------
# Availability details, history, feature flags
# ---------------------------------------------------------------------------

def _block_ranges(doc, open_re, close_re):
    """[(open_line, close_line or None)] for shortcode blocks in text lines."""
    out = []
    current = None
    for num in range(1, len(doc.lines) + 1):
        if not doc.is_text(num):
            continue
        raw = doc.lines[num - 1]
        if open_re.search(raw):
            if current is not None:
                out.append((current, None))
            current = num
        elif close_re.search(raw) and current is not None:
            out.append((current, num))
            current = None
    if current is not None:
        out.append((current, None))
    return out


def _prev_content_line(doc, num):
    j = num - 1
    while j >= 1:
        raw = doc.lines[j - 1].strip()
        if raw and not doc.in_comment[j] and not raw.startswith("<!--"):
            return j
        j -= 1
    return 0


def check_details(doc, emit, ctx):
    """Vale's Badges-Tiers and Badges-Offerings check case, order, and bold. These checks
    cover what they cannot: a tier list that stops short, Status values, unknown keys."""
    for start, end in _block_ranges(doc, DETAILS_OPEN, DETAILS_CLOSE):
        if end is None:
            emit("lint.details-unclosed", start, "Close the availability details with `{{< /details >}}`.")
            continue
        prev = _prev_content_line(doc, start)
        prev_raw = doc.line(prev).strip() if prev else ""
        if prev and not (prev_raw.startswith("#") or (doc.front_matter_range and prev == doc.front_matter_range[1])):
            emit("lint.details-placement", start,
                 "Put availability details directly after the front matter or the topic title.")
        in_collapsible = False
        for num in range(start + 1, end):
            raw = doc.lines[num - 1]
            if COLLAPSIBLE_OPEN.search(raw):
                in_collapsible = True
                continue
            if COLLAPSIBLE_CLOSE.search(raw):
                in_collapsible = False
                continue
            if in_collapsible or not raw.strip():
                continue
            m = re.match(r"^- ([A-Za-z][A-Za-z -]*?):\s*(.*?)\s*$", raw)
            if not m:
                continue
            key, value = m.group(1), m.group(2)
            if key == "Tier":
                found = [t for t in TIER_ORDER if re.search(r"\b" + t + r"\b", value)]
                fix = ", ".join(TIER_ORDER[TIER_ORDER.index(found[0]):]) if found else None
                if found and ", ".join(found) == value and fix != value:
                    emit("lint.details-tier", num,
                         "List every tier from the lowest one up: `Free, Premium, Ultimate`, `Premium, Ultimate`, "
                         "or `Ultimate`.", suggestion="- Tier: " + fix, fixable="auto")
            elif key == "Status":
                if value not in STATUSES:
                    fix = STATUS_FIX.get(value.lower())
                    if re.match(r"(?i)^(ga|generally available|general availability)$", value):
                        msg = "Generally available features have no `Status` line. Remove it."
                    else:
                        msg = "Status must be `Beta`, `Experiment`, or `Limited availability`."
                    emit("lint.details-status", num, msg,
                         suggestion="- Status: " + fix if fix else None, fixable="auto" if fix else "manual")
            elif key not in DETAILS_KEYS:
                emit("lint.details-unknown-key", num,
                     "`{}` is not an availability details field. Use Tier, Add-on, Offering, or Status.".format(key),
                     confidence="medium")


HISTORY_ITEM = re.compile(r"^(\s*)- (.*)$")
VERSION_OK = re.compile(r"\bGitLab (?:[\w.-]+ )?\d+\.\d+\b|\bon [A-Z][a-z]+ \d{1,2}, \d{4}\b|\b\d+\.\d+(?:\.\d+)?\b")
# "with a feature flag" in prose, a `[with a flag](...)` link as in current
# history entries, or an unlinked "with a flag named `x`".
FLAG_INTRO = re.compile(r"with a feature flag|\[with a (?:feature )?flag\]\(|\bwith a flag named\b", re.I)
FLAG_LINK = re.compile(r"\[with a (?:feature )?flag\]\(([^)]*)\)", re.I)
# A history entry links to the issue, MR, or epic that made the change. The
# feature flags page link (`with a flag`) does not count.
HISTORY_REF_LINK = re.compile(r"/-/(?:issues|work_items|merge_requests|epics)/\d+")
MD_LINK_TARGET = re.compile(r"\]\(([^)\s]+)[^)]*\)")
FLAG_REMOVED = re.compile(r"[Ff]eature flag\b[^.\n]*\bremoved\b|\bremoved\b[^.\n]*\bfeature flag\b|"
                          r"^\[?Generally available\b", re.I)


def _history_items(doc, start, end):
    """[(line, end_line, indent, text)] of list items inside a history block."""
    items = []
    for num in range(start + 1, end):
        raw = doc.lines[num - 1]
        if not raw.strip() or doc.in_comment[num]:
            continue
        m = HISTORY_ITEM.match(raw)
        if m:
            items.append([num, num, len(m.group(1)), m.group(2)])
        elif items and raw.startswith(" "):
            items[-1][1] = num
            items[-1][3] += " " + raw.strip()
        else:
            items.append([num, num, -1, raw.strip()])
    return items


def check_history_and_flags(doc, emit, ctx):
    blocks = _block_ranges(doc, HISTORY_OPEN, HISTORY_CLOSE)
    alerts = []
    for num in range(1, len(doc.lines) + 1):
        if doc.is_text(num):
            m = ALERT_RE.match(doc.lines[num - 1])
            if m and m.group(1).lower() == "flag":
                alerts.append(num)
    sections = doc.sections()

    def section_of(num):
        for h, s, e in sections:
            if s <= num <= e:
                return (s, e)
        return (1, len(doc.lines))

    hist_by_section = {}
    for start, end in blocks:
        if end is None:
            emit("lint.history-unclosed", start, "Close the history with `{{< /history >}}`.")
            continue
        hist_by_section.setdefault(section_of(start), []).append((start, end))
        items = _history_items(doc, start, end)
        for k, (num, last, indent, text) in enumerate(items):
            if indent >= 0 and text.rstrip().endswith(":") and k + 1 < len(items) and items[k + 1][2] > indent:
                continue  # a parent entry that groups nested entries
            if indent < 0:
                emit("lint.history-format", num,
                     "Write each history entry as a list item that starts with `- `.")
                continue
            targets = [t for t in MD_LINK_TARGET.findall(text) if "feature_flags" not in t]
            no_link = not any(HISTORY_REF_LINK.search(t) for t in targets)
            bad_version = not VERSION_OK.search(text) or re.search(r"\bGitLab \d+\.x\b", text)
            if bad_version:
                emit("lint.history-version", num,
                     "Name the exact GitLab version, for example `in GitLab 18.10.`"
                     + (" Also link the entry to its issue, merge request, or epic." if no_link else ""),
                     end_line=last)
            elif no_link:
                emit("lint.history-link", num, "Link the history entry to its issue, merge request, or epic.",
                     end_line=last, confidence="medium")
            if FLAG_INTRO.search(text):
                problems = []
                if not re.search(r"named `[^`]+`", text):
                    problems.append("the flag name in backticks (named `flag_name`)")
                if not re.search(r"\b(Enabled|Disabled) by default\b", text):
                    problems.append("the default state (Enabled by default. or Disabled by default.)")
                link = FLAG_LINK.search(text)
                if (link and "feature_flags" not in link.group(1)) or (
                        not link and re.search(r"\bwith a flag named\b", text, re.I)):
                    problems.append("a `with a feature flag` link to the feature flags page")
                if problems:
                    emit("lint.history-flag-format", num,
                         "Feature flag history needs " + "; ".join(problems) + ".", end_line=last)

    for sec, ranges in sorted(hist_by_section.items()):
        texts = []
        for start, end in ranges:
            texts.extend(t for _, _, _, t in _history_items(doc, start, end))
        introduced = [t for t in texts if FLAG_INTRO.search(t)]
        removed = any(FLAG_REMOVED.search(re.sub(r"\]\([^)]*\)", "]", t)) for t in texts)
        sec_alerts = [a for a in alerts if sec[0] <= a <= sec[1]]
        last_close = ranges[-1][1]
        if introduced and not removed and not sec_alerts:
            emit("lint.flag-note-missing", last_close,
                 "Add the `> [!flag]` note right after the history, because this feature is behind a flag.")
        for a in sec_alerts:
            if removed:
                emit("lint.flag-note-after-removal", a,
                     "The history says the feature flag was removed. Delete the flag note.")
            elif not introduced:
                emit("lint.flag-note-without-flag", a,
                     "This section's history does not mention a feature flag. Remove the flag note, "
                     "or add the flag to the history.")
            if _prev_content_line(doc, a) != last_close and not removed:
                emit("lint.flag-note-placement", a, "Put the flag note directly after `{{< /history >}}`.")
            block = []
            j = a
            while j <= len(doc.lines) and doc.lines[j - 1].lstrip().startswith(">"):
                block.append(doc.lines[j - 1])
                j += 1
            if not re.search(r"controlled by a feature flag", " ".join(block)):
                emit("lint.flag-note-text", a,
                     "Use the standard flag note text: `> The availability of this feature is controlled "
                     "by a feature flag.` and `> For more information, see the history.`", end_line=j - 1)
    for a in alerts:
        if not any(sec[0] <= a <= sec[1] for sec in hist_by_section):
            emit("lint.flag-note-without-flag", a,
                 "A flag note must follow a history entry that names the feature flag.")


# ---------------------------------------------------------------------------
# Redirect stubs
# ---------------------------------------------------------------------------

def check_redirect(doc, emit, ctx, abspath):
    fm = doc.front_matter
    if "redirect_to" not in fm:
        return
    line_rt = doc.front_matter_lines["redirect_to"]
    target = fm.get("redirect_to", "")
    external = re.match(r"^[a-z]+://", target) is not None
    if not external:
        tpath = os.path.normpath(os.path.join(os.path.dirname(abspath), target.split("#")[0]))
        if not target.endswith(".md") or not os.path.isfile(tpath):
            emit("lint.redirect-target-missing", line_rt,
                 "The `redirect_to` target `{}` does not exist. Point it to the new page's `.md` file.".format(target))
        else:
            tdoc = ctx.parsed(tpath)
            if tdoc is not None and "redirect_to" in tdoc.front_matter:
                emit("lint.redirect-chain", line_rt,
                     "The target is itself a redirect. Point `redirect_to` at the final page.")
    rd = fm.get("remove_date")
    rd_line = doc.front_matter_lines.get("remove_date", line_rt)
    date = None
    if rd is None or not re.match(r"^\d{4}-\d{2}-\d{2}$", rd or ""):
        emit("lint.redirect-remove-date", rd_line,
             "Set `remove_date: 'YYYY-MM-DD'`: three months out for redirects in this project, one year for "
             "external targets.")
    else:
        try:
            date = datetime.datetime.strptime(rd, "%Y-%m-%d").date()
        except ValueError:
            emit("lint.redirect-remove-date", rd_line, "`remove_date` is not a valid date.")
    if date:
        limit = 380 if external else 100
        delta = (date - ctx.today).days
        if delta < 0:
            emit("lint.redirect-remove-date-window", rd_line,
                 "This redirect expired on {}. You can delete the file.".format(rd), severity="nit")
        elif delta > limit:
            emit("lint.redirect-remove-date-window", rd_line,
                 "`remove_date` is {} days away. Use about {} for {} redirects.".format(
                     delta, "one year" if external else "three months", "external" if external else "internal"))
    for key, num in doc.front_matter_lines.items():
        if key not in ("redirect_to", "remove_date"):
            emit("lint.redirect-extra-key", num,
                 "A redirect file has only `redirect_to` and `remove_date` in its front matter.")
    body_start = doc.front_matter_range[1] + 1
    moved_line = None
    for num in range(body_start, len(doc.lines) + 1):
        raw = doc.lines[num - 1]
        m = re.search(r"<!-- This redirect file can be deleted after <?(\d{4}-\d{2}-\d{2})>?\.? -->", raw)
        if m and date and m.group(1) != rd:
            emit("lint.redirect-comment-date", num,
                 "The comment date ({}) must match `remove_date` ({}).".format(m.group(1), rd),
                 suggestion=raw.replace(m.group(1), rd), fixable="auto")
        if not doc.is_text(num) or not raw.strip() or raw.strip().startswith("<!--"):
            continue
        if re.match(r"^This (document|page) was moved to \[another location\]\(([^)]*)\)\.\s*$", raw.strip()):
            moved_line = num
            link = re.search(r"\]\(([^)]*)\)", raw).group(1)
            if link != target:
                emit("lint.redirect-body", num,
                     "The link must match `redirect_to` (`{}`).".format(target),
                     suggestion=raw.replace("](" + link + ")", "](" + target + ")"), fixable="auto")
        else:
            emit("lint.redirect-body", num,
                 "A redirect file has no other content than `This document was moved to [another location](...).`")
    if moved_line is None and not external:
        emit("lint.redirect-body", line_rt,
             "Add `This document was moved to [another location]({}).` below the front matter.".format(target))


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------

# Vale's gitlab_base.AlertFormat flags the `alert` shortcode and a `Note:` label at
# the line start. This catches the other legacy labels and a quoted `> Note:`.
LEGACY_LABEL = re.compile(r"^\s*(?:>\s*(?:\*\*|_)?(Note)|(?:>\s*)?(?:\*\*|_)?(Warning|Tip|Important|Caution))"
                          r"(?:\*\*|_)?:(?:\*\*|_)?\s", re.I)


def check_alerts(doc, emit, ctx):
    alert_blocks = []
    for num in range(1, len(doc.lines) + 1):
        if not doc.is_text(num):
            continue
        raw = doc.lines[num - 1]
        m = ALERT_RE.match(raw)
        if m:
            kind = m.group(1)
            alert_blocks.append(num)
            low = kind.lower()
            if low not in ALERT_TYPES:
                fix = ALERT_FIX.get(low)
                emit("lint.alert-type", num,
                     "`[!{}]` is not a supported alert. Use `[!note]`, `[!warning]`, `[!flag]`, or `[!disclaimer]`."
                     .format(kind), suggestion=raw.replace("[!" + kind + "]", "[!" + fix + "]") if fix else None,
                     fixable="suggest" if fix else "manual", kind="markdown")
            elif kind != low:
                emit("lint.alert-case", num, "Write the alert type in lowercase: `[!{}]`.".format(low),
                     suggestion=raw.replace("[!" + kind + "]", "[!" + low + "]"), fixable="auto", kind="markdown")
            continue
        legacy = LEGACY_LABEL.match(raw)
        if legacy:
            label = legacy.group(1) or legacy.group(2)
            emit("lint.alert-legacy", num, "Use a Markdown alert (`> [!note]`) or plain text, not a `{}:` label."
                 .format(label.strip("*_ ")), kind="markdown")
    prev_end = None
    for a in alert_blocks:
        end = a
        while end + 1 <= len(doc.lines) and doc.lines[end].lstrip().startswith(">"):
            end += 1
        if prev_end is not None and a > prev_end and all(not doc.lines[k - 1].strip() for k in range(prev_end + 1, a)):
            emit("lint.alert-consecutive", a, "Do not put one alert directly after another. Combine or rewrite them.",
                 kind="markdown")
        prev_end = end


# ---------------------------------------------------------------------------
# Product terms
# ---------------------------------------------------------------------------

BOLD_SPAN = re.compile(r"\*\*[^*\n]+\*\*")


def product_terms(ctx):
    out = []
    for item in ctx.config.get("product_terms") or []:
        if not isinstance(item, dict) or not item.get("use"):
            continue
        avoid = item.get("avoid") or []
        if isinstance(avoid, str):
            avoid = [avoid]
        for a in avoid:
            if a:
                out.append((str(item["use"]), str(a), item.get("severity") or "major",
                            re.compile(r"(?<![\w-])" + re.escape(str(a)) + r"(?![\w-])", re.I)))
    return out


def check_product_terms(doc, emit, ctx):
    terms = product_terms(ctx)
    if not terms:
        return
    for num in range(1, len(doc.lines) + 1):
        if not doc.is_text(num):
            continue
        prose = BOLD_SPAN.sub(lambda m: " " * len(m.group(0)), doc.prose[num])
        raw = doc.lines[num - 1]
        for use, avoid, sev, rx in terms:
            uses = [(m.start(), m.end()) for m in re.finditer(re.escape(use), prose)]
            for m in rx.finditer(prose):
                if any(s <= m.start() and m.end() <= e for s, e in uses):
                    continue
                fix = raw[:m.start()] + use + raw[m.end():] if raw[m.start():m.end()] == m.group(0) else None
                emit("lint.product-term", num, "Use \"{}\", not \"{}\" (project product terms).".format(use, m.group(0)),
                     severity=sev, suggestion=fix, fixable="suggest" if fix else "manual",
                     source=ctx.product_terms_source, kind="prose")
                break


# ---------------------------------------------------------------------------
# Headings
# ---------------------------------------------------------------------------

def check_headings(doc, emit, ctx):
    title = doc.front_matter.get("title", "")
    getting_started = re.match(r"^(Get started|Getting started|Tutorial:)", title or "") is not None
    seen = {}
    parents = []  # stack of (level, line) for the current heading's ancestors
    parent_of = {}
    for h in doc.headings:
        while parents and parents[-1][0] >= h.level:
            parents.pop()
        parent_of[h.line] = parents[-1][1] if parents else 0
        parents.append((h.level, h.line))
    for h in doc.headings:
        if h.level == 1 and title:
            emit("lint.heading-h1", h.line, "Remove the `#` heading. The front matter `title` is the page title.",
                 kind="markdown")
        if len(h.text) > 70:
            emit("lint.heading-length", h.line,
                 "Shorten the topic title to fewer than 70 characters ({} now).".format(len(h.text)), kind="markdown")
        if re.match(r"^\d+[.):]\s", h.text):
            emit("lint.heading-step-number", h.line, "Do not number topic titles.", kind="markdown")
        elif re.match(r"^Step \d+\b", h.text) and not getting_started:
            emit("lint.heading-step-number", h.line,
                 "Do not use step numbers in topic titles. Only Get started pages use `Step N:` titles.",
                 severity="nit", confidence="medium", kind="markdown")
        if not h.custom_id:
            if h.anchor in seen:
                first = seen[h.anchor]
                sibling = parent_of.get(first[0]) == parent_of[h.line] and first[1] == h.level
                if sibling:
                    emit("lint.heading-duplicate", h.line,
                         "This title repeats a sibling title on line {}. Make topic titles unique.".format(first[0]),
                         kind="markdown")
                else:
                    emit("lint.heading-duplicate", h.line,
                         "This title has the same anchor (`#{}`) as line {}, so its anchor becomes `#{}-1`. "
                         "Consider a more specific title.".format(h.anchor, first[0], h.anchor),
                         severity="nit", confidence="medium", kind="markdown")
            else:
                seen[h.anchor] = (h.line, h.level)
    # Gerund task titles: a section with an ordered list whose title starts with -ing.
    for h, start, end in doc.sections():
        if h is None:
            continue
        first = (h.text.split() or [""])[0]
        if not first.lower().endswith("ing") or first.lower() in ING_NOUNS or len(first) < 6:
            continue
        has_steps = False
        for num in range(start + 1, end + 1):
            if doc.is_text(num) and re.match(r"^\s*1\.\s", doc.lines[num - 1]):
                has_steps = True
                break
        if has_steps:
            emit("lint.heading-task-verb", h.line,
                 "Task titles start with an active verb (\"Configure\", not \"Configuring\").",
                 confidence="low", kind="markdown")


# ---------------------------------------------------------------------------
# Links and anchors
# ---------------------------------------------------------------------------

def _resolve(path_part, base_dir):
    cand = os.path.normpath(os.path.join(base_dir, path_part))
    if os.path.isfile(cand):
        return cand
    if os.path.isdir(cand):
        for name in ("_index.md", "index.md"):
            if os.path.isfile(os.path.join(cand, name)):
                return os.path.join(cand, name)
        return None
    if not cand.endswith(".md") and os.path.isfile(cand + ".md"):
        return cand + ".md"
    return None


def check_links(doc, emit, ctx, abspath):
    base_dir = os.path.dirname(abspath)
    in_docs = ctx.docs_root and _under(abspath, ctx.docs_root)
    for num, col, is_img, text, target in doc.links():
        if not target or re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target) or target.startswith("//"):
            continue
        if target.startswith("{{"):
            continue
        path_part, _, anchor = target.partition("#")
        path_part = path_part.split("?")[0]
        if path_part.startswith("/"):
            if not ctx.docs_root:
                continue
            resolved = _resolve(path_part.lstrip("/"), ctx.docs_root)
        elif path_part:
            resolved = _resolve(path_part, base_dir)
        else:
            resolved = abspath
        if resolved is None:
            rule = "lint.image-missing" if is_img else "lint.link-broken"
            emit(rule, num, "The link target `{}` does not exist.".format(path_part))
            continue
        if in_docs and path_part and not _under(resolved, ctx.docs_root):
            emit("lint.link-outside-docs", num,
                 "`{}` is outside the docs. Link to files outside the docs with a full URL.".format(path_part))
            continue
        if is_img or not resolved.endswith(".md"):
            continue
        tdoc = doc if resolved == abspath else ctx.parsed(resolved)
        if tdoc is None:
            continue
        if path_part and "redirect_to" in tdoc.front_matter and not anchor:
            new = tdoc.front_matter.get("redirect_to", "")
            fix = None
            if new and not re.match(r"^[a-z]+://", new):
                final = os.path.normpath(os.path.join(os.path.dirname(resolved), new))
                rel = os.path.relpath(final, base_dir).replace(os.sep, "/")
                raw = doc.lines[num - 1]
                if ("](" + target + ")") in raw:
                    fix = raw.replace("](" + target + ")", "](" + rel + ")", 1)
            emit("lint.link-to-redirect", num, "`{}` is a redirect. Link to its new location.".format(path_part),
                 suggestion=fix, fixable="suggest" if fix else "manual")
            continue
        if anchor:
            anchors = tdoc.anchors()
            if anchor in anchors:
                continue
            raw = doc.lines[num - 1]
            fix, msg = None, "The anchor `#{}` does not exist in `{}`.".format(anchor, path_part or "this page")
            if anchor.lower() in anchors:
                fix = raw.replace("#" + anchor + ")", "#" + anchor.lower() + ")", 1)
                msg = "Anchors are lowercase: `#{}`.".format(anchor.lower())
            else:
                close = difflib.get_close_matches(anchor, sorted(anchors), n=1, cutoff=0.75)
                if close:
                    fix = raw.replace("#" + anchor + ")", "#" + close[0] + ")", 1)
                    msg += " Did you mean `#{}`?".format(close[0])
            emit("lint.anchor-broken", num, msg, suggestion=fix if fix != raw else None,
                 fixable="suggest" if fix and fix != raw else "manual")


def _under(path, root):
    path, root = os.path.abspath(path), os.path.abspath(root)
    return path == root or path.startswith(root.rstrip(os.sep) + os.sep)


def check_fences(doc, emit, ctx):
    for fence in doc.fences:
        if not fence.closed:
            emit("lint.code-fence-unclosed", fence.start, "Close this code block.", kind="markdown")
        if not fence.lang:
            raw = doc.lines[fence.start - 1]
            fix = raw.rstrip() + "plaintext" if not raw.strip()[3:].strip() else None
            emit("lint.code-fence-language", fence.start,
                 "Add a language to the code block. Use `plaintext` if no other language fits.",
                 suggestion=fix, fixable="suggest" if fix else "manual", kind="markdown")


# ---------------------------------------------------------------------------
# Vale
# ---------------------------------------------------------------------------

def _read(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read()


def _ini_sections(text):
    """[(section or '', [(line_no, key, value)])] for Vale ini text."""
    out = [("", [])]
    for num, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith(("#", ";")):
            continue
        m = re.match(r"^\[(.+)\]$", line)
        if m:
            out.append((m.group(1), []))
        elif "=" in line:
            k, v = line.split("=", 1)
            out[-1][1].append((num, k.strip(), v.strip()))
    return out


def _glob_matches(pattern, relpaths):
    m = re.match(r"^(.*)\{([^}]*)\}(.*)$", pattern)
    pats = [m.group(1) + alt + m.group(3) for alt in m.group(2).split(",")] if m else [pattern]
    return any(fnmatch.fnmatch(r, p) or fnmatch.fnmatch(os.path.basename(r), p)
               or fnmatch.fnmatch(r, p.replace("**/", "")) for p in pats for r in relpaths)


def report_disabled_vale_rules(ctx, ini_path, relpaths):
    """One lint.vale-rule-disabled finding per whole rule set to NO in a docs scope."""
    try:
        text = _read(ini_path)
    except OSError:
        return
    emit = Emitter(ctx, mdparse.Doc(text, ctx.rel(ini_path)), ini_path)
    reported = set()
    for name, entries in _ini_sections(text):
        if not name or not _glob_matches(name, relpaths):
            continue
        styles = [v for _, k, v in entries if k == "BasedOnStyles"]
        if styles and not styles[-1].strip():
            continue
        for num, k, v in entries:
            if re.match(r"^[\w-]+\.[\w-]+$", k) and v.upper() == "NO" and k not in reported:
                reported.add(k)
                emit("lint.vale-rule-disabled", num,
                     "`{}` is off for all docs in `[{}]`. Turn it off inline for the lines that need it, "
                     "add the term to the project vocabulary, or make the rule entry case-sensitive.".format(k, name))


def check_vale_config(ctx, files, changed):
    """lint.vale-rule-disabled, only when the Vale config is in the diff or passed as a path:
    a rule turned off in an unchanged config is a standing project decision."""
    base = ctx.repo or os.getcwd()
    explicit = ctx.args.vale_config or ctx.config.get("vale_config")
    ini = os.path.join(base, explicit or ".vale.ini")
    targets = [os.path.abspath(p) for p in ctx.args.paths or []
               if os.path.isfile(p) and os.path.basename(p).endswith("vale.ini")]
    if not targets and changed is not None and os.path.isfile(ini) and ctx.rel(ini) in changed:
        targets.append(ini)
    relpaths = [ctx.rel(f) for f in files]
    if not relpaths and ctx.docs_root:
        relpaths = [ctx.rel(f) for _, f in zip(range(200), iter_markdown([ctx.docs_root]))]
    for t in targets:
        report_disabled_vale_rules(ctx, t, relpaths)


def vale_cache_current():
    try:
        with open(os.path.join(CACHE_DIR, "current"), encoding="utf-8") as fh:
            sha = fh.read().strip()
    except OSError:
        return None, None
    rules = os.path.join(CACHE_DIR, sha, "doc", ".vale")
    return (rules, sha) if os.path.isdir(os.path.join(rules, "gitlab_base")) else (None, None)


def current_vale_rules(max_age_days=7):
    """(rules_dir, sha): the cached GitLab rules, fetched first when missing, incomplete, or older
    than a week. A failed fetch falls back to the old cache. DOCS_REVIEW_OFFLINE=1 never fetches."""
    rules, sha = vale_cache_current()
    try:
        age = time.time() - os.path.getmtime(os.path.join(CACHE_DIR, "current"))
    except OSError:
        age = None
    stale = rules is None or age is None or age > max_age_days * 86400 or \
        not all(os.path.isfile(os.path.join(CACHE_DIR, sha, f)) for f in UPSTREAM_FILES)
    stamp = os.path.join(CACHE_DIR, "last-attempt")
    try:  # one attempt a day, so a failing fetch does not repeat on every run
        recent = time.time() - os.path.getmtime(stamp) < 86400
    except OSError:
        recent = False
    if os.environ.get("DOCS_REVIEW_OFFLINE") != "1" and stale and (rules is None or not recent):
        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
            open(stamp, "w").close()
            fetch_vale_rules()
            rules, sha = vale_cache_current()
            for old in os.listdir(CACHE_DIR):  # drop rules no run has used for a day
                path = os.path.join(CACHE_DIR, old)
                if old != sha and os.path.isdir(path) and re.match(r"^[0-9a-f]{40}$", old) \
                        and time.time() - os.path.getmtime(path) > 86400:
                    shutil.rmtree(path, ignore_errors=True)
        except Exception as exc:  # network or API error: keep what we have
            info("could not refresh the GitLab Vale rules ({}); {}".format(
                exc, "using the cached copy" if rules else "skipping Vale"))
    return rules, sha


def fetch_vale_rules():
    """Download gitlab-org/gitlab doc/.vale and UPSTREAM_FILES into the cache, keyed by commit SHA."""
    def get(url):
        req = urllib.request.Request(url, headers={"User-Agent": "docs-review"})
        with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310 (fixed https host)
            return resp.read()

    sha = json.loads(get(GITLAB_API + "/repository/commits/master"))["id"]
    dest = os.path.join(CACHE_DIR, sha)
    if not os.path.isdir(os.path.join(dest, "doc", ".vale", "gitlab_base")):
        data = get("{}/repository/archive.tar.gz?sha={}&path=doc/.vale".format(GITLAB_API, sha))
        os.makedirs(CACHE_DIR, exist_ok=True)
        tmp = tempfile.mkdtemp(prefix=".fetch-", dir=CACHE_DIR)  # a concurrent run never sees partial rules
        try:
            with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
                for member in tar.getmembers():
                    parts = member.name.split("/", 1)
                    if len(parts) < 2 or not parts[1].startswith("doc/.vale/") or ".." in parts[1].split("/") \
                            or not member.isfile():
                        continue
                    out = os.path.join(tmp, parts[1])
                    os.makedirs(os.path.dirname(out), exist_ok=True)
                    with open(out, "wb") as fh:
                        fh.write(tar.extractfile(member).read())
            try:
                os.replace(tmp, dest)
            except OSError:  # another run finished the same SHA first
                pass
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    for name in UPSTREAM_FILES:
        if not os.path.isfile(os.path.join(dest, name)):
            try:
                body = get("{}/repository/files/{}/raw?ref={}".format(GITLAB_API, urllib.request.quote(name), sha))
                with open(os.path.join(dest, name), "wb") as fh:
                    fh.write(body)
            except Exception as exc:  # the rules still work with the built-in fallbacks
                info("could not fetch {}: {}".format(name, exc))
    # A ready-to-use config for `--vale-config <cache>/<sha>/vale.ini`.
    with open(os.path.join(dest, "vale.ini"), "w", encoding="utf-8") as fh:
        fh.write(vale_ini(os.path.join(dest, "doc", ".vale"), os.path.join(dest, ".vale.ini")))
    with open(os.path.join(CACHE_DIR, "current"), "w", encoding="utf-8") as fh:
        fh.write(sha + "\n")
    return sha, dest


def gitlab_rules(ctx):
    """(doc/.vale dir or None, label): --vale-rules, else the cache. Fetches at most once per run."""
    if ctx.rules is None:
        ctx.rules = (os.path.abspath(ctx.args.vale_rules), "local") if ctx.args.vale_rules \
            else current_vale_rules()
    return ctx.rules


def upstream_file(ctx, name):
    """A gitlab-org/gitlab file next to the rules' doc/.vale (cache or checkout), or None."""
    rules = gitlab_rules(ctx)[0]
    if not rules or os.path.basename(rules) != ".vale" or os.path.basename(os.path.dirname(rules)) != "doc":
        return None
    path = os.path.join(os.path.dirname(os.path.dirname(rules)), name)
    return path if os.path.isfile(path) else None


# Used only when GitLab's .vale.ini was never fetched.
MIN_VALE_INI = r"""IgnoredScopes = code, text.frontmatter.redirect_to, text.frontmatter.info, text.frontmatter.type
[*.md]
BasedOnStyles = gitlab_base, gitlab_docs
TokenIgnores = \{\{< icon .*?>\}\}, \S+\.yml
"""


def vale_ini(styles_path, upstream=None, toggles=(), extra_styles=(), vocab=None, ignored=()):
    """GitLab's .vale.ini (all sections, such as release notes) with StylesPath set to the rules,
    plus the project's vocabulary and ignored scopes, and its styles and rule toggles in [*.md]."""
    sections = _ini_sections(_read(upstream) if upstream and os.path.isfile(upstream) else MIN_VALE_INI)
    if not any(name == "*.md" for name, _ in sections):
        sections.insert(1, ("*.md", [(0, "BasedOnStyles", "gitlab_base, gitlab_docs")]))
    top = {k: v for _, k, v in sections[0][1]}
    top["StylesPath"] = styles_path
    scopes = [s.strip() for s in top.get("IgnoredScopes", "").split(",") if s.strip()]
    top["IgnoredScopes"] = ", ".join(scopes + [s for s in ignored if s not in scopes])
    if vocab:
        top["Vocab"] = vocab
    lines = ["# Generated by docs-review docs_lint.py from gitlab-org/gitlab .vale.ini."]
    lines += ["{} = {}".format(k, v) for k, v in top.items() if v]
    for name, entries in sections[1:]:
        lines += ["", "[{}]".format(name)]
        for _, k, v in entries:
            if name == "*.md" and k == "BasedOnStyles":
                v = ", ".join([s.strip() for s in v.split(",") if s.strip()] + list(extra_styles))
            lines.append("{} = {}".format(k, v))
        if name == "*.md":
            lines += list(toggles)
    return "\n".join(lines) + "\n"


def project_vale_settings(ini_path, relpaths):
    """Styles, vocab, ignored scopes, and rule toggles from the project's .vale.ini (docs scope only)."""
    styles_dir, vocab, ignored, extra_styles, toggles = None, None, [], [], []
    base = os.path.dirname(ini_path)
    for name, entries in _ini_sections(_read(ini_path)):
        for _, k, v in entries:
            if not name:
                if k == "StylesPath":
                    styles_dir = os.path.normpath(os.path.join(base, v))
                elif k == "Vocab":
                    vocab = v
                elif k == "IgnoredScopes":
                    ignored = [s.strip() for s in v.split(",") if s.strip()]
            elif not _glob_matches(name, relpaths):
                continue
            elif k == "BasedOnStyles":
                extra_styles += [s.strip() for s in v.split(",") if s.strip() not in
                                 ("", "gitlab_base", "gitlab_docs", "Vale") and s.strip() not in extra_styles]
            elif re.match(r"^[\w-]+\.[\w-]+$", k):
                toggles.append("{} = {}".format(k, v))
    return styles_dir, vocab, ignored, extra_styles, toggles


def build_vale_config(ctx, rules_dir, relpaths, tmp):
    """Write a project-aware ini that points at GitLab's rules. Returns (ini path, notes)."""
    upstream = upstream_file(ctx, ".vale.ini")
    notes = ["gitlab-org/gitlab .vale.ini" if upstream else "built-in minimal .vale.ini (upstream never fetched)"]
    styles = os.path.join(tmp, "styles")
    os.makedirs(styles)
    for s in os.listdir(rules_dir):
        if os.path.isdir(os.path.join(rules_dir, s)):
            os.symlink(os.path.join(rules_dir, s), os.path.join(styles, s))
    toggles, extra, vocab, ignored = [], [], None, []
    proj_ini = os.path.join(ctx.repo, ".vale.ini") if ctx.repo else None
    if proj_ini and os.path.isfile(proj_ini):
        sdir, vocab, ignored, extra_all, toggles = project_vale_settings(proj_ini, relpaths)
        for s in extra_all:
            src = os.path.join(sdir or "", s)
            if sdir and os.path.isdir(src) and not os.path.exists(os.path.join(styles, s)):
                os.symlink(src, os.path.join(styles, s))
                extra.append(s)
        if vocab and sdir:
            vsrc = os.path.join(sdir, "config", "vocabularies")
            if os.path.isdir(vsrc):
                os.makedirs(os.path.join(styles, "config"), exist_ok=True)
                os.symlink(vsrc, os.path.join(styles, "config", "vocabularies"))
            else:
                vocab = None
        if toggles:
            notes.append("kept {} rule toggles from {}".format(len(toggles), ctx.rel(proj_ini)))
        if extra:
            notes.append("added project styles: " + ", ".join(extra))
    if ctx.layout != "gitlab":
        # Standalone docs projects publish under a docs.gitlab.com prefix and must link to
        # gitlab-org/gitlab docs with absolute URLs, so this repo-layout rule does not apply.
        toggles = [t for t in toggles if not t.startswith("gitlab_docs.RelativeLinks")]
        toggles.append("gitlab_docs.RelativeLinks = NO")
        notes.append("gitlab_docs.RelativeLinks off (standalone docs layout)")
    ini = os.path.join(tmp, "vale.ini")
    with open(ini, "w", encoding="utf-8") as fh:
        fh.write(vale_ini(styles, upstream, toggles, extra, vocab, ignored))
    return ini, notes


def run_vale(ctx, files):
    tool = {"ran": False}
    ctx.tools["vale"] = tool
    exe = shutil.which("vale")
    if not exe:
        info("vale not found on PATH; skipping Vale (install: https://vale.sh/docs/install).")
        tool["skipped"] = "vale not installed"
        return
    try:
        tool["version"] = subprocess.run([exe, "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                         universal_newlines=True, timeout=30).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    relpaths = [ctx.rel(f) for f in files]
    explicit = ctx.args.vale_config or ctx.config.get("vale_config")
    tmp = tempfile.mkdtemp(prefix="docs-review-vale-")
    try:
        if explicit:
            ini = explicit if os.path.isabs(explicit) else os.path.join(ctx.repo or os.getcwd(), explicit)
            if not os.path.isfile(ini):
                info("Vale config {} not found; skipping Vale.".format(explicit))
                tool["skipped"] = "config not found"
                return
            tool["config"] = ctx.rel(ini)
            tool["rules"] = "project"
        else:
            rules_dir, sha = gitlab_rules(ctx)
            if not rules_dir or not os.path.isdir(os.path.join(rules_dir, "gitlab_base")):
                info("no GitLab Vale rules available (fetch failed or offline); pass --vale-config or "
                     "--vale-rules. Skipping Vale.")
                tool["skipped"] = "no rules"
                return
            ini, notes = build_vale_config(ctx, rules_dir, relpaths, tmp)
            tool["rules"] = "gitlab-org/gitlab@" + sha if sha != "local" else rules_dir
            tool["config"] = "generated"
            tool["notes"] = notes
        cmd = [exe, "--config=" + ini, "--output=JSON", "--minAlertLevel=" + VALE_MIN_LEVEL,
               "--no-exit"] + relpaths
        res = subprocess.run(cmd, cwd=ctx.repo or os.getcwd(), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             universal_newlines=True)
        if res.returncode != 0 or not (res.stdout or "").strip():
            # With --no-exit, alerts do not change the exit code: this is a broken Vale, not a clean page.
            msg = (res.stderr or res.stdout or "no output").strip()[:300]
            info("Vale did not run (exit {}): {}".format(res.returncode, msg))
            tool["error"] = "exit {}: {}".format(res.returncode, msg)
            return
        try:
            data = json.loads(res.stdout or "{}")
        except ValueError:
            info("Vale output was not JSON: {}".format((res.stderr or res.stdout).strip()[:300]))
            tool["error"] = (res.stderr or res.stdout).strip()[:300]
            return
        if isinstance(data, dict) and "Code" in data and "Text" in data:
            info("Vale error: {}".format(data.get("Text")))
            tool["error"] = data.get("Text")
            return
        tool["ran"] = True
        count = 0
        for path, alerts in data.items():
            abspath = os.path.join(ctx.repo or os.getcwd(), path) if not os.path.isabs(path) else path
            doc = ctx.parsed(abspath)
            if doc is None:
                continue
            emit = Emitter(ctx, doc, abspath)
            for a in alerts:
                count += vale_alert(ctx, emit, doc, a, explicit)
        tool["alerts"] = count
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def vale_alert(ctx, emit, doc, a, project_config):
    check = a.get("Check") or ""
    level = a.get("Severity") or "warning"
    line = a.get("Line") or 0
    match = a.get("Match") or ""
    if not line or not match:
        return 0  # metric rules such as ReadingLevel have no quotable text
    if level == "error":
        severity = "blocker" if (project_config or ctx.layout == "gitlab") else "major"
        confidence = "high"
    else:  # warning; suggestions are below VALE_MIN_LEVEL
        severity, confidence = "minor", "medium" if check.endswith("Spelling") else "high"
    raw = doc.line(line)
    span = a.get("Span") or [0, 0]
    s, e = _vale_span(raw, span, match)
    tool = ctx.tools.get("vale", {})
    reason = vale_exception(check, match, raw, e) if s is not None else None
    if reason is None and check.endswith(".OxfordComma") and s is not None:
        reason = oxford_comma_false_positive(doc, line, raw, s, e)
    if reason is None and 0 < line < len(doc.in_front_matter) and doc.in_front_matter[line]:
        reason = "front matter value, not prose"
    if reason is None and s is not None:
        reason = split_across_line_break(doc, line, raw, s, a.get("Message") or "", match)
    if reason:
        dropped = tool.setdefault("suppressed", {})
        dropped[reason] = dropped.get(reason, 0) + 1
        return 0
    action = a.get("Action") or {}
    params = action.get("Params") or []
    message = (a.get("Message") or check).strip()
    fix = None
    if action.get("Name") == "replace" and len(params) == 1 and s is not None:
        fix, options = vale_fix(raw, s, e, match, params[0], doc.prose[line] if line <= len(doc.lines) else None)
        if options:
            message = message.rstrip(".") + ". Options: " + ", ".join("`{}`".format(o) for o in options) + \
                ". Pick the one that fits the sentence."
    w1 = vale_product_name(check, message)
    if w1:
        severity, reviewer = ("blocker" if severity == "blocker" else "major"), "word-list"
        message = "Product name (word list W1): " + message
    else:
        reviewer = "vale"
    key = (check, emit.file, line, match)
    if key in ctx.vale_seen:
        return 0  # the same word twice on one line gives the same quote; report it once
    ctx.vale_seen.add(key)
    before = len(ctx.findings)
    emit("vale." + check, line, "{} ({})".format(message, check),
         severity=severity, confidence=confidence, suggestion=fix, fixable="suggest" if fix else "manual",
         source=a.get("Link") or VALE_DOC, reviewer=reviewer, kind="vale")
    if w1 and len(ctx.findings) > before:
        ctx.findings[-1]["word_list_rule"] = "W1"
        return 1  # a product name is never a vocabulary exception
    if len(ctx.findings) > before and VOCAB_RULES.search(check):
        ctx.vocab_hits.append((check, match, ctx.findings[-1]))
    return 1


VALE_SUBST_MSG = re.compile(r"Use '([^']+)' instead of '([^']+)'")


def vale_product_name(check, message):
    """True when a Vale substitution enforces a product or feature name
    ("Use 'GitLab Duo' instead of 'Duo'"): word list W1, a major finding."""
    if not re.search(r"\.Substitution(s|Warning)?$", check):
        return False
    m = VALE_SUBST_MSG.search(message or "")
    if not m:
        return False
    repl, found = m.group(1).strip(), m.group(2).strip()
    return repl.startswith("GitLab ") and not found.startswith("GitLab")


def _vale_span(raw, span, match):
    """0-based [s, e) of the match in the line, from Vale's 1-based Span, or the first occurrence."""
    if span and span[0] >= 1:
        s, e = span[0] - 1, span[1]
        if raw[s:e] == match:
            return s, e
    i = raw.find(match)
    if i < 0:
        i = raw.lower().find(match.lower())
    return (i, i + len(match)) if i >= 0 else (None, None)


# Text before a match that puts it at the start of a sentence, list item, table cell, or heading.
SENTENCE_START = re.compile(r"(?:^\s*(?:>\s*)*(?:(?:[-*+]|\d+[.)])\s+)?(?:\[[ xX]\]\s+)?|^#+\s+|^title:\s*|"
                            r"[.!?:]\s+|\|\s*)(?:\*\*|_|\")?$")


def at_sentence_start(before):
    return SENTENCE_START.search(before) is not None


def vale_fix(raw, s, e, match, repl, prose=None):
    """(suggested line or None, [options]) for a Vale `replace` action.

    No suggestion when the rule offers several options ("'X' or 'Y'"), when the match occurs
    more than once on the line (Vale's Span can point at the wrong one), or when the text
    around the match already holds part of the replacement ("GitLab Duo" for "Duo").
    The first letter keeps its case at the start of a sentence, list item, or table cell.
    """
    if "' or '" in repl:
        return None, [o.strip(" '\"") for o in repl.split("' or '")]
    word = r"(?<![\w-])" + re.escape(match) + r"(?![\w-])"
    if len(re.findall(word, prose if prose is not None else raw, re.I)) > 1:
        return None, []
    before, after = raw[:s], raw[e:]
    joined = before + match
    if len(repl) > len(match) and joined.endswith(repl) and not re.search(r"\w$", joined[:-len(repl)]):
        return None, []
    for i, ch in enumerate(repl):
        if ch == " " and before.endswith(repl[:i + 1]):
            return None, []
    if match[:1].isupper() and repl[:1].islower() and at_sentence_start(before):
        repl = repl[0].upper() + repl[1:]
    return raw[:s] + repl + raw[e:], []


# Vale alerts on uses the word list explicitly allows: an alert is dropped when
# the check matches, `match` matches Vale's Match (case-insensitive), and
# `after` matches the text right after the match. Each entry cites its anchor.
VALE_EXCEPTIONS = (
    {   # "within" is allowed for a time frame, limit, or boundary.
        "check": "gitlab_base.SubstitutionWarning", "match": r"^within$",
        "after": r"^\s+(?:[\w-]+\s+){0,3}?(?:milliseconds?|seconds?|minutes?|hours?|days?|weeks?|months?|years?|ms|"
                 r"window|windows|limits?|radius|range|boundary|boundaries|period|timeout|timeframe|time frame|quota)\b",
        "anchor": WL + "#within",
    },
    {   # "since" is allowed when it indicates a time frame.
        "check": "gitlab_base.SubstitutionWarning", "match": r"^since$",
        "after": r"^\s+(?:GitLab \d|v?\d+\.\d+|\d{4}\b|(?:January|February|March|April|May|June|July|August|"
                 r"September|October|November|December)\b|(?:the )?(?:last|previous|first|initial) |then\b|"
                 r"version \d)",
        "anchor": WL + "#since",
    },
    {   # "once" means one time, as in "once a day".
        "check": "gitlab_base.SubstitutionWarning", "match": r"^once a$",
        "after": r"^\s+(?:day|week|month|year|minute|hour|second)\b",
        "anchor": WL + "#once",
    },
)


def vale_exception(check, match, raw, e):
    """A reason string when VALE_EXCEPTIONS allows this use, else None."""
    for ex in VALE_EXCEPTIONS:
        if check.endswith(ex["check"]) and re.search(ex["match"], match, re.I) \
                and re.search(ex["after"], raw[e:], re.I):
            return "word list allows: " + ex["anchor"]
    return None


def split_across_line_break(doc, line, raw, s, message, match=""):
    """A reason when a rule only fires because the right term wraps: "GitLab"
    ends the previous line and "Self-Managed" starts this one. The right term
    comes from a substitution ("Use 'X' instead of 'Y'") or any quoted term in
    the message ("The offerings are 'GitLab Self-Managed' and ...")."""
    if raw[:s].strip(" \t>-*0123456789.") != "":
        return None
    m = VALE_SUBST_MSG.search(message)
    pairs = [(m.group(1).strip(), m.group(2).strip())] if m else []
    if match:
        pairs += [(t.strip(), match.strip()) for t in re.findall(r"'([^']+)'", message)]
    prev = doc.lines[line - 2].rstrip() if line >= 2 else ""
    for repl, found in pairs:
        if not repl.lower().endswith(found.lower()) or len(repl) <= len(found):
            continue
        prefix = repl[:len(repl) - len(found)].strip()
        if prefix and prev.lower().endswith(prefix.lower()):
            return "matches across a line break"
    return None


def oxford_comma_false_positive(doc, line, raw, s, e):
    """OxfordComma fires on 'A, B, C and' even when the list ends with ', and D' later, or when a
    parenthetical or code span with commas makes the list look longer than it is."""
    text = raw
    nxt = doc.line(line + 1)
    if not re.search(r"[.!?:]\s*$", raw) and nxt.strip() and doc.is_text(line + 1):
        text = raw + " " + nxt.strip()
    rest = text[e:]
    end = re.search(r"[.!?:](\s|$)", rest)
    rest = rest[:end.start()] if end else rest
    if re.search(r",\s+(?:and|or)\s", rest):
        return "OxfordComma: serial comma present later in the list"
    head = text[:s]
    sent = re.split(r"[.!?:]\s+", head)[-1] + text[s:e]
    for m in mdparse.INLINE_CODE_RE.finditer(sent):
        if "," in m.group(2):
            return "OxfordComma: code span with commas"
    if re.search(r"\([^()]*,[^()]*\)?", sent) or re.search(r"\([^()]*$", head):
        return "OxfordComma: parenthetical with commas"
    return None


def build_vocabulary(ctx):
    if not ctx.vocab_hits:
        return []
    groups = {}
    for check, term, f in ctx.vocab_hits:
        key = (check, term.lower())
        groups.setdefault(key, []).append((term, f))
    out = []
    for (check, _low), hits in sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        forms = {t for t, _ in hits}
        out.append({
            "term": sorted(forms)[0],
            "rule": "vale." + check,
            "count": len(hits),
            "files": [{"file": f["file"], "line": f["line"], "quote": f["quote"]} for _, f in hits[:20]],
        })
    return out


def gitlab_mdl_config(path):
    """GitLab's .markdownlint-cli2.yaml without `customRules`: they are JavaScript files in
    gitlab-org/gitlab that are not fetched, and never run from the network."""
    text = re.sub(r"(?m)^customRules:.*\n(?:[ \t]+-.*\n)*", "", _read(path))
    return patch_yaml_brackets(text)[0]


# ---------------------------------------------------------------------------
# markdownlint-cli2
# ---------------------------------------------------------------------------

MDL_CONFIGS = (".markdownlint-cli2.yaml", ".markdownlint-cli2.yml", ".markdownlint-cli2.jsonc",
               ".markdownlint-cli2.cjs", ".markdownlint-cli2.mjs", ".markdownlint.yaml", ".markdownlint.yml",
               ".markdownlint.json", ".markdownlint.jsonc")
MDL_LINE = re.compile(r"^(?P<file>[^\s].*?):(?P<line>\d+)(?::(?P<col>\d+))?\s+(?:(?:error|warning)\s+)?"
                      r"(?P<rule>[A-Za-z0-9-]+(?:/[A-Za-z0-9 _-]+)*)\s+(?P<desc>.*)$")
MDL_CONFIG_ERROR = re.compile(r"Unable to use configuration|YAMLException|deficient indentation|"
                              r"Unexpected token|SyntaxError|bad indentation", re.I)

# Used only when the project has no markdownlint config and GitLab's was never fetched.
MIN_MDL = {"config": {"default": True, "line-length": False, "no-inline-html": False, "no-trailing-spaces": False,
                      "no-duplicate-heading": {"siblings_only": True}, "ol-prefix": {"style": "one"},
                      "ul-style": {"style": "dash"}, "emphasis-style": False, "no-emphasis-as-heading": False}}


def find_mdl():
    exe = shutil.which("markdownlint-cli2")
    if exe:
        return [exe]
    # GitLab's own repos pin markdownlint-cli2 in package.json; `yarn install` puts it here.
    top = gitdiff.repo_root(os.getcwd()) or ""
    for root in dict.fromkeys(r for r in (top, os.getcwd()) if r):
        local = os.path.join(root, "node_modules", ".bin", "markdownlint-cli2")
        if os.access(local, os.X_OK):
            return [local]
    npx = shutil.which("npx")
    if npx:
        try:
            res = subprocess.run([npx, "--no-install", "markdownlint-cli2", "--help"], stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, universal_newlines=True, timeout=60)
            if "markdownlint-cli2" in (res.stdout + res.stderr) and res.returncode in (0, 2):
                return [npx, "--no-install", "markdownlint-cli2"]
        except (OSError, subprocess.SubprocessError):
            pass
    return None


def patch_yaml_brackets(text):
    """Re-indent closing `]`/`}` lines that sit at or left of their key, the error newer
    js-yaml versions reject (`deficient indentation`) and older ones accepted."""
    lines = text.split("\n")
    stack = []
    changed = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if re.search(r":\s*[\[{]\s*(#.*)?$", line):
            stack.append(len(line) - len(line.lstrip()))
            continue
        if stack and re.match(r"^[\]}],?\s*$", stripped):
            key_indent = stack.pop()
            ind = len(line) - len(line.lstrip())
            if ind <= key_indent:
                lines[i] = " " * (key_indent + 2) + stripped
                changed = True
    return "\n".join(lines), changed


def run_markdownlint(ctx, files):
    tool = {"ran": False}
    ctx.tools["markdownlint"] = tool
    cmd = find_mdl()
    if not cmd:
        info("markdownlint-cli2 not found (PATH, node_modules/.bin, or npx); skipping markdownlint.")
        tool["skipped"] = "markdownlint-cli2 not installed"
        return
    root = ctx.repo or os.getcwd()
    relpaths = [ctx.rel(f) for f in files]
    project_cfg = None
    for name in MDL_CONFIGS:
        if os.path.isfile(os.path.join(root, name)):
            project_cfg = os.path.join(root, name)
            break

    def run(cwd, paths):
        res = subprocess.run(cmd + paths, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             universal_newlines=True)
        return res.stdout + "\n" + res.stderr

    def copy_tree(dst):
        for rel in relpaths:
            out = os.path.join(dst, rel)
            os.makedirs(os.path.dirname(out), exist_ok=True)
            shutil.copyfile(os.path.join(root, rel), out)

    tmp = tempfile.mkdtemp(prefix="docs-review-mdl-")
    try:
        if project_cfg:
            tool["config"] = ctx.rel(project_cfg)
            out = run(root, relpaths)
            tool["mode"] = "direct"
            if MDL_CONFIG_ERROR.search(out) and not _mdl_issue_lines(out):
                tool["config_error"] = MDL_CONFIG_ERROR.search(out).group(0)
                with open(project_cfg, encoding="utf-8") as fh:
                    text, changed = patch_yaml_brackets(fh.read())
                copy_tree(tmp)
                with open(os.path.join(tmp, os.path.basename(project_cfg)), "w", encoding="utf-8") as fh:
                    fh.write(text)
                out = run(tmp, relpaths)
                tool["mode"] = "patched-config" if changed else "patched-config (no change)"
                if MDL_CONFIG_ERROR.search(out) and not _mdl_issue_lines(out):
                    info("markdownlint-cli2 cannot parse {} even after patching: {}".format(
                        ctx.rel(project_cfg), tool["config_error"]))
                    tool["mode"] = "config-unusable"
                    tool["skipped"] = "config parse error"
                    return
                info("markdownlint-cli2 could not parse {} ({}); ran with a patched copy in a temp dir."
                     .format(ctx.rel(project_cfg), tool["config_error"]))
            severity = "blocker"
        else:
            copy_tree(tmp)
            upstream = upstream_file(ctx, ".markdownlint-cli2.yaml")
            if upstream:
                name, text, tool["config"] = ".markdownlint-cli2.yaml", gitlab_mdl_config(upstream), \
                    "gitlab-org/gitlab .markdownlint-cli2.yaml"
            else:
                name, text, tool["config"] = ".markdownlint-cli2.jsonc", json.dumps(MIN_MDL), "built-in minimal config"
            with open(os.path.join(tmp, name), "w", encoding="utf-8") as fh:
                fh.write(text)
            out = run(tmp, relpaths)
            if upstream and MDL_CONFIG_ERROR.search(out) and not _mdl_issue_lines(out):
                # GitLab's config stopped parsing here: say so and use the minimal config.
                info("markdownlint-cli2 could not use GitLab's config ({}); using the minimal config."
                     .format(MDL_CONFIG_ERROR.search(out).group(0)))
                os.remove(os.path.join(tmp, name))
                with open(os.path.join(tmp, ".markdownlint-cli2.jsonc"), "w", encoding="utf-8") as fh:
                    fh.write(json.dumps(MIN_MDL))
                tool["config"] = "built-in minimal config"
                out = run(tmp, relpaths)
            tool["mode"] = "fallback-config"
            severity = "minor"
        tool["ran"] = True
        n = 0
        for m in _mdl_issue_lines(out):
            rel = m.group("file")
            if rel not in relpaths:
                continue
            abspath = os.path.join(root, rel)
            doc = ctx.parsed(abspath)
            if doc is None:
                continue
            names = m.group("rule").split("/")
            rid = names[0] if re.match(r"^MD\d+$", names[0]) else "-".join(names).replace(" ", "-")
            Emitter(ctx, doc, abspath)("markdownlint." + rid, int(m.group("line")),
                                       "{} ({}).".format(m.group("desc").strip(), m.group("rule")),
                                       severity=severity, source=MDL_DOC, reviewer="markdownlint", kind="lint")
            n += 1
        tool["issues"] = n
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _mdl_issue_lines(out):
    found = []
    for line in out.splitlines():
        line = line.strip()
        if line.startswith(("Finding:", "Linting:", "Summary:", "markdownlint-cli2 v")):
            continue
        m = MDL_LINE.match(line)
        if m:
            found.append(m)
    return found


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

SKIP_DIRS = {".git", "node_modules", "vendor", "public", "tmp", "docs-locale"}


def iter_markdown(paths):
    for p in paths:
        if os.path.isfile(p):
            if p.endswith(".md"):
                yield os.path.abspath(p)
            continue
        for dirpath, dirnames, filenames in os.walk(p):
            dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith("."))
            for name in sorted(filenames):
                if name.endswith(".md"):
                    yield os.path.abspath(os.path.join(dirpath, name))


def detect_docs_root(ctx):
    cand = ctx.args.docs_root or ctx.config.get("docs_root")
    if cand:
        base = ctx.repo or os.getcwd()
        return os.path.abspath(cand if os.path.isabs(cand) else os.path.join(base, cand))
    if ctx.repo:
        for c in page_class.DOCS_ROOT_CANDIDATES:
            if os.path.isdir(os.path.join(ctx.repo, c)):
                return os.path.join(ctx.repo, c)
    return None


def page_class_of(ctx, doc, abspath):
    """`release-notes` for a release notes page, else None (lib/page_class.py)."""
    roots = [ctx.rel(ctx.docs_root)] if ctx.docs_root else ["doc"]
    return page_class.page_class(ctx.rel(abspath), doc.front_matter, roots)


def lint_file(ctx, abspath):
    doc = ctx.parsed(abspath)
    if doc is None:
        return
    emit = Emitter(ctx, doc, abspath)
    if "redirect_to" in doc.front_matter:
        check_redirect(doc, emit, ctx, abspath)
        check_links(doc, emit, ctx, abspath)
        return
    doc.page_class = page_class_of(ctx, doc, abspath)
    if doc.page_class:
        ctx.page_classes[ctx.rel(abspath)] = doc.page_class
    check_front_matter(doc, emit, ctx)
    check_details(doc, emit, ctx)
    check_history_and_flags(doc, emit, ctx)
    check_alerts(doc, emit, ctx)
    check_product_terms(doc, emit, ctx)
    check_headings(doc, emit, ctx)
    check_links(doc, emit, ctx, abspath)
    check_fences(doc, emit, ctx)


def list_checks():
    rows = ["| ID | Area | Default severity | Importance | Source |",
            "|----|------|------------------|------------|--------|"]
    for rid, (area, sev, src, imp) in sorted(CHECKS.items()):
        rows.append("| `{}` | {} | {} | {} | {} |".format(rid, area, sev, imp, src))
    rows.append("| `vale.<Style>.<Rule>` | vale | error: blocker or major, warning: minor, suggestion: nit | "
                "lib/importance.py | rule link |")
    rows.append("| `markdownlint.<MDnnn>` | markdownlint | blocker with the project config, minor otherwise | "
                "4 for a blocker, else 1 | "
                + MDL_DOC + " |")
    return "\n".join(rows)


def parse_args(argv):
    p = argparse.ArgumentParser(
        prog="docs_lint.py",
        description="Deterministic GitLab docs checks (Vale, markdownlint, built-in rules). "
                    "Emits the docs-review findings schema.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Config (.docs-review.yml, optional): docs_root, vale_config, product_terms "
               "(list of {use, avoid: [...], severity}), lint_disable (rule ids or prefixes, `*` suffix allowed). "
               "Supported YAML subset: nested maps, block and flow lists, quoted scalars, comments; "
               "or a JSON object.\n\nExit codes: 0 no blocker, 1 blockers found, 2 usage or environment error.")
    p.add_argument("paths", nargs="*", help="Markdown files or directories (default: changed files, or docs root).")
    p.add_argument("--diff", metavar="BASE..HEAD", help="Only report findings on lines changed in this range.")
    p.add_argument("--changed-only", action="store_true",
                   help="Only report findings on changed lines (working tree vs HEAD unless --diff is given).")
    p.add_argument("--config", help="Path to .docs-review.yml (default: <repo>/.docs-review.yml if present).")
    p.add_argument("--docs-root", help="Docs root, for example doc or docs/source.")
    p.add_argument("--vale-config", help="Use this .vale.ini as is (overrides config `vale_config`).")
    p.add_argument("--vale-rules", metavar="DIR", help="A local doc/.vale directory with gitlab_base and gitlab_docs.")
    p.add_argument("--fetch-vale-rules", action="store_true",
                   help="Download GitLab's Vale rules and configs into ~/.cache/docs-review/vale now "
                        "(normal runs refresh them weekly).")
    p.add_argument("--no-vale", action="store_true", help="Skip Vale.")
    p.add_argument("--no-markdownlint", action="store_true", help="Skip markdownlint-cli2.")
    p.add_argument("--today", help="Reference date for redirect expiry: YYYY-MM-DD or an ISO 8601 timestamp, "
                                   "whose date part is used (default: today).")
    p.add_argument("--out", help="Write JSON to this file instead of stdout.")
    p.add_argument("--list-checks", action="store_true", help="Print the built-in checks as a Markdown table.")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.list_checks:
        print(list_checks())
        return 0
    if args.fetch_vale_rules:
        try:
            sha, dest = fetch_vale_rules()
        except Exception as exc:
            info("could not fetch Vale rules: {}".format(exc))
            return 2
        info("cached GitLab Vale rules at {} (gitlab-org/gitlab@{})".format(dest, sha))
        if not args.paths and not args.diff and not args.changed_only:
            return 0
    ctx = Context(args)
    if args.today:
        ctx.today = dates.parse_day(args.today)
        if ctx.today is None:
            info("--today must be YYYY-MM-DD or an ISO 8601 timestamp")
            return 2
    start = args.paths[0] if args.paths else os.getcwd()
    if not os.path.exists(start):
        info("path not found: {}".format(start))
        return 2
    ctx.repo = gitdiff.repo_root(start)
    cfg_path = args.config or (os.path.join(ctx.repo, ".docs-review.yml") if ctx.repo else None)
    if args.config and not os.path.isfile(args.config):
        info("config not found: {}".format(args.config))
        return 2
    # With --diff, read the config at the base of the change, so the change
    # cannot turn off its own checks (`lint_disable`, `product_terms`).
    base = lint_config.base_of(ctx.repo, args.diff) if (args.diff and ctx.repo and not args.config) else None
    try:
        ctx.config = lint_config.load_at(ctx.repo, base, warn=info) if base else lint_config.load(cfg_path, warn=info)
    except lint_config.ConfigError as exc:
        info("{}: {}".format(cfg_path, exc))
        return 2
    ctx.config_path = cfg_path if cfg_path and os.path.isfile(cfg_path) else None
    ctx.product_terms_source = "project config " + ctx.rel(ctx.config_path) if ctx.config_path else WL
    ctx.disabled_ids = [str(x) for x in (ctx.config.get("lint_disable") or [])]
    ctx.docs_root = detect_docs_root(ctx)
    if ctx.repo and ctx.docs_root and os.path.normpath(ctx.docs_root) == os.path.join(ctx.repo, "doc") \
            and os.path.isdir(os.path.join(ctx.repo, "doc", ".vale", "gitlab_base")):
        ctx.layout = "gitlab"

    changed = None
    if args.diff or args.changed_only:
        if not ctx.repo:
            info("--diff and --changed-only need a git repository")
            return 2
        try:
            changed = gitdiff.changed_lines(ctx.repo, args.diff, None)
        except gitdiff.GitError as exc:
            info(str(exc))
            return 2
    if args.paths:
        files = list(iter_markdown(args.paths))
    elif changed is not None:
        files = [os.path.join(ctx.repo, p) for p in sorted(changed) if p.endswith(".md")
                 and os.path.isfile(os.path.join(ctx.repo, p))
                 and (not ctx.docs_root or _under(os.path.join(ctx.repo, p), ctx.docs_root))]
    elif ctx.docs_root:
        files = list(iter_markdown([ctx.docs_root]))
    else:
        info("no paths given and no docs root found")
        return 2
    if changed is not None:
        files = [f for f in files if ctx.rel(f) in changed]

    for f in files:
        lint_file(ctx, f)
    check_vale_config(ctx, files, changed)
    if files and not args.no_vale:
        run_vale(ctx, files)
    if files and not (ctx.tools.get("vale") or {}).get("ran"):
        for f in files:  # Vale's FrontMatter rule did not run: flag pages that have none
            doc = ctx.parsed(f)
            if doc is not None and doc.front_matter_range is None and "redirect_to" not in doc.front_matter:
                Emitter(ctx, doc, f)("lint.front-matter-missing", 1, "Add front matter with `title`, "
                                     "`description`, `stage`, `group`, and `info`.")
    if files and not args.no_markdownlint:
        run_markdownlint(ctx, files)

    findings = []
    for f in ctx.findings:
        if F.validate_finding(f) or not f.get("quote") or not f.get("source"):
            continue
        if changed is not None:
            lines = changed.get(f["file"], set())
            if not any(n in lines for n in range(f["line"], (f.get("end_line") or f["line"]) + 1)):
                continue
        findings.append(f)
    findings.sort(key=lambda f: (f["file"], f["line"], F.severity_rank(f["severity"]), f["id"]))
    kept = {id(f) for f in findings}
    ctx.vocab_hits = [h for h in ctx.vocab_hits if id(h[2]) in kept]
    target = {
        "paths": [ctx.rel(p) for p in args.paths] if args.paths else None,
        "repo": ctx.repo,
        "docs_root": ctx.rel(ctx.docs_root) if ctx.docs_root else None,
        "layout": ctx.layout,
        "diff": args.diff,
        "changed_only": bool(changed is not None),
        "files": len(files),
        "tools": ctx.tools,
        # Pages whose class changes the rules, such as `release-notes` (lib/page_class.py).
        "page_classes": dict(sorted(ctx.page_classes.items())),
    }
    if args.diff and ctx.repo:
        parts = re.split(r"\.\.\.?", args.diff)
        try:
            target["base"] = gitdiff._git(ctx.repo, ["rev-parse", parts[0]]).strip()
            target["head"] = gitdiff._git(ctx.repo, ["rev-parse", parts[1] or "HEAD"]).strip()
        except (gitdiff.GitError, IndexError):
            pass
    out = F.new_doc(target, findings, vocabulary=build_vocabulary(ctx))
    text = F.dump(out, args.out)
    if not args.out:
        sys.stdout.write(text)
    counts = {}
    for f in findings:
        counts[f["severity"]] = counts.get(f["severity"], 0) + 1
    info("{} files, {} findings ({})".format(len(files), len(findings),
                                             ", ".join("{} {}".format(v, k) for k, v in sorted(
                                                 counts.items(), key=lambda kv: F.severity_rank(kv[0]))) or "none"))
    return 1 if F.has_blocker(findings) else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, UnicodeError, ValueError, RuntimeError) as exc:  # a one-line error, not a traceback
        if os.environ.get("DOCS_REVIEW_DEBUG"):
            raise
        sys.stderr.write("{}: error: {}\n".format(sys.argv[0].rsplit("/", 1)[-1], exc))
        sys.exit(2)
