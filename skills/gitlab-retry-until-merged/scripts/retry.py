#!/usr/bin/env python3
"""The only write this skill makes: re-run CI for an MR.

Usage:
    python3 scripts/retry.py --expect-sha <sha> <mr-url> pipeline <pipeline-id>
        Retry the failed jobs of an existing MR pipeline (same commit).
    python3 scripts/retry.py --expect-sha <sha> <mr-url> new-pipeline
        Start a fresh MR pipeline (a merged-results pipeline picks up the
        current target branch; the MR's source branch is untouched).

Before writing, re-reads the MR and refuses (exit 3, nothing written) unless:
    - the MR is still open,
    - auto-merge is still set,
    - the MR head SHA still equals --expect-sha (nobody pushed since triage),
    - for `pipeline`: the pipeline belongs to this MR and is not a merge train
      pipeline (GitLab cannot retry those; the MR has to be re-added).

Exit codes: 0 retried, 1 API error (the write may or may not have happened),
2 usage error, 3 precondition failed (no write).
Prints JSON describing what was done, or why it was refused.
"""

import argparse
import sys

from glab_helpers import GlabError, api_path, emit, fail, glab_json, parse_mr_url


def refuse(reason):
    emit({"retried": False, "reason": reason})
    sys.exit(3)


def main():
    parser = argparse.ArgumentParser(description="Retry an MR pipeline or start a new one, after re-checking the MR.")
    parser.add_argument("--expect-sha", required=True, help="MR head SHA recorded at preflight")
    parser.add_argument("mr_url")
    parser.add_argument("mode", choices=["pipeline", "new-pipeline"])
    parser.add_argument("pipeline_id", nargs="?", type=int)
    args = parser.parse_args()

    if (args.mode == "pipeline") != (args.pipeline_id is not None):
        parser.error("`pipeline` needs a pipeline ID; `new-pipeline` takes none")
    try:
        _, encoded, iid = parse_mr_url(args.mr_url)
    except ValueError as exc:
        parser.error(str(exc))

    try:
        # --- Preconditions (read-only) ---------------------------------------
        mr = glab_json(f"projects/{encoded}/merge_requests/{iid}")
        if mr.get("state") != "opened":
            refuse(f"MR is {mr.get('state')}, not open")
        if mr.get("merge_when_pipeline_succeeds") is not True:
            refuse("auto-merge is no longer set on the MR")
        if mr.get("sha") != args.expect_sha:
            refuse(f"MR head moved from {args.expect_sha} to {mr.get('sha')}: new commits need review")

        if args.mode == "pipeline":
            pipelines = glab_json(api_path(f"projects/{encoded}/merge_requests/{iid}/pipelines", per_page=100),
                                  paginate=True)
            ref = next((p.get("ref") for p in pipelines if p.get("id") == args.pipeline_id), None)
            if ref is None:
                refuse(f"pipeline {args.pipeline_id} is not a pipeline of this MR")
            if ref.endswith("/train"):
                refuse(f"pipeline {args.pipeline_id} is a merge train pipeline and cannot be retried")

        # --- Write -----------------------------------------------------------
        if args.mode == "pipeline":
            result = glab_json(f"projects/{encoded}/pipelines/{args.pipeline_id}/retry", method="POST")
        else:
            result = glab_json(f"projects/{encoded}/merge_requests/{iid}/pipelines", method="POST")
    except GlabError as exc:
        fail(str(exc))

    emit({
        "retried": True,
        "mode": args.mode,
        "pipeline_id": result.get("id"),
        "status": result.get("status"),
        "web_url": result.get("web_url"),
    })


if __name__ == "__main__":
    main()
