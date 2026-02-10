"""Section name normalization: strip whitespace, fuzzy merge, alias map."""

from __future__ import annotations

from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import yaml

from src.models import Question

# Similarity threshold for auto-merging section names
SECTION_MERGE_THRESHOLD = 0.92


def _strip_section_name(name: str) -> str:
    """Strip leading/trailing whitespace from section name."""
    return name.strip() if name else name


def load_section_aliases(path: str | Path) -> dict[str, str]:
    """Load section alias map from YAML file.

    Returns {variant_name: canonical_name}.
    """
    path = Path(path)
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return {str(k): str(v) for k, v in data.items()}


def build_section_normalizer(
    all_sources: dict[str, list[Question]],
    reference_source: str,
    aliases: dict[str, str] | None = None,
) -> "SectionNormalizer":
    """Build a SectionNormalizer from all sources.

    1. Collects all unique section names across all sources
    2. Strips whitespace
    3. Applies explicit alias map
    4. Fuzzy-merges remaining near-duplicates (preferring reference source names)
    """
    aliases = aliases or {}

    # Collect all raw section names per source, preserving order
    raw_names_by_source: dict[str, list[str]] = {}
    for source_name, questions in all_sources.items():
        seen: list[str] = []
        for q in questions:
            name = q.section_name or "Other"
            if name not in seen:
                seen.append(name)
        raw_names_by_source[source_name] = seen

    # Build the canonical name mapping: raw_name → canonical_name
    name_map: dict[str, str] = {}

    # Phase 1: Strip whitespace (always)
    all_stripped: dict[str, str] = {}  # stripped → first raw name that produced it
    for source_name in _ordered_sources(raw_names_by_source, reference_source):
        for raw in raw_names_by_source.get(source_name, []):
            stripped = _strip_section_name(raw)
            if stripped not in all_stripped:
                all_stripped[stripped] = raw
            name_map[raw] = stripped

    # Phase 2: Apply explicit aliases
    for raw, canonical in name_map.items():
        if canonical in aliases:
            name_map[raw] = aliases[canonical]
        elif raw in aliases:
            name_map[raw] = aliases[raw]

    # Collect all unique canonical names after phases 1+2
    canonical_names: list[str] = []
    for source_name in _ordered_sources(raw_names_by_source, reference_source):
        for raw in raw_names_by_source.get(source_name, []):
            cn = name_map[raw]
            if cn not in canonical_names:
                canonical_names.append(cn)

    # Phase 3: Fuzzy merge remaining near-duplicates
    merged: dict[str, str] = {}  # maps canonical → merge_target
    for i, name_a in enumerate(canonical_names):
        if name_a in merged:
            continue
        for name_b in canonical_names[i + 1:]:
            if name_b in merged:
                continue
            sim = SequenceMatcher(
                None, name_a.lower(), name_b.lower()
            ).ratio()
            if sim >= SECTION_MERGE_THRESHOLD:
                # Prefer the name from the reference source
                ref_names = [
                    name_map[raw]
                    for raw in raw_names_by_source.get(reference_source, [])
                ]
                if name_a in ref_names:
                    merged[name_b] = name_a
                elif name_b in ref_names:
                    merged[name_a] = name_b
                else:
                    # Neither from reference — keep the first one
                    merged[name_b] = name_a

    # Apply merge to name_map
    for raw in name_map:
        cn = name_map[raw]
        if cn in merged:
            name_map[raw] = merged[cn]

    # Build reverse map for aliases display: canonical → set of original names
    alias_display: dict[str, list[str]] = {}
    for raw, canonical in name_map.items():
        stripped = _strip_section_name(raw)
        if stripped != canonical:
            alias_display.setdefault(canonical, [])
            if stripped not in alias_display[canonical]:
                alias_display[canonical].append(stripped)

    return SectionNormalizer(name_map, alias_display, raw_names_by_source, reference_source)


def _ordered_sources(
    raw_names_by_source: dict[str, list[str]],
    reference_source: str,
) -> list[str]:
    """Return source names with reference first."""
    sources = list(raw_names_by_source.keys())
    if reference_source in sources:
        sources.remove(reference_source)
        sources.insert(0, reference_source)
    return sources


class SectionNormalizer:
    """Normalizes section names and provides reference-based ordering."""

    def __init__(
        self,
        name_map: dict[str, str],
        alias_display: dict[str, list[str]],
        raw_names_by_source: dict[str, list[str]],
        reference_source: str,
    ):
        self._name_map = name_map
        self._alias_display = alias_display
        self._raw_names_by_source = raw_names_by_source
        self._reference_source = reference_source

    def normalize(self, raw_name: str) -> str:
        """Return the canonical section name for a raw section name."""
        return self._name_map.get(raw_name, _strip_section_name(raw_name))

    def aliases_for(self, canonical_name: str) -> list[str]:
        """Return list of variant names that map to this canonical name."""
        return self._alias_display.get(canonical_name, [])

    def ordered_sections(
        self,
        all_sources: dict[str, list[Question]],
    ) -> list[dict[str, Any]]:
        """Build ordered section list with question codes.

        Order is determined by the reference source's section order,
        then appends sections only found in other sources.
        """
        section_order: list[str] = []
        section_codes: dict[str, list[str]] = {}
        seen_codes: set[str] = set()

        # Process reference source first
        sources = _ordered_sources(
            {s: [] for s in all_sources}, self._reference_source
        )

        for source_name in sources:
            questions = all_sources.get(source_name, [])
            # Sort questions by section_index to preserve survey order
            for q in sorted(questions, key=lambda q: q.section_index):
                canonical = self.normalize(q.section_name or "Other")
                if canonical not in section_codes:
                    section_order.append(canonical)
                    section_codes[canonical] = []
                if q.normalized_code not in seen_codes:
                    section_codes[canonical].append(q.normalized_code)
                    seen_codes.add(q.normalized_code)

        # Build result with alias info
        result = []
        for name in section_order:
            aliases = self.aliases_for(name)
            entry: dict[str, Any] = {"name": name, "codes": section_codes[name]}
            if aliases:
                entry["aliases"] = aliases
            result.append(entry)
        return result

    @property
    def all_aliases(self) -> dict[str, list[str]]:
        """Return {canonical_name: [variant_names]} for all sections with aliases."""
        return {k: v for k, v in self._alias_display.items() if v}
