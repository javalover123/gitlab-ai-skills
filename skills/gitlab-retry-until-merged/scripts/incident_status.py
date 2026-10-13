#!/usr/bin/env python3
"""Snapshot of GitLab.com incident signals.

Usage:
    python3 scripts/incident_status.py [--hours N] [--all-severities]

Options:
    --hours N          Only report master-broken incidents opened in the last N
                       hours (default 12). The tracker keeps many stale ones.
    --all-severities   Include severity::3/4 production incidents (default:
                       severity::1 and severity::2 only; S3/S4 are routine).

Prints JSON with three signals. A signal that cannot be fetched reports
{"error": ...} instead of failing the whole snapshot.

The status page is read over HTTPS directly; GITLAB_STATUS_URL overrides its
address (used by the tests). Never writes anything: every call is a GET.
"""

import argparse
import datetime
import json
import os
import subprocess
import urllib.parse
import urllib.request

# status.gitlab.com is a Status.io page; this is its public page ID.
STATUS_PAGE_ID = "5b36dc6502d06804c08349f7"
STATUS_URL = f"https://status.gitlab.com/1.0/status/{STATUS_PAGE_ID}"
INCIDENT_URL = f"https://status.gitlab.com/pages/incident/{STATUS_PAGE_ID}/"
PRODUCTION_PROJECT = "gitlab-com%2Fgl-infra%2Fproduction"
MASTER_BROKEN_PROJECT = "gitlab-org%2Fquality%2Fengineering-productivity%2Fmaster-broken-incidents"


class GlabError(RuntimeError):
    """A `glab api` call failed or returned something that isn't JSON."""


def glab(path, method="GET"):
    """One `glab api` call, parsed as JSON. Times out after 30 seconds."""
    cmd = ["glab", "api", "--hostname", "gitlab.com"] + (["--method", method] if method != "GET" else []) + [path]
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True,
                              timeout=30)
        if proc.returncode != 0:
            raise GlabError(f"glab api {method} {path} failed ({proc.returncode}): {proc.stderr.strip()}")
        return json.loads(proc.stdout)
    except (subprocess.TimeoutExpired, OSError, ValueError) as exc:
        raise GlabError(f"glab api {method} {path} failed: {exc}") from exc


def issues(project, **params):
    return glab(f"projects/{project}/issues?{urllib.parse.urlencode(params)}")


def iso(moment):
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def status_page():
    """Overall status, degraded components, and open incidents."""
    url = os.environ.get("GITLAB_STATUS_URL", STATUS_URL)
    try:
        with urllib.request.urlopen(url, timeout=15) as response:
            result = json.load(response)["result"]
    except (OSError, ValueError, KeyError):
        return {"error": "could not fetch status.gitlab.com"}
    overall = result.get("status_overall") or {}
    return {
        "overall": overall.get("status"),
        "operational": overall.get("status_code") == 100,
        "degraded_components": [
            {"name": c.get("name"), "status": c.get("status")}
            for c in result.get("status") or [] if c.get("status_code") != 100
        ],
        "active_incidents": [
            {"name": i.get("name"), "url": INCIDENT_URL + str(i.get("_id"))}
            for i in result.get("incidents") or []
        ],
    }


def production_incidents(all_severities):
    """Active production incidents (infrastructure-wide problems)."""
    try:
        found = issues(PRODUCTION_PROJECT, state="opened", labels="incident,Incident::Active", per_page=50)
    except GlabError:
        return {"error": "could not fetch production incidents"}
    incidents = []
    for issue in found:
        labels = issue.get("labels") or []
        severity = next((l.split("::", 1)[1] for l in labels if l.startswith("severity::")), "unknown")
        if not all_severities and severity not in ("1", "2"):
            continue
        incidents.append({
            "iid": issue.get("iid"),
            "title": issue.get("title"),
            "severity": severity,
            "labels": [l for l in labels if l.startswith(("Service::", "incident-type::"))],
            "created_at": issue.get("created_at"),
            "web_url": issue.get("web_url"),
        })
    return incidents


def master_broken_incidents(since):
    """Recent master-broken incidents (default branch broken for everyone)."""
    try:
        found = issues(MASTER_BROKEN_PROJECT, state="opened", created_after=since, per_page=50)
    except GlabError:
        return {"error": "could not fetch master-broken incidents"}
    return [
        {
            "iid": issue.get("iid"),
            "title": issue.get("title"),
            "labels": [l for l in issue.get("labels") or [] if l.startswith(("master-broken::", "master:"))],
            "created_at": issue.get("created_at"),
            "web_url": issue.get("web_url"),
        }
        for issue in found
    ]


def main():
    parser = argparse.ArgumentParser(description="Snapshot of GitLab.com incident signals.")
    parser.add_argument("--hours", type=int, default=12, help="master-broken window in hours (default 12)")
    parser.add_argument("--all-severities", action="store_true", help="include S3/S4 production incidents")
    args = parser.parse_args()
    if args.hours < 0:
        parser.error("--hours must be >= 0")

    now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
    since = iso(now - datetime.timedelta(hours=args.hours))
    print(json.dumps({
        "checked_at": iso(now),
        "status_page": status_page(),
        "production_incidents": production_incidents(args.all_severities),
        "master_broken_since": since,
        "master_broken_incidents": master_broken_incidents(since),
    }, indent=2))


if __name__ == "__main__":
    main()
