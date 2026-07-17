#!/usr/bin/env python3
"""
Validate .iterate.json configuration file.

Usage:
    python3 validate-config.py [path/to/.iterate.json]

Exits with 0 if valid, 1 if invalid.
"""

import json
import sys
from pathlib import Path


def validate_config(config_path: Path) -> bool:
    """Validate .iterate.json configuration."""
    if not config_path.exists():
        print(f"Error: {config_path} does not exist", file=sys.stderr)
        return False

    try:
        with open(config_path, "r") as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {config_path}: {e}", file=sys.stderr)
        return False

    # Check for valid keys
    valid_keys = {
        # Flat schema (preferred)
        "include_paths", "exclude_paths",
        "include_extensions", "exclude_extensions",
        # Behaviour / tuning keys read by IterateConfig
        "timeouts", "skip_in_background", "custom_output_filters",
        "env", "cargo", "coverage_threshold",
        # Legacy nested schema
        "include", "exclude"
    }

    unknown_keys = set(config.keys()) - valid_keys
    if unknown_keys:
        print(f"Warning: Unknown keys in config: {', '.join(unknown_keys)}", file=sys.stderr)

    # Validate flat schema
    for key in ["include_paths", "exclude_paths", "include_extensions", "exclude_extensions"]:
        if key in config:
            if not isinstance(config[key], list):
                print(f"Error: '{key}' must be an array", file=sys.stderr)
                return False

            if not all(isinstance(item, str) for item in config[key]):
                print(f"Error: '{key}' must contain only strings", file=sys.stderr)
                return False

    # Validate nested schema
    for parent_key in ["include", "exclude"]:
        if parent_key in config:
            if not isinstance(config[parent_key], dict):
                print(f"Error: '{parent_key}' must be an object", file=sys.stderr)
                return False

            for child_key in ["paths", "extensions"]:
                if child_key in config[parent_key]:
                    if not isinstance(config[parent_key][child_key], list):
                        print(f"Error: '{parent_key}.{child_key}' must be an array", file=sys.stderr)
                        return False

    # Validate extension format
    for ext_key in ["include_extensions", "exclude_extensions"]:
        if ext_key in config:
            for ext in config[ext_key]:
                if not ext.startswith('.'):
                    print(f"Warning: Extension '{ext}' in '{ext_key}' should start with '.'", file=sys.stderr)

    print(f"✓ Configuration valid: {config_path}")
    return True


def main():
    if len(sys.argv) > 1:
        config_path = Path(sys.argv[1])
    else:
        config_path = Path(".iterate.json")

    if validate_config(config_path):
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
