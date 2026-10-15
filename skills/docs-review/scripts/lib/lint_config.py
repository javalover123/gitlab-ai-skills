"""Load `.docs-review.yml` with nested values, for docs_lint.py.

Python 3.9+, stdlib only (no PyYAML). Supported YAML subset:

- `key: value` mappings, nested by indentation (spaces only).
- Scalars: plain, 'single-quoted', "double-quoted", true/false/yes/no, null/~, integers.
- Flow lists on one line: `key: [a, "b, c", d]`.
- Block lists: `- item`, including lists of maps (`- use: X` then `  avoid: [...]`).
- `#` comments (outside quotes) and blank lines.

- Flow maps on one line: `key: {a: 1, b: 2}`.

Not supported: anchors, tags, multi-line strings, nested flow collections.
A file whose first non-blank character is `{` is read as JSON instead.
"""

import json
import os
import re

CONFIG_NAME = ".docs-review.yml"

# Every key `.docs-review.yml` may set (references/config.md).
KNOWN_KEYS = (
    # Shared with lint_config.py, the nested reader for docs_lint.py.
    "docs_root", "url_prefix", "vale_config", "nav_file", "product_terms",
    "cross_repo_search_groups", "technical_writer", "code_examples", "facts",
    "custom_heading_ids", "landing_paths", "severe_paths", "auto_mode",
    "lint_disable", "safety_cap", "first_time_threshold", "importance",
)


class ConfigError(ValueError):
    pass


def _strip_comment(line):
    quote = None
    for i, ch in enumerate(line):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
        elif ch == "#" and (i == 0 or line[i - 1] in " \t"):
            return line[:i].rstrip()
    return line.rstrip()


def _scalar(raw):
    raw = raw.strip()
    if raw == "":
        return None
    if len(raw) >= 2 and raw[0] in "'\"" and raw[-1] == raw[0]:
        inner = raw[1:-1]
        return inner.replace("''", "'") if raw[0] == "'" else inner.replace('\\"', '"')
    low = raw.lower()
    if low in ("null", "~"):
        return None
    if low in ("true", "yes", "on"):
        return True
    if low in ("false", "no", "off"):
        return False
    if re.match(r"^-?\d+$", raw):
        return int(raw)
    if raw.startswith("[") and raw.endswith("]"):
        return [_scalar(x) for x in _split_flow(raw[1:-1])]
    if raw.startswith("{") and raw.endswith("}"):
        out = {}
        for item in _split_flow(raw[1:-1]):
            m = KEY_RE.match(item.strip())
            if not m:
                raise ConfigError("flow map item {!r} is not `key: value`".format(item.strip()))
            out[_scalar(m.group(1))] = _scalar(m.group(2) or "")
        return out
    return raw


def _split_flow(inner):
    """Top-level comma-separated items of a flow list or map, quotes respected."""
    items, buf, quote = [], [], None
    for ch in inner:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
            buf.append(ch)
        elif ch == ",":
            items.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    if "".join(buf).strip():
        items.append("".join(buf))
    return [x for x in items if x.strip()]


def _tokens(text):
    out = []
    for num, raw in enumerate(text.splitlines(), 1):
        if "\t" in raw[:len(raw) - len(raw.lstrip())]:
            raise ConfigError("line {}: use spaces, not tabs, for indentation".format(num))
        line = _strip_comment(raw)
        if not line.strip() or line.strip() == "---":
            continue
        out.append((num, len(line) - len(line.lstrip(" ")), line.strip()))
    return out


KEY_RE = re.compile(r"^((?:\"[^\"]*\"|'[^']*'|[^:#'\"][^:]*?)):(?:\s+(.*)|)$")


def _parse_block(toks, i, indent):
    """Parse a mapping or list whose items sit at `indent`. Returns (value, next_i)."""
    if i >= len(toks):
        return None, i
    if toks[i][2].startswith("- ") or toks[i][2] == "-":
        return _parse_list(toks, i, indent)
    return _parse_map(toks, i, indent)


def _parse_map(toks, i, indent):
    data = {}
    while i < len(toks):
        num, ind, text = toks[i]
        if ind < indent:
            break
        if ind > indent:
            raise ConfigError("line {}: unexpected indentation".format(num))
        m = KEY_RE.match(text)
        if not m:
            raise ConfigError("line {}: expected `key: value`".format(num))
        key = _scalar(m.group(1))
        rest = m.group(2)
        i += 1
        if rest is None or rest == "":
            if i < len(toks) and (toks[i][1] > ind or (toks[i][1] == ind and toks[i][2].startswith("-"))):
                val, i = _parse_block(toks, i, toks[i][1])
            else:
                val = None
        else:
            val = _scalar(rest)
        data[key] = val
    return data, i


def _parse_list(toks, i, indent):
    items = []
    while i < len(toks):
        num, ind, text = toks[i]
        if ind < indent or not (text.startswith("- ") or text == "-"):
            break
        if ind > indent:
            raise ConfigError("line {}: unexpected indentation".format(num))
        body = text[1:].strip()
        i += 1
        if not body:
            if i < len(toks) and toks[i][1] > ind:
                val, i = _parse_block(toks, i, toks[i][1])
            else:
                val = None
            items.append(val)
            continue
        if KEY_RE.match(body) and not body.startswith(("'", '"', "[")):
            # A map item: the first key is on the dash line, the rest are indented.
            sub = [(num, ind + 2, body)]
            while i < len(toks) and toks[i][1] > ind:
                sub.append(toks[i])
                i += 1
            val, _ = _parse_map(sub, 0, ind + 2)
            items.append(val)
        else:
            items.append(_scalar(body))
    return items, i


def parse(text):
    stripped = text.lstrip()
    if stripped.startswith("{"):
        try:
            data = json.loads(text)
        except ValueError as exc:
            raise ConfigError("invalid JSON: {}".format(exc))
        if not isinstance(data, dict):
            raise ConfigError("top level must be an object")
        return data
    toks = _tokens(text)
    if not toks:
        return {}
    data, i = _parse_map(toks, 0, toks[0][1])
    if i < len(toks):
        raise ConfigError("line {}: could not parse".format(toks[i][0]))
    return data


def load(path, warn=None):
    """Parse a config file. Returns {} if `path` is None or missing."""
    if not path or not os.path.isfile(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        data = parse(fh.read())
    for key in data:
        if key not in KNOWN_KEYS and warn:
            warn("{}: unknown key `{}` ignored".format(os.path.basename(path), key))
    return data
