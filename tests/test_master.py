"""Tests for src.master – master question store."""

import tempfile
from pathlib import Path

import pytest

from src.models import (
    AnswerOption,
    LocalizedText,
    MatrixColumn,
    MatrixColumnGroup,
    MatrixRow,
    Question,
)
from src.master import extract_master, save_master, load_master, question_to_dict
from src.parse import load_and_parse


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _lt(text: str, lang: str = "en") -> LocalizedText:
    return LocalizedText(language=lang, text=text)


def _sample_questions() -> list[Question]:
    return [
        Question(
            id=1, code="Q1", element_type="SingleChoice",
            texts=[_lt("Pick one"), _lt("Wählen Sie", "de-ch")],
            choices=[
                AnswerOption(id=10, code="1", texts=[_lt("Yes"), _lt("Ja", "de-ch")]),
                AnswerOption(id=11, code="2", texts=[_lt("No"), _lt("Nein", "de-ch")]),
            ],
        ),
        Question(
            id=2, code="Q2", element_type="OpenQuestion",
            texts=[_lt("Comments?")],
        ),
        Question(
            id=3, code="Q3", element_type="Matrix",
            texts=[_lt("Rate these")],
            choices=[
                AnswerOption(id=20, code="1", texts=[_lt("Row A")]),
            ],
            matrix_rows=[
                MatrixRow(id=20, code="1", texts=[_lt("Row A")]),
            ],
            matrix_column_groups=[
                MatrixColumnGroup(id=1, columns=[
                    MatrixColumn(id=30, code="1", texts=[_lt("Bad")]),
                    MatrixColumn(id=31, code="2", texts=[_lt("Good")]),
                ]),
            ],
        ),
    ]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestExtractMaster:
    def test_keys_are_question_codes(self):
        master = extract_master(_sample_questions())
        assert set(master.keys()) == {"Q1", "Q2", "Q3"}

    def test_single_choice_structure(self):
        master = extract_master(_sample_questions())
        q1 = master["Q1"]
        assert q1["element_type"] == "SingleChoice"
        assert q1["texts"]["en"] == "Pick one"
        assert q1["texts"]["de-ch"] == "Wählen Sie"
        assert len(q1["choices"]) == 2
        assert q1["choices"][0]["code"] == "1"
        assert q1["choices"][0]["texts"]["en"] == "Yes"

    def test_open_question_no_choices(self):
        master = extract_master(_sample_questions())
        q2 = master["Q2"]
        assert "choices" not in q2

    def test_matrix_has_rows_and_columns(self):
        master = extract_master(_sample_questions())
        q3 = master["Q3"]
        assert len(q3["matrix_rows"]) == 1
        assert len(q3["matrix_columns"]) == 2
        assert q3["matrix_columns"][0]["texts"]["en"] == "Bad"


class TestSaveAndLoad:
    def test_round_trip(self):
        master = extract_master(_sample_questions())
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "master.yaml"
            save_master(master, path)
            loaded = load_master(path)
        assert loaded == master

    def test_load_empty_file(self):
        with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w", delete=False) as f:
            f.write("")
            path = f.name
        assert load_master(path) == {}
        Path(path).unlink()

    def test_manual_edit_survives(self):
        """Simulate a manual edit to master.yaml and verify it loads."""
        master = extract_master(_sample_questions())
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "master.yaml"
            save_master(master, path)
            # Simulate manual edit: change a text value
            content = path.read_text()
            content = content.replace("Pick one", "Choose one")
            path.write_text(content)
            loaded = load_master(path)
        assert loaded["Q1"]["texts"]["en"] == "Choose one"


EXPORTS_DIR = Path(__file__).resolve().parent.parent / "data" / "exports"
SAMPLE_JSON = next(EXPORTS_DIR.glob("*.json"), None)


@pytest.mark.skipif(SAMPLE_JSON is None, reason="No JSON export in data/exports/")
class TestRealExportMaster:
    def test_round_trip_real(self):
        questions = load_and_parse(SAMPLE_JSON)
        master = extract_master(questions)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "master.yaml"
            save_master(master, path)
            loaded = load_master(path)
        assert loaded == master
        assert len(master) == len(questions)
