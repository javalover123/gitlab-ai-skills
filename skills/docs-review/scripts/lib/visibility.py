"""Keep non-public content out of posted comments.

The facts reviewer reads source with the running account's access, which
can include confidential issues, confidential work items and epics, and
private or internal projects. A posted comment on a public MR must not
quote, describe, or link them. This module finds GitLab references in a
finding (evidence refs and text), checks each one with read-only API calls,
and rewrites the finding so only public references remain.

Fail closed: a reference that cannot be confirmed as public (API error, not
found, no API) is treated as non-public.

Python 3.9 or later, stdlib only.
"""

import re

PUBLIC, RESTRICTED, UNKNOWN = "public", "restricted", "unknown"

# https://host/group/project/-/issues/12, work_items, merge_requests, epics
URL_ITEM_RE = re.compile(
    r"https?://[^/\s)\]>]+/(?:groups/)?([\w.-]+(?:/[\w.-]+)*?)/-/(issues|work_items|merge_requests|epics)/(\d+)")
# https://host/group/project/-/blob/... or /-/tree/...
URL_FILE_RE = re.compile(r"https?://[^/\s)\]>]+/([\w.-]+(?:/[\w.-]+)+?)/-/(?:blob|tree|raw|commit)/")
# group/project#12, group/project!12 (a path with a slash), and group&12 (epics)
SHORT_RE = re.compile(r"(?<![\w/.-])([\w.-]+(?:/[\w.-]+)+)([#!])(\d+)\b")
EPIC_RE = re.compile(r"(?<![\w/.-])([\w.-]+(?:/[\w.-]+)*)&(\d+)\b")
# group/project@sha:path (code evidence with a full project path)
CODE_RE = re.compile(r"(?<![\w/.-])([\w.-]+(?:/[\w.-]+)+)@[0-9a-f]{6,40}:")

KIND = {"#": "issues", "!": "merge_requests", "&": "epics"}
TEXT_FIELDS = ("message", "suggestion", "why", "importance_why")
NEUTRAL = ("Public sources do not confirm this claim. Internal evidence exists that a team member with "
           "access can check.")


def enc(path):
    return path.replace("/", "%2F")


def refs_in(text):
    """[(kind, path, iid or None, matched text)] for GitLab references in text."""
    out = []
    if not isinstance(text, str) or not text:
        return out
    for m in URL_ITEM_RE.finditer(text):
        out.append((m.group(2), m.group(1), int(m.group(3)), m.group(0)))
    for m in URL_FILE_RE.finditer(text):
        out.append(("project", m.group(1), None, m.group(0)))
    for m in SHORT_RE.finditer(text):
        out.append((KIND[m.group(2)], m.group(1), int(m.group(3)), m.group(0)))
    for m in EPIC_RE.finditer(text):
        out.append(("epics", m.group(1), int(m.group(2)), m.group(0)))
    for m in CODE_RE.finditer(text):
        out.append(("project", m.group(1), None, m.group(0)))
    return out


class Visibility(object):
    """Cached, read-only visibility checks through a gitlab_api.GitLab."""

    def __init__(self, api):
        self.api = api
        self.cache = {}

    def _get(self, endpoint):
        if self.api is None:
            return None
        try:
            return self.api.get(endpoint)
        except Exception:  # noqa: BLE001 - any failure means "not confirmed public"
            return None

    def _project(self, path):
        key = ("project", path)
        if key not in self.cache:
            data = self._get("projects/{}".format(enc(path)))
            self.cache[key] = (PUBLIC if isinstance(data, dict) and data.get("visibility") == "public"
                               else RESTRICTED if isinstance(data, dict) else UNKNOWN)
        return self.cache[key]

    def _group(self, path):
        key = ("group", path)
        if key not in self.cache:
            data = self._get("groups/{}".format(enc(path)))
            self.cache[key] = (PUBLIC if isinstance(data, dict) and data.get("visibility") == "public"
                               else RESTRICTED if isinstance(data, dict) else UNKNOWN)
        return self.cache[key]

    def check(self, kind, path, iid=None):
        key = (kind, path, iid)
        if key in self.cache:
            return self.cache[key]
        if kind == "project":
            result = self._project(path)
        elif kind == "epics":
            result = self._group(path)
            if result == PUBLIC:
                data = self._get("groups/{}/epics/{}".format(enc(path), iid))
                result = (UNKNOWN if not isinstance(data, dict)
                          else RESTRICTED if data.get("confidential") else PUBLIC)
        else:
            result = self._project(path)
            if result == PUBLIC:
                endpoint = "merge_requests" if kind == "merge_requests" else "issues"
                data = self._get("projects/{}/{}/{}".format(enc(path), endpoint, iid))
                result = (UNKNOWN if not isinstance(data, dict)
                          else RESTRICTED if data.get("confidential") else PUBLIC)
        self.cache[key] = result
        return result

    def public(self, ref):
        kind, path, iid, _ = ref
        return self.check(kind, path, iid) == PUBLIC


def gate(f, vis):
    """(finding, withheld) with every non-public reference removed.

    - A reviewer that follows the contract marks non-public evidence as
      `{"ref": "non-public"}` and writes the message from public sources
      only. The finding keeps its message, with a withheld-evidence note.
    - When an evidence ref or note, or the finding's own text, names an item
      that is not confirmed public, that evidence is dropped, the message is
      replaced with a neutral sentence, and the suggestion is dropped: the
      text may describe the item, and a script cannot tell.
    """
    g = dict(f)
    evidence, marked, leaked = [], False, 0
    for e in g.get("evidence") or []:
        if not isinstance(e, dict):
            continue
        if str(e.get("ref") or "").strip().lower() in ("non-public", "a non-public project"):
            marked = True
            continue
        refs = refs_in(str(e.get("ref") or "")) + refs_in(str(e.get("note") or ""))
        if any(not vis.public(r) for r in refs):
            leaked += 1
            continue
        evidence.append(e)
    text_refs = [r for k in TEXT_FIELDS for r in refs_in(g.get(k) or "")]
    leaked += sum(1 for r in text_refs if not vis.public(r))
    if marked or leaked:
        evidence.append({"kind": "note", "ref": "non-public", "note": "internal evidence withheld"})
        g["withheld_internal"] = True
    g["evidence"] = evidence
    if leaked:
        g["message"] = NEUTRAL
        g["suggestion"] = None
        for k in ("why", "importance_why", "alternatives"):
            g.pop(k, None)
        if g.get("fixable") in ("auto", "suggest"):
            g["fixable"] = "manual"
    return g, leaked


PLACEHOLDER = "[internal reference withheld]"


def redact_text(text, vis):
    """Text with every reference that is not confirmed public replaced."""
    if not isinstance(text, str):
        return text, 0
    n = 0
    for r in sorted(refs_in(text), key=lambda r: -len(r[3])):
        if not vis.public(r) and r[3] in text:
            text = text.replace(r[3], PLACEHOLDER)
            n += 1
    return text, n

