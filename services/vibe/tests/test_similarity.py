"""Tests for stock similarity feature-vector engine."""

import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.indicators.similarity import (
    _cosine_similarity,
    _normalize,
    _build_feature_vector,
)


class TestCosineSimilarity:
    def test_identical_vectors(self):
        v = [1.0, 2.0, 3.0]
        assert abs(_cosine_similarity(v, v) - 1.0) < 1e-6

    def test_orthogonal_vectors(self):
        a = [1.0, 0.0, 0.0]
        b = [0.0, 1.0, 0.0]
        assert abs(_cosine_similarity(a, b)) < 1e-6

    def test_opposite_vectors(self):
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        assert abs(_cosine_similarity(a, b) - (-1.0)) < 1e-6

    def test_zero_vector(self):
        assert _cosine_similarity([0, 0], [1, 1]) == 0.0

    def test_both_zero(self):
        assert _cosine_similarity([0, 0], [0, 0]) == 0.0

    def test_similar_vectors(self):
        a = [1.0, 2.0, 3.0]
        b = [1.1, 2.1, 2.9]
        sim = _cosine_similarity(a, b)
        assert sim > 0.99  # Very similar


class TestNormalize:
    def test_min_value(self):
        assert _normalize(0, 0, 100) == 0.0

    def test_max_value(self):
        assert _normalize(100, 0, 100) == 1.0

    def test_mid_value(self):
        assert abs(_normalize(50, 0, 100) - 0.5) < 1e-6

    def test_none_returns_neutral(self):
        assert _normalize(None, 0, 100) == 0.5

    def test_equal_min_max(self):
        assert _normalize(5, 5, 5) == 0.5

    def test_clamps_below(self):
        assert _normalize(-10, 0, 100) == 0.0

    def test_clamps_above(self):
        assert _normalize(150, 0, 100) == 1.0


class TestBuildFeatureVector:
    def test_basic_vector(self):
        signal = {
            "rsi_value": 50,
            "disparity_value": 100,
            "technical_score": 0,
            "macro_score": 0,
            "raw_score": 0,
            "confidence": 0.5,
        }
        vec = _build_feature_vector(signal, "반도체")
        # 6 features + len(SECTORS) sector one-hot
        assert len(vec) > 6
        # First 6 should be normalized values
        assert all(0 <= v <= 1 for v in vec[:6])

    def test_sector_one_hot(self):
        signal = {
            "rsi_value": 50,
            "disparity_value": 100,
            "technical_score": 0,
            "macro_score": 0,
            "raw_score": 0,
            "confidence": 0.5,
        }
        vec = _build_feature_vector(signal, "반도체")
        sector_part = vec[6:]
        # Exactly one sector should be non-zero (weighted by 0.3)
        non_zero = [v for v in sector_part if v > 0]
        assert len(non_zero) == 1
        assert abs(non_zero[0] - 0.3) < 1e-6

    def test_unknown_sector_defaults_to_etc(self):
        signal = {
            "rsi_value": 50,
            "disparity_value": 100,
            "technical_score": 0,
            "macro_score": 0,
            "raw_score": 0,
            "confidence": 0.5,
        }
        vec = _build_feature_vector(signal, "unknown_sector")
        sector_part = vec[6:]
        # Last element should be 0.3 (기타)
        assert abs(sector_part[-1] - 0.3) < 1e-6

    def test_none_values_handled(self):
        signal = {
            "rsi_value": None,
            "disparity_value": None,
            "technical_score": None,
            "macro_score": None,
            "raw_score": None,
            "confidence": None,
        }
        vec = _build_feature_vector(signal, "IT")
        # Should not crash, first 6 values should be 0.5 (neutral default)
        assert all(abs(v - 0.5) < 1e-6 for v in vec[:6])
