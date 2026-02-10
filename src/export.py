"""Export comparison data to JSON format for client-side rendering."""

from __future__ import annotations

import json
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


def _diff_pair_key(source_a: str, source_b: str) -> str:
    """Build a canonical key for a directed comparison pair."""
    return f"{source_a}\u2192{source_b}"


def export_data(
    results: list[ComparisonResult],
    questions_by_source: dict[str, list[Question]],
    master_questions: list[Question] | None = None,
    default_reference: str = "master",
) -> dict[str, Any]:
    """Export comparison data to a JSON-serializable dict.

    Supports flexible comparison: any source can be the reference.

    Returns a dict with:
    - meta: source names, short names, languages, sections, default reference
    - questions: all sources indexed by source name, then normalized code
    - diffs: pairwise diffs indexed by "sourceA→sourceB", then question code
    """
    # Build unified questions dict for all sources (keyed by normalized code)
    questions_dict: dict[str, dict[str, Any]] = {}

    # Include master as a source if provided
    if master_questions is not None:
        questions_dict["master"] = {}
        for q in master_questions:
            questions_dict["master"][q.normalized_code] = _question_to_dict(q)

    # Include all survey sources
    for source_name, questions in questions_by_source.items():
        questions_dict[source_name] = {}
        for q in questions:
            questions_dict[source_name][q.normalized_code] = _question_to_dict(q)

    # Collect all source names in order
    source_names = list(questions_dict.keys())

    # Build short names for all sources
    short_names = {}
    for name in source_names:
        if name == "master":
            short_names[name] = "Master"
        else:
            short_names[name] = extract_short_name(name)

    # Collect available languages from all sources
    languages: set[str] = set()
    for source_questions in questions_dict.values():
        for q_dict in source_questions.values():
            for lang in q_dict.get("texts", {}).keys():
                languages.add(lang)
    sorted_languages = sorted(languages) if languages else ["en"]

    # Build pairwise diffs: {"sourceA→sourceB": {code: diff}}
    diffs_dict: dict[str, dict[str, Any]] = {}
    for result in results:
        pair_key = _diff_pair_key(result.source_a, result.source_b)
        diffs_dict[pair_key] = {}
        for qd in result.question_diffs:
            diffs_dict[pair_key][qd.code] = _question_diff_to_dict(qd)

    # Collect all normalized codes across all sources
    all_codes: set[str] = set()
    for source_questions in questions_dict.values():
        all_codes.update(source_questions.keys())

    # Group codes by section (prefer master ordering, then surveys)
    sections: dict[str, list[str]] = {}
    for code in sorted(all_codes):
        section = "Other"
        for source_questions in questions_dict.values():
            if code in source_questions:
                section = source_questions[code].get("section_name") or "Other"
                break
        if section not in sections:
            sections[section] = []
        sections[section].append(code)

    return {
        "meta": {
            "sources": source_names,
            "short_names": short_names,
            "default_reference": default_reference,
            "languages": sorted_languages,
            "sections": sections,
            "total_questions": len(all_codes),
        },
        "questions": questions_dict,
        "diffs": diffs_dict,
    }


def save_data(data: dict[str, Any], path: str | Path) -> None:
    """Write data dict to JSON file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
