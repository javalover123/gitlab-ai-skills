"""Importance: how much a finding matters to the reader, from 1 to 5.

Importance is separate from severity (how strict the rule is) and from
confidence (how sure the reviewer is). Reviewers set it with one sentence of
reasoning (`importance_why`). Scripts get a default for each rule: docs_lint.py
from its check table, the other scripts from SCRIPT_DEFAULTS below. A project overrides any of them with `importance:` in
.docs-review.yml. The rubric is in references/findings-schema.md.

Python 3.9+, stdlib only.
"""

import fnmatch
import re

LEVELS = (1, 2, 3, 4, 5)

# A blocker breaks the build, a link, or a fact: never below this.
BLOCKER_FLOOR = 4

# Defaults for script findings that do not carry `importance`, first match
# wins. docs_lint.py sets `importance` itself (CHECKS).
SCRIPT_DEFAULTS = (
    ("impact.moved-page-no-redirect", 5),
    ("impact.broken-anchor", 4),
    ("impact.broken-link", 4),
    ("impact.stale-reference", 3),
    ("docs-preview.*", 4),
    ("vale.*.Spelling", 2),
    ("vale.*.Substitutions", 2),
    ("vale.*.SubstitutionWarning", 2),
    ("vale.*.British", 1),
    ("vale.*.OxfordComma", 1),
    ("vale.*.SentenceLength", 2),
)

# Families whose findings come from scripts, for SCRIPT_DEFAULTS.
SCRIPT_FAMILIES = ("lint", "vale", "markdownlint", "impact", "docs-preview")


def severity_fallback(sev, deterministic=False, rule_id=""):
    """Importance from severity, for a finding that has none."""
    family = (rule_id or "").split(".", 1)[0]
    if family == "markdownlint":
        # A blocker here fails the docs pipeline; the rest is markup polish.
        return 4 if sev == "blocker" else 1
    if family == "vale":
        return {"blocker": 3, "major": 2, "minor": 2, "nit": 1}.get(sev, 2)
    return {"blocker": 4, "major": 3, "minor": 2, "nit": 1}.get(sev, 2)


def valid(value):
    return isinstance(value, int) and not isinstance(value, bool) and value in LEVELS


def level(f):
    """A finding's importance, or 2 when it has no valid one."""
    lvl = f.get("importance")
    return lvl if valid(lvl) else 2


def coerce(value):
    """An importance level from an int or a digit string, else None."""
    if valid(value):
        return value
    if isinstance(value, str) and re.match(r"^\s*[1-5]\s*$", value):
        return int(value)
    if isinstance(value, float) and value.is_integer() and int(value) in LEVELS:
        return int(value)
    return None


def _match(pattern, rule_id):
    return rule_id == pattern or fnmatch.fnmatchcase(rule_id, pattern)


def script_default(rule_id):
    for pattern, level in SCRIPT_DEFAULTS:
        if _match(pattern, rule_id):
            return level
    return None


def override(rule_id, overrides):
    """The config override for an id: an exact key, else the longest glob
    (`editor.style.*`) that matches."""
    if not overrides:
        return None
    if rule_id in overrides:
        return overrides[rule_id]
    best = None
    for pattern, level in overrides.items():
        if any(c in pattern for c in "*?[") and _match(pattern, rule_id):
            if best is None or len(pattern) > len(best[0]):
                best = (pattern, level)
    return best[1] if best else None


def resolve(f, overrides=None):
    """Set `importance` and `importance_source` on a finding, in place.
    Order: config override, the finding's own value, the script default,
    then the severity fallback. A blocker is never below BLOCKER_FLOOR."""
    rid = f.get("id") or ""
    level, source = override(rid, overrides), "config"
    if level is None:
        level = coerce(f.get("importance"))
        source = "script" if f.get("deterministic") else "reviewer"
    if level is None and (f.get("deterministic") or rid.split(".", 1)[0] in SCRIPT_FAMILIES):
        level, source = script_default(rid), "script"
    if level is None:
        level, source = severity_fallback(f.get("severity"), f.get("deterministic"), rid), "severity"
    if f.get("severity") == "blocker" and level < BLOCKER_FLOOR:
        level, source = BLOCKER_FLOOR, source + "+blocker-floor"
    f["importance"] = level
    f["importance_source"] = source
    return f


def parse_overrides(value):
    """`importance:` from .docs-review.yml (a map of rule id or glob to a level
    1-5). Returns ({id: level}, [warnings])."""
    out, warnings = {}, []
    if value in (None, ""):
        return out, warnings
    if not isinstance(value, dict):
        return out, ["importance: must be a map of rule id to 1-5"]
    for k, v in value.items():
        level = coerce(v)
        if level is None:
            warnings.append("importance.{}: {!r} ignored (use 1 to 5)".format(k, v))
            continue
        out[str(k)] = level
    return out, warnings
