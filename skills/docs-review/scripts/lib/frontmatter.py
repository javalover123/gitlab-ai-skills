"""Lenient YAML front matter reader for docs pages.

Reads `key: scalar`, `key: [a, b]`, and a block list of scalars under a key,
and skips anything else (nested maps, folded strings). Python 3.9+, stdlib only.
"""

import re


def _scalar(raw):
    raw = raw.strip()
    if not raw:
        return None
    if raw[0] in "'\"" and raw[-1] == raw[0] and len(raw) >= 2:
        return raw[1:-1]
    low = raw.lower()
    if low in ("null", "~"):
        return None
    if low in ("true", "yes"):
        return True
    if low in ("false", "no"):
        return False
    if re.match(r"^-?\d+$", raw):
        return int(raw)
    return raw


def _strip_comment(line):
    out, quote = [], None
    for i, ch in enumerate(line):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
        elif ch == "#" and (i == 0 or line[i - 1] in " \t"):
            break
        out.append(ch)
    return "".join(out).rstrip()


def parse(text):
    data, current = {}, None
    for raw in text.splitlines():
        line = _strip_comment(raw)
        if not line.strip():
            continue
        top = re.match(r"^([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$", line)
        if top:
            key, val = top.group(1), top.group(2).strip()
            current = key
            if val.startswith("[") and val.endswith("]"):
                inner = val[1:-1].strip()
                data[key] = [_scalar(x) for x in inner.split(",")] if inner else []
            elif val:
                data[key] = _scalar(val)
            else:
                data[key] = None
            continue
        item = re.match(r"^\s+-\s+(.*)$", line)
        if item and current is not None:
            val = item.group(1)
            if re.match(r"^[A-Za-z_][A-Za-z0-9_]*:\s", val + " "):
                data[current] = "<nested>"  # list of maps: not for us
                continue
            if not isinstance(data.get(current), list):
                data[current] = []
            data[current].append(_scalar(val))
    return data
