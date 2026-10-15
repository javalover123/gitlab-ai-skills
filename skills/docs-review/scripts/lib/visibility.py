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

# https://host/group/project/-/issues/12, work_items, merge_requests, epics,
# with an optional #note_34 fragment (a note can be internal on a public item)
URL_ITEM_RE = re.compile(
    r"https?://[^/\s)\]>]+/(?:groups/)?([\w.-]+(?:/[\w.-]+)*?)/-/(issues|work_items|merge_requests|epics)/(\d+)"
    r"(?:[^\s)\]>#]*#note_(\d+))?")
# https://host/group/project/-/blob/... or /-/tree/...
URL_FILE_RE = re.compile(r"https?://[^/\s)\]>]+/([\w.-]+(?:/[\w.-]+)+?)/-/(?:blob|tree|raw|commit)/")
# group/project#12, group/project!12 (a path with a slash), and group&12 (epics)
SHORT_RE = re.compile(r"(?<![\w/.-])([\w.-]+(?:/[\w.-]+)+)([#!])(\d+)\b")
# project#12 (same namespace) and bare #12, !12 (same project)
SIBLING_RE = re.compile(r"(?<![\w/.&#!-])([A-Za-z0-9_][\w.-]*)([#!])(\d+)\b")
PAGE_SUFFIXES = (".md", ".html", ".htm")
BARE_RE = re.compile(r"(?<![\w/.&#!\]-])([#!])(\d+)\b")
EPIC_RE = re.compile(r"(?<![\w/.-])([\w.-]+(?:/[\w.-]+)*)&(\d+)\b")
# group/project@sha:path (code evidence with a full project path)
CODE_RE = re.compile(r"(?<![\w/.-])([\w.-]+(?:/[\w.-]+)+)@[0-9a-f]{6,40}:")

KIND = {"#": "issues", "!": "merge_requests", "&": "epics"}
# The project feature a reference reads, and its access level field.
FEATURE = {"issues": "issues_access_level", "work_items": "issues_access_level",
           "merge_requests": "merge_requests_access_level", "project": "repository_access_level"}
# Fields that are ids, paths, hashes, or numbers, never prose.
SKIP_FIELDS = ("fingerprint", "file", "id", "reviewer", "severity", "group", "spot", "verdict", "confidence",
               "fixable", "line", "end_line", "importance", "scope", "sme", "conflicts_with")
NEUTRAL = ("Public sources do not confirm this claim. Internal evidence exists that a team member with "
           "access can check.")


def enc(path):
    return path.replace("/", "%2F")


def refs_in(text, project=None):
    """[(kind, path, iid or None, matched text, note id or None)] for GitLab
    references in text. Same-namespace and bare references resolve against
    `project` (group/project); with no project their path is None, which is
    never confirmed public."""
    out = []
    if not isinstance(text, str) or not text:
        return out
    namespace = project.rsplit("/", 1)[0] if project and "/" in project else None
    for m in URL_ITEM_RE.finditer(text):
        out.append((m.group(2), m.group(1), int(m.group(3)), m.group(0), int(m.group(4)) if m.group(4) else None))
    for m in URL_FILE_RE.finditer(text):
        out.append(("project", m.group(1), None, m.group(0), None))
    for m in SHORT_RE.finditer(text):
        out.append((KIND[m.group(2)], m.group(1), int(m.group(3)), m.group(0), None))
    for m in SIBLING_RE.finditer(text):
        if m.group(1).lower().endswith(PAGE_SUFFIXES):
            continue  # `page.md#3` is a link to a heading, not a project reference
        path = "{}/{}".format(namespace, m.group(1)) if namespace else None
        out.append((KIND[m.group(2)], path, int(m.group(3)), m.group(0), None))
    for m in BARE_RE.finditer(text):
        out.append((KIND[m.group(1)], project, int(m.group(2)), m.group(0), None))
    for m in EPIC_RE.finditer(text):
        out.append(("epics", m.group(1), int(m.group(2)), m.group(0), None))
    for m in CODE_RE.finditer(text):
        out.append(("project", m.group(1), None, m.group(0), None))
    return out


def strings(value, skip=SKIP_FIELDS):
    """Every string inside a finding, at any depth, except id-like fields."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for k, v in value.items():
            if k not in skip:
                for x in strings(v, skip):
                    yield x
    elif isinstance(value, (list, tuple)):
        for v in value:
            for x in strings(v, skip):
                yield x


class Visibility(object):
    """Cached, read-only visibility checks through a gitlab_api.GitLab.
    `project` is the target project, for same-project references."""

    def __init__(self, api, project=None):
        self.api = api
        self.project = project
        self.cache = {}

    def _get(self, endpoint):
        if self.api is None:
            return None
        try:
            return self.api.get(endpoint)
        except Exception:  # noqa: BLE001 - any failure means "not confirmed public"
            return None

    def _project(self, path, kind):
        key = ("project", path)
        if key not in self.cache:
            data = self._get("projects/{}".format(enc(path)))
            self.cache[key] = data if isinstance(data, dict) else None
        data = self.cache[key]
        if data is None:
            return UNKNOWN
        if data.get("visibility") != "public":
            return RESTRICTED
        # A public project can limit issues, MRs, or code to members.
        level = data.get(FEATURE.get(kind, "repository_access_level"))
        if level is None:
            return UNKNOWN
        return PUBLIC if level in ("enabled", "public") else RESTRICTED

    def _group(self, path):
        key = ("group", path)
        if key not in self.cache:
            data = self._get("groups/{}".format(enc(path)))
            self.cache[key] = (PUBLIC if isinstance(data, dict) and data.get("visibility") == "public"
                               else RESTRICTED if isinstance(data, dict) else UNKNOWN)
        return self.cache[key]

    def check(self, kind, path, iid=None, note=None):
        if not path:
            return UNKNOWN
        key = (kind, path, iid, note)
        if key in self.cache:
            return self.cache[key]
        if kind == "project":
            result = self._project(path, kind)
        elif kind == "epics":
            result = self._group(path)
            if result == PUBLIC:
                data = self._get("groups/{}/epics/{}".format(enc(path), iid))
                result = (UNKNOWN if not isinstance(data, dict)
                          else RESTRICTED if data.get("confidential") else PUBLIC)
        else:
            result = self._project(path, kind)
            endpoint = "merge_requests" if kind == "merge_requests" else "issues"
            item = "projects/{}/{}/{}".format(enc(path), endpoint, iid)
            if result == PUBLIC:
                data = self._get(item)
                result = (UNKNOWN if not isinstance(data, dict)
                          else RESTRICTED if data.get("confidential") else PUBLIC)
            if result == PUBLIC and note:
                data = self._get("{}/notes/{}".format(item, note))
                result = (UNKNOWN if not isinstance(data, dict)
                          else RESTRICTED if data.get("internal") or data.get("confidential") else PUBLIC)
        self.cache[key] = result
        return result

    def public(self, ref):
        kind, path, iid, _, note = ref
        return self.check(kind, path, iid, note) == PUBLIC

    def refs(self, text):
        return refs_in(text, self.project)


def gate(f, vis):
    """(finding, withheld) with every non-public reference removed.

    - A reviewer that follows the contract marks non-public evidence as
      `{"ref": "non-public"}` and writes the message from public sources
      only. The finding keeps its message, with a withheld-evidence note.
    - When an evidence ref or note, or any other text of the finding
      (message, suggestion, source, quote, preservation rows, alternatives,
      metrics), names an item that is not confirmed public, that evidence is
      dropped, the message is replaced with a neutral sentence, and every
      other free text field is dropped: the text may describe the item, and
      a script cannot tell.
    """
    g = dict(f)
    evidence, marked, leaked = [], False, 0
    for e in g.get("evidence") or []:
        if not isinstance(e, dict):
            continue
        if str(e.get("ref") or "").strip().lower() in ("non-public", "a non-public project"):
            marked = True
            continue
        refs = vis.refs(str(e.get("ref") or "")) + vis.refs(str(e.get("note") or ""))
        if any(not vis.public(r) for r in refs):
            leaked += 1
            continue
        evidence.append(e)
    rest = dict((k, v) for k, v in g.items() if k != "evidence")
    text_refs = [r for t in strings(rest) for r in vis.refs(t)]
    leaked += sum(1 for r in text_refs if not vis.public(r))
    if marked or leaked:
        evidence.append({"kind": "note", "ref": "non-public", "note": "internal evidence withheld"})
        g["withheld_internal"] = True
    g["evidence"] = evidence
    if leaked:
        g["message"] = NEUTRAL
        g["suggestion"] = None
        for k in ("why", "importance_why", "alternatives", "source", "quote", "preservation", "metrics"):
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
    for r in sorted(vis.refs(text), key=lambda r: -len(r[3])):
        if not vis.public(r) and r[3] in text:
            text = re.sub(r"(?<![\w/.&#!-])" + re.escape(r[3]) + r"(?![\w])", PLACEHOLDER, text)
            n += 1
    return text, n
