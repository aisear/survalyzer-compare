"""Normalized data models for Survalyzer questionnaire elements."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Code normalization (strip F/I prefix for cross-survey matching)
# ---------------------------------------------------------------------------

# Pattern: leading F, f, I, or i followed by an uppercase letter
_CODE_PREFIX_PATTERN = re.compile(r'^[FfIi](?=[A-Z])')


def normalize_code(code: str) -> str:
    """Strip survey-type prefix (F/f/I/i) from question code for matching."""
    return _CODE_PREFIX_PATTERN.sub('', code)


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

    @property
    def normalized_code(self) -> str:
        """Return code with survey-type prefix stripped for matching."""
        return normalize_code(self.code)


# ---------------------------------------------------------------------------
# Diff / comparison result models
# ---------------------------------------------------------------------------

@dataclass
class TextDiff:
    """Comparison result for a single language's text."""
    language: str
    status: str  # "exact", "similar", "different", "added", "removed"
    similarity: float  # 0.0 – 1.0
    old_text: str = ""
    new_text: str = ""


@dataclass
class ChoiceDiff:
    """Comparison result for a single answer option."""
    code: str
    status: str  # "unchanged", "text_changed", "added", "removed"
    text_diffs: list[TextDiff] = field(default_factory=list)


@dataclass
class QuestionDiff:
    """Full diff for one question across two questionnaires."""
    code: str
    element_type: str
    status: str  # "identical", "text_changed", "structure_changed", "added", "removed"
    text_diffs: list[TextDiff] = field(default_factory=list)
    choice_diffs: list[ChoiceDiff] = field(default_factory=list)
    matrix_row_diffs: list[ChoiceDiff] = field(default_factory=list)
    matrix_column_diffs: list[ChoiceDiff] = field(default_factory=list)


@dataclass
class ComparisonResult:
    """Complete comparison output for two questionnaires."""
    source_a: str
    source_b: str
    question_diffs: list[QuestionDiff] = field(default_factory=list)

    @property
    def matched(self) -> list[QuestionDiff]:
        return [d for d in self.question_diffs if d.status not in ("added", "removed")]

    @property
    def added(self) -> list[QuestionDiff]:
        return [d for d in self.question_diffs if d.status == "added"]

    @property
    def removed(self) -> list[QuestionDiff]:
        return [d for d in self.question_diffs if d.status == "removed"]
