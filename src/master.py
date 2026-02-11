"""Master question store: extract, save, and load master definitions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from src.models import (
    AnswerOption,
    LocalizedText,
    MatrixColumn,
    MatrixColumnGroup,
    MatrixRow,
    Question,
)
from src.parse import clean_text


# ---------------------------------------------------------------------------
# Extract: Question list → plain dict (YAML-friendly)
# ---------------------------------------------------------------------------

def _texts_to_dict(texts: list[LocalizedText]) -> dict[str, str]:
    return {lt.language: lt.text for lt in texts}


def _choice_to_dict(opt: AnswerOption) -> dict[str, Any]:
    return {"code": opt.code, "texts": _texts_to_dict(opt.texts)}


def _matrix_row_to_dict(row: MatrixRow) -> dict[str, Any]:
    return {"code": row.code, "texts": _texts_to_dict(row.texts)}


def _matrix_col_to_dict(col: MatrixColumn) -> dict[str, Any]:
    return {"code": col.code, "texts": _texts_to_dict(col.texts)}


def question_to_dict(q: Question) -> dict[str, Any]:
    """Convert a single Question to a YAML-friendly dict."""
    d: dict[str, Any] = {
        "element_type": q.element_type,
        "texts": _texts_to_dict(q.texts),
    }
    if q.section_name:
        d["section_name"] = q.section_name
    if q.section_index:
        d["section_index"] = q.section_index
    if q.choices:
        d["choices"] = [_choice_to_dict(c) for c in q.choices]
    if q.matrix_rows:
        d["matrix_rows"] = [_matrix_row_to_dict(r) for r in q.matrix_rows]
    if q.matrix_column_groups:
        d["matrix_columns"] = [
            _matrix_col_to_dict(col)
            for grp in q.matrix_column_groups
            for col in grp.columns
        ]
    return d


def extract_master(questions: list[Question]) -> dict[str, Any]:
    """Build a master dict keyed by normalized question code."""
    return {q.normalized_code: question_to_dict(q) for q in questions}


# ---------------------------------------------------------------------------
# Save / Load
# ---------------------------------------------------------------------------

def save_master(master: dict[str, Any], path: str | Path) -> None:
    """Write master dict to a YAML file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(master, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def load_master(path: str | Path) -> dict[str, Any]:
    """Read a master YAML file back into a dict."""
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


# ---------------------------------------------------------------------------
# Convert master dict back to Question objects
# ---------------------------------------------------------------------------

def _dict_to_texts(d: dict[str, str]) -> list[LocalizedText]:
    return [LocalizedText(language=lang, text=clean_text(text)) for lang, text in d.items()]


def _dict_to_choice(d: dict[str, Any], idx: int) -> AnswerOption:
    return AnswerOption(
        id=idx,
        code=d.get("code", ""),
        texts=_dict_to_texts(d.get("texts", {})),
    )


def _dict_to_matrix_row(d: dict[str, Any], idx: int) -> MatrixRow:
    return MatrixRow(
        id=idx,
        code=d.get("code", ""),
        texts=_dict_to_texts(d.get("texts", {})),
    )


def _dict_to_matrix_col(d: dict[str, Any], idx: int) -> MatrixColumn:
    return MatrixColumn(
        id=idx,
        code=d.get("code", ""),
        texts=_dict_to_texts(d.get("texts", {})),
    )


def dict_to_question(code: str, d: dict[str, Any]) -> Question:
    """Convert a master dict entry back to a Question object."""
    q = Question(
        id=0,
        code=code,  # Use normalized code
        element_type=d.get("element_type", ""),
        texts=_dict_to_texts(d.get("texts", {})),
        section_name=d.get("section_name"),
        section_index=d.get("section_index", 0),
    )
    if "choices" in d:
        q.choices = [_dict_to_choice(c, i) for i, c in enumerate(d["choices"])]
    if "matrix_rows" in d:
        q.matrix_rows = [_dict_to_matrix_row(r, i) for i, r in enumerate(d["matrix_rows"])]
    if "matrix_columns" in d:
        # Wrap columns in a single group
        cols = [_dict_to_matrix_col(c, i) for i, c in enumerate(d["matrix_columns"])]
        q.matrix_column_groups = [MatrixColumnGroup(id=0, columns=cols)]
    return q


def master_to_questions(master: dict[str, Any]) -> list[Question]:
    """Convert full master dict to a list of Question objects."""
    return [dict_to_question(code, data) for code, data in master.items()]
