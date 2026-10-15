#!/usr/bin/env bash
# Tests scripts/lib/visibility.py: posted findings never carry confidential
# or private references, and anything not confirmed public is withheld.
# No network: a fake API answers the visibility calls.
set -Eeuo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
scripts="$here/../scripts"

python3 - "$scripts" << 'PY'
import sys
sys.path.insert(0, sys.argv[1])
from lib import visibility as V

class FakeApi(object):
    data = {
        "projects/example-org%2Fpublic-docs": {"visibility": "public", "issues_access_level": "enabled",
                                               "merge_requests_access_level": "enabled",
                                               "repository_access_level": "enabled"},
        "projects/example-org%2Fpublic-docs/issues/1/notes/10": {"internal": False},
        "projects/example-org%2Fpublic-docs/issues/1/notes/11": {"internal": True},
        "projects/example-org%2Fmembers-only": {"visibility": "public", "issues_access_level": "private",
                                                "merge_requests_access_level": "enabled",
                                                "repository_access_level": "private"},
        "projects/example-org%2Fmembers-only/issues/4": {"confidential": False},
        "projects/example-org%2Fpublic-docs/issues/1": {"confidential": False},
        "projects/example-org%2Fpublic-docs/issues/2": {"confidential": True},
        "projects/example-org%2Fpublic-docs/merge_requests/7": {"iid": 7},
        "projects/example-org%2Fsecret-repo": {"visibility": "private"},
        "groups/example-org": {"visibility": "public"},
        "groups/example-org/epics/3": {"confidential": True},
    }

    def get(self, endpoint):
        if endpoint not in self.data:
            raise RuntimeError("404 Not Found")
        return self.data[endpoint]

vis = V.Visibility(FakeApi(), "example-org/public-docs")
failures = 0

def check(name, cond):
    global failures
    print(("ok - " if cond else "FAIL - ") + name)
    failures += 0 if cond else 1

base = {"id": "facts.behavior", "reviewer": "facts", "message": "The default is 30 days.", "suggestion": "Use 30 days.",
        "fixable": "suggest"}

f = dict(base, evidence=[{"kind": "issue", "ref": "https://gitlab.com/example-org/public-docs/-/issues/1"}])
g, n = V.gate(f, vis)
check("a public issue stays as evidence and the message is kept", n == 0 and g["message"] == base["message"]
      and g["evidence"][0]["ref"].endswith("/issues/1") and not g.get("withheld_internal"))

f = dict(base, evidence=[{"kind": "issue", "ref": "https://gitlab.com/example-org/public-docs/-/work_items/2",
                          "note": "The team decided the retention period in this work item."}])
g, n = V.gate(f, vis)
check("a confidential work item is dropped, and the message is replaced with the neutral text",
      n == 1 and g["message"] == V.NEUTRAL and g["suggestion"] is None and g["fixable"] == "manual"
      and g["withheld_internal"] and [e["ref"] for e in g["evidence"]] == ["non-public"])

f = dict(base, message="See example-org/public-docs#2 for the decision.", evidence=[])
g, n = V.gate(f, vis)
check("a confidential short reference in the message replaces the message", n == 1 and g["message"] == V.NEUTRAL)

f = dict(base, evidence=[{"kind": "code", "ref": "example-org/secret-repo@abc1234:lib/retention.rb:12"}])
g, n = V.gate(f, vis)
check("code in a private project is withheld", n == 1 and g["message"] == V.NEUTRAL)

f = dict(base, evidence=[{"kind": "mr", "ref": "https://gitlab.com/unknown-org/unknown/-/merge_requests/9"}])
g, n = V.gate(f, vis)
check("a reference that cannot be checked is withheld (fail closed)", n == 1 and g["message"] == V.NEUTRAL)

f = dict(base, evidence=[{"kind": "issue", "ref": "non-public"},
                         {"kind": "mr", "ref": "https://gitlab.com/example-org/public-docs/-/merge_requests/7"}])
g, n = V.gate(f, vis)
check("evidence the reviewer marked non-public keeps the message, with a withheld note",
      n == 0 and g["message"] == base["message"] and g["withheld_internal"]
      and [e["ref"] for e in g["evidence"]][-1] == "non-public")

text, n = V.redact_text("Planned in example-org&3 and example-org/public-docs!7.", vis)
check("redact_text replaces a confidential epic and keeps a public MR",
      n == 1 and V.PLACEHOLDER in text and "example-org/public-docs!7" in text)

conf = "https://gitlab.com/example-org/public-docs/-/issues/2"
for field, value in (("source", conf), ("quote", "see example-org/public-docs#2"),
                     ("preservation", [{"fact": "Decided in " + conf}]),
                     ("alternatives", [{"id": "editor.x", "message": "Per " + conf}]),
                     ("metrics", [{"message": "from " + conf}])):
    g, n = V.gate(dict(base, evidence=[], **{field: value}), vis)
    check("a confidential reference in `{}` withholds the finding and drops the field".format(field),
          n == 1 and g["message"] == V.NEUTRAL and field not in g)

for text in ("See #2 for the decision.", "See !99 first.", "Tracked in public-docs#2."):
    g, n = V.gate(dict(base, message=text, evidence=[]), vis)
    check("a same-project or same-namespace reference is resolved and withheld: " + text,
          n == 1 and g["message"] == V.NEUTRAL)
g, n = V.gate(dict(base, message="Fixed in #1.", evidence=[]), vis)
check("a bare reference to a public issue in the target project is kept", n == 0 and g["message"] == "Fixed in #1.")
g, n = V.gate(dict(base, message="See #2.", evidence=[]), V.Visibility(FakeApi()))
check("a bare reference with no target project is withheld (fail closed)", n == 1)
check("headings, anchors, and words are not references",
      V.refs_in("## Step 2, see page.md#3 and C#, issue 5", "example-org/public-docs") == [])

g, n = V.gate(dict(base, message="See https://gitlab.com/example-org/members-only/-/issues/4.", evidence=[]), vis)
check("an issue in a public project whose issues are members-only is withheld", n == 1)
g, n = V.gate(dict(base, evidence=[{"kind": "code", "ref": "example-org/members-only@abc1234:lib/a.rb:3"}]), vis)
check("code in a public project whose repository is members-only is withheld", n == 1)
g, n = V.gate(dict(base, message="As https://gitlab.com/example-org/public-docs/-/issues/1#note_11 says.",
                   evidence=[]), vis)
check("an internal note on a public issue is withheld", n == 1)
g, n = V.gate(dict(base, message="As https://gitlab.com/example-org/public-docs/-/issues/1#note_10 says.",
                   evidence=[]), vis)
check("a public note on a public issue is kept", n == 0)

text, n = V.redact_text("Ask about #2 or example-org/public-docs#2, not #1.", vis)
check("redact_text resolves bare references", n == 2 and text.count(V.PLACEHOLDER) == 2 and "#1." in text)

offline = V.Visibility(None)
g, n = V.gate(dict(base, evidence=[{"kind": "issue", "ref": "https://gitlab.com/example-org/public-docs/-/issues/1"}]),
              offline)
check("with no API, every reference is withheld", n == 1 and g["message"] == V.NEUTRAL)

sys.exit(1 if failures else 0)
PY
echo "all visibility tests passed"
