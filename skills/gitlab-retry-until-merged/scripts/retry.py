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
    - for `pipeline`: the pipeline belongs to this MR (its ref is the MR's
      refs/merge-requests/<iid>/{head,merge}, or its source branch when the MR
      isn't from a fork) and is not
      a merge train pipeline (GitLab cannot retry those; the MR has to be
      re-added).

Exit codes: 0 retried, 1 API error (the write may or may not have happened),
2 usage error, 3 precondition failed (no write).
Prints JSON describing what was done, or why it was refused.

Self-contained on purpose: the skill's only write path reads in one file.
"""

import argparse
import json
import re
import subprocess
import sys
import urllib.parse

MR_URL_RE = re.compile(r"^https?://(?P<host>[^/]+)/(?P<project>.+?)/-/merge_requests/(?P<iid>\d+)")


class GlabError(RuntimeError):
    """A `glab api` call failed or returned something that isn't JSON."""


def glab(path, host, method="GET"):
    """One `glab api` call to `host`, parsed as JSON. Times out after 30 seconds.

    The host comes from the MR URL, so running from a checkout of a different
    GitLab instance can't send the write anywhere but the MR's own instance.
    """
    cmd = ["glab", "api", "--hostname", host] + (["--method", method] if method != "GET" else []) + [path]
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True,
                              timeout=30)
        if proc.returncode != 0:
            raise GlabError(f"glab api {method} {path} failed ({proc.returncode}): {proc.stderr.strip()}")
        return json.loads(proc.stdout)
    except (subprocess.TimeoutExpired, OSError, ValueError) as exc:
        raise GlabError(f"glab api {method} {path} failed: {exc}") from exc


def emit(obj):
    print(json.dumps(obj, indent=2))


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
    match = MR_URL_RE.match(args.mr_url)
    if not match:
        parser.error(f"not a GitLab merge request URL: {args.mr_url}")
    host = match.group("host")
    encoded, iid = urllib.parse.quote(match.group("project"), safe=""), match.group("iid")

    try:
        # --- Preconditions (read-only) ---------------------------------------
        mr = glab(f"projects/{encoded}/merge_requests/{iid}", host)
        if mr.get("state") != "opened":
            refuse(f"MR is {mr.get('state')}, not open")
        if mr.get("merge_when_pipeline_succeeds") is not True:
            refuse("auto-merge is no longer set on the MR")
        if mr.get("sha") != args.expect_sha:
            refuse(f"MR head moved from {args.expect_sha} to {mr.get('sha')}: new commits need review")

        if args.mode == "pipeline":
            ref = glab(f"projects/{encoded}/pipelines/{args.pipeline_id}", host).get("ref") or ""
            if ref == f"refs/merge-requests/{iid}/train":
                refuse(f"pipeline {args.pipeline_id} is a merge train pipeline and cannot be retried")
            mr_refs = {f"refs/merge-requests/{iid}/head", f"refs/merge-requests/{iid}/merge"}
            if mr.get("source_project_id") == mr.get("target_project_id") and mr.get("source_branch"):
                mr_refs.add(mr["source_branch"])  # a fork's branch pipelines live in the fork
            if ref not in mr_refs:
                refuse(f"pipeline {args.pipeline_id} is not a pipeline of this MR")

        # --- Write -----------------------------------------------------------
        if args.mode == "pipeline":
            result = glab(f"projects/{encoded}/pipelines/{args.pipeline_id}/retry", host, method="POST")
        else:
            result = glab(f"projects/{encoded}/merge_requests/{iid}/pipelines", host, method="POST")
    except GlabError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    emit({
        "retried": True,
        "mode": args.mode,
        "pipeline_id": result.get("id"),
        "status": result.get("status"),
        "web_url": result.get("web_url"),
    })


if __name__ == "__main__":
    main()
