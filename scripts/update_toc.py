#!/usr/bin/env python3

import os
import re
import sys

# Paths relative to the script's directory
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
README_FILE = os.path.join(SCRIPT_DIR, "../README.md")

# Tags for the table of contents in the README file
TOC_START_TAG = "<!-- TOC_START -->"
TOC_END_TAG = "<!-- TOC_END -->"

# Debug flag
DEBUG = "--debug" in sys.argv


def log_debug(message):
    """Log debug messages to stderr if debugging is enabled."""
    if DEBUG:
        print(f"DEBUG: {message}", file=sys.stderr)


def extract_headers(min_level, max_level):
    """Extract headers from the README file to build the Table of Contents."""
    log_debug(f"Extracting headers from {README_FILE}")

    headers = []
    with open(README_FILE, "r") as readme:
        for line in readme:
            match = re.match(r"^(#{1,6})\s+(.+)", line)
            if match:
                level = len(match.group(1))
                if min_level <= level <= max_level:
                    header_text = match.group(2).strip()
                    log_debug(f"Found header: Level {level} - '{header_text}'")
                    headers.append((level, header_text))

    return headers


def header_to_anchor(header_text):
    """Convert a header string to a GitHub-flavored Markdown anchor.

    Strips markdown link syntax (e.g. [text](url) -> text), then lowercases,
    replaces spaces with hyphens, and removes all remaining non-alphanumeric
    characters except hyphens.
    """
    # Strip markdown links: [text](url) -> text
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", header_text)
    # Strip inline code backticks
    text = re.sub(r"`([^`]+)`", r"\1", text)
    # Lowercase, spaces to hyphens, drop everything else
    text = text.lower()
    text = text.replace(" ", "-")
    text = re.sub(r"[^a-z0-9-]", "", text)
    # Collapse consecutive hyphens (e.g. "Shell & Environment" -> "shell--environment" -> "shell-environment")
    text = re.sub(r"-+", "-", text)
    return text


def generate_toc(headers):
    """Generate the markdown table of contents from the extracted headers."""
    log_debug("Generating Table of Contents from headers")

    toc_lines = []
    for level, header_text in headers:
        anchor = header_to_anchor(header_text)
        indent = "  " * (level - 1)
        toc_line = f"{indent}- [{header_text}](#{anchor})"
        toc_lines.append(toc_line)
        log_debug(f"Generated TOC line: '{toc_line}'")

    toc = "\n".join(toc_lines)
    log_debug("Generated Table of Contents:\n" + toc)
    return toc


def readme_contains_toc():
    """Read the README file and extract the existing TOC between TOC_START_TAG and TOC_END_TAG."""
    log_debug(f"Reading existing TOC from {README_FILE}")
    with open(README_FILE, "r") as readme:
        content = readme.read()
        match = re.search(f"{TOC_START_TAG}(.*?){TOC_END_TAG}", content, re.DOTALL)
        if match:
            existing_toc = match.group(1).strip()
            log_debug(f"Existing TOC found:\n{existing_toc}")
            return existing_toc
    log_debug("No existing TOC found")
    return None


def update_readme(new_toc):
    """Update the README file with the new TOC, replacing the old TOC."""
    log_debug(f"Updating README file: {README_FILE}")
    with open(README_FILE, "r") as readme:
        content = readme.read()

    updated_content = re.sub(
        f"{TOC_START_TAG}.*?{TOC_END_TAG}",
        f"{TOC_START_TAG}\n{new_toc}\n{TOC_END_TAG}",
        content,
        flags=re.DOTALL,
    )

    if updated_content != content:
        with open(README_FILE, "w") as readme:
            readme.write(updated_content)
        log_debug("README.md updated with new TOC.")
        print("README.md updated.")
    else:
        log_debug("README.md is up to date. No changes needed.")
        print("README.md is up to date. No changes needed.")


def main():
    # Default header levels to include in TOC
    min_header_level = 2
    max_header_level = 3

    # Parse command line arguments
    is_ci_mode = "--ci" in sys.argv

    # Check for --header-level argument (min)
    for arg in sys.argv:
        if arg.startswith("--header-level="):
            try:
                min_header_level = int(arg.split("=")[1])
                log_debug(f"Minimum header level set to: {min_header_level}")
            except ValueError:
                print(
                    "Invalid value for --header-level. Please provide an integer.",
                    file=sys.stderr,
                )
                sys.exit(1)
        if arg.startswith("--max-header-level="):
            try:
                max_header_level = int(arg.split("=")[1])
                log_debug(f"Maximum header level set to: {max_header_level}")
            except ValueError:
                print(
                    "Invalid value for --max-header-level. Please provide an integer.",
                    file=sys.stderr,
                )
                sys.exit(1)

    # Extract headers from the README file
    headers = extract_headers(min_header_level, max_header_level)

    # Generate the Table of Contents
    new_toc = generate_toc(headers)

    # If in CI mode, compare the TOCs and return appropriate code
    if is_ci_mode:
        existing_toc = readme_contains_toc()
        if existing_toc and existing_toc.strip() == new_toc.strip():
            log_debug("TOCs match in CI mode. Exiting with code 0.")
            sys.exit(0)
        else:
            log_debug("TOCs do not match in CI mode. Exiting with code 1.")
            sys.exit(1)
    else:
        # Update the README file with the new TOC
        update_readme(new_toc)


if __name__ == "__main__":
    main()
