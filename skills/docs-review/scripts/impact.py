#!/usr/bin/env python3
"""Find what a docs change breaks elsewhere: lost anchors and moved pages.

Compares BASE..HEAD in a local git checkout. For each changed Markdown page it
finds the anchors that disappear (docs.gitlab.com Hugo slug rules) and the
pages that move, are deleted, or become redirects, then searches for inbound
references: in the repo at HEAD (Markdown links, help_page_path, helpPagePath,
docs.gitlab.com URLs, the nav file), and in other projects through GitLab blob
search and the docs.gitlab.com global nav. Read-only. Non-public project paths
and IDs never appear in the output.

Usage:
  impact.py --base origin/main [--head HEAD] [--docs-root doc] [--url-prefix orbit/] [--summary]
  impact.py --mr 123 --project gitlab-org/orbit/knowledge-graph --out impact.json

Exit codes: 0 no blocker, 1 blockers found, 2 usage or environment error.
"""

import argparse
import datetime
import difflib
import os
import posixpath
import re
import sys
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from lib import dates  # noqa: E402
from lib.mdparse import slugify  # noqa: E402  (one anchor algorithm for every script)
from lib import findings as F  # noqa: E402
from lib import gitdiff  # noqa: E402
from lib import gitlab_api  # noqa: E402
from lib import frontmatter, lint_config, page_class  # noqa: E402

REVIEWER = "impact"
DOCS_HOST = "docs.gitlab.com"
SRC_ANCHORS = "https://docs.gitlab.com/development/documentation/styleguide/#anchor-links"
SRC_REDIRECTS = "https://docs.gitlab.com/development/documentation/redirects/"
SRC_OTHER_REPOS = "https://docs.gitlab.com/development/documentation/redirects/#update-links-in-other-repositories"
SRC_NAV = "https://docs.gitlab.com/development/documentation/site_architecture/global_nav/"

NAV_PROJECT = "gitlab-org/technical-writing/docs-gitlab-com"
NAV_PROJECT_PATH = "data/en-us/navigation.yaml"
NAV_CANDIDATES = ("docs/navigation.yaml", "doc/navigation.yaml", "data/en-us/navigation.yaml", "navigation.yaml")
DEFAULT_GROUPS = ["gitlab-org", "gitlab-com"]

MAX_SEARCH_CALLS = 40      # blob search API calls per run
SEARCH_PER_PAGE = 50       # results per search call
SEARCH_DELAY = 1.5         # seconds between API calls
API_TIMEOUT = 45           # seconds per glab api call
MAX_REFS_PER_FINDING = 10  # cross-repo hits listed in one finding message
NON_PUBLIC = "a non-public project"


def warn(msg):
    sys.stderr.write("impact: {}\n".format(msg))


class UsageError(Exception):
    pass


# ---------------------------------------------------------------- git

class Git(object):
    def __init__(self, repo):
        self.repo = repo
        self._show = {}

    def run(self, *args, check=True):
        try:
            return gitdiff.run(self.repo, args, check=check)
        except gitdiff.GitError as exc:
            raise UsageError(str(exc))

    def show(self, rev, path):
        key = (rev, path)
        if key not in self._show:
            proc = self.run("show", "{}:{}".format(rev, path), check=False)
            self._show[key] = proc.stdout if proc.returncode == 0 else None
        return self._show[key]

    def exists(self, rev):
        return self.run("cat-file", "-e", rev + "^{commit}", check=False).returncode == 0

    def resolve(self, rev):
        return self.run("rev-parse", "--verify", rev + "^{commit}").stdout.strip()

    def name_status(self, base, head):
        out = self.run("diff", "--name-status", "-M", "-z", base, head).stdout
        parts = out.split("\0")
        entries, i = [], 0
        while i < len(parts) and parts[i]:
            status = parts[i]
            if status[0] in "RC":
                entries.append((status[0], parts[i + 1], parts[i + 2]))
                i += 3
            else:
                entries.append((status[0], parts[i + 1], parts[i + 1]))
                i += 2
        return entries

    def grep(self, rev, needles):
        """Fixed-string grep at `rev`. Returns [(path, line, text)]."""
        if not needles:
            return []
        args = ["grep", "-n", "-I", "-F"]
        for n in needles:
            args += ["-e", n]
        proc = self.run(*(args + [rev, "--"]), check=False)
        if proc.returncode not in (0, 1):
            warn("git grep failed: {}".format(proc.stderr.strip()[:200]))
            return []
        hits, prefix = [], rev + ":"
        for raw in proc.stdout.splitlines():
            if raw.startswith(prefix):
                raw = raw[len(prefix):]
            m = re.match(r"^(.*?):(\d+):(.*)$", raw)
            if m:
                hits.append((m.group(1), int(m.group(2)), m.group(3)))
        return hits


# ---------------------------------------------------------------- markdown

FENCE_RE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
HEADING_RE = re.compile(r"^ {0,3}(#{1,6})[ \t]+(.*?)(?:[ \t]+#+)?[ \t]*$")
CUSTOM_ID_RE = re.compile(r"\s*\{\s*#([A-Za-z0-9_:.\-]+)[^}]*\}\s*$")
HTML_ANCHOR_RE = re.compile(r"<a\s+[^>]*?(?:id|name)\s*=\s*[\"']([^\"']+)[\"']", re.I)


def front_matter(text):
    """(dict of top-level scalar/list keys, number of front matter lines)."""
    lines = (text or "").splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, 0
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return frontmatter.parse("\n".join(lines[1:i])), i + 1
    return {}, 0


def parse_headings(text):
    """(headings in order, all anchors incl. <a id>). Duplicates get Hugo's
    `-1`, `-2` suffixes."""
    out, seen, extra = [], {}, set()
    if text is None:
        return out, set()
    lines = text.splitlines()
    _, start = front_matter(text)
    fence = None
    for idx in range(start, len(lines)):
        line = lines[idx]
        fm = FENCE_RE.match(line)
        if fence:
            if fm and fm.group(1)[0] == fence[0] and len(fm.group(1)) >= len(fence):
                fence = None
            continue
        if fm:
            fence = fm.group(1)
            continue
        for a in HTML_ANCHOR_RE.findall(line):
            extra.add(a)
        m = HEADING_RE.match(line)
        if not m:
            continue
        htext = m.group(2)
        cm = CUSTOM_ID_RE.search(htext)
        if cm:
            anchor = cm.group(1)
            htext = htext[:cm.start()]
        else:
            base = slugify(htext)
            anchor = base
            if base in seen:
                n = seen[base]
                while True:
                    candidate = "{}-{}".format(base, n)
                    n += 1
                    if candidate not in seen:
                        break
                seen[base] = n
                anchor = candidate
        seen.setdefault(anchor, 1)
        out.append({"line": idx + 1, "level": len(m.group(1)), "text": htext.strip(), "raw": line,
                    "anchor": anchor})
    anchors = set(h["anchor"] for h in out) | extra
    return out, anchors


def pair_renames(old_heads, new_heads, new_anchors):
    """Guess old->new heading for anchors that disappeared."""
    a = [h["anchor"] for h in old_heads]
    b = [h["anchor"] for h in new_heads]
    pairs = {}
    sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag != "replace":
            continue
        olds, news = old_heads[i1:i2], new_heads[j1:j2]
        if len(olds) == len(news):
            for o, n in zip(olds, news):
                pairs[o["anchor"]] = n
        else:
            texts = [n["text"].lower() for n in news]
            for o in olds:
                best = difflib.get_close_matches(o["text"].lower(), texts, n=1, cutoff=0.5)
                if best:
                    pairs[o["anchor"]] = news[texts.index(best[0])]
    # Only keep guesses whose new anchor is itself new (not a heading that existed before).
    old_set = set(a)
    return {k: v for k, v in pairs.items() if v["anchor"] not in old_set and v["anchor"] in new_anchors}


# ---------------------------------------------------------------- pages and URLs

def page_rel(path, docs_root):
    """`docs/source/local/_index.md` -> `local`; None outside the docs root."""
    if not path.endswith(".md"):
        return None
    root = docs_root.strip("/")
    if root and not path.startswith(root + "/"):
        return None
    rel = path[len(root) + 1:] if root else path
    rel = rel[:-3]
    if rel in ("_index", "index"):
        return ""
    for suffix in ("/_index", "/index"):
        if rel.endswith(suffix):
            return rel[:-len(suffix)]
    return rel


def norm_key(path):
    """Normalize a docs path or URL path so the forms compare equal."""
    p = urllib.parse.unquote(path.split("#", 1)[0].split("?", 1)[0])
    p = p.strip().strip("/")
    for suffix in (".html", ".md"):
        if p.endswith(suffix):
            p = p[:-len(suffix)]
    for suffix in ("/_index", "/index"):
        if p.endswith(suffix):
            p = p[:-len(suffix)]
    if p in ("_index", "index"):
        p = ""
    return p


def url_key(rel, prefix):
    return norm_key((prefix or "") + rel)


def public_url(key):
    return "https://{}/{}{}".format(DOCS_HOST, key, "/" if key else "")


DOCS_URL_RE = re.compile(r"https?://docs\.gitlab\.com/([^\s)\"'<>`\]]*)")
MD_LINK_RE = re.compile(r"\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
REF_DEF_RE = re.compile(r"^\s*\[[^\]]+\]:\s*<?(\S+?)>?(?:\s|$)")
HREF_RE = re.compile(r"href\s*=\s*[\"']([^\"']+)[\"']")
RUBY_HELP_RE = re.compile(r"help_page_(?:path|url)\(\s*['\"]([^'\"]+)['\"]([^()]*)\)", re.S)
JS_HELP_RE = re.compile(r"helpPage(?:Path|Url)\(\s*['\"`]([^'\"`]+)['\"`]\s*(?:,\s*(\{[^}]*\}))?\s*\)", re.S)
ANCHOR_ARG_RE = re.compile(r"anchor\s*:\s*['\"`]([^'\"`]+)['\"`]")
NAV_URL_RE = re.compile(r"^\s*-?\s*url:\s*['\"]?([^'\"\s#]+)(#[^'\"\s]*)?['\"]?")


def split_anchor(target):
    if "#" in target:
        path, anchor = target.split("#", 1)
        return path, anchor
    return target, None


def resolve_md(src_file, target):
    """Candidate repo paths for a relative Markdown link target."""
    path, _ = split_anchor(target)
    if not path:
        return [src_file]
    if re.match(r"^[a-z][a-z0-9+.-]*:", path) or path.startswith("/"):
        return []
    joined = posixpath.normpath(posixpath.join(posixpath.dirname(src_file), urllib.parse.unquote(path)))
    if joined.endswith(".md"):
        return [joined]
    return [joined + ".md", joined + "/_index.md", joined + "/index.md"]


# ---------------------------------------------------------------- analysis

class Target(object):
    """A changed page whose old anchors or old URL can break references."""

    def __init__(self, path, old_path, kind):
        self.path = path            # path at HEAD (None when deleted)
        self.old_path = old_path    # path at BASE
        self.kind = kind            # anchors | moved | deleted | redirected
        self.lost = {}              # anchor -> info dict
        self.redirect_to = None     # repo path or URL
        self.has_redirect = False
        self.old_title = None
        self.rel = None
        self.key = None
        self.remove_date = None     # redirect stub `remove_date`, as a string
        self.lost_redirect_target = False
        self.redirect_line = (None, None)  # (line, text) of `redirect_to:`

    def label(self):
        return self.path or self.old_path


def analyze(git, base, head, cfg, out_notes):
    docs_root = cfg["docs_root"]
    entries = git.name_status(base, head)
    targets = []
    changed_md, added_paths = [], []
    for status, old, new in entries:
        if status in ("A", "C", "R"):
            added_paths.append(new)
        if old.endswith(".md") or new.endswith(".md"):
            changed_md.append((status, old, new))

    redirect_texts = []  # contents of changed redirect config files and new aliases
    for status, old, new in entries:
        if status != "D" and re.search(r"redirect", posixpath.basename(new), re.I) and not new.endswith(".md"):
            redirect_texts.append(git.show(head, new) or "")

    for status, old, new in changed_md:
        if status == "A" or status == "C":
            continue
        old_text = git.show(base, old)
        if old_text is None:
            continue
        old_fm, _ = front_matter(old_text)
        if old_fm.get("redirect_to"):
            continue  # already a redirect at BASE: nothing new breaks
        old_heads, _ = parse_headings(old_text)
        title = old_fm.get("title")
        old_title_line = None
        for ln in old_text.splitlines():
            if ln.startswith("title:") or (title is None and ln.startswith("# ")):
                old_title_line = ln
                break
        if status == "D":
            t = Target(None, old, "deleted")
        elif status == "R":
            t = Target(new, old, "moved")
        else:
            new_text = git.show(head, new)
            new_fm, _ = front_matter(new_text)
            t = Target(new, old, "redirected" if new_fm.get("redirect_to") else "anchors")
            if t.kind == "redirected":
                t.redirect_to = new_fm.get("redirect_to")
                if new_fm.get("remove_date"):
                    t.remove_date = str(new_fm.get("remove_date"))
        t.old_title = old_title_line
        t.rel = page_rel(old, docs_root)
        t.key = url_key(t.rel, cfg["url_prefix"]) if t.rel is not None else None

        # Which anchors survive, and where?
        if t.kind == "deleted":
            new_heads, new_anchors = [], set()
        elif t.kind == "redirected":
            dest = t.redirect_to
            if dest and not re.match(r"^https?:", dest):
                dest_path = posixpath.normpath(posixpath.join(posixpath.dirname(new), dest))
                t.redirect_to = dest_path
                dest_text = git.show(head, dest_path)
                if dest_text is None:
                    out_notes.append("{}: redirect_to `{}` does not exist at HEAD".format(new, dest))
                    t.lost_redirect_target = True
                    # A real quote, so the finding dedupes with lint.redirect-target-missing.
                    for i, ln in enumerate((git.show(head, new) or "").split("\n"), 1):
                        if ln.startswith("redirect_to:"):
                            t.redirect_line = (i, ln)
                            break
                else:
                    t.has_redirect = True
                new_heads, new_anchors = parse_headings(dest_text)
            else:
                t.has_redirect = bool(dest)
                new_heads, new_anchors = [], set()
        else:
            new_heads, new_anchors = parse_headings(git.show(head, new))
        if t.kind in ("moved", "deleted"):
            t.has_redirect = has_alias(git, head, added_paths, t, redirect_texts)

        guesses = pair_renames(old_heads, new_heads, new_anchors) if t.kind in ("anchors", "moved") else {}
        new_by_anchor = dict((h["anchor"], h) for h in new_heads)
        for h in old_heads:
            if h["anchor"] in new_anchors:
                if t.kind == "redirected":
                    t.lost[h["anchor"]] = {"old": h, "new": new_by_anchor.get(h["anchor"]), "state": "on-target"}
                continue
            t.lost[h["anchor"]] = {"old": h, "new": guesses.get(h["anchor"]), "state": "lost"}
        if t.kind == "anchors" and not t.lost:
            continue
        targets.append(t)
    return targets


def has_alias(git, head, added_paths, t, redirect_texts):
    """A moved or deleted page still resolves if a Hugo alias or a redirect
    file in this change points at its old URL."""
    if t.key is None:
        return False
    forms = set([t.key, t.key + "/", "/" + t.key, "/" + t.key + "/", t.old_path])
    for p in added_paths:
        if not p.endswith(".md"):
            continue
        fm, _ = front_matter(git.show(head, p))
        aliases = fm.get("aliases")
        if isinstance(aliases, list) and forms & set(str(a) for a in aliases):
            return True
    for text in redirect_texts:
        if any(f and f in text for f in forms):
            return True
    return False


# ---------------------------------------------------------------- reference search

class Ref(object):
    def __init__(self, file, line, text, kind, anchor, paths=None, key=None):
        self.file = file
        self.line = line
        self.text = text      # exact substring in the file
        self.kind = kind      # md-link | help_page_path | helpPagePath | url | nav
        self.anchor = anchor
        self.paths = paths or []
        self.key = key


def refs_in_line(path, lineno, line):
    refs = []
    for m in MD_LINK_RE.finditer(line):
        refs.extend(_classify(path, lineno, m.group(0), m.group(1)))
    rm = REF_DEF_RE.match(line)
    if rm:
        refs.extend(_classify(path, lineno, line.strip(), rm.group(1)))
    for m in HREF_RE.finditer(line):
        refs.extend(_classify(path, lineno, m.group(0), m.group(1)))
    for m in DOCS_URL_RE.finditer(line):
        if any(m.group(0) in r.text for r in refs):
            continue
        p, a = split_anchor(m.group(1))
        refs.append(Ref(path, lineno, m.group(0), "url", a, key=_url_path_key(p)))
    return refs


def _url_path_key(p):
    p = norm_key(p)
    if p.startswith("ee/"):
        p = p[3:]
    return p


def _classify(path, lineno, text, target):
    target = target.strip()
    if re.match(r"^https?://docs\.gitlab\.com/", target):
        rest = target.split("docs.gitlab.com/", 1)[1]
        p, a = split_anchor(rest)
        return [Ref(path, lineno, text, "url", a, key=_url_path_key(p))]
    if re.match(r"^[a-z][a-z0-9+.-]*:", target):
        return []
    return [Ref(path, lineno, text, "md-link", split_anchor(target)[1], paths=resolve_md(path, target))]


def refs_in_code(path, text):
    refs = []
    for regex, kind in ((RUBY_HELP_RE, "help_page_path"), (JS_HELP_RE, "helpPagePath")):
        for m in regex.finditer(text):
            target = m.group(1)
            p, a = split_anchor(target)
            args = m.group(2) or ""
            am = ANCHOR_ARG_RE.search(args)
            if am:
                a = am.group(1)
            lineno = text.count("\n", 0, m.start()) + 1
            # Report the line that holds the anchor when the call spans lines.
            if am:
                lineno = text.count("\n", 0, m.start(2) + am.start()) + 1
            refs.append(Ref(path, lineno, m.group(0).split("\n")[0] if not am else am.group(0), kind, a,
                            key=norm_key(p)))
    return refs


def search_repo(git, head, targets, nav_file):
    """All references at HEAD that point at a target page."""
    needles = set()
    for t in targets:
        for anchor in t.lost:
            needles.add("#" + anchor)
            needles.add("'" + anchor + "'")
            needles.add('"' + anchor + '"')
        if t.kind in ("moved", "deleted", "redirected"):
            base = posixpath.basename(t.old_path)
            if base in ("_index.md", "index.md"):
                d = posixpath.basename(posixpath.dirname(t.old_path))
                needles.add(d + "/")
                needles.add("](" + base)
            else:
                needles.add(base)
            if t.rel:
                needles.add(t.rel)
    hits = git.grep(head, sorted(needles))
    by_file = {}
    for path, lineno, text in hits:
        by_file.setdefault(path, []).append((lineno, text))
    refs = []
    for path, lines in sorted(by_file.items()):
        if nav_file and path == nav_file:
            for lineno, text in lines:
                m = NAV_URL_RE.match(text)
                if m:
                    refs.append(Ref(path, lineno, text.strip(), "nav", (m.group(2) or "")[1:] or None,
                                    key=_url_path_key(m.group(1))))
            continue
        if not path.endswith(".md"):
            content = git.show(head, path) or ""
            code_refs = refs_in_code(path, content)
            hit_lines = set(ln for ln, _ in lines)
            refs.extend(r for r in code_refs if r.line in hit_lines or any(abs(r.line - h) <= 3 for h in hit_lines))
        for lineno, text in lines:
            refs.extend(refs_in_line(path, lineno, text))
    return refs


def match_target(ref, targets):
    """The target a reference points at, or None."""
    for t in targets:
        if ref.kind == "md-link":
            if t.old_path in ref.paths:
                return t
        elif ref.kind in ("help_page_path", "helpPagePath"):
            if t.rel is not None and ref.key == norm_key(t.rel):
                return t
            if t.key is not None and ref.key == t.key:
                return t
        elif ref.kind in ("url", "nav"):
            if t.key is not None and ref.key == t.key:
                return t
    return None


# ---------------------------------------------------------------- cross-repo

def search_cross_repo(api, targets, cfg, notes):
    """Blob search for docs.gitlab.com/<key> in each group. Returns
    {target_index: [hit dicts]}."""
    out = {}
    calls = 0
    own = cfg.get("project_id")
    project_cache = {}
    seen = set()
    for ti, t in enumerate(targets):
        if t.key is None:
            continue
        if t.kind == "anchors" and not any(v["state"] == "lost" for v in t.lost.values()):
            continue
        for needle, group in [(n, g) for n in search_needles(t, targets) for g in cfg["groups"]]:
            if calls >= MAX_SEARCH_CALLS:
                notes.append("cross-repo search stopped after {} calls; later pages were not searched".format(calls))
                return out
            calls += 1
            results = blob_search(api, group, needle, notes)
            for r in results:
                pid = r.get("project_id")
                if own is not None and pid == own:
                    continue
                data = r.get("data") or ""
                start = int(r.get("startline") or 1)
                for idx, line in enumerate(data.split("\n")):
                    for m in DOCS_URL_RE.finditer(line):
                        p, a = split_anchor(m.group(1))
                        if _url_path_key(p) != t.key:
                            continue
                        hit_key = (pid, r.get("path"), start + idx, m.group(0))
                        if hit_key in seen:
                            continue
                        seen.add(hit_key)
                        proj = project_info(api, pid, project_cache, notes)
                        out.setdefault(ti, []).append({
                            "project_id": pid, "project": proj["path"], "public": proj["public"],
                            "path": r.get("path") or r.get("filename"), "line": start + idx,
                            "ref": r.get("ref"), "anchor": a, "text": m.group(0), "web_url": proj.get("web_url")})
    return out


def search_needles(t, targets):
    """Search strings for one page. A page whose URL is a prefix of other
    changed pages' URLs (a section `_index.md`) would match every child page,
    so search its lost anchors one by one instead."""
    base = "{}/{}".format(DOCS_HOST, t.key).rstrip("/")
    is_prefix = t.key == "" or any(o is not t and o.key and o.key.startswith(t.key + "/") for o in targets) \
        or posixpath.basename(t.old_path) in ("_index.md", "index.md")
    if t.kind == "anchors" and is_prefix:
        return ["{}/#{}".format(base, a) for a, v in sorted(t.lost.items()) if v["state"] == "lost"]
    return [base]


def blob_search(api, group, needle, notes):
    per_page = SEARCH_PER_PAGE
    results = []
    for search_type in ("zoekt", "advanced"):
        endpoint = "groups/{}/search?{}".format(gitlab_api.enc(group), gitlab_api.query({
            "scope": "blobs", "search": needle, "search_type": search_type, "per_page": per_page}))
        try:
            data = api.get(endpoint)
        except gitlab_api.GlabError as exc:
            if exc.status == 400 and search_type == "zoekt":
                continue  # exact code search not enabled: fall back to advanced search
            notes.append("search `{}` in {} failed: {}".format(needle, group, str(exc)[:160]))
            return []
        results = data if isinstance(data, list) else []
        if len(results) >= per_page:
            notes.append("search `{}` in {} returned {} results (cap); more references may exist".format(
                needle, group, len(results)))
        if search_type == "advanced":
            notes.append("search `{}` in {} used advanced search (tokenized, lower recall)".format(needle, group))
        return results
    return results


def project_info(api, pid, cache, notes):
    if pid in cache:
        return cache[pid]
    info = {"path": "project {}".format(pid), "public": False, "web_url": None}
    try:
        data = api.get("projects/{}".format(pid))
        if isinstance(data, dict):
            info = {"path": data.get("path_with_namespace") or info["path"],
                    "public": data.get("visibility") == "public", "web_url": data.get("web_url")}
    except gitlab_api.GlabError:
        # The error text can name the project, so it is not kept.
        notes.append("a project lookup failed; its hits are treated as non-public")
    cache[pid] = info
    return info


def fetch_global_nav(api, notes):
    endpoint = "projects/{}/repository/files/{}/raw?ref=main".format(
        gitlab_api.enc(NAV_PROJECT), gitlab_api.enc(NAV_PROJECT_PATH))
    try:
        text = api.get(endpoint)
    except gitlab_api.GlabError as exc:
        notes.append("global nav fetch failed: {}".format(str(exc)[:160]))
        return []
    if not isinstance(text, str):
        return []
    entries = []
    for i, line in enumerate(text.splitlines(), 1):
        m = NAV_URL_RE.match(line)
        if m:
            entries.append((i, line.strip(), _url_path_key(m.group(1))))
    return entries


# ---------------------------------------------------------------- findings

def fix_hint(cfg, anchor):
    hint = ("If the other project cannot change before this merges, keep the old heading text "
            "or open a follow-up MR there.")
    if cfg.get("custom_ids"):
        hint += " This project allows custom heading IDs, so you can also add `{{#{}}}` to the new heading.".format(anchor)
    return hint


def line_text(git, head, path, lineno):
    text = git.show(head, path) or ""
    lines = text.splitlines()
    if 1 <= lineno <= len(lines):
        return lines[lineno - 1]
    return None


def build_findings(git, head, targets, refs, cross, cfg):
    out = []
    redirect_stubs = set(t.path for t in targets if t.kind == "redirected")
    # In-repo references.
    for ref in refs:
        if ref.file in redirect_stubs:
            continue  # the stub's own "moved to" link
        t = match_target(ref, targets)
        if t is None:
            continue
        if ref.kind == "md-link" and not ref.paths and ref.file != (t.path or t.old_path):
            continue
        info = t.lost.get(ref.anchor) if ref.anchor else None
        page = t.path or t.old_path
        if ref.kind == "nav":
            if t.kind in ("moved", "deleted") and not t.has_redirect:
                out.append(F.make_finding(
                    "impact.broken-link", REVIEWER, "blocker", ref.file,
                    "This nav entry points to `{}`, which this change {} without a redirect. "
                    "Update the entry to the new URL or remove it.".format(t.old_path, verb(t)),
                    line=ref.line, quote=ref.text, source=SRC_NAV, evidence=[ev_doc(t)]))
            elif t.kind in ("moved", "deleted", "redirected"):
                out.append(F.make_finding(
                    "impact.stale-reference", REVIEWER, "major", ref.file,
                    "This nav entry points to `{}`, which is now a redirect{}. Point the entry at the "
                    "new page, or remove it.".format(t.old_path, to_clause(t)),
                    line=ref.line, quote=ref.text, source=SRC_NAV, evidence=[ev_doc(t)]))
            continue
        if t.kind in ("moved", "deleted") and not t.has_redirect:
            new_line = None
            if t.kind == "moved" and ref.kind == "md-link":
                new_line = replace_md_target(git, head, ref, t)
            out.append(F.make_finding(
                "impact.broken-link", REVIEWER, "blocker", ref.file,
                "This link points to `{}`, which this change {} without a redirect. Update the link{}."
                .format(t.old_path, verb(t), " to `{}`".format(t.path) if t.path else ""),
                line=ref.line, quote=ref.text, suggestion=new_line, fixable="suggest" if new_line else "manual",
                source=SRC_REDIRECTS, evidence=[ev_doc(t)]))
            continue
        if info and info["state"] == "lost":
            new = info.get("new")
            suggestion = None
            if new and t.kind == "anchors":
                suggestion = replace_anchor(git, head, ref, ref.anchor, new["anchor"])
            if new:
                msg = ("The heading `{}` in `{}` is now `{}`, so `#{}` no longer exists. Update this link to `#{}`."
                       .format(info["old"]["text"], page, new["text"], ref.anchor, new["anchor"]))
            elif t.kind == "redirected":
                msg = ("`{}` is now a redirect{}, and the target has no `#{}` section. Link to the section "
                       "that now covers this content.".format(t.old_path, to_clause(t), ref.anchor))
            else:
                msg = ("The heading `{}` was removed from `{}`, so `#{}` no longer exists. Link to the section "
                       "that now covers it, or keep the heading.".format(info["old"]["text"], page, ref.anchor))
            out.append(F.make_finding(
                "impact.broken-anchor", REVIEWER, "blocker", ref.file, msg, line=ref.line, quote=ref.text,
                suggestion=suggestion, fixable="suggest" if suggestion else "manual", source=SRC_ANCHORS,
                evidence=[ev_doc(t, info)]))
            continue
        if t.kind in ("moved", "deleted", "redirected"):
            expired = redirect_expired(t, cfg)
            out.append(F.make_finding(
                "impact.stale-reference", REVIEWER, "major" if expired else "minor", ref.file,
                "This link points to `{}`, which is now a redirect{}. Link to the new page directly; {}".format(
                    t.old_path, to_clause(t), "the redirect expired on {}.".format(t.remove_date) if expired
                    else "redirects expire."),
                line=ref.line, quote=ref.text, confidence="high", source=SRC_REDIRECTS, evidence=[ev_doc(t)]))

    # Pages that moved or were deleted without a redirect.
    for t in targets:
        if t.kind in ("moved", "deleted") and not t.has_redirect:
            url = " so `{}` keeps working".format(public_url(t.key)) if t.key is not None else ""
            out.append(F.make_finding(
                "impact.moved-page-no-redirect", REVIEWER, "blocker", t.old_path,
                "This change {} `{}` without a redirect. Keep `{}` as a redirect file with `redirect_to` and "
                "`remove_date`{}.".format("deletes" if t.kind == "deleted" else "moves", t.old_path, t.old_path, url),
                quote=t.old_title, source=SRC_REDIRECTS, evidence=[ev_doc(t)]))
        if t.lost_redirect_target:
            out.append(F.make_finding(
                "impact.broken-link", REVIEWER, "blocker", t.path,
                "`redirect_to` points to `{}`, which does not exist. Point it at the page that replaces "
                "this one.".format(t.redirect_to), line=t.redirect_line[0], quote=t.redirect_line[1],
                source=SRC_REDIRECTS))

    # Cross-repo references: one finding per page and anchor, all hits as evidence.
    for ti, hits in sorted(cross.items()):
        t = targets[ti]
        by_anchor = {}
        for h in hits:
            info = t.lost.get(h["anchor"]) if h["anchor"] else None
            if t.kind in ("moved", "deleted") and not t.has_redirect:
                by_anchor.setdefault(("page", None), []).append(h)
            elif info and info["state"] == "lost":
                by_anchor.setdefault(("anchor", h["anchor"]), []).append(h)
            elif t.kind in ("moved", "deleted", "redirected"):
                by_anchor.setdefault(("stale", None), []).append(h)
        for (kind, anchor), group in sorted(by_anchor.items(), key=lambda x: (x[0][0], x[0][1] or "")):
            listing, more = hit_listing(group)
            evidence = []
            for h in group:
                ev = ev_search(h)
                if ev not in evidence:
                    evidence.append(ev)
            if kind == "anchor":
                info = t.lost[anchor]
                new = info.get("new")
                head_line = new["line"] if (new and t.kind == "anchors") else None
                quote = new["raw"] if head_line else info["old"]["raw"]
                if new:
                    change = "renames the heading `{}` to `{}` (`#{}`)".format(info["old"]["text"], new["text"], new["anchor"])
                else:
                    change = "removes the heading `{}`".format(info["old"]["text"])
                out.append(F.make_finding(
                    "impact.broken-anchor", REVIEWER, "major", t.label(),
                    "This change {}, but {} reference(s) in other projects still link to `{}#{}`: {}{}. "
                    "Update those links. {}".format(change, len(group), public_url(t.key), anchor, listing, more,
                                                   fix_hint(cfg, anchor)),
                    line=head_line, quote=quote, confidence="high", source=SRC_OTHER_REPOS, evidence=evidence))
            elif kind == "page":
                out.append(F.make_finding(
                    "impact.broken-link", REVIEWER, "major", t.old_path,
                    "{} reference(s) in other projects link to `{}`, which this change {} without a redirect: "
                    "{}{}. Add a redirect, then update those links.".format(
                        len(group), public_url(t.key), verb(t), listing, more),
                    quote=t.old_title, source=SRC_OTHER_REPOS, evidence=evidence))
            else:
                expired = redirect_expired(t, cfg)
                out.append(F.make_finding(
                    "impact.stale-reference", REVIEWER, "major" if expired else "minor", t.label(),
                    "{} reference(s) in other projects link to `{}`, which is now a redirect{}: {}{}. {}".format(
                        len(group), public_url(t.key), to_clause(t), listing, more,
                        "The redirect expired on {}, so update them now.".format(t.remove_date) if expired else
                        "Update them in a follow-up MR before the redirect expires{}.".format(
                            " on {}".format(t.remove_date) if t.remove_date else "")),
                    quote=t.old_title, confidence="medium", source=SRC_OTHER_REPOS, evidence=evidence))

    return out


def add_global_nav_hits(cross, targets, global_nav):
    """Global nav entries count as cross-repo references."""
    for lineno, text, key in global_nav:
        for ti, t in enumerate(targets):
            if t.key is None or key != t.key or t.kind == "anchors":
                continue
            cross.setdefault(ti, []).append({
                "project_id": None, "project": NAV_PROJECT, "public": True,
                "path": NAV_PROJECT_PATH, "line": lineno, "ref": "main", "anchor": None,
                "text": text, "web_url": "https://gitlab.com/" + NAV_PROJECT})


def redirect_expired(t, cfg):
    """True when the redirect's remove_date is on or before today."""
    day = dates.parse_day(t.remove_date)
    return bool(day and cfg.get("today") and day <= cfg["today"])


def private_strings(cross):
    """Identifiers of non-public projects seen in cross-repo hits."""
    out, ids = set(), set()
    for hits in cross.values():
        for h in hits:
            if h["public"]:
                continue
            for v in (h.get("project"), h.get("web_url")):
                if v and not str(v).startswith("project "):
                    out.add(str(v))
            if h.get("project_id") is not None:
                ids.add(str(h["project_id"]))
    return out, ids


def redact(value, strings, ids):
    """Remove non-public project paths and IDs from any output value."""
    if isinstance(value, dict):
        return dict((k, redact(v, strings, ids)) for k, v in value.items())
    if isinstance(value, list):
        return [redact(v, strings, ids) for v in value]
    if not isinstance(value, str):
        return value
    for sv in sorted(strings, key=len, reverse=True):
        value = value.replace(sv, NON_PUBLIC)
    for pid in ids:
        value = re.sub(r"(project_id[:= ]\s*|projects/|\(id |project )" + re.escape(pid) + r"\b", NON_PUBLIC, value)
    return value


def verb(t):
    return {"moved": "moves to `{}`".format(t.path), "deleted": "deletes",
            "redirected": "turns into a redirect", "anchors": "changes"}[t.kind]


def to_clause(t):
    return " to `{}`".format(t.redirect_to or t.path) if (t.redirect_to or (t.kind == "moved" and t.path)) else ""


def ev_doc(t, info=None):
    note = "{} ({})".format(t.kind, t.old_path)
    if info:
        note = "old heading `{}` at {}:{}".format(info["old"]["text"], t.old_path, info["old"]["line"])
    return {"kind": "doc", "ref": t.label(), "note": note}



def hit_label(h):
    if h["public"]:
        return "{}:{}:{}".format(h["project"], h["path"], h["line"])
    return NON_PUBLIC


def hit_listing(group):
    """Readable list of hits: public ones by path, non-public ones counted."""
    shown = [hit_label(h) for h in group if h["public"]][:MAX_REFS_PER_FINDING]
    hidden = sum(1 for h in group if not h["public"])
    parts = list(shown)
    if hidden:
        parts.append("{} reference(s) in non-public projects (paths withheld)".format(hidden))
    more = sum(1 for h in group if h["public"]) - len(shown)
    return ", ".join(parts), (" and {} more".format(more) if more > 0 else "")


def ev_search(h):
    if h["public"]:
        ref = "{}:{}:{}".format(h["project"], h["path"], h["line"])
        if h.get("web_url") and h.get("ref"):
            ref = "{}/-/blob/{}/{}#L{}".format(h["web_url"], h["ref"], h["path"], h["line"])
        return {"kind": "search", "ref": ref, "note": h["text"]}
    return {"kind": "search", "ref": NON_PUBLIC, "note": "path and ID withheld"}


def replace_anchor(git, head, ref, old, new):
    line = line_text(git, head, ref.file, ref.line)
    if line is None:
        return None
    for a, b in (("#" + old, "#" + new), ("'" + old + "'", "'" + new + "'"), ('"' + old + '"', '"' + new + '"')):
        if a in line:
            return line.replace(a, b, 1)
    return None


def replace_md_target(git, head, ref, t):
    line = line_text(git, head, ref.file, ref.line)
    if line is None or not t.path:
        return None
    m = MD_LINK_RE.search(ref.text)
    if not m:
        return None
    target = m.group(1)
    _, anchor = split_anchor(target)
    rel = posixpath.relpath(t.path, posixpath.dirname(ref.file) or ".")
    new_target = rel + ("#" + anchor if anchor else "")
    return line.replace(ref.text, ref.text.replace(target, new_target, 1), 1)


# ---------------------------------------------------------------- output

def render_summary(base, head, targets, refs_by_target, cross, notes, cfg):
    lines = ["# Impact summary ({}..{})".format(base[:12], head[:12]), ""]
    anchors = [(t, a, i) for t in targets for a, i in sorted(t.lost.items()) if i["state"] == "lost"]
    lines.append("## Lost anchors ({})".format(len(anchors)))
    lines.append("")
    if not anchors:
        lines.append("None.")
    for t, a, info in anchors:
        new = info.get("new")
        what = "renamed to `#{}` ({})".format(new["anchor"], new["text"]) if new else "removed"
        lines.append("- `{}#{}` (heading \"{}\"): {}".format(t.label(), a, info["old"]["text"], what))
    lines.append("")
    pages = [t for t in targets if t.kind in ("moved", "deleted", "redirected")]
    lines.append("## Moved, deleted, or redirected pages ({})".format(len(pages)))
    lines.append("")
    if not pages:
        lines.append("None.")
    for t in pages:
        state = "redirect in place" if t.has_redirect else "NO redirect"
        if t.remove_date:
            state += ", remove_date {}{}".format(t.remove_date, " (expired)" if redirect_expired(t, cfg) else "")
        dest = " -> `{}`".format(t.redirect_to or t.path) if (t.redirect_to or t.path) else ""
        url = " ({})".format(public_url(t.key)) if t.key is not None else ""
        lines.append("- `{}`{}: {}, {}{}".format(t.old_path, dest, t.kind, state, url))
    lines.append("")
    lines.append("## Inbound references")
    lines.append("")
    any_refs = False
    for ti, t in enumerate(targets):
        rs = refs_by_target.get(ti, [])
        xs = cross.get(ti, [])
        if not rs and not xs:
            continue
        any_refs = True
        lines.append("- `{}`: {} in this repo, {} in other projects".format(t.label(), len(rs), len(xs)))
        for r in rs[:15]:
            lines.append("  - {}:{} ({}{})".format(r.file, r.line, r.kind, ", #" + r.anchor if r.anchor else ""))
        for h in xs[:15]:
            where = hit_label(h)
            lines.append("  - {} (cross-repo{}{})".format(where, ", #" + h["anchor"] if h["anchor"] else "",
                                                          "" if h["public"] else ", non-public"))
    if not any_refs:
        lines.append("None found.")
    if notes:
        lines.append("")
        lines.append("## Search notes")
        lines.append("")
        for n in notes:
            lines.append("- " + n)
    return "\n".join(lines) + "\n"


def parse_args(argv):
    p = argparse.ArgumentParser(
        description="Find inbound references that a docs change breaks: lost anchors and moved, deleted, "
                    "or redirected pages. Read-only.",
        epilog="Exit codes: 0 no blocker, 1 blockers found, 2 usage or environment error.")
    p.add_argument("--repo", default=".", help="local git checkout (default: .)")
    p.add_argument("--base", help="base commit (SHA or ref)")
    p.add_argument("--head", default=None, help="head commit (default: HEAD)")
    p.add_argument("--mr", type=int, help="MR IID; with --project, reads base and head SHAs through glab api")
    p.add_argument("--project", help="project path, for --mr and to exclude self-hits in cross-repo search")
    p.add_argument("--docs-root", help="docs root in the repo (config docs_root; default: detected)")
    p.add_argument("--url-prefix", help="docs.gitlab.com path prefix such as `orbit/` (config url_prefix)")
    p.add_argument("--nav-file", help="nav file in the repo (config nav_file; default: detected)")
    p.add_argument("--offline", action="store_true", help="skip all GitLab API calls (no cross-repo search)")
    p.add_argument("--glab", default=None, help="glab binary (default: $DOCS_REVIEW_GLAB or glab)")
    p.add_argument("--summary", action="store_true", help="print a Markdown summary of inbound links and moved pages")
    p.add_argument("--json", action="store_true", help="print findings JSON to stdout")
    p.add_argument("--out", help="write findings JSON to this file")
    return p.parse_args(argv)


# docs.gitlab.com path prefixes of the projects whose docs are published there.
# A standalone docs project without `url_prefix` gets wrong public URLs.
KNOWN_URL_PREFIXES = {
    "gitlab-org/gitlab": "",
    "gitlab-org/gitlab-foss": "",
    "gitlab-org/gitlab-runner": "runner/",
    "gitlab-org/omnibus-gitlab": "omnibus/",
    "gitlab-org/charts/gitlab": "charts/",
    "gitlab-org/cloud-native/gitlab-operator": "operator/",
    "gitlab-org/orbit/knowledge-graph": "orbit/",
}


def resolve_url_prefix(cli, conf_value, project, docs_root):
    """(url_prefix, note). --url-prefix, then `url_prefix` in the config, then
    the known prefix for the project. A docs root other than `doc` is a
    standalone docs project: without a prefix its URLs are probably wrong."""
    if cli is not None:
        return cli, None
    if conf_value:
        return conf_value, None
    if project in KNOWN_URL_PREFIXES:
        prefix = KNOWN_URL_PREFIXES[project]
        return prefix, ("url_prefix `{}` inferred from the project path {}".format(prefix, project) if prefix else None)
    if docs_root and docs_root != "doc":
        return "", ("url_prefix is not set, and docs_root `{}` looks like a standalone docs project: public "
                    "docs.gitlab.com URLs in these findings may lack the project's path prefix (for example "
                    "`orbit/`). Set `url_prefix` in .docs-review.yml or pass --url-prefix.".format(docs_root))
    return "", None


def detect_project(git):
    proc = git.run("remote", "get-url", "origin", check=False)
    url = proc.stdout.strip()
    m = re.search(r"gitlab\.com[:/](.+?)(?:\.git)?$", url)
    return m.group(1) if m else None


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    repo = os.path.abspath(args.repo)
    if not os.path.isdir(repo):
        warn("--repo {} is not a directory".format(repo))
        return 2
    git = Git(repo)
    if git.run("rev-parse", "--git-dir", check=False).returncode != 0:
        warn("{} is not a git checkout".format(repo))
        return 2
    try:
        conf = lint_config.load(os.path.join(repo, lint_config.CONFIG_NAME), warn)
    except lint_config.ConfigError as exc:
        warn("{}: {}; using defaults".format(lint_config.CONFIG_NAME, exc))
        conf = {}
    notes = []
    api = None if args.offline else gitlab_api.GitLab(args.glab, delay=SEARCH_DELAY, timeout=API_TIMEOUT)

    base, head = args.base, args.head
    if args.mr:
        if not args.project:
            warn("--mr needs --project")
            return 2
        if api is None:
            warn("--mr needs API access; drop --offline or pass --base and --head")
            return 2
        try:
            mr = api.get("projects/{}/merge_requests/{}".format(gitlab_api.enc(args.project), args.mr))
        except gitlab_api.GlabError as exc:
            warn(str(exc))
            return 2
        refs = (mr or {}).get("diff_refs") or {}
        base = base or refs.get("start_sha") or refs.get("base_sha")
        head = head or refs.get("head_sha")
    head = head or "HEAD"
    if not base:
        warn("pass --base (and optionally --head), or --mr with --project")
        return 2
    for rev in (base, head):
        if not git.exists(rev):
            warn("commit {} is not in {}; fetch it first, for example "
                 "`git fetch origin refs/merge-requests/<iid>/head`".format(rev, repo))
            return 2
    base, head = git.resolve(base), git.resolve(head)

    docs_root = args.docs_root or conf.get("docs_root")
    if not docs_root:
        docs_root = next((d for d in page_class.DOCS_ROOT_CANDIDATES if os.path.isdir(os.path.join(repo, d))), "")
    docs_root = docs_root.strip("/")
    nav_file = args.nav_file or conf.get("nav_file")
    if not nav_file:
        nav_file = next((n for n in NAV_CANDIDATES if git.show(head, n) is not None), None)
    groups = conf.get("cross_repo_search_groups") or DEFAULT_GROUPS
    project = args.project or detect_project(git)
    url_prefix, prefix_note = resolve_url_prefix(args.url_prefix, conf.get("url_prefix"), project, docs_root)
    if prefix_note:
        notes.append(prefix_note)
        if not url_prefix and docs_root != "doc":
            warn(prefix_note)
    cfg = {
        "docs_root": docs_root, "url_prefix": url_prefix,
        "groups": [g.strip() for g in groups if g and str(g).strip()],
        "custom_ids": bool(conf.get("custom_heading_ids")), "project_id": None,
        "today": datetime.date.today(),
    }

    try:
        targets = analyze(git, base, head, cfg, notes)
        refs = search_repo(git, head, targets, nav_file) if targets else []
    except UsageError as exc:
        warn(str(exc))
        return 2

    cross = {}
    if api is not None and targets:
        if project:
            try:
                info = api.get("projects/{}".format(gitlab_api.enc(project)))
                cfg["project_id"] = (info or {}).get("id")
            except gitlab_api.GlabError as exc:
                notes.append("could not resolve project {}: {}".format(project, str(exc)[:120]))
        cross = search_cross_repo(api, targets, cfg, notes)
        if any(t.kind != "anchors" for t in targets):
            add_global_nav_hits(cross, targets, fetch_global_nav(api, notes))
    elif args.offline:
        notes.append("offline: cross-repo search and global nav skipped")

    findings = build_findings(git, head, targets, refs, cross, cfg)

    refs_by_target = {}
    for r in refs:
        t = match_target(r, targets)
        if t is not None:
            refs_by_target.setdefault(targets.index(t), []).append(r)

    summary = {
        "lost_anchors": [{"file": t.label(), "anchor": a, "old_heading": i["old"]["text"],
                          "new_anchor": (i.get("new") or {}).get("anchor"), "state": i["state"]}
                         for t in targets for a, i in sorted(t.lost.items())],
        "pages": [{"old_path": t.old_path, "path": t.path, "kind": t.kind, "has_redirect": t.has_redirect,
                   "redirect_to": t.redirect_to, "remove_date": t.remove_date,
                   "url": public_url(t.key) if t.key is not None else None}
                  for t in targets if t.kind != "anchors"],
        "notes": notes,
        "cross_repo_hits": sum(len(v) for v in cross.values()),
        "non_public_hits": sum(1 for v in cross.values() for h in v if not h["public"]),
    }
    target = {"repo": repo, "base": base, "head": head, "project": project, "mr": args.mr,
              "docs_root": docs_root, "url_prefix": url_prefix, "nav_file": nav_file}
    strings, ids = private_strings(cross)
    doc = redact(F.new_doc(target, findings, impact=summary), strings, ids)
    findings = doc["findings"]
    if args.out:
        F.dump(doc, args.out)
    if args.summary:
        sys.stdout.write(redact(render_summary(base, head, targets, refs_by_target, cross, notes, cfg), strings, ids))
    elif args.json:
        sys.stdout.write(F.dump(doc))
    else:
        for f in findings:
            loc = "{}:{}".format(f["file"], f["line"]) if f.get("line") else f["file"]
            sys.stdout.write("{} [{}] {}: {}\n".format(loc, f["severity"], f["id"], f["message"]))
        sys.stdout.write("{} finding(s); {} lost anchor(s); {} moved/deleted/redirected page(s)\n".format(
            len(findings), len(summary["lost_anchors"]), len(summary["pages"])))
        for n in doc["impact"]["notes"]:
            sys.stdout.write("note: {}\n".format(n))
    return 1 if F.has_blocker(findings) else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, UnicodeError, ValueError, RuntimeError) as exc:  # a one-line error, not a traceback
        if os.environ.get("DOCS_REVIEW_DEBUG"):
            raise
        sys.stderr.write("{}: error: {}\n".format(sys.argv[0].rsplit("/", 1)[-1], exc))
        sys.exit(2)
