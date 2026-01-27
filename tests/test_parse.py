"""Tests for src.parse – Survalyzer JSON ingestion."""

import json
from pathlib import Path

import pytest

from src.parse import parse_survey, load_and_parse, _parse_localized
from src.models import Question

EXPORTS_DIR = Path(__file__).resolve().parent.parent / "data" / "exports"
SAMPLE_JSON = next(EXPORTS_DIR.glob("*.json"), None)


# ---------------------------------------------------------------------------
# Helper-level tests
# ---------------------------------------------------------------------------

class TestParseLocalized:
    def test_empty_input(self):
        assert _parse_localized(None) == []
        assert _parse_localized([]) == []

    def test_normal(self):
        raw = [
            {"languageCode": "de-CH", "text": "Hallo"},
            {"languageCode": "en", "text": "Hello"},
        ]
        result = _parse_localized(raw)
        assert len(result) == 2
        assert result[0].language == "de-CH"
        assert result[0].text == "Hallo"


# ---------------------------------------------------------------------------
# Minimal synthetic survey
# ---------------------------------------------------------------------------

MINIMAL_SURVEY = {
    "sections": [
        {
            "name": "Section A",
            "elements": [
                {
                    "id": 1,
                    "code": "Q1",
                    "elementType": "SingleChoice",
                    "text": [{"languageCode": "en", "text": "Pick one"}],
                    "hintText": [],
                    "choices": [
                        {"id": 10, "code": "1", "text": [{"languageCode": "en", "text": "Yes"}]},
                        {"id": 11, "code": "2", "text": [{"languageCode": "en", "text": "No"}]},
                    ],
                    "forceResponse": True,
                    "conditions": None,
                },
                {
                    "id": 2,
                    "code": "Q2",
                    "elementType": "OpenQuestion",
                    "text": [{"languageCode": "en", "text": "Tell us more"}],
                    "hintText": None,
                    "forceResponse": False,
                    "conditions": None,
                },
                {
                    "id": 99,
                    "elementType": "PageBreak",
                    "conditions": None,
                    "cssClasses": None,
                },
                {
                    "id": 3,
                    "code": "Q3",
                    "elementType": "Matrix",
                    "text": [{"languageCode": "en", "text": "Rate these"}],
                    "hintText": None,
                    "choices": [
                        {"id": 20, "code": "1", "text": [{"languageCode": "en", "text": "Row A"}]},
                        {"id": 21, "code": "2", "text": [{"languageCode": "en", "text": "Row B"}]},
                    ],
                    "columnGroups": [
                        {
                            "id": 1,
                            "choiceType": "SingleChoice",
                            "choices": [
                                {"id": 30, "code": "1", "text": [{"languageCode": "en", "text": "Bad"}]},
                                {"id": 31, "code": "2", "text": [{"languageCode": "en", "text": "Good"}]},
                            ],
                        }
                    ],
                    "forceResponse": False,
                    "conditions": None,
                },
            ],
        }
    ]
}


class TestParseSurvey:
    def test_skips_non_question_elements(self):
        questions = parse_survey(MINIMAL_SURVEY)
        assert all(isinstance(q, Question) for q in questions)
        assert all(q.element_type != "PageBreak" for q in questions)

    def test_correct_count(self):
        questions = parse_survey(MINIMAL_SURVEY)
        assert len(questions) == 3  # SingleChoice, OpenQuestion, Matrix

    def test_single_choice(self):
        q = parse_survey(MINIMAL_SURVEY)[0]
        assert q.code == "Q1"
        assert q.element_type == "SingleChoice"
        assert len(q.choices) == 2
        assert q.choices[0].texts[0].text == "Yes"
        assert q.force_response is True
        assert q.section_name == "Section A"

    def test_open_question(self):
        q = parse_survey(MINIMAL_SURVEY)[1]
        assert q.element_type == "OpenQuestion"
        assert q.choices == []

    def test_matrix(self):
        q = parse_survey(MINIMAL_SURVEY)[2]
        assert q.element_type == "Matrix"
        assert len(q.matrix_rows) == 2
        assert q.matrix_rows[0].texts[0].text == "Row A"
        assert len(q.matrix_column_groups) == 1
        assert len(q.matrix_column_groups[0].columns) == 2

    def test_get_text_helper(self):
        q = parse_survey(MINIMAL_SURVEY)[0]
        assert q.get_text("en") == "Pick one"
        # fallback to first available
        assert q.get_text("fr") == "Pick one"


# ---------------------------------------------------------------------------
# Integration: real export file
# ---------------------------------------------------------------------------

@pytest.mark.skipif(SAMPLE_JSON is None, reason="No JSON export in data/exports/")
class TestRealExport:
    @pytest.fixture(autouse=True)
    def _load(self):
        self.questions = load_and_parse(SAMPLE_JSON)

    def test_loads_questions(self):
        assert len(self.questions) > 0

    def test_all_have_id_and_type(self):
        for q in self.questions:
            assert q.id > 0
            assert q.element_type in {
                "SingleChoice", "MultipleChoice", "OpenQuestion", "Matrix", "Dropdown"
            }

    def test_all_have_code(self):
        for q in self.questions:
            assert q.code, f"Question id={q.id} has no code"

    def test_all_have_text(self):
        for q in self.questions:
            assert q.texts, f"Question id={q.id} has no text"

    def test_matrix_questions_have_structure(self):
        matrices = [q for q in self.questions if q.element_type == "Matrix"]
        assert len(matrices) > 0
        for m in matrices:
            assert len(m.matrix_rows) > 0, f"Matrix id={m.id} has no rows"
            assert len(m.matrix_column_groups) > 0, f"Matrix id={m.id} has no column groups"

    def test_choice_questions_have_choices(self):
        for q in self.questions:
            if q.element_type in {"SingleChoice", "MultipleChoice", "Dropdown"}:
                assert len(q.choices) > 0, f"{q.element_type} id={q.id} has no choices"

    def test_expected_counts(self):
        """Verify against known counts from the sample export."""
        from collections import Counter
        counts = Counter(q.element_type for q in self.questions)
        assert counts["Matrix"] == 32
        assert counts["SingleChoice"] == 14
        assert counts["MultipleChoice"] == 7
        assert counts["OpenQuestion"] == 6
        assert counts["Dropdown"] == 2
