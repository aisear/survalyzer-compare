"""Tests for src.compare – questionnaire diff engine."""

from src.models import (
    AnswerOption,
    LocalizedText,
    MatrixColumnGroup,
    MatrixColumn,
    MatrixRow,
    Question,
)
from src.compare import (
    compare_texts,
    compare_choices,
    compare_matrix_rows,
    compare_matrix_columns,
    compare_questions,
    compare_surveys,
)


# ---------------------------------------------------------------------------
# Helpers to build test data quickly
# ---------------------------------------------------------------------------

def _lt(text: str, lang: str = "en") -> LocalizedText:
    return LocalizedText(language=lang, text=text)


def _option(code: str, text: str, lang: str = "en") -> AnswerOption:
    return AnswerOption(id=int(code), code=code, texts=[_lt(text, lang)])


def _row(code: str, text: str) -> MatrixRow:
    return MatrixRow(id=int(code), code=code, texts=[_lt(text)])


def _col(code: str, text: str) -> MatrixColumn:
    return MatrixColumn(id=int(code), code=code, texts=[_lt(text)])


def _colgroup(cols: list[MatrixColumn]) -> MatrixColumnGroup:
    return MatrixColumnGroup(id=1, columns=cols)


def _question(code: str, text: str, etype: str = "SingleChoice", **kwargs) -> Question:
    return Question(id=1, code=code, element_type=etype, texts=[_lt(text)], **kwargs)


# ---------------------------------------------------------------------------
# Text comparison
# ---------------------------------------------------------------------------

class TestCompareTexts:
    def test_exact_match(self):
        diffs = compare_texts([_lt("Hello")], [_lt("Hello")])
        assert len(diffs) == 1
        assert diffs[0].status == "exact"
        assert diffs[0].similarity == 1.0

    def test_similar(self):
        diffs = compare_texts([_lt("Hello world")], [_lt("Hello World")], threshold=0.8)
        assert diffs[0].status == "similar"
        assert diffs[0].similarity >= 0.8

    def test_different(self):
        diffs = compare_texts([_lt("apples")], [_lt("oranges")], threshold=0.9)
        assert diffs[0].status == "different"
        assert diffs[0].similarity < 0.9

    def test_language_added(self):
        old = [_lt("Hallo", "de-ch")]
        new = [_lt("Hallo", "de-ch"), _lt("Hello", "en")]
        diffs = compare_texts(old, new)
        by_lang = {d.language: d for d in diffs}
        assert by_lang["de-ch"].status == "exact"
        assert by_lang["en"].status == "added"

    def test_language_removed(self):
        old = [_lt("Hallo", "de-ch"), _lt("Hello", "en")]
        new = [_lt("Hallo", "de-ch")]
        diffs = compare_texts(old, new)
        by_lang = {d.language: d for d in diffs}
        assert by_lang["en"].status == "removed"


# ---------------------------------------------------------------------------
# Choice comparison
# ---------------------------------------------------------------------------

class TestCompareChoices:
    def test_unchanged(self):
        old = [_option("1", "Yes"), _option("2", "No")]
        new = [_option("1", "Yes"), _option("2", "No")]
        diffs = compare_choices(old, new)
        assert all(d.status == "unchanged" for d in diffs)

    def test_text_changed(self):
        old = [_option("1", "Yes")]
        new = [_option("1", "Absolutely")]
        diffs = compare_choices(old, new)
        assert diffs[0].status == "text_changed"

    def test_added_option(self):
        old = [_option("1", "Yes")]
        new = [_option("1", "Yes"), _option("2", "No")]
        diffs = compare_choices(old, new)
        assert diffs[0].status == "unchanged"
        assert diffs[1].status == "added"

    def test_removed_option(self):
        old = [_option("1", "Yes"), _option("2", "No")]
        new = [_option("1", "Yes")]
        diffs = compare_choices(old, new)
        assert diffs[1].status == "removed"


# ---------------------------------------------------------------------------
# Matrix comparison
# ---------------------------------------------------------------------------

class TestCompareMatrix:
    def test_row_diff(self):
        old = [_row("1", "Row A"), _row("2", "Row B")]
        new = [_row("1", "Row A"), _row("3", "Row C")]
        diffs = compare_matrix_rows(old, new)
        by_code = {d.code: d for d in diffs}
        assert by_code["1"].status == "unchanged"
        assert by_code["2"].status == "removed"
        assert by_code["3"].status == "added"

    def test_column_diff(self):
        old_groups = [_colgroup([_col("1", "Bad"), _col("2", "Good")])]
        new_groups = [_colgroup([_col("1", "Bad"), _col("2", "Great")])]
        diffs = compare_matrix_columns(old_groups, new_groups)
        by_code = {d.code: d for d in diffs}
        assert by_code["1"].status == "unchanged"
        assert by_code["2"].status == "text_changed"


# ---------------------------------------------------------------------------
# Question-level comparison
# ---------------------------------------------------------------------------

class TestCompareQuestions:
    def test_identical(self):
        a = _question("Q1", "Pick one", choices=[_option("1", "Yes")])
        b = _question("Q1", "Pick one", choices=[_option("1", "Yes")])
        diff = compare_questions(a, b)
        assert diff.status == "identical"

    def test_text_changed(self):
        a = _question("Q1", "Pick one")
        b = _question("Q1", "Choose one")
        diff = compare_questions(a, b)
        assert diff.status == "text_changed"

    def test_structure_changed(self):
        a = _question("Q1", "Pick", choices=[_option("1", "A")])
        b = _question("Q1", "Pick", choices=[_option("1", "A"), _option("2", "B")])
        diff = compare_questions(a, b)
        assert diff.status == "structure_changed"

    def test_matrix_structure(self):
        a = _question("Q1", "Rate", etype="Matrix",
                       matrix_rows=[_row("1", "R1")],
                       matrix_column_groups=[_colgroup([_col("1", "C1")])])
        b = _question("Q1", "Rate", etype="Matrix",
                       matrix_rows=[_row("1", "R1"), _row("2", "R2")],
                       matrix_column_groups=[_colgroup([_col("1", "C1")])])
        diff = compare_questions(a, b)
        assert diff.status == "structure_changed"
        assert any(d.status == "added" for d in diff.matrix_row_diffs)


# ---------------------------------------------------------------------------
# Full survey comparison
# ---------------------------------------------------------------------------

class TestCompareSurveys:
    def test_matching_questions(self):
        a = [_question("Q1", "Pick one"), _question("Q2", "Tell us")]
        b = [_question("Q1", "Pick one"), _question("Q2", "Tell us")]
        result = compare_surveys(a, b)
        assert len(result.question_diffs) == 2
        assert all(d.status == "identical" for d in result.question_diffs)
        assert result.added == []
        assert result.removed == []

    def test_added_question(self):
        a = [_question("Q1", "A")]
        b = [_question("Q1", "A"), _question("Q2", "B")]
        result = compare_surveys(a, b, source_a="old", source_b="new")
        assert len(result.added) == 1
        assert result.added[0].code == "Q2"
        assert result.source_a == "old"

    def test_removed_question(self):
        a = [_question("Q1", "A"), _question("Q2", "B")]
        b = [_question("Q1", "A")]
        result = compare_surveys(a, b)
        assert len(result.removed) == 1
        assert result.removed[0].code == "Q2"

    def test_mixed(self):
        a = [_question("Q1", "Same"), _question("Q2", "Old text"), _question("Q3", "Gone")]
        b = [_question("Q1", "Same"), _question("Q2", "New text"), _question("Q4", "New")]
        result = compare_surveys(a, b)
        by_code = {d.code: d for d in result.question_diffs}
        assert by_code["Q1"].status == "identical"
        assert by_code["Q2"].status == "text_changed"
        assert by_code["Q3"].status == "removed"
        assert by_code["Q4"].status == "added"

    def test_cross_survey_prefix_matching(self):
        """Test that F-prefixed and I-prefixed codes match on normalized code."""
        # Final survey uses F prefix
        final = [
            _question("FUnternehmenArt", "Organisation type"),
            _question("FPersonal", "Staff count"),
        ]
        # Impact survey uses I prefix
        impact = [
            _question("IUnternehmenArt", "Organisation type - updated"),
            _question("IPersonal", "Staff count"),
        ]
        result = compare_surveys(final, impact, source_a="Final", source_b="Impact")
        # Should match on normalized codes (without F/I prefix)
        assert len(result.question_diffs) == 2
        by_code = {d.code: d for d in result.question_diffs}
        assert "UnternehmenArt" in by_code
        assert "Personal" in by_code
        assert by_code["UnternehmenArt"].status == "text_changed"
        assert by_code["Personal"].status == "identical"

    def test_lowercase_prefix_matching(self):
        """Test that lowercase f/i prefixes are also normalized."""
        a = [_question("fGruendungsjahr", "Founded")]
        b = [_question("iGruendungsjahr", "Founded")]
        result = compare_surveys(a, b)
        assert len(result.question_diffs) == 1
        # Should not treat as added/removed
        assert result.question_diffs[0].status == "identical"
