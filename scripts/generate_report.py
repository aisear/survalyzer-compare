#!/usr/bin/env python3
"""Generate HTML comparison report from all Survalyzer JSON exports.

Usage:
    python scripts/generate_report.py [--exports-dir data/exports] [--output docs/index.html]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.parse import load_and_parse
from src.compare import compare_surveys
from src.render import render_report, save_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate HTML comparison report")
    parser.add_argument(
        "--exports-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "exports",
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

    json_files = sorted(args.exports_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)
    if not json_files:
        print(f"No JSON files found in {args.exports_dir}")
        sys.exit(1)

    # Parse all exports
    questions_by_source: dict[str, list] = {}
    for jf in json_files:
        name = jf.stem
        questions_by_source[name] = load_and_parse(jf)
        print(f"Parsed {name}: {len(questions_by_source[name])} questions")

    # Pairwise comparison (each consecutive pair)
    results = []
    source_names = list(questions_by_source.keys())
    for i in range(len(source_names) - 1):
        a_name = source_names[i]
        b_name = source_names[i + 1]
        result = compare_surveys(
            questions_by_source[a_name],
            questions_by_source[b_name],
            source_a=a_name,
            source_b=b_name,
        )
        results.append(result)
        print(f"Compared {a_name} → {b_name}: "
              f"{len(result.matched)} matched, "
              f"{len(result.added)} added, "
              f"{len(result.removed)} removed")

    # If only one file, create a self-comparison so the report still renders
    if not results:
        name = source_names[0]
        result = compare_surveys(
            questions_by_source[name],
            questions_by_source[name],
            source_a=name,
            source_b=name,
        )
        results.append(result)
        print(f"Single file — self-comparison: {len(result.matched)} questions")

    html = render_report(results, questions_by_source, default_language=args.language)
    save_report(html, args.output)
    print(f"Report written to {args.output}")


if __name__ == "__main__":
    main()
