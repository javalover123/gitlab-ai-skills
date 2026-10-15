#!/usr/bin/env python3
"""Search the review-derived rule catalog (assets/rules.tsv).

Each rule was distilled from reviewed nixpkgs pull requests and deduplicated.
The numbers are evidence, not law: `support` is how many PRs backed the rule,
`merged` is the share of those PRs that merged, `cr` counts PRs where a reviewer
formally requested changes, and `maint` counts PRs reviewed by a maintainer.
A high cr share means reviewers actively enforce the rule. Merge rates
correlate with many things besides the rule itself, so treat them as a hint.

Examples:
  find-rules.py fetchFromGitHub tag
  find-rules.py --category nixos-modules --min-support 10 systemd
  find-rules.py --sort enforced passthru.tests
  find-rules.py --list-categories
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

DEFAULT_RULES = Path(__file__).resolve().parents[1] / "assets" / "rules.tsv"
SORTS = {"support": "support", "merged": "merged_pct", "enforced": "changes_requested"}


def load_rules(path: Path) -> list[dict]:
    rules = []
    with path.open(newline="") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            rules.append({
                "category": row["category"],
                "support": int(row["support"]),
                "merged_pct": int(row["merged_pct"]),
                "changes_requested": int(row["changes_requested"]),
                "maintainer_reviewed": int(row["maintainer_reviewed"]),
                "rule": row["rule"],
            })
    return rules


def search(rules: list[dict], keywords: list[str], category: str | None = None,
           min_support: int = 0, sort: str = "support", limit: int | None = None) -> list[dict]:
    words = [k.lower() for k in keywords]
    hits = [
        r for r in rules
        if (category is None or r["category"] == category)
        and r["support"] >= min_support
        and all(w in r["rule"].lower() for w in words)
    ]
    key = SORTS[sort]
    hits.sort(key=lambda r: (-r[key], -r["support"], r["rule"]))
    return hits[:limit] if limit else hits


def format_rule(r: dict) -> str:
    return (f"[{r['category']}] support {r['support']}, {r['merged_pct']}% merged, "
            f"{r['changes_requested']} cr, {r['maintainer_reviewed']} maint\n    {r['rule']}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("keywords", nargs="*", help="every keyword must appear in the rule (case-insensitive)")
    p.add_argument("--category", help="restrict to one category slug (see --list-categories)")
    p.add_argument("--min-support", type=int, default=0)
    p.add_argument("--sort", choices=sorted(SORTS), default="support")
    p.add_argument("--limit", type=int, default=15)
    p.add_argument("--rules", type=Path, default=DEFAULT_RULES)
    p.add_argument("--list-categories", action="store_true")
    args = p.parse_args(argv)

    if not args.rules.exists():
        print(f"find-rules: rules file not found: {args.rules}", file=sys.stderr)
        return 2
    rules = load_rules(args.rules)

    if args.list_categories:
        counts: dict[str, int] = {}
        for r in rules:
            counts[r["category"]] = counts.get(r["category"], 0) + 1
        for cat, n in sorted(counts.items(), key=lambda kv: -kv[1]):
            print(f"{n:5d}  {cat}")
        return 0

    hits = search(rules, args.keywords, args.category, args.min_support, args.sort, args.limit)
    if not hits:
        print("find-rules: no matching rules", file=sys.stderr)
        return 1
    for r in hits:
        print(format_rule(r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
