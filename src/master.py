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
    """Build a master dict keyed by question code."""
    return {q.code: question_to_dict(q) for q in questions}


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
