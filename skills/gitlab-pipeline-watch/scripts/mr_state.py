#!/usr/bin/env python3
"""Read-only snapshot of an MR's merge state and latest pipeline.

Usage:
    python3 scripts/mr_state.py [--files] <mr-url>

Prints JSON with the MR state, auto-merge flag, head SHA, latest pipeline,
and its blocking failed jobs and bridges. --files adds the MR's changed file
paths, for correlating failures with the MR's changes.

Never writes anything: every call is a GET.
"""

import argparse
import re

from glab_helpers import GlabError, api_path, emit, fail, glab_json, parse_mr_url

PIPELINE_KINDS = [
    (re.compile(r"^refs/merge-requests/\d+/train$"), "merge_train"),
    (re.compile(r"^refs/merge-requests/\d+/merge$"), "merged_result"),
    (re.compile(r"^refs/merge-requests/\d+/head$"), "detached"),
]


def pipeline_kind(ref):
    for pattern, kind in PIPELINE_KINDS:
        if pattern.match(ref or ""):
            return kind
    return "branch"


def blocking(items):
    """Failed, not superseded by a retry, and able to stop the merge."""
    return [
        item for item in items
        if item.get("status") == "failed" and not item.get("retried") and not item.get("allow_failure")
    ]


def mr_state(mr_url, with_files=False):
    host, project, encoded, iid = parse_mr_url(mr_url)

    def get(path, paginate=False):
        return glab_json(path, paginate=paginate, hostname=host)

    mr = get(f"projects/{encoded}/merge_requests/{iid}")

    # The MR pipelines list, not head_pipeline: head_pipeline can be null while
    # GitLab is still checking mergeability.
    pipelines = get(api_path(f"projects/{encoded}/merge_requests/{iid}/pipelines", per_page=1))

    pipeline, failed_jobs, failed_bridges = None, [], []
    if pipelines:
        latest = pipelines[0]
        pipeline = {key: latest.get(key) for key in ("id", "status", "ref", "sha", "web_url", "source")}
        pipeline["kind"] = pipeline_kind(latest.get("ref"))
        base = f"projects/{encoded}/pipelines/{latest['id']}"

        jobs = get(api_path(f"{base}/jobs", **{"scope[]": "failed", "per_page": 100}), paginate=True)
        failed_jobs = [
            {key: job.get(key) for key in ("id", "name", "stage", "failure_reason", "web_url")}
            for job in blocking(jobs)
        ]

        # Trigger jobs (bridges) for child/downstream pipelines. Their failures
        # hide inside the downstream pipeline, so surface where to look.
        # `trigger_jobs` replaces the `bridges` endpoint, deprecated in 19.2.
        bridges = get(api_path(f"{base}/trigger_jobs", **{"scope[]": "failed", "per_page": 100}), paginate=True)
        for bridge in blocking(bridges):
            downstream = bridge.get("downstream_pipeline") or {}
            failed_bridges.append({
                "id": bridge.get("id"),
                "name": bridge.get("name"),
                "stage": bridge.get("stage"),
                "failure_reason": bridge.get("failure_reason"),
                "downstream_project_id": downstream.get("project_id"),
                "downstream_pipeline_id": downstream.get("id"),
                "downstream_web_url": downstream.get("web_url"),
            })

    state = {
        "host": host,
        "project": project,
        "project_encoded": encoded,
        "mr_iid": iid,
        "web_url": mr.get("web_url"),
        "title": mr.get("title"),
        "author": (mr.get("author") or {}).get("username"),
        "state": mr.get("state"),
        "sha": mr.get("sha"),
        "source_branch": mr.get("source_branch"),
        "target_branch": mr.get("target_branch"),
        "auto_merge": mr.get("merge_when_pipeline_succeeds") is True,
        "merge_user": (mr.get("merge_user") or {}).get("username"),
        "detailed_merge_status": mr.get("detailed_merge_status"),
        "merge_error": mr.get("merge_error"),
        "pipeline": pipeline,
        "failed_jobs": failed_jobs,
        "failed_bridges": failed_bridges,
        "blocking_failure_count": len(failed_jobs) + len(failed_bridges),
    }

    if with_files:
        diffs = get(api_path(f"projects/{encoded}/merge_requests/{iid}/diffs", per_page=100), paginate=True)
        paths = set()
        for diff in diffs:
            paths.update(p for p in (diff.get("new_path"), diff.get("old_path")) if p)
        state["changed_files"] = sorted(paths)

    return state


def main():
    parser = argparse.ArgumentParser(description="Read-only snapshot of an MR and its latest pipeline.")
    parser.add_argument("--files", action="store_true", help="include the MR's changed file paths")
    parser.add_argument("mr_url")
    args = parser.parse_args()
    try:
        emit(mr_state(args.mr_url, with_files=args.files))
    except ValueError as exc:
        parser.error(str(exc))
    except GlabError as exc:
        fail(str(exc))


if __name__ == "__main__":
    main()
