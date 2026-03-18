"""Shared YAML frontmatter parser for SKILL.md files.

Extracts top-level key-value pairs from ``---``-delimited YAML frontmatter.
Supports simple scalars and YAML multi-line scalars (``>``, ``>-``, ``|``, ``|-``).
Nested keys (indented under a mapping parent) are intentionally skipped.
"""


def parse_frontmatter(skill_file, *, debug=False):
    """Extract all top-level key-value pairs from YAML frontmatter.

    Returns a dict of field_name -> value (as string).
    Returns empty dict if no frontmatter found.

    Supports YAML multi-line scalars (``>``, ``>-``, ``|``, ``|-``) by collecting
    subsequent indented lines and joining them.
    """
    fields = {}

    with open(skill_file, "r") as f:
        lines = f.readlines()

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
            value = stripped.split(":", 1)[1].strip().strip("\"'")
            if value in (">", ">-", "|", "|-"):
                current_key = key
                multiline_parts = []
                multiline_folded = value.startswith(">")
            else:
                fields[key] = value

    return fields
