"""Parse Survalyzer JSON exports into normalized Question objects."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.models import (
    AnswerOption,
    LocalizedText,
    MatrixColumn,
    MatrixColumnGroup,
    MatrixRow,
    Question,
)

# Element types we treat as questions (everything else is skipped).
QUESTION_TYPES = {"SingleChoice", "MultipleChoice", "OpenQuestion", "Matrix", "Dropdown"}


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def _parse_localized(raw: list[dict[str, str]] | None) -> list[LocalizedText]:
    """Convert a Survalyzer multilingual text array to LocalizedText list."""
    if not raw:
        return []
    return [
        LocalizedText(language=item["languageCode"], text=item.get("text", ""))
        for item in raw
    ]


def _parse_choice(raw: dict[str, Any]) -> AnswerOption:
    return AnswerOption(
        id=raw["id"],
        code=raw.get("code", ""),
        texts=_parse_localized(raw.get("text")),
        allow_text_entry=raw.get("allowTextEntry", False),
        exclusive=raw.get("exclusive", False),
    )


def _parse_matrix_column(raw: dict[str, Any]) -> MatrixColumn:
    return MatrixColumn(
        id=raw["id"],
        code=raw.get("code", ""),
        texts=_parse_localized(raw.get("text")),
    )


def _parse_matrix_column_group(raw: dict[str, Any]) -> MatrixColumnGroup:
    return MatrixColumnGroup(
        id=raw["id"],
        columns=[_parse_matrix_column(c) for c in raw.get("choices", [])],
        choice_type=raw.get("choiceType", "Text"),
    )


# ---------------------------------------------------------------------------
# Element → Question
# ---------------------------------------------------------------------------

def _parse_element(element: dict[str, Any], section_name: str | None) -> Question | None:
    etype = element.get("elementType")
    if etype not in QUESTION_TYPES:
        return None

    q = Question(
        id=element["id"],
        code=element.get("code", ""),
        element_type=etype,
        texts=_parse_localized(element.get("text")),
        hint_texts=_parse_localized(element.get("hintText")),
        choices=[_parse_choice(c) for c in element.get("choices", [])],
        force_response=element.get("forceResponse", False),
        section_name=section_name,
        conditions=element.get("conditions"),
    )

    # Matrix-specific: column groups and rows
    if etype == "Matrix":
        q.matrix_column_groups = [
            _parse_matrix_column_group(cg)
            for cg in element.get("columnGroups", [])
        ]
        # Matrix rows are the top-level "choices" list
        q.matrix_rows = [
            MatrixRow(
                id=c["id"],
                code=c.get("code", ""),
                texts=_parse_localized(c.get("text")),
            )
            for c in element.get("choices", [])
        ]

    return q


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_survey(data: dict[str, Any]) -> list[Question]:
    """Parse a full Survalyzer survey dict and return all Question objects."""
    questions: list[Question] = []
    for section in data.get("sections", []):
        section_name = section.get("name")
        for element in section.get("elements", []):
            q = _parse_element(element, section_name)
            if q is not None:
                questions.append(q)
    return questions


def load_and_parse(path: str | Path) -> list[Question]:
    """Load a JSON file from *path* and return parsed questions."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return parse_survey(data)
