#!/usr/bin/env python3
"""Print a CI job's metadata and the cleaned tail of its log.

Usage:
    python3 scripts/job_log_tail.py [--hostname HOST] <project-encoded> <job-id> [lines]

--hostname is the GitLab instance (mr_state.py reports it as `host`). Without
it, glab uses the host of the current git checkout, or gitlab.com.

Prints job metadata as JSON, then the last N (default 150) non-blank log
lines with ANSI colors, GitLab section markers, and carriage returns removed.

Never writes anything: every call is a GET.
"""

import argparse
import json
import re

from glab_helpers import GlabError, fail, glab_json, glab_text

# Timestamped traces prefix every line with `<RFC 3339 time> <stream><type>`,
# e.g. `2026-09-24T17:23:52.844727Z 01O ` (a `+` marks a continued line).
TIMESTAMP_PREFIX = re.compile(r"^\d{4}-\d\d-\d\dT[\d:.]+Z \d+[OE]\+?\s?")
# Collapsible log sections: `section_start:<ts>:<name>[opts]\r\e[0K`.
SECTION_MARKER = re.compile(r"section_(?:start|end):\d+:[^\s\x1b]*\r?(?:\x1b\[0K)?")
ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def clean(trace):
    lines = []
    for line in trace.split("\n"):
        line = TIMESTAMP_PREFIX.sub("", line, count=1)
        line = SECTION_MARKER.sub("", line)
        line = ANSI.sub("", line).replace("\r", "")
        if line.strip():
            lines.append(line)
    return lines


def main():
    parser = argparse.ArgumentParser(description="Show a CI job's metadata and log tail.")
    parser.add_argument("--hostname", help="GitLab host (default: glab's, from the current checkout)")
    parser.add_argument("project_encoded")
    parser.add_argument("job_id", type=int)
    parser.add_argument("lines", nargs="?", type=int, default=150)
    args = parser.parse_args()
    if args.lines < 1:
        parser.error("lines must be >= 1")

    base = f"projects/{args.project_encoded}/jobs/{args.job_id}"
    try:
        job = glab_json(base, hostname=args.hostname)
        trace = glab_text(f"{base}/trace", hostname=args.hostname)
    except GlabError as exc:
        fail(str(exc))

    info = {key: job.get(key) for key in (
        "id", "name", "stage", "status", "failure_reason", "web_url", "allow_failure", "started_at", "finished_at")}
    info["runner"] = (job.get("runner") or {}).get("description")

    print("=== JOB INFO ===")
    print(json.dumps(info, indent=2))
    print()
    print(f"=== JOB LOG (last {args.lines} lines) ===")
    print("\n".join(clean(trace)[-args.lines:]))


if __name__ == "__main__":
    main()
