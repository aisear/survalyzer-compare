#!/usr/bin/env python3
"""Generate master.yaml from the most recent Survalyzer JSON export.

Usage:
    python scripts/generate_master.py [--exports-dir data/exports] [--output master/master.yaml]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure project root is on sys.path when running as a script.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.parse import load_and_parse, sort_files_by_date, extract_date_from_filename
from src.master import extract_master, save_master


def latest_json(exports_dir: Path) -> Path:
    """Return the most recent JSON file by date in filename (YYYYMMDD)."""
    files = list(exports_dir.glob("*.json"))
    if not files:
        raise FileNotFoundError(f"No JSON files found in {exports_dir}")
    sorted_files = sort_files_by_date(files)
    return sorted_files[-1]  # Last = most recent


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate master.yaml from Survalyzer export")
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

    json_path = latest_json(args.exports_dir)
    date_str = extract_date_from_filename(json_path.name)
    print(f"Using export: {json_path.name} (date: {date_str})")

    questions = load_and_parse(json_path)
    print(f"Parsed {len(questions)} questions")

    master = extract_master(questions)
    save_master(master, args.output)
    print(f"Master written to {args.output}")


if __name__ == "__main__":
    main()
