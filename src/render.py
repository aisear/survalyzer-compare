"""HTML report generation from comparison results."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from src.models import ComparisonResult, Question
from src.parse import extract_short_name

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


def _build_question_index(
    questions_by_source: dict[str, list[Question]],
    master_questions: list[Question],
) -> dict[str, dict[str, Question]]:
    """Return {normalized_code: {source_name: Question}} for quick lookup."""
    index: dict[str, dict[str, Question]] = {}
    # Add master questions
    for q in master_questions:
        index.setdefault(q.normalized_code, {})["master"] = q
    # Add survey questions
    for source, qlist in questions_by_source.items():
        for q in qlist:
            index.setdefault(q.normalized_code, {})[source] = q
    return index


def _collect_all_codes(
    questions_by_source: dict[str, list[Question]],
    master_questions: list[Question],
) -> list[str]:
    """Return ordered unique normalized codes across all sources, preserving master order first."""
    seen: dict[str, None] = {}
    # Master codes first
    for q in master_questions:
        seen.setdefault(q.normalized_code, None)
    # Then survey codes
    for qlist in questions_by_source.values():
        for q in qlist:
            seen.setdefault(q.normalized_code, None)
    return list(seen)


def _collect_sections(
    questions_by_source: dict[str, list[Question]],
    master_questions: list[Question],
) -> list[dict[str, Any]]:
    """Group normalized codes by section name, preserving order."""
    section_order: list[str] = []
    section_codes: dict[str, list[str]] = {}
    seen_codes: set[str] = set()

    # Process master first (may not have section_name)
    for q in master_questions:
        section = q.section_name or "Uncategorized"
        if section not in section_codes:
            section_order.append(section)
            section_codes[section] = []
        if q.normalized_code not in seen_codes:
            section_codes[section].append(q.normalized_code)
            seen_codes.add(q.normalized_code)

    # Then surveys
    for qlist in questions_by_source.values():
        for q in qlist:
            section = q.section_name or "Uncategorized"
            if section not in section_codes:
                section_order.append(section)
                section_codes[section] = []
            if q.normalized_code not in seen_codes:
                section_codes[section].append(q.normalized_code)
                seen_codes.add(q.normalized_code)

    return [
        {"name": name, "codes": section_codes[name]}
        for name in section_order
    ]


def _build_diff_lookup(
    results: list[ComparisonResult],
) -> dict[str, dict[str, Any]]:
    """Return {code: {survey_name: QuestionDiff}} for template access.

    Each result compares master → survey, so we key by source_b (the survey name).
    """
    lookup: dict[str, dict[str, Any]] = {}
    for result in results:
        survey_name = result.source_b
        for qd in result.question_diffs:
            lookup.setdefault(qd.code, {})[survey_name] = qd
    return lookup


STATUS_COLOR = {
    "identical": "green",
    "text_changed": "yellow",
    "similar": "yellow",
    "structure_changed": "red",
    "different": "red",
    "added": "grey",
    "removed": "grey",
}


def render_report(
    results: list[ComparisonResult],
    questions_by_source: dict[str, list[Question]],
    master_questions: list[Question],
    default_language: str = "de-CH",
) -> str:
    """Render a self-contained HTML comparison report.

    Each result is a comparison of master → survey_name.
    """
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=True,
    )
    template = env.get_template("report.html.jinja")

    question_index = _build_question_index(questions_by_source, master_questions)
    sections = _collect_sections(questions_by_source, master_questions)
    diff_lookup = _build_diff_lookup(results)

    # Survey names (columns in the report)
    survey_names = [r.source_b for r in results]

    # Short names for display (IPf, IPi, etc.)
    short_names = {name: extract_short_name(name) for name in survey_names}

    # Available languages (collect from master questions)
    available_languages = set()
    for q in master_questions:
        for lt in q.texts:
            available_languages.add(lt.language)
    languages = sorted(available_languages) if available_languages else ["en"]

    # Summary stats
    all_codes = _collect_all_codes(questions_by_source, master_questions)
    status_counts = {"identical": 0, "text_changed": 0, "structure_changed": 0, "added": 0, "removed": 0}
    for code in all_codes:
        code_diffs = diff_lookup.get(code, {})
        if not code_diffs:
            continue
        worst = "identical"
        priority = ["structure_changed", "text_changed", "added", "removed", "identical"]
        for qd in code_diffs.values():
            if priority.index(qd.status) < priority.index(worst):
                worst = qd.status
        status_counts[worst] = status_counts.get(worst, 0) + 1

    return template.render(
        sections=sections,
        survey_names=survey_names,
        short_names=short_names,
        languages=languages,
        question_index=question_index,
        diff_lookup=diff_lookup,
        status_color=STATUS_COLOR,
        status_counts=status_counts,
        total_questions=len(all_codes),
        default_language=default_language,
    )


def save_report(html: str, path: str | Path) -> None:
    """Write rendered HTML to a file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
