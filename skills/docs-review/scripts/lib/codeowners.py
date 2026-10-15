"""GitLab CODEOWNERS: glob patterns, sections, and the owners of a path.

Python 3.9+, stdlib only.
"""

import re

# GitLab uses the first of these that exists.
LOCATIONS = ("CODEOWNERS", "docs/CODEOWNERS", ".gitlab/CODEOWNERS")
SECTION_RE = re.compile(r"^\^?\[([^\]]+)\](?:\[\d*\])?\s*(.*)$")


def glob_regex(pattern):
    """Regex for a CODEOWNERS or `.docs-review.yml` path glob (`/` anchors, `**`)."""
    pattern = pattern.strip()
    anchored = pattern.startswith("/")
    p = pattern.lstrip("/")
    if p.endswith("/"):
        p += "**"
    out, i = "", 0
    while i < len(p):
        if p.startswith("**/", i):
            out, i = out + "(?:.*/)?", i + 3
        elif p.startswith("**", i):
            out, i = out + ".*", i + 2
        elif p[i] == "*":
            out, i = out + "[^/]*", i + 1
        elif p[i] == "?":
            out, i = out + "[^/]", i + 1
        else:
            out, i = out + re.escape(p[i]), i + 1
    return re.compile(("^" if anchored else "^(?:.*/)?") + out + "(?:/.*)?$")


def owner_handles(tokens):
    """`@user` and `@group/sub`. Roles (`@@developer`) and emails cannot be
    named, so they are dropped."""
    return [t for t in tokens if t.startswith("@") and not t.startswith("@@")]


def parse(text):
    """[(section_key, section_name, pattern, regex, owners)] in file order.

    Rules before any `[Section]` header are in the default section. Section
    names are case-insensitive, so repeated sections merge. A rule with no
    owners takes its section's default owners (`[Section] @owner`).
    """
    rules, name, defaults = [], "", []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        sm = SECTION_RE.match(line)
        if sm:
            name, defaults = sm.group(1).strip(), owner_handles(sm.group(2).split())
            continue
        parts = re.split(r"(?<!\\)\s+", line)
        pattern = parts[0].replace("\\ ", " ").replace("\\#", "#")
        owners = owner_handles(parts[1:]) if len(parts) > 1 else defaults
        rules.append((name.lower(), name, pattern, glob_regex(pattern), owners))
    return rules


def owners_for(rules, path):
    """{section_key: (section_name, pattern, owners)}: the last matching rule in
    each section wins (GitLab semantics)."""
    best = {}
    for key, name, pattern, regex, owners in rules:
        if regex.match(path):
            best[key] = (name, pattern, owners)
    return best


def first_owner(text, path):
    """The first owner of the last rule that matches `path`, across sections."""
    found = None
    for _key, _name, _pattern, regex, owners in parse(text):
        if owners and regex.match(path):
            found = owners[0].lstrip("@")
    return found
