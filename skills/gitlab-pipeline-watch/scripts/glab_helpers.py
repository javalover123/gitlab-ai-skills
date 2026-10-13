"""Shared `glab api` helpers for the gitlab-pipeline-watch scripts.

Standard library only (Python 3.7+). Every GitLab call goes through the
authenticated `glab api` CLI; query parameters are encoded into the path, so
no `-f`/`-F` field flags are ever passed. Calls are pinned to gitlab.com (the
only host the MR URLs are parsed for), so running from a checkout of another
GitLab host can't redirect them. Each call times out after GLAB_TIMEOUT
seconds so a hung request can't stall a watcher.
"""

import json
import re
import subprocess
import sys
import urllib.parse

GLAB_TIMEOUT = 30

MR_URL_RE = re.compile(r"^https://gitlab\.com/(?P<project>.+?)/-/merge_requests/(?P<iid>\d+)")


class GlabError(RuntimeError):
    """A `glab api` call failed or returned something that isn't JSON."""


def parse_mr_url(url):
    """Return (project_path, project_encoded, mr_iid) for a gitlab.com MR URL."""
    match = MR_URL_RE.match(url)
    if not match:
        raise ValueError(f"not a gitlab.com merge request URL: {url}")
    project = match.group("project")
    return project, urllib.parse.quote(project, safe=""), match.group("iid")


def api_path(path, **params):
    """Append URL-encoded query parameters to an API path."""
    if not params:
        return path
    return f"{path}?{urllib.parse.urlencode(params, safe='[]')}"


def _json_documents(text):
    """Parse one or more concatenated JSON documents (`glab api --paginate`)."""
    decoder = json.JSONDecoder()
    docs, index, text = [], 0, text.strip()
    while index < len(text):
        doc, index = decoder.raw_decode(text, index)
        docs.append(doc)
        while index < len(text) and text[index].isspace():
            index += 1
    return docs


def glab_text(path, method="GET", paginate=False):
    cmd = ["glab", "api", "--hostname", "gitlab.com"]
    if method != "GET":
        cmd += ["--method", method]
    if paginate:
        cmd.append("--paginate")
    cmd.append(path)
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True,
                              timeout=GLAB_TIMEOUT)
    except subprocess.TimeoutExpired as exc:
        raise GlabError(f"glab api {method} {path} timed out after {GLAB_TIMEOUT}s") from exc
    except OSError as exc:
        raise GlabError(f"could not run glab: {exc}") from exc
    if proc.returncode != 0:
        raise GlabError(f"glab api {method} {path} failed ({proc.returncode}): {proc.stderr.strip()}")
    return proc.stdout


def glab_json(path, method="GET", paginate=False):
    """Call `glab api` and parse the result. Paginated arrays are merged."""
    text = glab_text(path, method=method, paginate=paginate)
    try:
        docs = _json_documents(text)
    except ValueError as exc:
        raise GlabError(f"glab api {method} {path} returned invalid JSON: {exc}") from exc
    if paginate:
        merged = []
        for doc in docs:
            merged.extend(doc if isinstance(doc, list) else [doc])
        return merged
    if not docs:
        raise GlabError(f"glab api {method} {path} returned nothing")
    return docs[0]


def emit(obj):
    print(json.dumps(obj, indent=2))


def fail(message, code=1):
    print(f"Error: {message}", file=sys.stderr)
    sys.exit(code)
