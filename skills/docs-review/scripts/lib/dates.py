"""Parse the `--today` and `--as-of` dates the docs-review scripts take.

Python 3.9+, stdlib only. A value is a date (`2026-10-14`) or a full ISO 8601
timestamp (`2026-10-14T09:30:00Z`, `2026-10-14T09:30:00+02:00`,
`2026-10-14 09:30`). Only the date part is used, as written: the timestamp is
not converted to another time zone.
"""

import datetime
import re

DAY_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2})(?::(\d{2})(?:[.,]\d+)?)?"
                    r"(?:Z|[+-]\d{2}(?::?\d{2})?)?)?$", re.I)


def parse_day(value):
    """datetime.date for a date or an ISO timestamp, or None when invalid."""
    m = DAY_RE.match(str(value or "").strip())
    if not m:
        return None
    try:
        day = datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if m.group(4) is not None:
            datetime.time(int(m.group(4)), int(m.group(5)), int(m.group(6) or 0))
    except ValueError:
        return None
    return day
