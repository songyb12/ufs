"""Tests for vocabulary similarity — feature-based functions (pure unit tests)."""

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.services.vocab_similarity import (
    _jaccard,
    _char_overlap,
    _feature_similarity,
)


# ── Jaccard similarity ──


class TestJaccard:
    def test_identical_sets(self):
        assert _jaccard({"a", "b", "c"}, {"a", "b", "c"}) == 1.0

    def test_disjoint_sets(self):
        assert _jaccard({"a", "b"}, {"c", "d"}) == 0.0

    def test_partial_overlap(self):
        result = _jaccard({"a", "b", "c"}, {"b", "c", "d"})
        assert abs(result - 0.5) < 1e-9  # 2/4

    def test_empty_sets(self):
        assert _jaccard(set(), set()) == 0.0

    def test_one_empty(self):
        assert _jaccard({"a"}, set()) == 0.0

    def test_single_element_match(self):
        assert _jaccard({"a"}, {"a"}) == 1.0


# ── Character overlap ──


class TestCharOverlap:
    def test_identical_words(self):
        assert _char_overlap("食べる", "食べる") == 1.0

    def test_no_overlap(self):
        assert _char_overlap("犬", "猫") == 0.0

    def test_partial_overlap_kanji(self):
        # 食事 vs 食べる: share 食
        result = _char_overlap("食事", "食べる")
        assert 0 < result < 1

    def test_empty_strings(self):
        assert _char_overlap("", "") == 0.0


# ── Feature similarity ──


class TestFeatureSimilarity:
    def _make_word(self, **overrides):
        base = {
            "word": "食べる",
            "reading": "たべる",
            "meaning": "to eat",
            "jlpt_level": "N5",
            "part_of_speech": "verb",
            "tags": "[]",
        }
        base.update(overrides)
        return base

    def test_identical_words_empty_tags(self):
        """Same word with empty tags → 0.75 (tags jaccard(empty,empty)=0)."""
        a = self._make_word()
        result = _feature_similarity(a, a)
        assert result == 0.75  # 0.3 jlpt + 0.25 pos + 0.0 tags + 0.2 chars

    def test_identical_features_score(self):
        """Same JLPT, POS, empty tags, same word → 0.75."""
        a = self._make_word()
        b = self._make_word()
        result = _feature_similarity(a, b)
        assert result == 0.75  # 0.3 + 0.25 + 0 + 0.2

    def test_with_matching_tags(self):
        """Matching tags add 0.25."""
        a = self._make_word(tags='["food", "daily"]')
        b = self._make_word(tags='["food", "daily"]')
        result = _feature_similarity(a, b)
        assert result == 1.0  # 0.3 + 0.25 + 0.25 + 0.2

    def test_completely_different(self):
        """Different JLPT, POS, no tag overlap, no char overlap → 0."""
        a = self._make_word(word="犬", jlpt_level="N5", part_of_speech="noun", tags='["animal"]')
        b = self._make_word(word="走る", jlpt_level="N3", part_of_speech="verb", tags='["action"]')
        result = _feature_similarity(a, b)
        assert result == 0.0

    def test_partial_tag_overlap(self):
        """Partial tag overlap gives proportional score."""
        a = self._make_word(tags='["food", "daily"]')
        b = self._make_word(tags='["food", "cooking"]')
        result = _feature_similarity(a, b)
        # jlpt(0.3) + pos(0.25) + tags(0.25 * 1/3) + chars(0.2) = 0.3+0.25+0.0833+0.2 = 0.8333
        assert 0.83 < result < 0.84

    def test_tags_as_list(self):
        """Tags can be passed as Python list (not just JSON string)."""
        a = self._make_word(tags=["food", "daily"])
        b = self._make_word(tags=["food", "daily"])
        result = _feature_similarity(a, b)
        assert result == 1.0

    def test_jlpt_only_match(self):
        """Only JLPT match → 0.3."""
        a = self._make_word(word="犬", part_of_speech="noun")
        b = self._make_word(word="猫", part_of_speech="adjective")
        result = _feature_similarity(a, b)
        assert result == 0.3

    def test_missing_fields_dont_crash(self):
        """Missing fields return partial score without errors.
        None == None is True, so jlpt(0.3) + pos(0.25) + chars(0.2) = 0.75."""
        a = {"word": "食べる"}
        b = {"word": "食べる"}
        result = _feature_similarity(a, b)
        assert result == 0.75  # None==None matches for jlpt & pos
