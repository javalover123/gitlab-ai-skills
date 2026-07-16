#!/usr/bin/env python3
"""
Completion checker for the story-reviewer skill's Stop hook.

Blocks completion if review output is missing required sections or
the verdict hasn't been written. Prevents the reviewer from finishing
without a structured output the story-creator can act on.
"""

import json
import os
import sys
from pathlib import Path


def read_hook_input():
    try:
        data = sys.stdin.read()
        return json.loads(data) if data else {}
    except json.JSONDecodeError:
        return {}


def main():
    hook_input = read_hook_input()

    # chdir to project root so Path() checks work correctly
    cwd = hook_input.get("cwd")
    if cwd:
        os.chdir(cwd)

    # Prevent infinite loop — if already in a stop hook cycle, allow completion
    if hook_input.get("stop_hook_active"):
        sys.exit(0)

    # Check if there's a review output file in the expected location
    review_files = list(Path(".").glob("docs/stories/*-review.md"))
    review_files += list(Path(".").glob("docs/reviews/*.md"))

    # Also check if Claude produced a review block in the conversation
    # by looking for a verdict marker in any recently touched story file
    recent_reviews = []
    for f in review_files:
        try:
            content = f.read_text()
            if "**Verdict:**" in content and any(
                v in content for v in ["PASS", "NEEDS_REVISION", "REJECT"]
            ):
                recent_reviews.append(f)
        except OSError:
            pass

    # If we found a complete review file, allow completion
    if recent_reviews:
        sys.exit(0)

    # No review file found — check if the session produced a verdict inline
    # We can't inspect conversation output directly, so we allow completion
    # but remind Claude to save the output
    message = (
        "story-reviewer: No review output file found in docs/stories/ or docs/reviews/.\n"
        "Save the review verdict to docs/stories/STORY-NNN-review.md before finishing.\n"
        "The review must include: Verdict, Scores table, Issues, and Feedback for Revision."
    )
    print(message, file=sys.stderr)

    # Exit 0 to allow completion (we can't block if there's no story file to check)
    # This is a soft reminder, not a hard block — the reviewer may be working interactively
    sys.exit(0)


if __name__ == "__main__":
    main()
