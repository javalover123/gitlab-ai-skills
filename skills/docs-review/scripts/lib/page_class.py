"""Page classes that change which docs rules apply.

Python 3.9+, stdlib only.

Release notes (`release-notes`) are their own page class. They follow the
release notes templates, not the topic types: a feature release note has
`tier`, `offering`, `documentation_link`, `work_item`, and `categories` in
its front matter and a short body; a minor release index has `stage: Release
Notes` and `group: Monthly Release`. Neither has `info`, and the standard
stage and group values, the availability details, and the task rules do not
apply. A page is a release note when it is under `<docs root>/releases/`, or
when its front matter matches a release notes template.
"""

import re

RELEASE_NOTES = "release-notes"
RELEASE_NOTES_STAGE = "release notes"
RELEASE_NOTES_GROUPS = ("monthly release", "patch release")
# Keys only the feature release note template uses.
FEATURE_NOTE_KEYS = ("documentation_link", "work_item")
# Front matter keys the release notes templates use, beyond the standard ones.
RELEASE_NOTE_KEYS = ("tier", "offering", "documentation_link", "work_item", "categories", "level", "weight",
                     "date")
# Docs roots to try when the config sets none, most specific first.
DOCS_ROOT_CANDIDATES = ("doc", "docs/source", "docs/content", "content", "docs")

FRONT_MATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*(\n|\Z)", re.S)


def front_matter_of(text):
    """{key: value} of the top-level scalar keys in a page's front matter."""
    m = FRONT_MATTER_RE.match(text or "")
    out = {}
    if not m:
        return out
    for line in m.group(1).split("\n"):
        kv = re.match(r"^([A-Za-z_][\w-]*):\s*(.*?)\s*$", line)
        if kv:
            out[kv.group(1)] = kv.group(2).strip("'\"")
    return out


def under_releases(path, docs_roots):
    """True when `path` (relative to the repository) is under `<docs root>/releases/`."""
    path = re.sub(r"^\./", "", path or "")
    for root in docs_roots or ():
        r = (root or "").strip("/")
        if r in ("", "."):
            if path.startswith("releases/"):
                return True
        elif path.startswith(r + "/releases/"):
            return True
    return False


def is_release_notes(path, front_matter=None, docs_roots=("doc",)):
    """True for a release notes page, by path or by template front matter."""
    if under_releases(path, docs_roots):
        return True
    fm = front_matter or {}
    if "redirect_to" in fm:
        return False
    if str(fm.get("stage") or "").strip().lower() == RELEASE_NOTES_STAGE:
        return True
    if str(fm.get("group") or "").strip().lower() in RELEASE_NOTES_GROUPS:
        return True
    return all(k in fm for k in FEATURE_NOTE_KEYS)


def page_class(path, front_matter=None, docs_roots=("doc",)):
    """The page class that changes rules, or None for a standard page."""
    return RELEASE_NOTES if is_release_notes(path, front_matter, docs_roots) else None
