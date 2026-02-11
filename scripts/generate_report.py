#!/usr/bin/env python3
"""Generate HTML comparison report with flexible reference survey selection.

Usage:
    python scripts/generate_report.py [--exports-dir data/exports] [--output-dir docs]
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.parse import load_and_parse, sort_files_by_date, extract_date_from_filename
from src.compare import compare_surveys
from src.master import load_master, master_to_questions
from src.export import export_data, save_data
from src.sections import build_section_normalizer, load_section_aliases

TEMPLATE_PATH = PROJECT_ROOT / "templates" / "report-dynamic.html"


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
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "docs",
        help="Output directory for index.html and data.json",
    )
    parser.add_argument(
        "--language",
        default="de-ch",
        help="Default display language (default: de-ch)",
    )
    parser.add_argument(
        "--section-aliases",
        type=Path,
        default=PROJECT_ROOT / "config" / "section_aliases.yaml",
        help="YAML file mapping section name variants to canonical names",
    )
    args = parser.parse_args()

    # Build unified sources dict: {source_name: [Question, ...]}
    all_sources: dict[str, list] = {}

    # Load master (optional – if the file exists, include it as a source)
    if args.master.exists():
        master_dict = load_master(args.master)
        master_questions = master_to_questions(master_dict)
        all_sources["master"] = master_questions
        print(f"Loaded master: {len(master_questions)} questions")
    else:
        master_questions = None
        print(f"Master file not found: {args.master} (proceeding without master)")

    # Find and sort all JSON files by date in filename
    json_files = list(args.exports_dir.glob("*.json"))
    if not json_files:
        print(f"No JSON files found in {args.exports_dir}")
        sys.exit(1)
    json_files = sort_files_by_date(json_files)

    # Parse all exports
    for jf in json_files:
        name = jf.stem
        date_str = extract_date_from_filename(jf.name)
        all_sources[name] = load_and_parse(jf)
        print(f"Parsed {name} (date: {date_str}): {len(all_sources[name])} questions")

    # Compute ALL pairwise comparisons
    source_names = list(all_sources.keys())
    results = []
    for i, name_a in enumerate(source_names):
        for j, name_b in enumerate(source_names):
            if i == j:
                continue
            result = compare_surveys(
                all_sources[name_a],
                all_sources[name_b],
                source_a=name_a,
                source_b=name_b,
            )
            results.append(result)
            print(f"Compared {name_a} \u2192 {name_b}: "
                  f"{len(result.matched)} matched, "
                  f"{len(result.added)} added, "
                  f"{len(result.removed)} removed")

    # Build section normalizer
    default_ref = "master" if "master" in all_sources else source_names[0]
    aliases = load_section_aliases(args.section_aliases)
    if aliases:
        print(f"Loaded {len(aliases)} section aliases from {args.section_aliases}")
    normalizer = build_section_normalizer(all_sources, default_ref, aliases)
    if normalizer.all_aliases:
        print(f"Section merges: {normalizer.all_aliases}")

    # Separate master_questions from survey sources for export
    questions_by_source = {k: v for k, v in all_sources.items() if k != "master"}

    # Export data to JSON
    data = export_data(
        results,
        questions_by_source,
        master_questions=master_questions,
        default_reference=default_ref,
        section_normalizer=normalizer,
    )

    # Ensure output directory exists
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Save data.json
    data_path = args.output_dir / "data.json"
    save_data(data, data_path)
    print(f"Data written to {data_path}")

    # Copy HTML template
    html_path = args.output_dir / "index.html"
    shutil.copy(TEMPLATE_PATH, html_path)
    print(f"Report written to {html_path}")


if __name__ == "__main__":
    main()
