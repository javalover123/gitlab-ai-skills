#!/usr/bin/env python3
"""Content-quality checks for skills/*/SKILL.md and their reference files.

Three checks, adapted from the personal skills repo's structure/voice linters
to this repo's `skills/<name>/` layout and its AGENTS.md conventions:

  1. Broken relative links  (HARD FAIL) — every `[text](path)` in a SKILL.md or
     reference file that points at a local file must resolve. This repo links
     heavily into `references/`, so a stale link is a real breakage.

  2. Structural lint        (WARN)      — a prose skill should carry a
     "When to Use" / trigger section, and no stray TODO/FIXME markers should
     leak into shipped prose.

  3. Voice / anti-AI-tell    (WARN)     — flags the words AGENTS.md already bans
     ("utilize", "leverage", "robust", "comprehensive", "seamless", "delve",
     "holistic", "synergy", "cutting-edge", "endeavor") plus a few classic
     filler phrases. Makes the existing written convention enforceable.

Per the repo decision, only broken links fail CI; structure and voice are
warn-only (like `validate_skill_length.py`) so they surface offenders without
blocking unrelated MRs. Promote to hard gates once the corpus is clean.

Usage:
    python3 scripts/validate_content_quality.py           # report
    python3 scripts/validate_content_quality.py --ci      # exit 1 on broken links
    python3 scripts/validate_content_quality.py --debug   # debug logging
"""

import os
import re
import sys

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
REPO_ROOT = os.path.join(SCRIPT_DIR, "..")
SKILLS_DIR = os.path.join(REPO_ROOT, "skills")

DEBUG = "--debug" in sys.argv

# Words AGENTS.md bans in written output. Kept in sync with the "Voice
# reminders" / description guidance there.
VOICE_WORD_BLOCKLIST = [
    "utilize", "leverage", "robust", "comprehensive", "seamless", "delve",
    "holistic", "synergy", "cutting-edge", "endeavor",
]

# Classic filler / AI-tell phrases.
VOICE_PHRASE_BLOCKLIST = [
    "it's important to note",
    "it's worth noting",
    "in conclusion",
    "in today's fast-paced world",
    "plays a crucial role",
    "paving the way",
    "serves as a testament",
]

# A line teaching about a banned pattern (e.g. listing it as forbidden) should
# not itself trip the check.
TEACHING_PREFIXES = (
    "never use", "never say", "avoid", "don't use", "do not use", "banned",
    "blocklist", "blocklisted", "bad:", "wrong:", "anti-pattern",
)

LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")


def log_debug(message):
    if DEBUG:
        print(f"DEBUG: {message}", file=sys.stderr)


def prose_lines(text):
    """Yield (line_no, line) for lines outside code fences and frontmatter."""
    in_code = False
    in_fm = False
    fm_count = 0
    for i, line in enumerate(text.split("\n"), 1):
        stripped = line.strip()
        if stripped == "---":
            fm_count += 1
            in_fm = fm_count == 1
            continue
        if in_fm:
            continue
        if fm_count >= 2:
            in_fm = False
        if stripped.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        yield i, line


def is_teaching_line(line):
    low = line.lower().strip()
    if any(p in low for p in TEACHING_PREFIXES):
        return True
    # Bullet whose content is a quoted example is usually a "don't" sample.
    return bool(re.match(r"^-\s+[\"']", low))


def check_links(md_file):
    """Return a list of broken-relative-link error strings for one file."""
    errors = []
    skill_dir = os.path.dirname(md_file)
    with open(md_file, "r") as f:
        text = f.read()
    for _, line in prose_lines(text):
        # Ignore links inside inline code spans.
        line = re.sub(r"`[^`]*`", "", line)
        for m in LINK_RE.finditer(line):
            target = m.group(2).strip()
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            path = target.split("#", 1)[0]
            if not path:
                continue
            resolved = os.path.normpath(os.path.join(skill_dir, path))
            if not os.path.exists(resolved):
                errors.append(f"broken link [{m.group(1)}]({target})")
    return errors


def check_structure(skill_md):
    """Return a list of structural WARN strings for a SKILL.md."""
    warnings = []
    with open(skill_md, "r") as f:
        text = f.read()

    # "When to use" / trigger guidance. The description also routes, but a body
    # section helps the agent. Warn if neither a heading nor a "Use when" /
    # "Triggers" cue is present anywhere.
    has_when = bool(
        re.search(r"^#{1,4}\s*When to Use", text, re.IGNORECASE | re.MULTILINE)
        or re.search(r"\bUse when\b", text, re.IGNORECASE)
        or re.search(r"\bTriggers?:\b", text, re.IGNORECASE)
    )
    if not has_when:
        warnings.append("no 'When to Use' section or 'Use when'/'Triggers' cue")

    for line_no, line in prose_lines(text):
        stripped = line.strip()
        if is_teaching_line(stripped):
            continue
        no_code = re.sub(r"`[^`]*`", "", stripped)
        if re.search(r"\bTODO\b", no_code) or re.search(r"\bFIXME\b", no_code):
            warnings.append(f"line {line_no}: stray TODO/FIXME in prose — {stripped}")
    return warnings


def check_voice(md_file):
    """Return a list of voice WARN strings for one markdown file."""
    warnings = []
    with open(md_file, "r") as f:
        text = f.read()
    # Match a blocklisted word only when it stands alone — not as part of a
    # hyphenated compound (e.g. "highest-leverage", "cross-cutting-edge") where
    # the usage is usually legitimate. A hyphen or letter on either side means
    # it's a compound, so require non-hyphen/non-letter boundaries.
    word_re = re.compile(
        r"(?<![\w-])(" + "|".join(re.escape(w) for w in VOICE_WORD_BLOCKLIST) + r")(?![\w-])",
        re.IGNORECASE,
    )
    for line_no, line in prose_lines(text):
        if is_teaching_line(line):
            continue
        for m in word_re.finditer(line):
            warnings.append(f"line {line_no}: blocklisted word '{m.group(1)}' — {line.strip()}")
        low = line.lower()
        for phrase in VOICE_PHRASE_BLOCKLIST:
            if phrase in low:
                warnings.append(f"line {line_no}: filler phrase '{phrase}'")
    return warnings


def markdown_files(skill_dir):
    """SKILL.md plus every reference markdown file under the skill."""
    out = []
    skill_md = os.path.join(skill_dir, "SKILL.md")
    if os.path.isfile(skill_md):
        out.append(skill_md)
    ref_dir = os.path.join(skill_dir, "references")
    if os.path.isdir(ref_dir):
        for root, _, files in os.walk(ref_dir):
            for fn in sorted(files):
                if fn.endswith(".md"):
                    out.append(os.path.join(root, fn))
    return out


def main():
    is_ci = "--ci" in sys.argv
    if not os.path.isdir(SKILLS_DIR):
        print("No skills directory found.")
        sys.exit(0)

    total_link_errors = 0
    total_warnings = 0
    skills = sorted(
        d for d in os.listdir(SKILLS_DIR)
        if os.path.isfile(os.path.join(SKILLS_DIR, d, "SKILL.md"))
    )

    for name in skills:
        skill_dir = os.path.join(SKILLS_DIR, name)
        skill_md = os.path.join(skill_dir, "SKILL.md")

        link_errors = []
        for md in markdown_files(skill_dir):
            rel = os.path.relpath(md, REPO_ROOT)
            link_errors += [f"{rel}: {e}" for e in check_links(md)]

        warnings = [f"{name}: {w}" for w in check_structure(skill_md)]
        for md in markdown_files(skill_dir):
            rel = os.path.relpath(md, REPO_ROOT)
            warnings += [f"{rel}: {w}" for w in check_voice(md)]

        if not link_errors and not warnings:
            print(f"  OK: {name}")
        else:
            for e in link_errors:
                print(f"FAIL: {e}")
                total_link_errors += 1
            for w in warnings:
                print(f"WARN: {w}")
                total_warnings += 1

    print(
        f"\n{len(skills)} skills checked: "
        f"{total_link_errors} broken link(s), {total_warnings} warning(s)."
    )

    if total_link_errors:
        print(
            "\nERROR: broken relative links found — every local [text](path) "
            "must resolve.",
            file=sys.stderr,
        )
        if is_ci:
            sys.exit(1)
    if total_warnings and not total_link_errors:
        print("\nStructure/voice warnings above are advisory (warn-only).")


if __name__ == "__main__":
    main()
