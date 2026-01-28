"""Export comparison data to JSON format for client-side rendering."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from src.models import ComparisonResult, Question, LocalizedText
from src.parse import extract_short_name


def _localized_texts_to_dict(texts: list[LocalizedText]) -> dict[str, str]:
    """Convert list of LocalizedText to {language: text} dict."""
    return {lt.language: lt.text for lt in texts}


def _question_to_dict(q: Question) -> dict[str, Any]:
    """Convert Question to JSON-serializable dict."""
    d: dict[str, Any] = {
        "id": q.id,
        "code": q.code,
        "element_type": q.element_type,
        "section_name": q.section_name,
        "texts": _localized_texts_to_dict(q.texts),
    }
    # For Matrix: use matrix_rows/columns; for others: use choices
    if q.element_type == "Matrix":
        d["matrix_rows"] = [
            {"code": r.code, "texts": _localized_texts_to_dict(r.texts)}
            for r in q.matrix_rows
        ]
        d["matrix_columns"] = [
            {"code": c.code, "texts": _localized_texts_to_dict(c.texts)}
            for cg in q.matrix_column_groups
            for c in cg.columns
        ]
    else:
        d["choices"] = [
            {"code": c.code, "texts": _localized_texts_to_dict(c.texts)}
            for c in q.choices
        ]
    return d


def _question_diff_to_dict(qd) -> dict[str, Any]:
    """Convert QuestionDiff to JSON-serializable dict."""
    return {
        "code": qd.code,
        "element_type": qd.element_type,
        "status": qd.status,
        "text_diffs": [
            {
                "language": td.language,
                "status": td.status,
                "similarity": td.similarity,
                "old_text": td.old_text,
                "new_text": td.new_text,
            }
            for td in qd.text_diffs
        ],
        "choice_diffs": [
            {
                "code": cd.code,
                "status": cd.status,
                "text_diffs": [
                    {
                        "language": td.language,
                        "status": td.status,
                        "similarity": td.similarity,
                        "old_text": td.old_text,
                        "new_text": td.new_text,
                    }
                    for td in cd.text_diffs
                ],
            }
            for cd in qd.choice_diffs
        ],
        "matrix_row_diffs": [
            {"code": rd.code, "status": rd.status}
            for rd in qd.matrix_row_diffs
        ],
        "matrix_column_diffs": [
            {"code": cd.code, "status": cd.status}
            for cd in qd.matrix_column_diffs
        ],
    }


def export_data(
    results: list[ComparisonResult],
    questions_by_source: dict[str, list[Question]],
    master_questions: list[Question],
) -> dict[str, Any]:
    """Export comparison data to a JSON-serializable dict.

    Returns a dict with:
    - meta: summary stats, survey names, languages
    - master: master questions indexed by code
    - surveys: survey questions indexed by survey name, then code
    - diffs: comparison diffs indexed by code, then survey name
    """
    # Collect survey names and short names
    survey_names = [r.source_b for r in results]
    short_names = {name: extract_short_name(name) for name in survey_names}

    # Collect available languages from master
    languages = set()
    for q in master_questions:
        for lt in q.texts:
            languages.add(lt.language)
    languages = sorted(languages) if languages else ["en"]

    # Build master questions dict
    master_dict = {}
    for q in master_questions:
        master_dict[q.code] = _question_to_dict(q)

    # Build survey questions dict (keyed by normalized code for consistency)
    surveys_dict = {}
    for survey_name, questions in questions_by_source.items():
        surveys_dict[survey_name] = {}
        for q in questions:
            surveys_dict[survey_name][q.normalized_code] = _question_to_dict(q)

    # Build diffs dict: {code: {survey_name: diff}}
    diffs_dict = {}
    for result in results:
        survey_name = result.source_b
        for qd in result.question_diffs:
            if qd.code not in diffs_dict:
                diffs_dict[qd.code] = {}
            diffs_dict[qd.code][survey_name] = _question_diff_to_dict(qd)

    # Collect all codes and sections
    all_codes = set(master_dict.keys())
    for survey_questions in surveys_dict.values():
        all_codes.update(survey_questions.keys())

    # Group codes by section
    sections = {}
    for code in sorted(all_codes):
        # Find section from master or any survey
        section = "Other"
        if code in master_dict:
            section = master_dict[code].get("section_name") or "Other"
        else:
            for survey_questions in surveys_dict.values():
                if code in survey_questions:
                    section = survey_questions[code].get("section_name") or "Other"
                    break
        if section not in sections:
            sections[section] = []
        sections[section].append(code)

    # Calculate summary stats
    status_counts = {"identical": 0, "text_changed": 0, "structure_changed": 0, "added": 0, "removed": 0}
    for code in all_codes:
        code_diffs = diffs_dict.get(code, {})
        if not code_diffs:
            continue
        worst = "identical"
        priority = ["structure_changed", "text_changed", "added", "removed", "identical"]
        for qd in code_diffs.values():
            if priority.index(qd["status"]) < priority.index(worst):
                worst = qd["status"]
        status_counts[worst] = status_counts.get(worst, 0) + 1

    return {
        "meta": {
            "survey_names": survey_names,
            "short_names": short_names,
            "languages": languages,
            "sections": sections,
            "total_questions": len(all_codes),
            "status_counts": status_counts,
        },
        "master": master_dict,
        "surveys": surveys_dict,
        "diffs": diffs_dict,
    }


def save_data(data: dict[str, Any], path: str | Path) -> None:
    """Write data dict to JSON file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
