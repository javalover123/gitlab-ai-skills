#!/usr/bin/env python3
"""Block until one MR's pipeline or merge state needs attention, then print why.

Unlike pipeline-watch.py (many MRs, terminal pipeline transitions only), this
watches a single MR at the job level: it returns as soon as a blocking job
fails, even while the rest of the pipeline is still running.

Usage:
    python3 scripts/watch_mr.py [options] <mr-url>

Options:
    --expect-sha SHA   Emit SHA_CHANGED if the MR head moves off SHA. Omit it
                       when you push to the MR yourself.
    --auto-merge       The MR is set to auto-merge: emit AUTO_MERGE_OFF if that
                       is canceled, and on a green pipeline keep waiting for
                       MERGED instead of emitting PIPELINE_SUCCESS.
    --newer-than ID    Ignore pipelines with an ID <= ID (use after a push).
                       Emit NO_NEW_PIPELINE instead of TIMEOUT if none appears.
    --seen IDS         Comma-separated failed job/bridge IDs already triaged
    --grace N          Ignore a terminal pipeline status for the first N seconds
                       (use after a retry, while the retried pipeline may still
                       read as failed). Default 0.
    --mr-only          Ignore the pipeline entirely; watch only the MR itself
                       (merge, close, push, auto-merge), e.g. while waiting out
                       an incident with the pipeline sitting failed.
    --interval N       Seconds between polls (default 60)
    --timeout N        Give up after N seconds and emit TIMEOUT (default 480,
                       leaving headroom under a 10-minute tool-call limit).
                       Always polls once.

Prints the final mr_state.py snapshot plus an "event" field, one of:
    MERGED            the MR merged
    CLOSED            the MR was closed without merging
    SHA_CHANGED       (--expect-sha) new commits were pushed
    AUTO_MERGE_OFF    (--auto-merge) auto-merge was canceled, by a person or a
                      merge train drop
    NEW_FAILURE       a blocking job failed while the pipeline is still running
    PIPELINE_SUCCESS  pipeline green (not emitted with --auto-merge)
    PIPELINE_FAILED / PIPELINE_CANCELED / PIPELINE_SKIPPED / PIPELINE_MANUAL
    NO_PIPELINE       the MR has no pipeline
    NO_NEW_PIPELINE   (--newer-than) no newer pipeline appeared in time
    API_ERROR         3 polls in a row failed (GitLab API erroring or
                      unreachable); carries the last good snapshot, if any
    TIMEOUT           nothing actionable yet; not a failure, just run again

Never writes anything.
"""

import argparse
import sys
import time

from glab_helpers import GlabError, emit, parse_mr_url
from mr_state import mr_state

TERMINAL = {"success", "failed", "canceled", "skipped", "manual"}


def non_negative_int(value):
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError("must be >= 0")
    return number


def id_list(value):
    return {int(part) for part in value.split(",") if part.strip()}


def classify(state, args, in_grace):
    """Return the event for one snapshot, or None to keep polling."""
    if state["state"] == "merged":
        return "MERGED"
    if state["state"] == "closed":
        return "CLOSED"
    if args.expect_sha and state["sha"] != args.expect_sha:
        return "SHA_CHANGED"
    if args.auto_merge and not state["auto_merge"]:
        return "AUTO_MERGE_OFF"
    if args.mr_only:
        return None

    pipeline = state["pipeline"]
    if args.newer_than is not None and (pipeline is None or pipeline["id"] <= args.newer_than):
        return None  # still waiting for the pipeline a push should create
    if pipeline is None:
        return "NO_PIPELINE"
    status = pipeline["status"]
    if status == "success" and args.auto_merge:
        return None  # auto-merge acts on success; wait for MERGED or TIMEOUT
    if status in TERMINAL:
        return None if in_grace else f"PIPELINE_{status.upper()}"
    failures = state["failed_jobs"] + state["failed_bridges"]
    if any(item["id"] not in args.seen for item in failures):
        return "NEW_FAILURE"
    return None


def waiting_for_new_pipeline(state, args):
    pipeline = state.get("pipeline")
    return args.newer_than is not None and (pipeline is None or pipeline["id"] <= args.newer_than)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--expect-sha")
    parser.add_argument("--auto-merge", action="store_true")
    parser.add_argument("--newer-than", type=int)
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
            event = classify(state, args, elapsed < args.grace)
            if event:
                emit(dict(state, event=event))
                return
            if out_of_time:
                event = "NO_NEW_PIPELINE" if waiting_for_new_pipeline(state, args) else "TIMEOUT"
                emit(dict(state, event=event))
                return

        sys.stdout.flush()
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
