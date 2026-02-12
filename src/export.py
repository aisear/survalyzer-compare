"""Export comparison data to JSON format for client-side rendering."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.models import ComparisonResult, Question, LocalizedText
from src.parse import extract_short_name
from src.sections import SectionNormalizer


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
            {
                "code": rd.code,
                "status": rd.status,
                "text_diffs": [
                    {
                        "language": td.language,
                        "status": td.status,
                        "similarity": td.similarity,
                        "old_text": td.old_text,
                        "new_text": td.new_text,
                    }
                    for td in rd.text_diffs
                ],
            }
            for rd in qd.matrix_row_diffs
        ],
        "matrix_column_diffs": [
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
    section_normalizer: SectionNormalizer | None = None,
) -> dict[str, Any]:
    """Export comparison data to a JSON-serializable dict.

    Supports flexible comparison: any source can be the reference.

    Returns a dict with:
    - meta: source names, short names, languages, sections, default reference
    - questions: all sources indexed by source name, then normalized code
    - diffs: pairwise diffs indexed by "sourceA→sourceB", then question code
    """
    # Build unified sources dict (Question objects) for section ordering
    all_sources: dict[str, list[Question]] = {}
    if master_questions is not None:
        all_sources["master"] = master_questions
    all_sources.update(questions_by_source)

    # Build unified questions dict for all sources (keyed by normalized code)
    questions_dict: dict[str, dict[str, Any]] = {}
    for source_name, questions in all_sources.items():
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

    # Build sections using normalizer (reference-based ordering + fuzzy merge)
    # or fall back to simple grouping
    if section_normalizer is not None:
        section_list = section_normalizer.ordered_sections(all_sources)
        sections = {s["name"]: s["codes"] for s in section_list}
        section_aliases = section_normalizer.all_aliases
    else:
        # Fallback: group by raw section_name, ordered by reference source
        sections = {}
        seen_codes: set[str] = set()
        ref_source = all_sources.get(default_reference, [])
        other_sources = [q for s, qs in all_sources.items() if s != default_reference for q in qs]
        for q in sorted(ref_source, key=lambda q: q.section_index):
            section = q.section_name or "Other"
            if section not in sections:
                sections[section] = []
            if q.normalized_code not in seen_codes:
                sections[section].append(q.normalized_code)
                seen_codes.add(q.normalized_code)
        for q in other_sources:
            section = q.section_name or "Other"
            if section not in sections:
                sections[section] = []
            if q.normalized_code not in seen_codes:
                sections[section].append(q.normalized_code)
                seen_codes.add(q.normalized_code)
        section_aliases = {}

    # Count total unique codes
    all_codes: set[str] = set()
    for source_questions in questions_dict.values():
        all_codes.update(source_questions.keys())

    meta: dict[str, Any] = {
        "sources": source_names,
        "short_names": short_names,
        "default_reference": default_reference,
        "languages": sorted_languages,
        "sections": sections,
        "total_questions": len(all_codes),
    }
    if section_aliases:
        meta["section_aliases"] = section_aliases

    return {
        "meta": meta,
        "questions": questions_dict,
        "diffs": diffs_dict,
    }


def save_data(data: dict[str, Any], path: str | Path) -> None:
    """Write data dict to JSON file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
