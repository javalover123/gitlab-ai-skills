#!/usr/bin/env python3
"""Verify one docs section as rendered by a local docs.gitlab.com (Hugo) preview.

Python 3.9+, stdlib only. Read-only: it fetches pages over HTTP and reads files.

Checks (run one, or `all`):
  files      index.md files and duplicate content paths (static, no server)
  nav        every page has a navigation entry; entries point at real pages
             (static, needs --nav-file)
  trail      every page has a nav trail in page-metadata.json (needs --site-dir)
  sidebar    every rendered page has the side nav and marks itself active
  redirects  every redirect stub resolves, emits a meta refresh, and its
             target returns 200 and is not another redirect
  links      every internal link on every page returns 200 and every
             #anchor exists as an id on the target page
  cards      every {{< cards >}} item renders, and every card has a description

Pages come from the docs source tree: each .md maps to /<prefix>/<path>/
(_index.md and index.md map to the directory URL). Files with redirect_to are
redirect stubs, not pages.

Exit codes: 0 no failures (warnings allowed), 1 failures, 2 usage or
environment error (no server, missing directory).

Examples:
  site_check.py all --base http://localhost:1313 --prefix cli \\
      --docs-root ~/src/cli/docs/source --site-dir ~/src/docs-gitlab-com \\
      --nav-file ~/src/cli/docs/navigation.yaml
  site_check.py links --base http://localhost:1313 --prefix '' --docs-root doc --json
"""

import argparse
import concurrent.futures
import hashlib
import json
import os
import re
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

# Hugo's dev server renders on demand; the first request after a rebuild of a
# large site can take several seconds. 15 s keeps a hung server from stalling
# the run while leaving room for a slow first render.
TIMEOUT_SECONDS = 15
# The Hugo dev server handles a handful of parallel requests well; more than
# 8 gave no speedup on a 300-link section and made failures harder to read.
WORKERS = 8
# docs-gitlab-com hugo.yaml `ignoreFiles` skips agent instruction files.
IGNORED_FILES = {"AGENTS.md", "CLAUDE.md"}
REMOVE_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
CHECKS = ["files", "nav", "trail", "sidebar", "redirects", "links", "cards"]

SOURCES = {
    "nav": "https://docs.gitlab.com/development/documentation/site_architecture/global_nav/",
    "redirect": "https://docs.gitlab.com/development/documentation/redirects/",
    "links": "https://docs.gitlab.com/development/documentation/styleguide/#links",
    "cards": "https://docs.gitlab.com/development/documentation/topic_types/top_level_page/",
    "files": "https://docs.gitlab.com/development/documentation/site_architecture/folder_structure/#work-with-directories-and-files",
    "duplicate": "https://docs.gitlab.com/development/documentation/redirects/#error-duplicate-content-path-after-moving-a-page",
}

# Severity decides pass or fail: blocker and major fail the run, minor and nit
# are warnings.
FAILING = {"blocker", "major"}


# --------------------------------------------------------------------------
# Source tree
# --------------------------------------------------------------------------

def front_matter(path):
    """Return the top-level scalar keys of a page's YAML front matter."""
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except (OSError, UnicodeDecodeError):
        return {}, ""
    meta = {}
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end != -1:
            for line in text[4:end].splitlines():
                m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*?)\s*$", line)
                if m:
                    meta[m.group(1)] = m.group(2).strip("'\"")
    return meta, text


def url_for(rel, prefix):
    """Map a source path (posix, relative to the docs root) to its URL path."""
    base = os.path.basename(rel)
    if base in ("_index.md", "index.md"):
        sub = rel[: -len(base)]
    else:
        sub = rel[:-3] + "/"
    path = "/" + (prefix + "/" if prefix else "") + sub
    # Hugo lowercases URL paths by default (disablePathToLower: false).
    return path.lower()


class Page:
    def __init__(self, rel, prefix, root):
        self.rel = rel
        self.abs = os.path.join(root, rel)
        self.url = url_for(rel, prefix)
        self.meta, self.text = front_matter(self.abs)
        self.redirect_to = self.meta.get("redirect_to")

    def line_of(self, needle):
        """1-based line of the first occurrence of needle in the source, else 1."""
        if needle:
            for i, line in enumerate(self.text.splitlines(), 1):
                if needle in line:
                    return i
        return 1


def load_tree(root, prefix):
    pages = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
        for name in sorted(filenames):
            if not name.endswith(".md") or name in IGNORED_FILES:
                continue
            rel = os.path.relpath(os.path.join(dirpath, name), root).replace(os.sep, "/")
            pages.append(Page(rel, prefix, root))
    return pages


def repo_relative(root):
    """Prefix for finding paths: the docs root relative to its git repo, if any."""
    cur = os.path.abspath(root)
    while True:
        if os.path.exists(os.path.join(cur, ".git")):
            rel = os.path.relpath(os.path.abspath(root), cur).replace(os.sep, "/")
            return "" if rel == "." else rel + "/"
        parent = os.path.dirname(cur)
        if parent == cur:
            return ""
        cur = parent


# --------------------------------------------------------------------------
# HTTP and HTML
# --------------------------------------------------------------------------

class Fetcher:
    def __init__(self, base):
        self.base = base.rstrip("/")
        self.cache = {}
        self.lock = threading.Lock()

    def full(self, path):
        return path if path.startswith("http") else self.base + path

    def get(self, path):
        """Return (status, body). status 0 means a connection error."""
        with self.lock:
            if path in self.cache:
                return self.cache[path]
        try:
            with urllib.request.urlopen(self.full(path), timeout=TIMEOUT_SECONDS) as resp:
                result = (resp.status, resp.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as err:
            result = (err.code, "")
        except (urllib.error.URLError, OSError, ValueError):
            result = (0, "")
        with self.lock:
            self.cache[path] = result
        return result

    def prefetch(self, paths):
        todo = sorted(set(paths))
        with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
            list(pool.map(self.get, todo))


class PageParser(HTMLParser):
    """Collect the facts the checks need from one rendered page."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids = set()
        self.links = []          # (href, aria_current)
        self.has_nav = False
        self.refresh = None
        self.cards = []          # dicts: href, title, text
        self._card = None
        self._field = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get("id"):
            self.ids.add(a["id"])
        if tag == "a" and a.get("name"):
            self.ids.add(a["name"])
        cls = a.get("class") or ""
        if "global-nav-wrapper" in cls.split():
            self.has_nav = True
        if tag == "meta" and (a.get("http-equiv") or "").lower() == "refresh":
            m = re.search(r"url=(.+)$", a.get("content") or "", re.I)
            if m:
                self.refresh = m.group(1).strip()
        if tag == "a" and a.get("href") is not None:
            self.links.append((a["href"], a.get("aria-current")))
            if "card-body" in cls.split():
                self._card = {"href": a["href"], "title": "", "text": None}
        if self._card is not None and tag == "div":
            if "card-title" in cls.split():
                self._field = "title"
            elif "card-text" in cls.split():
                self._field = "text"
                self._card["text"] = ""

    def handle_endtag(self, tag):
        if tag == "div":
            self._field = None
        if tag == "a" and self._card is not None:
            self.cards.append(self._card)
            self._card = None

    def handle_data(self, data):
        if self._card is not None and self._field:
            self._card[self._field] = (self._card[self._field] or "") + data


def parse(body):
    p = PageParser()
    try:
        p.feed(body)
    except Exception:  # malformed HTML: keep what was parsed  # noqa: BLE001
        pass
    return p


# --------------------------------------------------------------------------
# Findings
# --------------------------------------------------------------------------

class Report:
    def __init__(self, path_prefix):
        self.findings = []
        self.counts = {}
        self.path_prefix = path_prefix

    def add(self, check, rule, severity, file, line, quote, message, source):
        self.findings.append({
            "id": "docs-preview." + rule,
            "reviewer": "docs-preview",
            "check": check,
            "severity": severity,
            "confidence": "high",
            "file": file,
            "line": line,
            "end_line": line,
            "quote": quote,
            "message": message,
            "suggestion": None,
            "fixable": "manual",
            "source": source,
            "deterministic": True,
        })

    def src(self, rel):
        """Path of a docs source file as findings report it (repo-relative when possible)."""
        return self.path_prefix + rel

    def failures(self, check=None):
        return [f for f in self.findings if f["severity"] in FAILING and (check is None or f["check"] == check)]

    def warnings(self, check=None):
        return [f for f in self.findings if f["severity"] not in FAILING and (check is None or f["check"] == check)]


# --------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------

def check_files(ctx):
    rep, pages = ctx["report"], ctx["pages"]
    rels = {p.rel for p in pages}
    for p in pages:
        if os.path.basename(p.rel) == "index.md":
            rep.add("files", "index-md", "blocker", rep.src(p.rel), 1, p.rel,
                    "Rename index.md to _index.md; docs-gitlab-com `make check-index-pages` rejects index.md.",
                    SOURCES["files"])
        if p.rel.endswith(".md") and os.path.basename(p.rel) not in ("_index.md", "index.md"):
            twin = p.rel[:-3] + "/_index.md"
            if twin in rels:
                rep.add("files", "duplicate-path", "blocker", rep.src(p.rel), 1, p.rel,
                        f"{p.rel} and {twin} publish the same URL; Hugo fails with 'Duplicate content path'. Keep one.",
                        SOURCES["duplicate"])
    return len(pages)


def nav_entries(nav_file):
    """Return [(url, line)] for every `url:` value in a navigation YAML file."""
    out = []
    with open(nav_file, encoding="utf-8") as fh:
        for i, line in enumerate(fh, 1):
            m = re.match(r"^\s*-?\s*url:\s*['\"]?([^'\"#\s]+(?:#[^'\"\s]*)?)['\"]?", line)
            if m:
                out.append((m.group(1), i))
    return out


def check_nav(ctx):
    rep, pages, prefix, nav_file = ctx["report"], ctx["pages"], ctx["prefix"], ctx["nav_file"]
    entries = nav_entries(nav_file)
    nav_label = nav_file
    by_url = {p.url.lstrip("/"): p for p in pages}
    top_dirs = {p.rel.split("/")[0] for p in pages if "/" in p.rel}
    scope = (prefix + "/") if prefix else ""
    seen = {}
    checked = 0
    for url, line in entries:
        if scope and not url.startswith(scope):
            continue
        if not scope and url.split("/")[0] not in top_dirs and url not in by_url:
            continue  # another project's section in a full navigation.yaml
        checked += 1
        if url.startswith(("http:", "https:", "/")) or "#" in url or not url.endswith("/"):
            rep.add("nav", "nav-bad-url", "major", nav_label, line, url,
                    "Navigation URLs are relative, have no anchor, and end with '/'.", SOURCES["nav"])
            continue
        if url in seen:
            rep.add("nav", "nav-duplicate", "blocker", nav_label, line, url,
                    f"Duplicate navigation entry (first at line {seen[url]}); the docs pipeline rejects duplicates.",
                    SOURCES["nav"])
            continue
        seen[url] = line
        page = by_url.get(url)
        if page is None:
            rep.add("nav", "nav-dead-entry", "blocker", nav_label, line, url,
                    "Navigation entry has no page in the docs source. Remove it or fix the URL.", SOURCES["nav"])
        elif page.redirect_to:
            rep.add("nav", "nav-dead-entry", "blocker", nav_label, line, url,
                    f"Navigation entry points at a redirect stub ({page.rel}). Point it at the new page.",
                    SOURCES["nav"])
    for p in pages:
        if p.redirect_to or p.meta.get("ignore_in_report") == "true":
            continue
        if p.url.lstrip("/") not in seen:
            rep.add("nav", "nav-missing-page", "major", rep.src(p.rel), p.line_of("title:"), p.url,
                    f"Page has no entry in {os.path.basename(nav_file)}, so it renders without a side nav. "
                    "Add an entry, or set ignore_in_report: true if it is meant to be unlisted.",
                    SOURCES["nav"])
    return checked


def metadata_path(site_dir):
    for cand in (os.path.join(site_dir, "data", "en-us", "page-metadata.json"),
                 os.path.join(site_dir, "docs-gitlab-com", "data", "en-us", "page-metadata.json")):
        if os.path.isfile(cand):
            return cand
    return None


def check_trail(ctx):
    rep, pages = ctx["report"], ctx["pages"]
    meta_file = metadata_path(ctx["site_dir"])
    if not meta_file:
        raise EnvError(f"no data/en-us/page-metadata.json under {ctx['site_dir']}; run `make build-data` "
                       "in docs-gitlab-com (scripts/regen-nav-data.sh)")
    nav_yaml = os.path.join(os.path.dirname(meta_file), "navigation.yaml")
    if os.path.isfile(nav_yaml) and os.path.getmtime(nav_yaml) > os.path.getmtime(meta_file):
        rep.add("trail", "metadata-stale", "minor", meta_file, 1, nav_yaml,
                "navigation.yaml is newer than page-metadata.json; trails and sidebars are stale. "
                "Run scripts/regen-nav-data.sh, then re-check.", SOURCES["nav"])
    with open(meta_file, encoding="utf-8") as fh:
        meta = json.load(fh)
    n = 0
    for p in pages:
        if p.redirect_to:
            continue
        n += 1
        key = p.url.lstrip("/")
        entry = meta.get(key)
        trail = entry.get("trail_items") if isinstance(entry, dict) else None
        if not trail:
            rep.add("trail", "trail-missing", "major", rep.src(p.rel), p.line_of("title:"), key,
                    "No nav trail in page-metadata.json, so the page renders without a side nav. "
                    "Add the page to navigation.yaml and run make build-data.", SOURCES["nav"])
        elif trail[-1].get("path") != key:
            rep.add("trail", "trail-mismatch", "major", rep.src(p.rel), p.line_of("title:"), key,
                    f"Nav trail ends at {trail[-1].get('path')!r}, not at this page. Fix its navigation.yaml url.",
                    SOURCES["nav"])
    return n


def content_pages(ctx):
    return [p for p in ctx["pages"] if not p.redirect_to]


def check_sidebar(ctx):
    rep, fetch = ctx["report"], ctx["fetch"]
    pages = content_pages(ctx)
    fetch.prefetch(p.url for p in pages)
    for p in pages:
        status, body = fetch.get(p.url)
        if status != 200:
            rep.add("sidebar", "page-not-rendered", "blocker", rep.src(p.rel), 1, p.url,
                    f"Page returns HTTP {status}. Check the front matter and the Hugo log.", SOURCES["nav"])
            continue
        doc = parse(body)
        active = any(h == p.url and cur == "page" for h, cur in doc.links)
        if not doc.has_nav:
            rep.add("sidebar", "sidebar-missing", "major", rep.src(p.rel), p.line_of("title:"), p.url,
                    "Rendered page has no side nav (no global-nav-wrapper). The page is missing from "
                    "navigation.yaml or page-metadata.json is stale.", SOURCES["nav"])
        elif not active:
            rep.add("sidebar", "sidebar-not-active", "minor", rep.src(p.rel), p.line_of("title:"), p.url,
                    "Side nav renders but does not mark this page active; the nav url may not match the page URL.",
                    SOURCES["nav"])
    return len(pages)


def resolve_source(page_rel, target):
    """Resolve a relative .md link from a source file; return a posix path."""
    target = target.split("#", 1)[0]
    joined = os.path.normpath(os.path.join(os.path.dirname(page_rel), target)).replace(os.sep, "/")
    return joined


def check_redirects(ctx):
    rep, fetch, pages, root = ctx["report"], ctx["fetch"], ctx["pages"], ctx["root"]
    stubs = [p for p in pages if p.redirect_to]
    by_rel = {p.rel: p for p in pages}
    fetch.prefetch(p.url for p in stubs)
    chained = set()
    for p in stubs:
        target = p.redirect_to
        if not target.startswith("http"):
            dest = resolve_source(p.rel, target)
            if dest not in by_rel and not os.path.isfile(os.path.join(root, dest)):
                rep.add("redirects", "redirect-target-missing", "blocker", rep.src(p.rel), p.line_of("redirect_to"), target,
                        f"redirect_to resolves to {dest}, which does not exist. The path is relative to the stub's own directory.",
                        SOURCES["redirect"])
            elif dest in by_rel and by_rel[dest].redirect_to:
                chained.add(p.rel)
                rep.add("redirects", "redirect-chain", "blocker", rep.src(p.rel), p.line_of("redirect_to"), target,
                        f"redirect_to points at another redirect stub ({dest}). Point it at the final page.",
                        SOURCES["redirect"])
        rd = p.meta.get("remove_date")
        if not rd or not REMOVE_DATE_RE.match(rd):
            rep.add("redirects", "redirect-remove-date", "minor", rep.src(p.rel), p.line_of("remove_date") if rd else 1,
                    rd or "", "Redirect stub needs remove_date: 'YYYY-MM-DD' (3 months out for pages in the same "
                    "project, 1 year for external targets).", SOURCES["redirect"])
        status, body = fetch.get(p.url)
        refresh = parse(body).refresh if status == 200 else None
        if not refresh:
            rep.add("redirects", "redirect-no-refresh", "blocker", rep.src(p.rel), p.line_of("redirect_to"), p.url,
                    f"Stub at {p.url} (HTTP {status}) emits no meta refresh; Hugo drops a redirect whose target "
                    "does not resolve (see 'Invalid internal redirect path' in the Hugo log).", SOURCES["redirect"])
            continue
        tpath = urllib.parse.urlsplit(urllib.parse.urljoin(fetch.full(p.url), refresh))
        tstatus, tbody = fetch.get(tpath.path if not refresh.startswith("http") else refresh)
        if tstatus != 200:
            rep.add("redirects", "redirect-target-broken", "blocker", rep.src(p.rel), p.line_of("redirect_to"), refresh,
                    f"Redirect target {refresh} returns HTTP {tstatus}.", SOURCES["redirect"])
        elif parse(tbody).refresh and p.rel not in chained:
            rep.add("redirects", "redirect-chain", "blocker", rep.src(p.rel), p.line_of("redirect_to"), refresh,
                    f"Redirect target {refresh} is itself a redirect. Point the stub at the final page.",
                    SOURCES["redirect"])
    return len(stubs)


def in_scope(path, scopes):
    return any(path.startswith(s) for s in scopes)


def check_links(ctx):
    rep, fetch = ctx["report"], ctx["fetch"]
    pages = content_pages(ctx)
    scopes = ctx["scopes"]
    host = urllib.parse.urlsplit(fetch.base).netloc
    stubs = {p.url for p in ctx["pages"] if p.redirect_to}
    fetch.prefetch(p.url for p in pages)
    links = []  # (page, path, fragment, href)
    for p in pages:
        status, body = fetch.get(p.url)
        if status != 200:
            continue
        for href, _ in parse(body).links:
            if not href or href.startswith(("mailto:", "javascript:", "tel:")) or href == "#":
                continue
            u = urllib.parse.urlsplit(urllib.parse.urljoin(fetch.full(p.url), href))
            if u.scheme not in ("http", "https") or u.netloc != host:
                continue
            if not in_scope(u.path, scopes):
                continue
            links.append((p, u.path, u.fragment, href))
    fetch.prefetch(path for _, path, _, _ in links)
    seen = set()
    for p, path, frag, href in links:
        key = (p.url, path, frag)
        if key in seen:
            continue
        seen.add(key)
        status, body = fetch.get(path)
        needle = frag or path.rstrip("/").rsplit("/", 1)[-1]
        if status != 200:
            rep.add("links", "link-broken", "blocker", rep.src(p.rel), p.line_of(needle), href,
                    f"Link to {path} returns HTTP {status}.", SOURCES["links"])
            continue
        if path in stubs or (path + "/") in stubs:
            rep.add("links", "link-to-redirect", "minor", rep.src(p.rel), p.line_of(needle), href,
                    f"Link goes through the redirect stub {path}. Link to the new page instead.",
                    SOURCES["redirect"])
        if frag and frag not in parse(body).ids:
            rep.add("links", "anchor-broken", "blocker", rep.src(p.rel), p.line_of("#" + frag), href,
                    f"Anchor #{frag} does not exist on {path}. A renamed heading changes its anchor; "
                    "update the link or the heading.", SOURCES["links"])
    return len(seen)


CARDS_BLOCK_RE = re.compile(r"\{\{<\s*cards\s*>\}\}(.*?)\{\{<\s*/cards\s*>\}\}", re.S)
CARD_ITEM_RE = re.compile(r"^\s*[-*]\s+\[([^\]]+)\]\(([^)\s]+)", re.M)


def check_cards(ctx):
    rep, fetch, pages = ctx["report"], ctx["fetch"], ctx["pages"]
    by_rel = {p.rel: p for p in pages}
    with_cards = [p for p in content_pages(ctx) if CARDS_BLOCK_RE.search(p.text)]
    fetch.prefetch(p.url for p in with_cards)
    for p in with_cards:
        items = []
        for block in CARDS_BLOCK_RE.findall(p.text):
            items.extend(CARD_ITEM_RE.findall(block))
        status, body = fetch.get(p.url)
        if status != 200:
            continue
        cards = parse(body).cards
        before = len(rep.failures("cards"))
        rendered = {urllib.parse.urlsplit(c["href"]).path for c in cards} | {c["href"] for c in cards}
        for title, target in items:
            if target.startswith("http"):
                if target not in rendered:
                    rep.add("cards", "cards-dropped", "major", rep.src(p.rel), p.line_of(target), target,
                            f"Card '{title}' did not render.", SOURCES["cards"])
                continue
            dest = resolve_source(p.rel, target)
            tp = by_rel.get(dest)
            expect = tp.url if tp else url_for(dest, ctx["prefix"]) if dest.endswith(".md") else None
            if expect and expect in rendered:
                continue
            why = ("the target is a redirect stub" if tp and tp.redirect_to else
                   "the target has no title" if tp and not tp.meta.get("title") else
                   "the target page does not exist" if not tp else "unknown")
            rep.add("cards", "cards-dropped", "major", rep.src(p.rel), p.line_of(target), target,
                    f"Card '{title}' was silently dropped: {why}. Link the card to the final page.",
                    SOURCES["cards"])
        for c in cards:
            if not (c["text"] or "").strip():
                rep.add("cards", "card-no-description", "major", rep.src(p.rel), p.line_of(c["title"].strip() or c["href"]),
                        c["href"], f"Card '{c['title'].strip()}' has no description; the card text comes from the "
                        "target page's front matter `description`. Add one there.", SOURCES["cards"])
        if len(cards) != len(items) and len(rep.failures("cards")) == before:
            rep.add("cards", "cards-count", "major", rep.src(p.rel), 1, p.url,
                    f"{len(cards)} cards rendered, {len(items)} in source.", SOURCES["cards"])
    return len(with_cards)


class EnvError(Exception):
    pass


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog=__doc__.split("\n\n", 1)[1])
    ap.add_argument("check", choices=CHECKS + ["all"])
    ap.add_argument("--base", default="http://localhost:1313", help="preview base URL (default %(default)s)")
    ap.add_argument("--prefix", required=True,
                    help="section path prefix on docs.gitlab.com, for example 'runner' or '' for the gitlab doc/ root")
    ap.add_argument("--docs-root", required=True, help="docs source directory that Hugo mounts for the prefix")
    ap.add_argument("--site-dir", help="docs-gitlab-com checkout (or its parent); enables the trail check")
    ap.add_argument("--nav-file", help="navigation YAML (project copy or docs-gitlab-com data/en-us/navigation.yaml); "
                                       "enables the nav check")
    ap.add_argument("--scope", action="append",
                    help="URL path prefix whose links are checked (repeatable; default /<prefix>/)")
    ap.add_argument("--json", action="store_true", help="print findings JSON instead of text")
    ap.add_argument("--out", help="write findings JSON to this file (text still goes to stdout)")
    args = ap.parse_args(argv)

    prefix = args.prefix.strip("/")
    root = os.path.abspath(os.path.expanduser(args.docs_root))
    if not os.path.isdir(root):
        print(f"ERROR: docs root not found: {root}", file=sys.stderr)
        return 2
    pages = load_tree(root, prefix)
    if not pages:
        print(f"ERROR: no .md files under {root}", file=sys.stderr)
        return 2
    report = Report(repo_relative(root))
    ctx = {
        "report": report, "pages": pages, "prefix": prefix, "root": root,
        "fetch": Fetcher(args.base), "nav_file": args.nav_file,
        "site_dir": os.path.expanduser(args.site_dir) if args.site_dir else None,
        "scopes": args.scope or ["/" + (prefix + "/" if prefix else "")],
    }
    funcs = {"files": check_files, "nav": check_nav, "trail": check_trail, "sidebar": check_sidebar,
             "redirects": check_redirects, "links": check_links, "cards": check_cards}
    wanted = CHECKS if args.check == "all" else [args.check]
    needs_server = {"sidebar", "redirects", "links", "cards"}
    log = sys.stderr if args.json else sys.stdout

    if needs_server & set(wanted):
        landing = ctx["scopes"][0]
        status, _ = ctx["fetch"].get(landing)
        if status == 0:
            print(f"ERROR: no server at {args.base}{landing}. Start the preview first (references/setup.md).",
                  file=sys.stderr)
            return 2

    for name in wanted:
        if name == "nav" and not args.nav_file:
            if args.check == "nav":
                print("ERROR: the nav check needs --nav-file", file=sys.stderr)
                return 2
            print("SKIP nav: pass --nav-file to check navigation entries", file=log)
            continue
        if name == "trail" and not ctx["site_dir"]:
            if args.check == "trail":
                print("ERROR: the trail check needs --site-dir", file=sys.stderr)
                return 2
            print("SKIP trail: pass --site-dir to check page-metadata.json trails", file=log)
            continue
        if name == "nav" and not os.path.isfile(args.nav_file):
            print(f"ERROR: nav file not found: {args.nav_file}", file=sys.stderr)
            return 2
        try:
            n = funcs[name](ctx)
        except EnvError as err:
            print(f"ERROR: {err}", file=sys.stderr)
            return 2
        for f in [x for x in report.findings if x["check"] == name]:
            tag = "FAIL" if f["severity"] in FAILING else "WARN"
            print(f"{tag} {f['id']} {f['file']}:{f['line']} {f['quote']}: {f['message']}", file=log)
        print(f"{name}: {n} checked, {len(report.failures(name))} failures, "
              f"{len(report.warnings(name))} warnings", file=log)

    for f in report.findings:
        f["fingerprint"] = hashlib.sha1(f"{f['id']}|{f['file']}|{f['quote']}".encode()).hexdigest()
    fails, warns = len(report.failures()), len(report.warnings())
    verdict = "PASS" if fails == 0 else "FAIL"
    print(f"site-check: {verdict} ({fails} failures, {warns} warnings)", file=log)
    doc = {
        "version": 1,
        "target": {"base_url": args.base, "prefix": prefix, "docs_root": root, "checks": wanted},
        "findings": report.findings,
    }
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=2)
            fh.write("\n")
    if args.json:
        json.dump(doc, sys.stdout, indent=2)
        sys.stdout.write("\n")
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, UnicodeError, ValueError, RuntimeError) as exc:  # a one-line error, not a traceback
        if os.environ.get("DOCS_REVIEW_DEBUG"):
            raise
        sys.stderr.write("{}: error: {}\n".format(sys.argv[0].rsplit("/", 1)[-1], exc))
        sys.exit(2)
