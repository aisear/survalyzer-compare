"""HTML report generation from comparison results."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from src.models import ComparisonResult, Question

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


def _build_question_index(
    questions_by_source: dict[str, list[Question]],
) -> dict[str, dict[str, Question]]:
    """Return {normalized_code: {source_name: Question}} for quick lookup."""
    index: dict[str, dict[str, Question]] = {}
    for source, qlist in questions_by_source.items():
        for q in qlist:
            index.setdefault(q.normalized_code, {})[source] = q
    return index


def _collect_all_codes(questions_by_source: dict[str, list[Question]]) -> list[str]:
    """Return ordered unique normalized codes across all sources, preserving first-seen order."""
    seen: dict[str, None] = {}
    for qlist in questions_by_source.values():
        for q in qlist:
            seen.setdefault(q.normalized_code, None)
    return list(seen)


def _collect_sections(
    questions_by_source: dict[str, list[Question]],
) -> list[dict[str, Any]]:
    """Group normalized codes by section name, preserving order."""
    section_order: list[str] = []
    section_codes: dict[str, list[str]] = {}
    seen_codes: set[str] = set()

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
    """Return {code: {source_pair: QuestionDiff}} for template access."""
    lookup: dict[str, dict[str, Any]] = {}
    for result in results:
        pair_key = f"{result.source_a} → {result.source_b}"
        for qd in result.question_diffs:
            lookup.setdefault(qd.code, {})[pair_key] = qd
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
    default_language: str = "de-CH",
) -> str:
    """Render a self-contained HTML comparison report."""
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=True,
    )
    template = env.get_template("report.html.jinja")

    question_index = _build_question_index(questions_by_source)
    sections = _collect_sections(questions_by_source)
    diff_lookup = _build_diff_lookup(results)
    sources = list(questions_by_source.keys())
    pair_keys = [f"{r.source_a} → {r.source_b}" for r in results]

    # Summary stats
    all_codes = _collect_all_codes(questions_by_source)
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
        sources=sources,
        pair_keys=pair_keys,
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
