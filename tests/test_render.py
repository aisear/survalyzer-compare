"""Tests for src.render – HTML report generation."""

import tempfile
from pathlib import Path

import pytest

from src.models import (
    AnswerOption,
    ChoiceDiff,
    ComparisonResult,
    LocalizedText,
    Question,
    QuestionDiff,
    TextDiff,
)
from src.render import render_report, save_report


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _lt(text: str, lang: str = "en") -> LocalizedText:
    return LocalizedText(language=lang, text=text)


def _question(code: str, text: str, etype: str = "SingleChoice", section: str = "S1") -> Question:
    return Question(id=1, code=code, element_type=etype, texts=[_lt(text)], section_name=section)


def _build_fixture():
    """Build a minimal comparison result for rendering tests.

    New model: master questions + surveys compared to master.
    """
    # Master questions
    master = [
        _question("Q1", "Master Q1"),
        _question("Q2", "Master Q2"),
        _question("Q3", "Master Q3"),
    ]

    # Survey A (compared to master)
    survey_a = [
        _question("Q1", "Master Q1"),  # identical
        _question("Q2", "Changed Q2"),  # text changed
        # Q3 removed in survey
        _question("Q4", "New in A"),  # added
    ]

    # Comparison result: master → survey_A
    result = ComparisonResult(
        source_a="master",
        source_b="survey_A",
        question_diffs=[
            QuestionDiff(code="Q1", element_type="SingleChoice", status="identical",
                         text_diffs=[TextDiff("en", "exact", 1.0, "Master Q1", "Master Q1")]),
            QuestionDiff(code="Q2", element_type="SingleChoice", status="text_changed",
                         text_diffs=[TextDiff("en", "different", 0.5, "Master Q2", "Changed Q2")]),
            QuestionDiff(code="Q3", element_type="SingleChoice", status="removed"),
            QuestionDiff(code="Q4", element_type="SingleChoice", status="added"),
        ],
    )
    questions_by_source = {"survey_A": survey_a}
    return result, questions_by_source, master


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestRenderReport:
    def test_renders_without_error(self):
        result, qbs, master = _build_fixture()
        html = render_report([result], qbs, master, default_language="en")
        assert isinstance(html, str)
        assert len(html) > 100

    def test_contains_html_structure(self):
        result, qbs, master = _build_fixture()
        html = render_report([result], qbs, master, default_language="en")
        assert "<!DOCTYPE html>" in html
        assert "<title>" in html
        assert "</html>" in html

    def test_contains_question_codes(self):
        result, qbs, master = _build_fixture()
        html = render_report([result], qbs, master, default_language="en")
        assert "Q1" in html
        assert "Q2" in html
        assert "Q3" in html
        assert "Q4" in html

    def test_contains_status_badges(self):
        result, qbs, master = _build_fixture()
        html = render_report([result], qbs, master, default_language="en")
        assert "badge-identical" in html
        assert "badge-text_changed" in html
        assert "badge-removed" in html
        assert "badge-added" in html

    def test_contains_color_classes(self):
        result, qbs, master = _build_fixture()
        html = render_report([result], qbs, master, default_language="en")
        assert "cell-green" in html
        assert "cell-yellow" in html
        assert "cell-grey" in html

    def test_contains_summary_stats(self):
        result, qbs, master = _build_fixture()
        html = render_report([result], qbs, master, default_language="en")
        # Total questions = 4 (Q1, Q2, Q3 from master + Q4 from survey)
        assert ">4<" in html

    def test_contains_section_name(self):
        result, qbs, master = _build_fixture()
        html = render_report([result], qbs, master, default_language="en")
        assert "S1" in html

    def test_contains_detail_rows(self):
        result, qbs, master = _build_fixture()
        html = render_report([result], qbs, master, default_language="en")
        assert 'id="detail-Q1"' in html
        assert 'id="detail-Q2"' in html

    def test_text_diff_detail(self):
        result, qbs, master = _build_fixture()
        html = render_report([result], qbs, master, default_language="en")
        # Q2 has text diff with master/survey text
        assert "Master Q2" in html
        assert "Changed Q2" in html

    def test_contains_survey_column(self):
        result, qbs, master = _build_fixture()
        html = render_report([result], qbs, master, default_language="en")
        # Short name "A" is extracted from "survey_A"
        assert ">A<" in html or ">A " in html

    def test_master_text_column(self):
        result, qbs, master = _build_fixture()
        html = render_report([result], qbs, master, default_language="en")
        assert "Master Text" in html


class TestSaveReport:
    def test_writes_file(self):
        result, qbs, master = _build_fixture()
        html = render_report([result], qbs, master, default_language="en")
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "report.html"
            save_report(html, path)
            assert path.exists()
            content = path.read_text()
            assert "<!DOCTYPE html>" in content
