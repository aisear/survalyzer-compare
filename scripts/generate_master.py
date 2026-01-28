#!/usr/bin/env python3
"""Generate master.yaml by merging all Survalyzer JSON exports.

Questions are merged from newest to oldest - if a code exists in a newer
export, that version is used; otherwise falls back to older exports.

Usage:
    python scripts/generate_master.py [--exports-dir data/exports] [--output master/master.yaml]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

# Ensure project root is on sys.path when running as a script.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.parse import load_and_parse, sort_files_by_date, extract_date_from_filename
from src.master import extract_master, save_master


def merge_masters(masters: list[dict[str, Any]]) -> dict[str, Any]:
    """Merge multiple master dicts, earlier ones take precedence."""
    merged: dict[str, Any] = {}
    for master in reversed(masters):  # Oldest first, newest overwrites
        merged.update(master)
    return merged


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate master.yaml from Survalyzer exports")
    parser.add_argument(
        "--exports-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "exports",
        help="Directory containing JSON exports (default: data/exports)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "master" / "master.yaml",
        help="Output path for master YAML (default: master/master.yaml)",
    )
    args = parser.parse_args()

    # Find and sort all JSON files by date (oldest first)
    json_files = list(args.exports_dir.glob("*.json"))
    if not json_files:
        print(f"No JSON files found in {args.exports_dir}")
        sys.exit(1)
    json_files = sort_files_by_date(json_files)

    # Parse all exports and extract master from each
    masters: list[dict[str, Any]] = []
    for jf in json_files:
        date_str = extract_date_from_filename(jf.name)
        questions = load_and_parse(jf)
        master = extract_master(questions)
        masters.append(master)
        print(f"Parsed {jf.name} (date: {date_str}): {len(questions)} questions")

    # Merge all masters (newest takes precedence)
    merged = merge_masters(masters)
    print(f"Merged master: {len(merged)} unique question codes")

    save_master(merged, args.output)
    print(f"Master written to {args.output}")


if __name__ == "__main__":
    main()
