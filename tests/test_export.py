"""Tests for src.export – JSON data export with flexible comparison."""

from src.models import (
    AnswerOption,
    ComparisonResult,
    LocalizedText,
    Question,
    QuestionDiff,
    TextDiff,
)
from src.export import export_data, _diff_pair_key


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _lt(text: str, lang: str = "en") -> LocalizedText:
    return LocalizedText(language=lang, text=text)


def _question(code: str, text: str, etype: str = "SingleChoice", section: str = "S1") -> Question:
    return Question(id=1, code=code, element_type=etype, texts=[_lt(text)], section_name=section)


def _make_result(source_a, source_b, diffs):
    return ComparisonResult(source_a=source_a, source_b=source_b, question_diffs=diffs)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestDiffPairKey:
    def test_produces_arrow_key(self):
        assert _diff_pair_key("master", "surveyA") == "master\u2192surveyA"

    def test_direction_matters(self):
        assert _diff_pair_key("A", "B") != _diff_pair_key("B", "A")


class TestExportDataFlexible:
    def test_sources_include_master_and_surveys(self):
        master = [_question("Q1", "Master Q1")]
        surveys = {"surveyA": [_question("Q1", "Survey Q1")]}
        result = _make_result("master", "surveyA", [
            QuestionDiff(code="Q1", element_type="SingleChoice", status="identical"),
        ])
        data = export_data([result], surveys, master_questions=master)
        assert "master" in data["meta"]["sources"]
        assert "surveyA" in data["meta"]["sources"]
        assert data["meta"]["short_names"]["master"] == "Master"

    def test_questions_indexed_by_source(self):
        master = [_question("Q1", "Master Q1")]
        surveys = {"surveyA": [_question("Q1", "Survey Q1")]}
        result = _make_result("master", "surveyA", [
            QuestionDiff(code="Q1", element_type="SingleChoice", status="identical"),
        ])
        data = export_data([result], surveys, master_questions=master)
        assert "Q1" in data["questions"]["master"]
        assert "Q1" in data["questions"]["surveyA"]

    def test_diffs_keyed_by_pair(self):
        master = [_question("Q1", "Master Q1")]
        surveys = {"surveyA": [_question("Q1", "Survey Q1")]}
        result = _make_result("master", "surveyA", [
            QuestionDiff(code="Q1", element_type="SingleChoice", status="text_changed",
                         text_diffs=[TextDiff("en", "different", 0.5, "Master Q1", "Survey Q1")]),
        ])
        data = export_data([result], surveys, master_questions=master)
        pair_key = "master\u2192surveyA"
        assert pair_key in data["diffs"]
        assert "Q1" in data["diffs"][pair_key]
        assert data["diffs"][pair_key]["Q1"]["status"] == "text_changed"

    def test_default_reference(self):
        master = [_question("Q1", "Master Q1")]
        surveys = {"surveyA": [_question("Q1", "Survey Q1")]}
        result = _make_result("master", "surveyA", [
            QuestionDiff(code="Q1", element_type="SingleChoice", status="identical"),
        ])
        data = export_data([result], surveys, master_questions=master)
        assert data["meta"]["default_reference"] == "master"

    def test_custom_default_reference(self):
        surveys = {
            "surveyA": [_question("Q1", "A Q1")],
            "surveyB": [_question("Q1", "B Q1")],
        }
        result = _make_result("surveyA", "surveyB", [
            QuestionDiff(code="Q1", element_type="SingleChoice", status="identical"),
        ])
        data = export_data([result], surveys, master_questions=None, default_reference="surveyA")
        assert data["meta"]["default_reference"] == "surveyA"
        assert "master" not in data["meta"]["sources"]

    def test_pairwise_both_directions(self):
        master = [_question("Q1", "Master Q1")]
        surveys = {"surveyA": [_question("Q1", "Survey Q1")]}
        result_fwd = _make_result("master", "surveyA", [
            QuestionDiff(code="Q1", element_type="SingleChoice", status="text_changed"),
        ])
        result_rev = _make_result("surveyA", "master", [
            QuestionDiff(code="Q1", element_type="SingleChoice", status="text_changed"),
        ])
        data = export_data([result_fwd, result_rev], surveys, master_questions=master)
        assert "master\u2192surveyA" in data["diffs"]
        assert "surveyA\u2192master" in data["diffs"]

    def test_survey_to_survey_comparison(self):
        surveys = {
            "surveyA": [_question("Q1", "A text")],
            "surveyB": [_question("Q1", "B text")],
        }
        result = _make_result("surveyA", "surveyB", [
            QuestionDiff(code="Q1", element_type="SingleChoice", status="text_changed"),
        ])
        data = export_data([result], surveys, master_questions=None)
        pair_key = "surveyA\u2192surveyB"
        assert pair_key in data["diffs"]
        assert data["diffs"][pair_key]["Q1"]["status"] == "text_changed"

    def test_no_master_key_in_output(self):
        """The new format uses 'questions' not 'master'+'surveys'."""
        master = [_question("Q1", "Master Q1")]
        surveys = {"surveyA": [_question("Q1", "Survey Q1")]}
        result = _make_result("master", "surveyA", [
            QuestionDiff(code="Q1", element_type="SingleChoice", status="identical"),
        ])
        data = export_data([result], surveys, master_questions=master)
        assert "master" not in data or "master" in data.get("questions", {})
        assert "surveys" not in data
