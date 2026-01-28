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
    """Build a minimal comparison result for rendering tests."""
    qa = [_question("Q1", "Same"), _question("Q2", "Old text"), _question("Q3", "Only in A")]
    qb = [_question("Q1", "Same"), _question("Q2", "New text"), _question("Q4", "Only in B")]

    result = ComparisonResult(
        source_a="A",
        source_b="B",
        question_diffs=[
            QuestionDiff(code="Q1", element_type="SingleChoice", status="identical",
                         text_diffs=[TextDiff("en", "exact", 1.0, "Same", "Same")]),
            QuestionDiff(code="Q2", element_type="SingleChoice", status="text_changed",
                         text_diffs=[TextDiff("en", "different", 0.5, "Old text", "New text")]),
            QuestionDiff(code="Q3", element_type="SingleChoice", status="removed"),
            QuestionDiff(code="Q4", element_type="SingleChoice", status="added"),
        ],
    )
    questions_by_source = {"A": qa, "B": qb}
    return result, questions_by_source


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestRenderReport:
    def test_renders_without_error(self):
        result, qbs = _build_fixture()
        html = render_report([result], qbs, default_language="en")
        assert isinstance(html, str)
        assert len(html) > 100

    def test_contains_html_structure(self):
        result, qbs = _build_fixture()
        html = render_report([result], qbs, default_language="en")
        assert "<!DOCTYPE html>" in html
        assert "<title>" in html
        assert "</html>" in html

    def test_contains_question_codes(self):
        result, qbs = _build_fixture()
        html = render_report([result], qbs, default_language="en")
        assert "Q1" in html
        assert "Q2" in html
        assert "Q3" in html
        assert "Q4" in html

    def test_contains_status_badges(self):
        result, qbs = _build_fixture()
        html = render_report([result], qbs, default_language="en")
        assert "badge-identical" in html
        assert "badge-text_changed" in html
        assert "badge-removed" in html
        assert "badge-added" in html

    def test_contains_color_classes(self):
        result, qbs = _build_fixture()
        html = render_report([result], qbs, default_language="en")
        assert "cell-green" in html
        assert "cell-yellow" in html
        assert "cell-grey" in html

    def test_contains_summary_stats(self):
        result, qbs = _build_fixture()
        html = render_report([result], qbs, default_language="en")
        # Total questions = 4
        assert ">4<" in html

    def test_contains_section_name(self):
        result, qbs = _build_fixture()
        html = render_report([result], qbs, default_language="en")
        assert "S1" in html

    def test_contains_detail_rows(self):
        result, qbs = _build_fixture()
        html = render_report([result], qbs, default_language="en")
        assert 'id="detail-Q1"' in html
        assert 'id="detail-Q2"' in html

    def test_text_diff_detail(self):
        result, qbs = _build_fixture()
        html = render_report([result], qbs, default_language="en")
        # Q2 has text diff with old/new text
        assert "Old text" in html
        assert "New text" in html


class TestSaveReport:
    def test_writes_file(self):
        result, qbs = _build_fixture()
        html = render_report([result], qbs, default_language="en")
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "report.html"
            save_report(html, path)
            assert path.exists()
            content = path.read_text()
            assert "<!DOCTYPE html>" in content
