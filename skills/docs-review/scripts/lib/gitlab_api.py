"""Thin wrapper over `glab api` so every script uses glab's auth.

Python 3.9+, stdlib only. Bodies are always sent through a JSON file with
`--input`, never interpolated into a shell string. Every call is recorded in
`GitLab.calls` so callers and tests can prove what was (not) written.
"""

import json
import os
import re
import subprocess
import tempfile
import time
import urllib.parse

WRITE_METHODS = ("POST", "PUT", "PATCH", "DELETE")


class GlabError(RuntimeError):
    def __init__(self, message, status=None):
        RuntimeError.__init__(self, message)
        self.status = status


def enc(value):
    """URL-encode a project or group path, or a file path, for an endpoint."""
    return urllib.parse.quote(str(value), safe="")


def query(params):
    """Build a query string, skipping None values."""
    items = [(k, v) for k, v in params.items() if v is not None]
    return urllib.parse.urlencode(items)


class GitLab(object):
    def __init__(self, glab="glab", hostname=None, delay=0.0, timeout=120):
        self.glab = glab or os.environ.get("DOCS_REVIEW_GLAB") or "glab"
        self.hostname = hostname
        self.delay = delay
        self.timeout = timeout
        self.calls = []  # (method, endpoint)
        self._last = 0.0

    def _run(self, method, endpoint, body=None):
        if self.delay:
            wait = self.delay - (time.time() - self._last)
            if wait > 0:
                time.sleep(wait)
        cmd = [self.glab, "api", endpoint, "--method", method]
        if self.hostname:
            cmd += ["--hostname", self.hostname]
        body_path = None
        try:
            if body is not None:
                fd, body_path = tempfile.mkstemp(prefix="docs-review-body-", suffix=".json")
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    json.dump(body, fh)
                cmd += ["--input", body_path, "--header", "Content-Type: application/json"]
            self.calls.append((method, endpoint))
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=self.timeout)
            except FileNotFoundError:
                raise GlabError("`{}` not found; install glab and run `glab auth login`".format(self.glab))
            except subprocess.TimeoutExpired:
                raise GlabError("glab api {} {} timed out after {}s".format(method, endpoint, self.timeout))
        finally:
            self._last = time.time()
            if body_path:
                try:
                    os.unlink(body_path)
                except OSError:
                    pass
        if proc.returncode != 0:
            msg = (proc.stderr or proc.stdout or "").strip()
            status = None
            if "(HTTP " in msg:
                try:
                    status = int(msg.rsplit("(HTTP ", 1)[1].split(")", 1)[0])
                except ValueError:
                    status = None
            raise GlabError("glab api {} {} failed: {}".format(method, endpoint, msg[:500]), status)
        out = proc.stdout.strip()
        if not out:
            return None
        try:
            return json.loads(out)
        except json.JSONDecodeError:
            return out

    def get(self, endpoint):
        """GET, retried once after a server error (GitLab.com 5xx on heavy queries). Writes never retry."""
        try:
            return self._run("GET", endpoint)
        except GlabError as exc:
            if not re.search(r"\b(500|502|503|504)\b", str(exc)):
                raise
            time.sleep(2)
            return self._run("GET", endpoint)

    def get_pages(self, endpoint, per_page=100, max_pages=5):
        """GET a list endpoint page by page. Returns (items, truncated)."""
        sep = "&" if "?" in endpoint else "?"
        items = []
        for page in range(1, max_pages + 1):
            data = self.get("{}{}per_page={}&page={}".format(endpoint, sep, per_page, page))
            if not isinstance(data, list):
                break
            items.extend(data)
            if len(data) < per_page:
                return items, False
        return items, len(items) >= per_page * max_pages

    def write(self, method, endpoint, body):
        if method not in WRITE_METHODS:
            raise ValueError("not a write method: {}".format(method))
        return self._run(method, endpoint, body)

    def writes(self):
        return [c for c in self.calls if c[0] in WRITE_METHODS]
