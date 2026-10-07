"""Shared YAML frontmatter parser for SKILL.md files.

Extracts top-level key-value pairs from ``---``-delimited YAML frontmatter.
Supports simple scalars, single-line quoted scalars (double-quoted escapes and
single-quoted ``''`` are decoded, like YAML) and YAML multi-line scalars
(``>``, ``>-``, ``|``, ``|-``).

Valid YAML that is NOT supported and yields wrong values without an error:
trailing comments after a quoted value (``"foo" # c``) and quoted scalars
spanning several lines. CI's strict parse and the PyYAML parity test catch these.
Nested keys (indented under a mapping parent) are intentionally skipped.
"""


def _read_lines(skill_file):
    """Read all lines from *skill_file* and return them as a list."""
    with open(skill_file, "r") as f:
        return f.readlines()


def extract_raw_frontmatter(skill_file):
    """Return the raw YAML text between the ``---`` delimiters, or *None*.

    The closing delimiter is a ``---`` that appears **on its own line**
    (matching the same rule ``parse_frontmatter`` uses), so a ``---`` inside a
    quoted value does not truncate the block.
    """
    lines = _read_lines(skill_file)
    if not lines or lines[0].strip() != "---":
        return None

    body_lines = []
    for line in lines[1:]:
        if line.strip() == "---":
            return "".join(body_lines)
        body_lines.append(line)

    # Reached EOF without a closing ``---``.
    return None


import string

_SIMPLE_ESCAPES = {
    "0": "\0", "a": "\a", "b": "\b", "t": "\t", "\t": "\t", "n": "\n",
    "v": "\v", "f": "\f", "r": "\r", "e": "\x1b", " ": " ", '"': '"',
    "/": "/", "\\": "\\", "N": "\x85", "_": "\xa0",
    "L": "\u2028", "P": "\u2029",
}
_HEX_ESCAPES = {"x": 2, "u": 4, "U": 8}


def _decode_double_quoted(body):
    """Decode YAML double-quoted escapes in *body* (quotes already removed)."""
    out = []
    i = 0
    while i < len(body):
        ch = body[i]
        if ch != "\\" or i + 1 >= len(body):
            out.append(ch)
            i += 1
            continue
        esc = body[i + 1]
        if esc in _HEX_ESCAPES:
            digits = body[i + 2 : i + 2 + _HEX_ESCAPES[esc]]
            if len(digits) == _HEX_ESCAPES[esc] and all(
                c in string.hexdigits for c in digits
            ):
                try:
                    out.append(chr(int(digits, 16)))
                    i += 2 + len(digits)
                    continue
                except (ValueError, OverflowError):
                    pass
        elif esc in _SIMPLE_ESCAPES:
            out.append(_SIMPLE_ESCAPES[esc])
            i += 2
            continue
        # Unknown escape: keep it literally rather than guess.
        out.append(ch)
        i += 1
    return "".join(out)


def _decode_scalar(value):
    """Decode a single-line YAML scalar; unquoted values are returned as-is."""
    if len(value) >= 2 and value[0] == value[-1] == "'":
        return value[1:-1].replace("''", "'")
    if len(value) >= 2 and value[0] == value[-1] == '"':
        # Reject a closing quote that is itself escaped (e.g. "abc\\\").
        backslashes = len(value[:-1]) - len(value[:-1].rstrip("\\"))
        if backslashes % 2 == 0:
            return _decode_double_quoted(value[1:-1])
    return value


def parse_frontmatter(skill_file, *, debug=False):
    """Extract all top-level key-value pairs from YAML frontmatter.

    Returns a dict of field_name -> value (as string).
    Returns empty dict if no frontmatter found.

    Supports YAML multi-line scalars (``>``, ``>-``, ``|``, ``|-``) by collecting
    subsequent indented lines and joining them.
    """
    fields = {}

    lines = _read_lines(skill_file)

    if not lines or lines[0].strip() != "---":
        return fields

    current_key = None
    multiline_parts = []
    multiline_folded = False

    def _flush_multiline():
        if current_key:
            joiner = " " if multiline_folded else "\n"
            fields[current_key] = joiner.join(multiline_parts)

    for line in lines[1:]:
        stripped = line.strip()
        if stripped == "---":
            _flush_multiline()
            break

        # Indented continuation line for a multi-line scalar
        if current_key and line[0:1].isspace() and stripped:
            multiline_parts.append(stripped)
            continue

        # New top-level key — flush any previous multi-line value
        _flush_multiline()
        current_key = None
        multiline_parts = []
        multiline_folded = False

        # Only match top-level keys (lines that don't start with whitespace)
        if not line[0:1].isspace() and ":" in stripped:
            key = stripped.split(":", 1)[0].strip()
            value = stripped.split(":", 1)[1].strip()
            if value in (">", ">-", "|", "|-"):
                current_key = key
                multiline_parts = []
                multiline_folded = value.startswith(">")
            else:
                fields[key] = _decode_scalar(value)

    return fields
