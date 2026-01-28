#!/usr/bin/env python3
"""Generate HTML comparison report comparing each survey against master.

Usage:
    python scripts/generate_report.py [--exports-dir data/exports] [--output docs/index.html]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.parse import load_and_parse, sort_files_by_date, extract_date_from_filename
from src.compare import compare_surveys
from src.master import load_master, master_to_questions
from src.render import render_report, save_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate HTML comparison report")
    parser.add_argument(
        "--exports-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "exports",
    )
    parser.add_argument(
        "--master",
        type=Path,
        default=PROJECT_ROOT / "master" / "master.yaml",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "docs" / "index.html",
    )
    parser.add_argument(
        "--language",
        default="de-CH",
        help="Default display language (default: de-CH)",
    )
    args = parser.parse_args()

    # Load master
    if not args.master.exists():
        print(f"Master file not found: {args.master}")
        print("Run scripts/generate_master.py first.")
        sys.exit(1)

    master_dict = load_master(args.master)
    master_questions = master_to_questions(master_dict)
    print(f"Loaded master: {len(master_questions)} questions")

    # Find and sort all JSON files by date in filename
    json_files = list(args.exports_dir.glob("*.json"))
    if not json_files:
        print(f"No JSON files found in {args.exports_dir}")
        sys.exit(1)
    json_files = sort_files_by_date(json_files)

    # Parse all exports
    questions_by_source: dict[str, list] = {}
    for jf in json_files:
        name = jf.stem
        date_str = extract_date_from_filename(jf.name)
        questions_by_source[name] = load_and_parse(jf)
        print(f"Parsed {name} (date: {date_str}): {len(questions_by_source[name])} questions")

    # Compare each survey against master
    results = []
    for source_name, questions in questions_by_source.items():
        result = compare_surveys(
            master_questions,
            questions,
            source_a="master",
            source_b=source_name,
        )
        results.append(result)
        print(f"Compared master → {source_name}: "
              f"{len(result.matched)} matched, "
              f"{len(result.added)} added, "
              f"{len(result.removed)} removed")

    html = render_report(results, questions_by_source, master_questions, default_language=args.language)
    save_report(html, args.output)
    print(f"Report written to {args.output}")


if __name__ == "__main__":
    main()
