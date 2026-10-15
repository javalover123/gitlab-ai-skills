"""Shared findings schema helpers for the docs-review scripts.

Python 3.9+, stdlib only. The schema is the contract every reviewer and
script emits: {"version": 1, "target": {...}, "findings": [...]}.
"""

import hashlib
import json
import re

SCHEMA_VERSION = 1

# Ordered from most to least severe; the index is the rank.
SEVERITIES = ["blocker", "major", "minor", "nit"]
CONFIDENCES = ["high", "medium", "low"]
FIXABLE = ["auto", "suggest", "manual"]
VERDICTS = ["verified", "contradicted", "unverified"]
EVIDENCE_KINDS = ["code", "test", "cli", "mr", "issue", "doc", "search"]
REVIEWER_STATUSES = ["complete", "partial", "blocked"]

REQUIRED = ["id", "reviewer", "severity", "confidence", "file", "message", "fixable"]

# Findings from these reviewers describe the effect of a change on other
# files, so the changed-lines filter must keep them.
KEEP_UNCHANGED_REVIEWERS = ("impact", "facts")

ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*(\.[A-Za-z0-9_-]+)+$")


def severity_rank(sev):
    """0 for blocker, 3 for nit, 4 for anything unknown."""
    try:
        return SEVERITIES.index(sev)
    except ValueError:
        return len(SEVERITIES)


def lower_severity(sev, steps=1):
    """Move a severity toward nit by `steps`, never past nit."""
    rank = min(severity_rank(sev) + steps, len(SEVERITIES) - 1)
    return SEVERITIES[rank]


def fingerprint(f):
    """sha1 of id|file|quote. Line is left out so it survives rebases."""
    raw = "{}|{}|{}".format(f.get("id", ""), f.get("file", ""), f.get("quote") or "")
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def rule_family(rule_id):
    """Reviewer area of a rule id: `editor.style.bold` -> `editor`."""
    return (rule_id or "").split(".", 1)[0]


def rule_key(rule_id):
    """Normalized last segment, so `lint.word-list.utilize` and
    `vale.gitlab_base.Utilize` compare equal for dedupe."""
    last = (rule_id or "").rsplit(".", 1)[-1]
    return re.sub(r"[^a-z0-9]", "", last.lower())


def line_range(f):
    """(start, end) of a finding, or None when it has no line."""
    line = f.get("line")
    if not isinstance(line, int):
        return None
    end = f.get("end_line")
    if not isinstance(end, int) or end < line:
        end = line
    return (line, end)


def evidence_kind_for(ref):
    """Best guess at the evidence `kind` for a bare reference string."""
    ref = ref.strip()
    if re.search(r"/-/merge_requests/\d+|(^|\s)!\d+\b", ref):
        return "mr"
    if re.search(r"/-/(issues|work_items)/\d+|(^|\s)#\d+\b", ref):
        return "issue"
    path = re.split(r"[:#?\s]", re.sub(r"^https?://[^/]+/.*?/-/blob/[^/]+/", "", ref), 1)[0]
    if re.search(r"(^|/)(spec|test|tests|__tests__)/|_spec\.rb$|_test\.(go|py|rs)$|\.test\.[jt]sx?$", path):
        return "test"
    if re.search(r"\.(md|markdown)$", path):
        return "doc"
    if re.search(r"\.(rb|py|go|rs|js|ts|tsx|jsx|vue|java|kt|c|h|cc|cpp|cs|sql|yml|yaml|json|toml|sh)$", path):
        return "code"
    if re.match(r"^(glab|git|curl|orbit)\s", ref):
        return "cli"
    return "search"


def coerce_finding(f):
    """Repair common, harmless shape errors in place instead of dropping the
    finding. Returns a list of notes (empty when nothing changed).

    - `evidence` given as a string becomes a one-item list.
    - Evidence items given as strings become `{kind, ref}` objects.
    - `importance` given as a digit string becomes an int; a value outside
      1 to 5 is removed, so the combine step derives it.
    """
    notes = []
    if not isinstance(f, dict):
        return notes
    ev = f.get("evidence")
    if isinstance(ev, str):
        f["evidence"] = [{"kind": evidence_kind_for(ev), "ref": ev}] if ev.strip() else []
        notes.append("`evidence` was a string; coerced to a one-item list")
    elif isinstance(ev, dict):
        f["evidence"] = [ev]
        notes.append("`evidence` was an object; coerced to a one-item list")
    if isinstance(f.get("evidence"), list):
        items = []
        for item in f["evidence"]:
            if isinstance(item, str):
                if item.strip():
                    items.append({"kind": evidence_kind_for(item), "ref": item})
                    notes.append("an `evidence` item was a string; coerced to an object")
                continue
            if isinstance(item, dict) and item.get("ref") and item.get("kind") not in EVIDENCE_KINDS:
                item = dict(item, kind=evidence_kind_for(str(item["ref"])))
                notes.append("an `evidence` item had no valid `kind`; guessed `{}`".format(item["kind"]))
            items.append(item)
        f["evidence"] = items
    if "importance" in f and f["importance"] is not None:
        level = _coerce_importance(f["importance"])
        if level is None:
            notes.append("`importance` {!r} is not 1 to 5; derived instead".format(f.pop("importance")))
        elif level != f["importance"] or isinstance(f["importance"], bool):
            f["importance"] = level
            notes.append("`importance` coerced to {}".format(level))
    return notes


def _coerce_importance(value):
    # Imported here: apply_findings.py loads this file as a top-level module.
    try:
        from . import importance
    except ImportError:
        import importance
    return importance.coerce(value)


def validate_status(doc):
    """Warnings for a reviewer result's top-level `status`. Empty when the
    status is missing (script output) or one of complete|partial|blocked."""
    if not isinstance(doc, dict) or "status" not in doc:
        return []
    status = doc.get("status")
    if status in REVIEWER_STATUSES:
        return []
    return ["`status` {!r} must be one of {}".format(status, "|".join(REVIEWER_STATUSES))]


def validate_finding(f):
    """Return a list of human-readable errors; empty means valid."""
    errs = []
    if not isinstance(f, dict):
        return ["finding is not an object"]
    for key in REQUIRED:
        if key not in f or f[key] in (None, ""):
            errs.append("missing required field `{}`".format(key))
    if f.get("reviewer") in ("editor", "facts", "reader"):
        # A reviewer finding must quote the text and cite a rule (dispatch.md).
        for key in ("quote", "source"):
            if not f.get(key):
                errs.append("reviewer finding has no `{}`".format(key))
    rid = f.get("id")
    if isinstance(rid, str) and rid and not ID_RE.match(rid):
        errs.append("`id` {!r} must look like `reviewer.rule` (lowercase prefix, dot separated)".format(rid))
    if "severity" in f and f.get("severity") not in SEVERITIES:
        errs.append("`severity` {!r} must be one of {}".format(f.get("severity"), "|".join(SEVERITIES)))
    if "confidence" in f and f.get("confidence") not in CONFIDENCES:
        errs.append("`confidence` {!r} must be one of {}".format(f.get("confidence"), "|".join(CONFIDENCES)))
    if "fixable" in f and f.get("fixable") not in FIXABLE:
        errs.append("`fixable` {!r} must be one of {}".format(f.get("fixable"), "|".join(FIXABLE)))
    for key in ("line", "end_line"):
        val = f.get(key)
        if val is not None and (not isinstance(val, int) or isinstance(val, bool) or val < 1):
            errs.append("`{}` must be a positive integer or null, got {!r}".format(key, val))
    rng_line, rng_end = f.get("line"), f.get("end_line")
    if isinstance(rng_line, int) and isinstance(rng_end, int) and rng_end < rng_line:
        errs.append("`end_line` ({}) is before `line` ({})".format(rng_end, rng_line))
    for key in ("quote", "suggestion", "source"):
        val = f.get(key)
        if val is not None and not isinstance(val, str):
            errs.append("`{}` must be a string or null".format(key))
    if "deterministic" in f and not isinstance(f.get("deterministic"), bool):
        errs.append("`deterministic` must be true or false")
    verdict = f.get("verdict")
    if verdict is not None and verdict not in VERDICTS:
        errs.append("`verdict` {!r} must be one of {} or null".format(verdict, "|".join(VERDICTS)))
    ev = f.get("evidence")
    if ev is not None:
        if not isinstance(ev, list):
            errs.append("`evidence` must be a list")
        else:
            for i, item in enumerate(ev):
                if not isinstance(item, dict) or not item.get("ref"):
                    errs.append("`evidence[{}]` needs a `ref`".format(i))
                elif item.get("kind") not in EVIDENCE_KINDS:
                    errs.append("`evidence[{}].kind` {!r} must be one of {}".format(
                        i, item.get("kind"), "|".join(EVIDENCE_KINDS)))
    sme = f.get("sme")
    if sme is not None:
        if not isinstance(sme, list):
            errs.append("`sme` must be a list")
        else:
            for i, item in enumerate(sme):
                if not isinstance(item, dict) or not item.get("username"):
                    errs.append("`sme[{}]` needs a `username`".format(i))
    return errs


def load_doc(path):
    """Load a findings file. Accepts the full document or a bare list.

    Returns a dict with at least `version`, `target`, and `findings`.
    Raises ValueError with a readable message on bad JSON.
    """
    with open(path, encoding="utf-8") as fh:
        try:
            data = json.load(fh)
        except json.JSONDecodeError as exc:
            raise ValueError("{}: invalid JSON: {}".format(path, exc))
    if isinstance(data, list):
        data = {"version": SCHEMA_VERSION, "target": {}, "findings": data}
    if not isinstance(data, dict):
        raise ValueError("{}: expected an object with `findings` or a list".format(path))
    if not isinstance(data.get("findings"), list):
        raise ValueError("{}: `findings` must be a list".format(path))
    data.setdefault("version", SCHEMA_VERSION)
    data.setdefault("target", {})
    return data


def new_doc(target, findings, **extra):
    doc = {"version": SCHEMA_VERSION, "target": target or {}, "findings": findings}
    doc.update(extra)
    return doc


def dump(doc, path=None):
    text = json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
    if path and path != "-":
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
    return text


def make_finding(rule_id, reviewer, severity, file, message, confidence="high", line=None,
                 end_line=None, quote=None, suggestion=None, fixable="manual", source=None,
                 deterministic=True, evidence=None, sme=None, verdict=None):
    f = {
        "id": rule_id,
        "reviewer": reviewer,
        "severity": severity,
        "confidence": confidence,
        "file": file,
        "line": line,
        "end_line": end_line if end_line is not None else line,
        "quote": quote,
        "message": message,
        "suggestion": suggestion,
        "fixable": fixable,
        "source": source,
        "deterministic": deterministic,
    }
    if evidence is not None:
        f["evidence"] = evidence
    if sme is not None:
        f["sme"] = sme
    if verdict is not None:
        f["verdict"] = verdict
    return f


def has_blocker(findings):
    return any(f.get("severity") == "blocker" for f in findings)
