#!/usr/bin/env python3
"""Block until an auto-merge MR needs attention, then print why.

Usage:
    python3 scripts/watch_mr.py --expect-sha <sha> [options] <mr-url>

Options:
    --expect-sha SHA   MR head SHA recorded at preflight (required)
    --seen IDS         Comma-separated failed job/bridge IDs already triaged
    --grace N          Ignore a terminal pipeline status for the first N seconds
                       (use after a retry, while the retried pipeline may still
                       read as failed). Default 0.
    --mr-only          Ignore the pipeline entirely; watch only the MR itself
                       (merge, close, push, auto-merge). For waiting out an
                       incident while the pipeline sits failed.
    --interval N       Seconds between polls (default 60)
    --timeout N        Give up after N seconds and emit TIMEOUT (default 480,
                       leaving headroom under a 10-minute tool-call limit).
                       Always polls once.

Prints the final mr_state.py snapshot plus an "event" field, one of:
    MERGED          the MR merged; done
    CLOSED          the MR was closed without merging
    SHA_CHANGED     new commits were pushed; the approval premise is gone
    AUTO_MERGE_OFF  auto-merge was canceled (by a person, or a merge train drop)
    NEW_FAILURE     a blocking job failed while the pipeline is still running
    PIPELINE_FAILED / PIPELINE_CANCELED / PIPELINE_SKIPPED / PIPELINE_MANUAL
    NO_PIPELINE     the MR has no pipeline
    API_ERROR       3 polls in a row failed (GitLab API erroring or
                    unreachable); carries the last good snapshot, if any
    TIMEOUT         nothing actionable yet; not a failure, just run again

Never writes anything.
"""

import argparse
import sys
import time

from glab_helpers import GlabError, emit, parse_mr_url
from mr_state import mr_state

TERMINAL = {"failed", "canceled", "skipped", "manual"}


def non_negative_int(value):
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError("must be >= 0")
    return number


def id_list(value):
    return {int(part) for part in value.split(",") if part.strip()}


def classify(state, expect_sha, seen, mr_only, in_grace):
    """Return the event for one snapshot, or None to keep polling."""
    if state["state"] == "merged":
        return "MERGED"
    if state["state"] == "closed":
        return "CLOSED"
    if state["sha"] != expect_sha:
        return "SHA_CHANGED"
    if not state["auto_merge"]:
        return "AUTO_MERGE_OFF"
    if mr_only:
        return None

    pipeline = state["pipeline"]
    if pipeline is None:
        return "NO_PIPELINE"
    status = pipeline["status"]
    if status in TERMINAL:
        return None if in_grace else f"PIPELINE_{status.upper()}"
    if status == "success":
        return None  # auto-merge acts on success; wait for MERGED or TIMEOUT
    failures = state["failed_jobs"] + state["failed_bridges"]
    if any(item["id"] not in seen for item in failures):
        return "NEW_FAILURE"
    return None


def main():
    parser = argparse.ArgumentParser(description="Block until an auto-merge MR needs attention.")
    parser.add_argument("--expect-sha", required=True)
    parser.add_argument("--seen", type=id_list, default=set())
    parser.add_argument("--grace", type=non_negative_int, default=0)
    parser.add_argument("--mr-only", action="store_true")
    parser.add_argument("--interval", type=non_negative_int, default=60)
    parser.add_argument("--timeout", type=non_negative_int, default=480)
    parser.add_argument("mr_url")
    args = parser.parse_args()
    try:
        parse_mr_url(args.mr_url)
    except ValueError as exc:
        parser.error(str(exc))

    start = time.monotonic()
    state, api_failures = {}, 0

    while True:
        # A failed poll (API 5xx, network) is not fatal: GitLab erroring is
        # exactly what happens during an incident. Keep the last good snapshot.
        try:
            poll = mr_state(args.mr_url)
        except (GlabError, KeyError, TypeError) as exc:
            poll, error = None, exc
        elapsed = time.monotonic() - start
        out_of_time = elapsed + args.interval > args.timeout

        if poll is None:
            api_failures += 1
            if api_failures >= 3 or out_of_time:
                emit(dict(state, event="API_ERROR",
                          api_error=f"{api_failures} poll(s) in a row failed; last error: {error}"))
                return
        else:
            api_failures, state = 0, poll
            event = classify(state, args.expect_sha, args.seen, args.mr_only, elapsed < args.grace)
            if event:
                emit(dict(state, event=event))
                return
            if out_of_time:
                emit(dict(state, event="TIMEOUT"))
                return

        sys.stdout.flush()
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
