"""Comparison engine: diff questions across two Survalyzer questionnaires."""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any

from src.models import (
    AnswerOption,
    ChoiceDiff,
    ComparisonResult,
    LocalizedText,
    MatrixRow,
    Question,
    QuestionDiff,
    TextDiff,
)

DEFAULT_SIMILARITY_THRESHOLD = 0.9


# ---------------------------------------------------------------------------
# Text comparison helpers
# ---------------------------------------------------------------------------

def _similarity(a: str, b: str) -> float:
    """Return SequenceMatcher ratio for two strings."""
    if a == b:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def _text_status(score: float, threshold: float) -> str:
    if score == 1.0:
        return "exact"
    if score >= threshold:
        return "similar"
    return "different"


def _build_text_index(texts: list[LocalizedText]) -> dict[str, str]:
    """Map lowercased language code → text."""
    return {lt.language.lower(): lt.text for lt in texts}


def compare_texts(
    old: list[LocalizedText],
    new: list[LocalizedText],
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> list[TextDiff]:
    """Compare multilingual texts and return per-language diffs."""
    old_map = _build_text_index(old)
    new_map = _build_text_index(new)
    all_langs = sorted(set(old_map) | set(new_map))
    diffs: list[TextDiff] = []
    for lang in all_langs:
        old_text = old_map.get(lang)
        new_text = new_map.get(lang)
        if old_text is None:
            diffs.append(TextDiff(lang, "added", 0.0, "", new_text or ""))
        elif new_text is None:
            diffs.append(TextDiff(lang, "removed", 0.0, old_text, ""))
        else:
            score = _similarity(old_text, new_text)
            diffs.append(TextDiff(lang, _text_status(score, threshold), score, old_text, new_text))
    return diffs


# ---------------------------------------------------------------------------
# Choice / option comparison
# ---------------------------------------------------------------------------

def _compare_coded_items(
    old_items: list[Any],
    new_items: list[Any],
    threshold: float,
) -> list[ChoiceDiff]:
    """Compare two lists of items that have .code and .texts attributes."""
    old_map = {item.code: item for item in old_items}
    new_map = {item.code: item for item in new_items}
    all_codes = list(dict.fromkeys(
        [item.code for item in old_items] + [item.code for item in new_items]
    ))

    diffs: list[ChoiceDiff] = []
    for code in all_codes:
        old_item = old_map.get(code)
        new_item = new_map.get(code)
        if old_item is None:
            diffs.append(ChoiceDiff(code, "added"))
        elif new_item is None:
            diffs.append(ChoiceDiff(code, "removed"))
        else:
            text_diffs = compare_texts(old_item.texts, new_item.texts, threshold)
            any_change = any(td.status != "exact" for td in text_diffs)
            diffs.append(ChoiceDiff(
                code,
                "text_changed" if any_change else "unchanged",
                text_diffs,
            ))
    return diffs


def compare_choices(
    old: list[AnswerOption],
    new: list[AnswerOption],
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> list[ChoiceDiff]:
    return _compare_coded_items(old, new, threshold)


def compare_matrix_rows(
    old: list[MatrixRow],
    new: list[MatrixRow],
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> list[ChoiceDiff]:
    return _compare_coded_items(old, new, threshold)


def compare_matrix_columns(
    old_groups: list,
    new_groups: list,
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> list[ChoiceDiff]:
    """Flatten column groups into individual columns and compare by code."""
    old_cols = [col for grp in old_groups for col in grp.columns]
    new_cols = [col for grp in new_groups for col in grp.columns]
    return _compare_coded_items(old_cols, new_cols, threshold)


# ---------------------------------------------------------------------------
# Question-level comparison
# ---------------------------------------------------------------------------

def compare_questions(
    old: Question,
    new: Question,
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> QuestionDiff:
    """Produce a full diff for a single question present in both surveys."""
    text_diffs = compare_texts(old.texts, new.texts, threshold)

    # For Matrix questions, use matrix_rows instead of choices
    choice_diffs: list[ChoiceDiff] = []
    matrix_row_diffs: list[ChoiceDiff] = []
    matrix_col_diffs: list[ChoiceDiff] = []
    if old.element_type == "Matrix" or new.element_type == "Matrix":
        matrix_row_diffs = compare_matrix_rows(old.matrix_rows, new.matrix_rows, threshold)
        matrix_col_diffs = compare_matrix_columns(
            old.matrix_column_groups, new.matrix_column_groups, threshold,
        )
    else:
        choice_diffs = compare_choices(old.choices, new.choices, threshold)

    # Determine overall status
    has_text_change = any(td.status != "exact" for td in text_diffs)
    has_structure_change = any(
        cd.status in ("added", "removed")
        for cd in choice_diffs + matrix_row_diffs + matrix_col_diffs
    )
    has_child_text_change = any(
        cd.status == "text_changed"
        for cd in choice_diffs + matrix_row_diffs + matrix_col_diffs
    )

    if has_structure_change:
        status = "structure_changed"
    elif has_text_change or has_child_text_change:
        status = "text_changed"
    else:
        status = "identical"

    return QuestionDiff(
        code=old.code,
        element_type=old.element_type,
        status=status,
        text_diffs=text_diffs,
        choice_diffs=choice_diffs,
        matrix_row_diffs=matrix_row_diffs,
        matrix_column_diffs=matrix_col_diffs,
    )


# ---------------------------------------------------------------------------
# Full survey comparison
# ---------------------------------------------------------------------------

def compare_surveys(
    questions_a: list[Question],
    questions_b: list[Question],
    source_a: str = "A",
    source_b: str = "B",
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> ComparisonResult:
    """Compare two full question lists and return a ComparisonResult.

    Questions are matched by normalized_code (with F/I prefix stripped).
    """
    # Index by normalized code for cross-survey matching
    map_a = {q.normalized_code: q for q in questions_a}
    map_b = {q.normalized_code: q for q in questions_b}
    all_codes = list(dict.fromkeys(
        [q.normalized_code for q in questions_a] + [q.normalized_code for q in questions_b]
    ))

    diffs: list[QuestionDiff] = []
    for norm_code in all_codes:
        qa = map_a.get(norm_code)
        qb = map_b.get(norm_code)
        if qa is None:
            diffs.append(QuestionDiff(code=norm_code, element_type=qb.element_type, status="added"))
        elif qb is None:
            diffs.append(QuestionDiff(code=norm_code, element_type=qa.element_type, status="removed"))
        else:
            diff = compare_questions(qa, qb, threshold)
            # Use normalized code in the diff for consistent matching
            diff.code = norm_code
            diffs.append(diff)

    return ComparisonResult(source_a=source_a, source_b=source_b, question_diffs=diffs)
