"""Normalized data models for Survalyzer questionnaire elements."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Multilingual text helper
# ---------------------------------------------------------------------------

@dataclass
class LocalizedText:
    """A single text value with its language code."""
    language: str
    text: str


# ---------------------------------------------------------------------------
# Answer option (used in SingleChoice, MultipleChoice, Dropdown, Matrix rows)
# ---------------------------------------------------------------------------

@dataclass
class AnswerOption:
    """One selectable choice inside a question."""
    id: int
    code: str
    texts: list[LocalizedText] = field(default_factory=list)
    allow_text_entry: bool = False
    exclusive: bool = False


# ---------------------------------------------------------------------------
# Matrix-specific structures
# ---------------------------------------------------------------------------

@dataclass
class MatrixColumn:
    """A column (answer option) inside a matrix column group."""
    id: int
    code: str
    texts: list[LocalizedText] = field(default_factory=list)
    choice_type: str = "Text"


@dataclass
class MatrixColumnGroup:
    """A group of columns in a matrix question."""
    id: int
    columns: list[MatrixColumn] = field(default_factory=list)
    choice_type: str = "Text"


@dataclass
class MatrixRow:
    """A row (sub-question) inside a matrix — reuses AnswerOption shape."""
    id: int
    code: str
    texts: list[LocalizedText] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Question (top-level normalized element)
# ---------------------------------------------------------------------------

@dataclass
class Question:
    """Normalized representation of any Survalyzer question element."""
    id: int
    code: str
    element_type: str  # SingleChoice, MultipleChoice, OpenQuestion, Matrix, Dropdown
    texts: list[LocalizedText] = field(default_factory=list)
    hint_texts: list[LocalizedText] = field(default_factory=list)
    choices: list[AnswerOption] = field(default_factory=list)
    matrix_rows: list[MatrixRow] = field(default_factory=list)
    matrix_column_groups: list[MatrixColumnGroup] = field(default_factory=list)
    force_response: bool = False
    section_name: Optional[str] = None
    conditions: Optional[list] = None

    # ---- convenience helpers ------------------------------------------------

    def get_text(self, language: str = "de-CH") -> str:
        """Return question text for *language*, falling back to first available."""
        lang_lower = language.lower()
        for lt in self.texts:
            if lt.language.lower() == lang_lower:
                return lt.text
        return self.texts[0].text if self.texts else ""
