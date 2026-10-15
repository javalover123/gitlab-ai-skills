#!/usr/bin/env python3
"""Pick the review tier for a docs change, from the diff alone. No model.

Output: tier, signals, reader scope, first-time writer, technical writer,
base and head. Rules: references/triage.md. Exit 0, or 2 on a usage error.
"""

import argparse
import difflib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import codeowners, gitdiff, gitlab_api, lint_config, page_class  # noqa: E402
from lib.mdparse import slugify  # noqa: E402  (same anchors as impact.py)

TIERS = ["low", "medium", "high", "severe"]

DEFAULT_FIRST_TIME_THRESHOLD = 3
# Most earlier merged MRs whose diffs are read for the first-time check.
FIRST_TIME_SCAN = 40
# Signals that make the reader walk every task on the page, at any tier.
READER_FULL_SIGNALS = ("new-page", "procedure-change")

# Docs roots tried when the config has no docs_root.
# Every docs tree counts, translations included (doc-locale/ is tiered like English).
DEFAULT_DOCS_ROOTS = list(page_class.DOCS_ROOT_CANDIDATES) + ["doc-locale"]

# High-impact page classes: legal, privacy, pricing, subscriptions, releases.
DEFAULT_SEVERE_PATHS = [
    "**/legal/**", "**/*privacy*", "**/*pricing*", "**/*billing*",
    "**/subscriptions/**", "**/*licensing*", "**/releases/**",
    "**/release-posts*", "**/release_posts*", "**/*deprecations*", "**/*removals*",
]
# Section landing and getting-started pages: high, not severe.
DEFAULT_ENTRY_PATHS = [
    "**/get_started/**", "**/get-started*", "**/getting-started*",
    "**/getting_started*", "**/quickstart*", "**/_index.md", "**/index.md",
]

# A medium change with this many changed prose lines is high (large-rewrite).
LARGE_REWRITE_LINES = 150
# Word pairs at or above this similarity count as a spelling fix ("teh" -> "the").
TYPO_SIMILARITY = 0.75
# At most this many changed words in one change group still count as a typo fix.
TYPO_MAX_WORDS = 3

STOPWORDS = {"a", "an", "the", "to", "of", "and", "or", "in", "on", "for", "is", "are"}
NUMBER_WORDS = {"0": "zero", "1": "one", "2": "two", "3": "three", "4": "four",
                "5": "five", "6": "six", "7": "seven", "8": "eight", "9": "nine"}

RE_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
RE_FENCE = re.compile(r"^\s*(`{3,}|~{3,})\s*([\w+-]*)")
RE_OLIST = re.compile(r"^\s*\d+\.\s")
RE_TABLE = re.compile(r"^\s*\|")
RE_LIST_MARKER = re.compile(r"^(\s*)(?:[*+-]|\d+\.)\s+")
RE_LINK_TARGET = re.compile(r"\]\([^)]*\)")
RE_URL = re.compile(r"https?://\S+")
RE_HISTORY_LINE = re.compile(
    r"(\{\{<\s*/?history|\b(Introduced|Generally available|Enabled on|Disabled by default|"
    r"Enabled by default|Feature flag|with a feature flag|Moved|Deprecated|Removed)\b.*"
    r"\bGitLab\s+\d+\.\d+|\[!flag\]|default_enabled)", re.IGNORECASE)
RE_DETAILS_LINE = re.compile(r"(\{\{<\s*/?details|^\s*-\s*(Tier|Offering|Status|Add-on):)")
RE_DEPRECATION = re.compile(r"(\(deprecated\)|\(removed\)|start_remove|end_remove|"
                            r"\bdeprecated in GitLab\b|\bremoved in GitLab\b)", re.IGNORECASE)
RE_CARDS = re.compile(r"\{\{<\s*cards\s*>\}\}")
RE_REDIRECT = re.compile(r"^redirect_to:\s*\S", re.MULTILINE)
RE_REFERENCE_PATH = re.compile(r"(^|/)(api|reference|cli|commands?)(/|[_.-])", re.IGNORECASE)
RE_ATTR_TABLE = re.compile(r"^\s*\|\s*(Attribute|Parameter|Option|Flag|Setting|Variable)\s*\|",
                           re.IGNORECASE | re.MULTILINE)
RE_TOKEN = re.compile(r"`[^`]*`|\*\*[^*]+\*\*|\w[\w.'/-]*|[^\w\s]")
RE_NUMBER = re.compile(r"\d")


class UsageError(Exception):
    pass


# --- config ------------------------------------------------------------------

def load_config(text, source):
    """`.docs-review.yml` (or JSON) as a dict; a parse error is a usage error."""
    try:
        return lint_config.parse(text) if text.strip() else {}
    except lint_config.ConfigError as exc:
        raise UsageError("config %s: %s" % (source, exc))


def as_list(value, key):
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list) and all(isinstance(v, str) for v in value):
        return value
    raise UsageError("config key %s must be a string or a list of strings" % key)


# --- git and diff --------------------------------------------------------------

def git(repo, *args, check=True):
    try:
        return gitdiff.run(repo, args, check=check)
    except gitdiff.GitError as exc:
        raise UsageError(str(exc))


def show_file(repo, ref, path):
    """File content at ref, or None if it does not exist there."""
    if ref is None:
        full = os.path.join(repo, path)
        if os.path.isfile(full):
            with open(full, encoding="utf-8", errors="replace") as handle:
                return handle.read()
        return None
    proc = git(repo, "show", "%s:%s" % (ref, path), check=False)
    return proc.stdout if proc.returncode == 0 else None


class FileDiff:
    def __init__(self, old_path, new_path):
        self.old_path = old_path
        self.new_path = new_path
        self.status = "M"
        self.groups = []  # list of (removed[(lineno, text)], added[(lineno, text)])

    @property
    def path(self):
        return self.new_path if self.status != "D" else self.old_path


def parse_unified_diff(text):
    files = []
    cur = None
    removed, added = [], []
    old_no = new_no = 0
    in_hunk = False

    def flush():
        if cur is not None and (removed or added):
            cur.groups.append((list(removed), list(added)))
        del removed[:]
        del added[:]

    for line in text.splitlines():
        if line.startswith("diff --git "):
            flush()
            in_hunk = False
            m = re.match(r"^diff --git (?:\"?a/(.*?)\"?) (?:\"?b/(.*?)\"?)$", line)
            old, new = (m.group(1), m.group(2)) if m else ("", "")
            cur = FileDiff(old, new)
            files.append(cur)
            continue
        if cur is None:
            continue
        if not in_hunk:
            if line.startswith("new file mode"):
                cur.status = "A"
            elif line.startswith("deleted file mode"):
                cur.status = "D"
            elif line.startswith("rename from "):
                cur.status = "R"
                cur.old_path = line[len("rename from "):]
            elif line.startswith("rename to "):
                cur.new_path = line[len("rename to "):]
            elif line.startswith("copy to "):
                cur.status = "A"
                cur.new_path = line[len("copy to "):]
            elif line.startswith("Binary files"):
                pass  # binary file: no text lines
            elif line.startswith("--- "):
                if line[4:].strip() == "/dev/null":
                    cur.status = "A"
                continue
            elif line.startswith("+++ "):
                if line[4:].strip() == "/dev/null":
                    cur.status = "D"
                continue
        m = re.match(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
        if m:
            flush()
            in_hunk = True
            old_no, new_no = int(m.group(1)), int(m.group(2))
            continue
        if not in_hunk:
            continue
        if line.startswith("-"):
            removed.append((old_no, line[1:]))
            old_no += 1
        elif line.startswith("+"):
            added.append((new_no, line[1:]))
            new_no += 1
        elif line.startswith("\\"):
            continue
        else:
            flush()
            old_no += 1
            new_no += 1
    flush()
    return files


def apply_name_status(files, text):
    by_new = {f.new_path: f for f in files}
    by_old = {f.old_path: f for f in files}
    for line in text.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        code = parts[0][:1]
        if code in ("R", "C") and len(parts) >= 3:
            fd = by_new.get(parts[2]) or by_old.get(parts[1])
            if fd is None:
                fd = FileDiff(parts[1], parts[2])
                files.append(fd)
            fd.old_path, fd.new_path = parts[1], parts[2]
            fd.status = "R" if code == "R" else "A"
        else:
            fd = by_new.get(parts[1]) or by_old.get(parts[1])
            if fd is None:
                fd = FileDiff(parts[1], parts[1])
                files.append(fd)
            if code in ("A", "D", "M"):
                fd.status = code


# --- classification helpers ----------------------------------------------------

def matches_any(path, patterns):
    return any(codeowners.glob_regex(p).match(path) for p in patterns)


def docs_root_for(path, roots):
    for root in sorted(roots, key=len, reverse=True):
        r = root.strip("/")
        if r and (path == r or path.startswith(r + "/")):
            return r
    return None


def is_docs_file(path, roots):
    return path.endswith(".md") and docs_root_for(path, roots) is not None


def landing_patterns(roots, extra):
    """Severe landing pages: the docs root landing page plus `landing_paths`."""
    pats = list(extra)
    for root in roots:
        r = root.strip("/")
        pats += ["/%s/_index.md" % r, "/%s/index.md" % r]
    return pats


def slug(heading):
    """Hugo anchor for a heading; a custom {#id} wins."""
    custom = re.search(r"\{#([A-Za-z0-9_-]+)[^}]*\}\s*$", heading)
    if custom:
        return custom.group(1)
    return slugify(heading)


def scan_regions(content):
    """Map 1-based line numbers to a set of region names."""
    regions = {}
    if content is None:
        return regions
    lines = content.splitlines()
    in_front = bool(lines) and lines[0].strip() == "---"
    fence = None
    history = details = flag = prereq = False
    for no, line in enumerate(lines, 1):
        tags = set()
        stripped = line.strip()
        if in_front:
            tags.add("frontmatter")
            if no > 1 and stripped == "---":
                in_front = False
            regions[no] = tags
            continue
        fm = RE_FENCE.match(line)
        if fence is not None:
            tags.add("code")
            if fm and fm.group(1)[0] == fence[0] and len(fm.group(1)) >= len(fence) \
                    and not fm.group(2):
                fence = None
            regions[no] = tags
            continue
        if fm:
            fence = fm.group(1)
            tags.add("code")
            regions[no] = tags
            continue
        if re.search(r"\{\{<\s*history", line):
            history = True
        if re.search(r"\{\{<\s*details", line):
            details = True
        if history:
            tags.add("history")
        if details:
            tags.add("details")
        if re.search(r"\{\{<\s*/history", line):
            history = False
        if re.search(r"\{\{<\s*/details", line):
            details = False
        if stripped.startswith("> [!flag]"):
            flag = True
        elif not stripped.startswith(">"):
            flag = False
        if flag:
            tags.add("history")
        if RE_HEADING.match(line):
            tags.add("heading")
            prereq = False
        if RE_TABLE.match(line):
            tags.add("table")
        if RE_OLIST.match(line):
            tags.add("olist")
        if re.match(r"^\s*Prerequisites\b", stripped):
            prereq = True
            tags.add("prereq")
        elif prereq:
            if stripped == "" or RE_LIST_MARKER.match(line) or line.startswith("  "):
                tags.add("prereq")
            else:
                prereq = False
        regions[no] = tags
    return regions


def normalize(line):
    line = RE_LIST_MARKER.sub(lambda m: m.group(1) + "- ", line)
    return re.sub(r"\s+", " ", line).strip()


def strip_links(text):
    return RE_URL.sub("<url>", RE_LINK_TARGET.sub("](<link>)", text))


def tokens(text):
    return RE_TOKEN.findall(text)


def is_fact_token(tok):
    """Code spans, bold UI labels, and numbers must match the product exactly."""
    return tok.startswith(("`", "**")) or bool(RE_NUMBER.search(tok))


RE_QUOTE_MARKER = re.compile(r"^\s*(?:>\s?)+")


def is_formatting_only(removed, added):
    """Same text, same number of list items: only whitespace, list markers, or
    line breaks changed, also inside a blockquote. combine_findings.py uses it."""
    def flat(lines):
        parts = [normalize(RE_QUOTE_MARKER.sub("", t)) for t in lines]
        return " ".join(p for p in parts if p)

    def items(lines):
        return sum(1 for t in lines if RE_LIST_MARKER.match(RE_QUOTE_MARKER.sub("", t)))

    def quoted(lines):
        return [bool(RE_QUOTE_MARKER.match(t)) for t in lines if t.strip()][:1]

    if not removed or not added or quoted(removed) != quoted(added):
        return False  # a pure insertion, or text moved into or out of a blockquote
    return flat(removed) == flat(added) and items(removed) == items(added)


def classify_text_change(removed, added):
    """Return one of: whitespace, reorder, link, typo, fact, semantic."""
    old = [normalize(t) for t in removed]
    new = [normalize(t) for t in added]
    if [o for o in old if o] == [n for n in new if n] or is_formatting_only(removed, added):
        return "whitespace"
    if old and new and sorted(o for o in old if o) == sorted(n for n in new if n):
        return "reorder"
    old_text, new_text = " ".join(old), " ".join(new)
    if strip_links(old_text) == strip_links(new_text):
        return "link"
    if not old or not new:
        # Pure insertion or deletion of prose changes what readers are told.
        return "fact" if any(is_fact_token(t) for t in tokens(old_text + " " + new_text)) \
            else "semantic"
    a, b = tokens(old_text), tokens(new_text)
    changed_words, fact = 0, False
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if op == "equal":
            continue
        olds, news = a[i1:i2], b[j1:j2]
        for tok in olds + news:
            if is_fact_token(tok):
                fact = True
        words_old = [t for t in olds if re.match(r"\w", t)]
        words_new = [t for t in news if re.match(r"\w", t)]
        if op == "replace" and len(words_old) == len(words_new):
            for wo, wn in zip(words_old, words_new):
                if wo.lower() == wn.lower():
                    continue
                if NUMBER_WORDS.get(wo) == wn.lower() or NUMBER_WORDS.get(wn) == wo.lower():
                    fact = fact and not (wo.isdigit() or wn.isdigit())
                    changed_words += 1
                    continue
                if difflib.SequenceMatcher(None, wo.lower(), wn.lower()).ratio() < TYPO_SIMILARITY:
                    return "fact" if fact else "semantic"
                changed_words += 1
        else:
            for tok in words_old + words_new:
                if tok.lower() not in STOPWORDS:
                    return "fact" if fact else "semantic"
                changed_words += 1
    if fact:
        return "fact"
    return "typo" if changed_words <= TYPO_MAX_WORDS else "semantic"


COSMETIC = {"whitespace": "formatting", "reorder": "reorder", "link": "link-fix", "typo": "typo"}


class Triage:
    def __init__(self, config, repo, base_ref, head_ref, first_time=None):
        self.config = config
        self.first_time = first_time or {"value": None, "source": "not checked"}
        self.repo = repo
        self.base_ref = base_ref
        self.head_ref = head_ref
        root = config.get("docs_root")
        self.roots = as_list(root, "docs_root") if root else list(DEFAULT_DOCS_ROOTS)
        self.severe = DEFAULT_SEVERE_PATHS + as_list(config.get("severe_paths"), "severe_paths")
        self.landing = landing_patterns(self.roots, as_list(config.get("landing_paths"),
                                                             "landing_paths"))
        nav = config.get("nav_file")
        self.nav_files = [nav] if isinstance(nav, str) else []
        self.signals = []
        self.code_files = self.semantic_lines = 0

    def add(self, sid, tier, path, line, detail):
        key = (sid, path, line)
        if any((s["id"], s["file"], s["line"]) == key for s in self.signals):
            return
        self.signals.append({"id": sid, "tier": tier, "file": path, "line": line,
                             "detail": detail})

    def content(self, ref, path):
        return show_file(self.repo, ref, path)

    def run(self, files):
        docs = []
        for fd in files:
            path = fd.path
            if path in self.nav_files or path.endswith("navigation.yaml"):
                self.add("nav-change", "medium", path, None,
                         "Global navigation changed; check titles, URLs, and duplicates.")
                continue
            if is_docs_file(path, self.roots) or \
                    (fd.status == "R" and is_docs_file(fd.old_path, self.roots)):
                docs.append(fd)
            elif not path.endswith(".md") and docs_root_for(path, self.roots) is None:
                self.code_files += 1
        for fd in docs:
            self.triage_file(fd)
        if self.code_files:
            self.add("code-change", None, None, None,
                     "%d non-docs file(s) changed; impact checks for docs that must change too."
                     % self.code_files)
        return self.result(docs)

    def page_class(self, fd, head_content, base_content):
        """(signal id, tier, detail) for the page, or (None, None, None)."""
        paths = [p for p in (fd.path, fd.old_path) if p]
        for path in paths:
            if matches_any(path, self.severe):
                return "severe-page", "severe", "Path matches a high-impact page class (%s)." % path
            if matches_any(path, self.landing):
                return "landing-page", "severe", "Docs landing page (%s)." % path
        for path in paths:
            if matches_any(path, DEFAULT_ENTRY_PATHS):
                return "entry-page", "high", "Section landing or getting-started page (%s)." % path
        for text in (head_content, base_content):
            if text and RE_CARDS.search(text):
                return "entry-page", "high", "Page uses the cards shortcode, so it is a section landing page."
        return None, None, None

    def triage_file(self, fd):
        path = fd.path
        head = self.content(self.head_ref, path) if fd.status != "D" else None
        base = self.content(self.base_ref, fd.old_path) if fd.status != "A" else None
        if self.base_ref is None and fd.status != "A":
            base = None  # diff-file mode: only the working tree is available
        changed = changed_lines(fd)
        cls, cls_tier, why = self.page_class(fd, head, base)
        if cls:
            self.add(cls, cls_tier, path, None, why)
        if page_class.is_release_notes(path, page_class.front_matter_of(head if head is not None else base),
                                       self.roots):
            # Not a tier signal: it tells reviewers which rules apply (lib/page_class.py).
            self.add(page_class.RELEASE_NOTES, None, path, None,
                     "Release notes page: it follows the release notes templates, so the standard front matter "
                     "keys, availability details, and topic type rules for tasks do not apply.")
        removed_text = "\n".join(t for r, _ in fd.groups for _, t in r)
        added_text = "\n".join(t for _, a in fd.groups for _, t in a)
        if fd.status == "A":
            body = head if head is not None else added_text
            if RE_REDIRECT.search(body or ""):
                self.add("redirect-added", "low", path, None, "New redirect stub.")
            else:
                self.add("new-page", "high", path, None, "New page.")
                self.semantic_lines += changed
                if re.search(r"^\s*(```|~~~)", body or "", re.MULTILINE):
                    self.add("code-block-change", "medium", path, None,
                             "New page contains code blocks.")
            return
        if fd.status == "D":
            body = base if base is not None else removed_text
            if RE_REDIRECT.search(body or ""):
                self.add("redirect-removed", "low", path, None, "Expired redirect stub removed.")
            else:
                self.add("deleted-page", "high", path, None,
                         "Page deleted; it needs a redirect, and inbound links break.")
            return
        if fd.status == "R":
            self.add("page-renamed", "high", path, None,
                     "Page renamed from %s; it needs a redirect, and inbound links break."
                     % fd.old_path)
        head_regions = scan_regions(head)
        base_regions = scan_regions(base)
        for removed, added in fd.groups:
            self.triage_group(path, removed, added, head_regions, base_regions)

    def triage_group(self, path, removed, added, head_regions, base_regions):
        line = added[0][0] if added else (removed[0][0] if removed else None)
        regions = set()
        for no, text in removed:
            regions |= base_regions.get(no, set()) or self.guess_regions(text)
        for no, text in added:
            regions |= head_regions.get(no, set()) or self.guess_regions(text)
        r_text = [t for _, t in removed]
        a_text = [t for _, t in added]
        kind = classify_text_change(r_text, a_text)
        n = len(removed) + len(added)
        joined_added = "\n".join(a_text)
        joined_all = "\n".join(r_text + a_text)

        # Headings: anchors change when the slug changes, even for a typo fix.
        old_slugs = [slug(RE_HEADING.match(t).group(2)) for t in r_text if RE_HEADING.match(t)]
        new_slugs = [slug(RE_HEADING.match(t).group(2)) for t in a_text if RE_HEADING.match(t)]
        for s in old_slugs:
            if s not in new_slugs:
                sid = "heading-renamed" if new_slugs else "heading-removed"
                self.add(sid, "medium", path, line,
                         "Anchor #%s no longer exists; inbound links break." % s)
        if new_slugs and not old_slugs:
            self.add("new-topic", "medium", path, line, "New topic: #%s." % new_slugs[0])

        if regions == {"frontmatter"} or (regions and regions <= {"frontmatter"}):
            if re.search(r"^redirect_to:", joined_added, re.MULTILINE):
                self.add("page-moved", "high", path, line,
                         "Page turned into a redirect; nav and inbound links change.")
            else:
                self.add("frontmatter-only", "low", path, line, "Front matter edit.")
            return

        cosmetic = kind in COSMETIC
        if RE_DEPRECATION.search(joined_added) and not cosmetic:
            self.add("deprecation", "high", path, line, "Deprecation or removal content.")
        if ("history" in regions or RE_HISTORY_LINE.search(joined_all)):
            if cosmetic:
                self.add("history-touched", "low", path, line, "Cosmetic edit in history or flag text.")
            else:
                self.add("history-change", "high", path, line,
                         "History, feature flag, or version change.")
        if "details" in regions or RE_DETAILS_LINE.search(joined_all):
            if cosmetic:
                self.add("details-touched", "low", path, line, "Cosmetic edit in availability details.")
            else:
                self.add("details-change", "high", path, line,
                         "Availability details (tier, offering, status, add-on) changed.")
        if "code" in regions and kind != "whitespace":
            self.add("code-block-change", "medium", path, line, "Code block changed.")
        if cosmetic:
            self.add(COSMETIC[kind], "low", path, line, "Cosmetic change (%s)." % kind)
            return
        self.semantic_lines += n
        if regions & {"olist", "prereq"}:
            self.add("procedure-change", "high", path, line, "Steps or prerequisites changed.")
        if "table" in regions:
            head = self.content(self.head_ref, path) or ""
            if RE_REFERENCE_PATH.search(path) or RE_ATTR_TABLE.search(head):
                self.add("reference-change", "high", path, line, "Reference table changed.")
            else:
                self.add("table-change", "medium", path, line, "Table content changed.")
        if kind == "fact":
            self.add("fact-change", "high", path, line,
                     "A number, version, or code span changed; verify against source.")
        prose = regions - {"heading", "code", "history", "details", "frontmatter"}
        if prose or not regions:
            self.add("prose-change", "medium", path, line, "Prose meaning changed.")

    @staticmethod
    def guess_regions(text):
        tags = set()
        if RE_HEADING.match(text):
            tags.add("heading")
        if RE_TABLE.match(text):
            tags.add("table")
        if RE_OLIST.match(text):
            tags.add("olist")
        if RE_HISTORY_LINE.search(text):
            tags.add("history")
        if RE_DETAILS_LINE.search(text):
            tags.add("details")
        if RE_FENCE.match(text):
            tags.add("code")
        return tags

    def result(self, docs):
        tier = "low"
        if docs:
            tier = max((s["tier"] for s in self.signals if s["tier"]), key=TIERS.index, default="low")
            if tier == "medium" and self.semantic_lines >= LARGE_REWRITE_LINES:
                self.add("large-rewrite", "high", None, None,
                         "%d changed prose lines: review it like a new page." % self.semantic_lines)
                tier = "high"
        ids = set(s["id"] for s in self.signals)
        full = bool(docs) and (bool(ids & set(READER_FULL_SIGNALS)) or self.first_time.get("value") is True)
        drivers = [s for s in self.signals if s["tier"] == tier] if docs else []
        small = sum(changed_lines(d) for d in docs) < INLINE_LINE_LIMIT
        return {
            "tier": tier,
            "subagents": not (tier == "low" and small),
            "signals": self.signals,
            "reader": {"scope": "full" if full else "changed"},
            "first_time_writer": self.first_time,
            "technical_writer": self.technical_writer(drivers, docs),
            "base": self.base_ref,
            "head": self.head_ref,
        }

    def technical_writer(self, drivers, docs):
        """The writer from the config, or the CODEOWNERS owner (at the base ref)
        of the most changed lines; ties go to the owner of a file that drove
        the tier."""
        writer = self.config.get("technical_writer")
        if isinstance(writer, str) and writer.strip():
            return writer.strip().lstrip("@")
        text = None
        for loc in codeowners.LOCATIONS:
            text = self.content(self.base_ref, loc) if docs else None
            if text is not None:
                break
        if text is None:
            return None
        driving = set(s["file"] for s in drivers if s["file"])
        lines, drives = {}, {}
        for d in docs:
            owner = codeowners.first_owner(text, d.path)
            if owner:
                lines[owner] = lines.get(owner, 0) + changed_lines(d)
                drives[owner] = drives.get(owner, False) or d.path in driving
        return min(lines, key=lambda w: (-lines[w], not drives[w], w), default=None)


# A low tier change under this many changed docs lines gets one inline
# correctness pass instead of reviewer subagents (references/triage.md).
INLINE_LINE_LIMIT = 20


def changed_lines(d):
    return sum(len(removed) + len(added) for removed, added in d.groups)


def first_time_threshold(config):
    raw = config.get("first_time_threshold")
    try:
        n = int(raw) if raw is not None else DEFAULT_FIRST_TIME_THRESHOLD
    except (TypeError, ValueError):
        n = DEFAULT_FIRST_TIME_THRESHOLD
    return n if n >= 0 else DEFAULT_FIRST_TIME_THRESHOLD


def first_time_writer(args, config):
    """True when the author has fewer than `first_time_threshold` earlier merged
    docs MRs in the project. Read-only `glab api` calls; None when unknown."""
    threshold = first_time_threshold(config)
    out = {"value": None, "source": "not checked", "threshold": threshold}
    if args.first_time_writer:
        out.update(value=True, source="flag")
        return out
    if not args.project or not (args.mr or args.author):
        return out
    root = config.get("docs_root")
    roots = as_list(root, "docs_root") if root else list(DEFAULT_DOCS_ROOTS)
    api = gitlab_api.GitLab(args.glab)
    pid = gitlab_api.enc(args.project)
    author, before = args.author, None
    try:
        if args.mr:
            mr = api.get("projects/%s/merge_requests/%d" % (pid, args.mr)) or {}
            author = author or ((mr.get("author") or {}).get("username") if isinstance(mr, dict) else None)
            before = before or (mr.get("created_at") if isinstance(mr, dict) else None)
        if not author:
            out["source"] = "no MR author"
            return out
        q = gitlab_api.query({"author_username": author, "state": "merged", "created_before": before,
                              "order_by": "created_at", "sort": "desc", "scope": "all"})
        mrs, _ = api.get_pages("projects/%s/merge_requests?%s" % (pid, q), per_page=FIRST_TIME_SCAN, max_pages=1)
        count, scanned = 0, 0
        for m in mrs:
            if count >= threshold or scanned >= FIRST_TIME_SCAN:
                break
            iid = m.get("iid") if isinstance(m, dict) else None
            if not isinstance(iid, int) or iid == args.mr:
                continue
            scanned += 1
            diffs, _ = api.get_pages("projects/%s/merge_requests/%d/diffs" % (pid, iid), per_page=100, max_pages=3)
            if any(is_docs_file(d.get("new_path") or "", roots) or is_docs_file(d.get("old_path") or "", roots)
                   for d in diffs if isinstance(d, dict)):
                count += 1
    except gitlab_api.GlabError as exc:
        out.update(source="glab api failed: %s" % str(exc)[:160])
        return out
    out.update(value=count < threshold, source="glab api", author=author, merged_docs_mrs=count)
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Deterministic docs review tier (low, medium, high, severe) from a diff. "
                    "Rules: references/triage.md.",
        epilog="Exit codes: 0 success, 2 usage or environment error.")
    parser.add_argument("--base", help="Base ref or SHA (git mode).")
    parser.add_argument("--head", default="HEAD", help="Head ref or SHA (default: HEAD).")
    parser.add_argument("--diff-file", help="Unified diff to read instead of running git.")
    parser.add_argument("--repo", default=".", help="Repository directory (default: .).")
    parser.add_argument("--config", help="Config file (YAML subset or JSON). Default: "
                        ".docs-review.yml at the base ref, so an MR cannot change its own tier.")
    parser.add_argument("--out", help="Write JSON here instead of stdout.")
    parser.add_argument("--project", help="Project path (group/project), for the first-time writer check.")
    parser.add_argument("--mr", type=int, help="MR IID, for the first-time writer check (reads its author).")
    parser.add_argument("--author", help="MR author username, instead of reading it from --mr.")
    parser.add_argument("--first-time-writer", action="store_true",
                        help="Offline: the author is a first-time docs writer (no API call).")
    parser.add_argument("--glab", default=None, help="glab binary (default: $DOCS_REVIEW_GLAB or glab).")
    args = parser.parse_args(argv)
    try:
        if not args.base and not args.diff_file:
            raise UsageError("give --base <ref> (git mode) or --diff-file <file>")
        if args.base and args.diff_file:
            raise UsageError("use either --base or --diff-file, not both")
        repo = args.repo
        if not os.path.isdir(repo):
            raise UsageError("repo directory not found: %s" % repo)
        if args.diff_file:
            try:
                with open(args.diff_file, encoding="utf-8", errors="replace") as handle:
                    diff_text = handle.read()
            except OSError as exc:
                raise UsageError("cannot read diff file: %s" % exc)
            files = parse_unified_diff(diff_text)
            base_ref = head_ref = None
        else:
            git(repo, "rev-parse", "--git-dir")
            for ref in (args.base, args.head):
                if git(repo, "rev-parse", "--verify", "--quiet", ref + "^{commit}", check=False).returncode:
                    raise UsageError("%s is not a commit in %s (fetch it first)" % (ref, repo))
            base_ref, head_ref = args.base, args.head
            rng = "%s...%s" % (base_ref, head_ref)
            files = parse_unified_diff(git(repo, "diff", "-U0", "-M",
                                           "--no-ext-diff", rng).stdout)
            apply_name_status(files, git(repo, "diff", "--name-status", "-M", rng).stdout)
            base_ref = git(repo, "merge-base", base_ref, head_ref).stdout.strip() or base_ref
            # A SHA, so later phases see the same change even after new commits.
            head_ref = git(repo, "rev-parse", "--verify", head_ref + "^{commit}").stdout.strip() or head_ref
        if args.config:
            try:
                with open(args.config, encoding="utf-8") as handle:
                    config = load_config(handle.read(), args.config)
            except OSError as exc:
                raise UsageError("cannot read config: %s" % exc)
        else:
            text = show_file(repo, base_ref, ".docs-review.yml")
            config = load_config(text or "", ".docs-review.yml")
        first_time = first_time_writer(args, config)
        result = Triage(config, repo, base_ref, head_ref, first_time).run(files)
    except UsageError as exc:
        print("triage.py: error: %s" % exc, file=sys.stderr)
        return 2
    payload = json.dumps(result, indent=2) + "\n"
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(payload)
    else:
        sys.stdout.write(payload)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, UnicodeError, ValueError, RuntimeError) as exc:  # a one-line error, not a traceback
        if os.environ.get("DOCS_REVIEW_DEBUG"):
            raise
        sys.stderr.write("{}: error: {}\n".format(sys.argv[0].rsplit("/", 1)[-1], exc))
        sys.exit(2)
