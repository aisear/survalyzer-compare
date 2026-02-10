"""Tests for src.sections – section normalization, ordering, and alias merging."""

import tempfile
from pathlib import Path

from src.models import LocalizedText, Question
from src.sections import (
    SectionNormalizer,
    build_section_normalizer,
    load_section_aliases,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _q(code: str, section: str, section_index: int = 0) -> Question:
    return Question(
        id=1, code=code, element_type="SingleChoice",
        texts=[LocalizedText("en", f"Text for {code}")],
        section_name=section, section_index=section_index,
    )


# ---------------------------------------------------------------------------
# Tests: load_section_aliases
# ---------------------------------------------------------------------------

class TestLoadSectionAliases:
    def test_loads_yaml(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write('"Section A": "Section B"\n')
            f.flush()
            aliases = load_section_aliases(f.name)
        assert aliases == {"Section A": "Section B"}

    def test_missing_file_returns_empty(self):
        aliases = load_section_aliases("/nonexistent/path.yaml")
        assert aliases == {}


# ---------------------------------------------------------------------------
# Tests: build_section_normalizer
# ---------------------------------------------------------------------------

class TestBuildSectionNormalizer:
    def test_strips_whitespace(self):
        sources = {
            "ref": [_q("Q1", "  Section A  ", 0)],
        }
        norm = build_section_normalizer(sources, "ref")
        assert norm.normalize("  Section A  ") == "Section A"

    def test_applies_explicit_alias(self):
        sources = {
            "ref": [_q("Q1", "Variant Name", 0)],
        }
        aliases = {"Variant Name": "Canonical Name"}
        norm = build_section_normalizer(sources, "ref", aliases)
        assert norm.normalize("Variant Name") == "Canonical Name"

    def test_fuzzy_merges_similar_names(self):
        """Names with >92% similarity should be merged."""
        sources = {
            "ref": [_q("Q1", "Charakterisierung des Projekts", 0)],
            "other": [_q("Q2", "Charakterisierung des Projektes", 0)],
        }
        norm = build_section_normalizer(sources, "ref")
        # Both should map to the reference's version
        assert norm.normalize("Charakterisierung des Projekts") == "Charakterisierung des Projekts"
        assert norm.normalize("Charakterisierung des Projektes") == "Charakterisierung des Projekts"

    def test_fuzzy_merge_prefers_reference_name(self):
        """When merging, prefer the name from the reference source."""
        sources = {
            "other": [_q("Q1", "Charakterisierung des Projektes", 0)],
            "ref": [_q("Q2", "Charakterisierung des Projekts", 0)],
        }
        norm = build_section_normalizer(sources, "ref")
        # Both should map to reference's version
        assert norm.normalize("Charakterisierung des Projektes") == "Charakterisierung des Projekts"
        assert norm.normalize("Charakterisierung des Projekts") == "Charakterisierung des Projekts"

    def test_does_not_merge_dissimilar_names(self):
        sources = {
            "ref": [_q("Q1", "Nutzen", 0)],
            "other": [_q("Q2", "Ergebnisse", 0)],
        }
        norm = build_section_normalizer(sources, "ref")
        assert norm.normalize("Nutzen") != norm.normalize("Ergebnisse")

    def test_aliases_for_merged_section(self):
        sources = {
            "ref": [_q("Q1", "Charakterisierung des Projekts", 0)],
            "other": [_q("Q2", "Charakterisierung des Projektes", 0)],
        }
        norm = build_section_normalizer(sources, "ref")
        canonical = norm.normalize("Charakterisierung des Projekts")
        aliases = norm.aliases_for(canonical)
        assert "Charakterisierung des Projektes" in aliases


# ---------------------------------------------------------------------------
# Tests: ordered_sections
# ---------------------------------------------------------------------------

class TestOrderedSections:
    def test_reference_order_preserved(self):
        ref_qs = [
            _q("Q1", "Section B", 1),
            _q("Q2", "Section A", 0),
            _q("Q3", "Section C", 2),
        ]
        other_qs = [_q("Q4", "Section D", 0)]
        sources = {"ref": ref_qs, "other": other_qs}
        norm = build_section_normalizer(sources, "ref")
        sections = norm.ordered_sections(sources)
        names = [s["name"] for s in sections]
        # Reference sections should come in their section_index order
        assert names[0] == "Section A"
        assert names[1] == "Section B"
        assert names[2] == "Section C"
        assert names[3] == "Section D"

    def test_other_source_sections_appended(self):
        ref_qs = [_q("Q1", "Ref Section", 0)]
        other_qs = [_q("Q2", "Other Section", 0)]
        sources = {"ref": ref_qs, "other": other_qs}
        norm = build_section_normalizer(sources, "ref")
        sections = norm.ordered_sections(sources)
        names = [s["name"] for s in sections]
        assert "Ref Section" in names
        assert "Other Section" in names
        assert names.index("Ref Section") < names.index("Other Section")

    def test_merged_sections_combine_codes(self):
        ref_qs = [_q("Q1", "Char des Projekts", 0)]
        other_qs = [_q("Q2", "Char des Projektes", 0)]
        sources = {"ref": ref_qs, "other": other_qs}
        # These are 96% similar → should merge
        norm = build_section_normalizer(sources, "ref")
        sections = norm.ordered_sections(sources)
        # Should produce 1 section, not 2
        assert len(sections) == 1
        assert "Q1" in sections[0]["codes"]
        assert "Q2" in sections[0]["codes"]

    def test_codes_are_normalized(self):
        ref_qs = [_q("FQuestion1", "Section", 0)]
        sources = {"ref": ref_qs}
        norm = build_section_normalizer(sources, "ref")
        sections = norm.ordered_sections(sources)
        assert "Question1" in sections[0]["codes"]

    def test_no_duplicate_codes(self):
        """Same normalized code from multiple sources should appear only once."""
        ref_qs = [_q("FQ1", "Section", 0)]
        other_qs = [_q("IQ1", "Section", 0)]
        sources = {"ref": ref_qs, "other": other_qs}
        norm = build_section_normalizer(sources, "ref")
        sections = norm.ordered_sections(sources)
        all_codes = [c for s in sections for c in s["codes"]]
        assert all_codes.count("Q1") == 1

    def test_section_aliases_in_output(self):
        ref_qs = [_q("Q1", "Char des Projekts", 0)]
        other_qs = [_q("Q2", "Char des Projektes", 0)]
        sources = {"ref": ref_qs, "other": other_qs}
        norm = build_section_normalizer(sources, "ref")
        sections = norm.ordered_sections(sources)
        assert len(sections) == 1
        assert "aliases" in sections[0]
        assert "Char des Projektes" in sections[0]["aliases"]
