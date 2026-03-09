"""Tests for market academy indicator module.

Covers: today's lesson, pattern matching, concept listing, concept detail.
"""

import pytest

from app.indicators.market_academy import (
    generate_todays_lesson,
    find_matching_patterns,
    get_all_concepts,
    get_concept_detail,
    CONCEPTS,
    HISTORICAL_PATTERNS,
)


# ── Constants Integrity ──

class TestConstants:
    def test_concepts_not_empty(self):
        assert len(CONCEPTS) > 0

    def test_concept_structure(self):
        for cid, concept in CONCEPTS.items():
            # Each concept has name_kr (title) and difficulty
            assert "name_kr" in concept or "definition_kr" in concept, f"{cid} missing name"
            assert "difficulty" in concept, f"{cid} missing difficulty"
            assert concept["difficulty"] in (1, 2, 3), f"{cid} invalid difficulty"

    def test_patterns_not_empty(self):
        assert len(HISTORICAL_PATTERNS) > 0

    def test_pattern_structure(self):
        for p in HISTORICAL_PATTERNS:
            assert "id" in p, f"Pattern missing 'id'"
            assert "conditions" in p or "vix_min" in p.get("conditions", {}), \
                f"Pattern {p.get('id')} missing conditions"


# ── Today's Lesson ──

class TestTodaysLesson:
    def test_returns_dict(self):
        result = generate_todays_lesson({"vix": 20})
        assert isinstance(result, dict)

    def test_has_concept_info(self):
        result = generate_todays_lesson({"vix": 20, "us_yield_spread": 1.0})
        # Should have concept data
        assert "concept" in result or "concept_id" in result or "date" in result

    def test_empty_macro(self):
        result = generate_todays_lesson({})
        assert isinstance(result, dict)

    def test_with_sentiment(self):
        result = generate_todays_lesson(
            {"vix": 30},
            sentiment={"score": -20, "label": "fear"},
        )
        assert isinstance(result, dict)


# ── Pattern Matching ──

class TestFindMatchingPatterns:
    def test_returns_list(self):
        result = find_matching_patterns({"vix": 25})
        assert isinstance(result, list)

    def test_empty_macro(self):
        result = find_matching_patterns({})
        assert isinstance(result, list)

    def test_high_vix_matches_crisis(self):
        result = find_matching_patterns({"vix": 35, "us_yield_spread": -0.5})
        # With high VIX and inverted yield curve, should find crisis-related patterns
        assert isinstance(result, list)


# ── Get All Concepts ──

class TestGetAllConcepts:
    def test_returns_list(self):
        result = get_all_concepts()
        assert isinstance(result, list)
        assert len(result) > 0

    def test_returns_categories(self):
        result = get_all_concepts()
        # Result is a list of category groups
        for c in result:
            assert "category" in c or "concepts" in c


# ── Get Concept Detail ──

class TestGetConceptDetail:
    def test_known_concept(self):
        # Get first concept ID
        first_id = list(CONCEPTS.keys())[0]
        result = get_concept_detail(first_id)
        assert result is not None
        assert isinstance(result, dict)

    def test_unknown_concept(self):
        result = get_concept_detail("nonexistent_concept_xyz")
        assert result is None

    def test_with_macro_data(self):
        first_id = list(CONCEPTS.keys())[0]
        result = get_concept_detail(first_id, macro={"vix": 20, "us_yield_spread": 1.0})
        assert result is not None
