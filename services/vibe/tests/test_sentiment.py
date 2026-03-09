"""Tests for app.indicators.sentiment — contrarian sentiment scoring."""

import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.indicators.sentiment import compute_sentiment_score


class TestSentimentEmpty:
    def test_empty_data(self):
        result = compute_sentiment_score({})
        assert result["sentiment_score"] == 0
        assert result["components"] == {}


class TestFearGreed:
    def test_extreme_fear(self):
        result = compute_sentiment_score({"fear_greed_index": 10})
        assert result["sentiment_score"] == 40

    def test_fear(self):
        result = compute_sentiment_score({"fear_greed_index": 30})
        assert result["sentiment_score"] == 20

    def test_mild_fear(self):
        result = compute_sentiment_score({"fear_greed_index": 45})
        assert result["sentiment_score"] == 5

    def test_mild_greed(self):
        result = compute_sentiment_score({"fear_greed_index": 55})
        assert result["sentiment_score"] == -5

    def test_greed(self):
        result = compute_sentiment_score({"fear_greed_index": 70})
        assert result["sentiment_score"] == -20

    def test_extreme_greed(self):
        result = compute_sentiment_score({"fear_greed_index": 85})
        assert result["sentiment_score"] == -40

    def test_boundaries(self):
        # 20 is not < 20, so it falls to < 35
        r20 = compute_sentiment_score({"fear_greed_index": 20})
        assert r20["sentiment_score"] == 20

        # 35 is not < 35, so it falls to < 50
        r35 = compute_sentiment_score({"fear_greed_index": 35})
        assert r35["sentiment_score"] == 5

        # 50 is not < 50, so it falls to < 65
        r50 = compute_sentiment_score({"fear_greed_index": 50})
        assert r50["sentiment_score"] == -5

        # 65 is not < 65, so it falls to < 80
        r65 = compute_sentiment_score({"fear_greed_index": 65})
        assert r65["sentiment_score"] == -20

        # 80 is not < 80, so it falls to else
        r80 = compute_sentiment_score({"fear_greed_index": 80})
        assert r80["sentiment_score"] == -40


class TestPutCallRatio:
    def test_high_puts(self):
        result = compute_sentiment_score({"put_call_ratio": 1.4})
        assert result["sentiment_score"] == 25

    def test_moderate_puts(self):
        result = compute_sentiment_score({"put_call_ratio": 1.2})
        assert result["sentiment_score"] == 15

    def test_neutral(self):
        result = compute_sentiment_score({"put_call_ratio": 1.0})
        assert result["sentiment_score"] == 0

    def test_low_puts(self):
        result = compute_sentiment_score({"put_call_ratio": 0.8})
        assert result["sentiment_score"] == -15

    def test_very_low_puts(self):
        result = compute_sentiment_score({"put_call_ratio": 0.5})
        assert result["sentiment_score"] == -25


class TestVixTermStructure:
    def test_severe_backwardation(self):
        result = compute_sentiment_score({
            "vix_term_structure": "backwardation",
            "vix_ratio": 1.2,
        })
        assert result["sentiment_score"] == 20

    def test_mild_backwardation(self):
        result = compute_sentiment_score({
            "vix_term_structure": "backwardation",
            "vix_ratio": 1.05,
        })
        assert result["sentiment_score"] == 10

    def test_deep_contango(self):
        result = compute_sentiment_score({
            "vix_term_structure": "contango",
            "vix_ratio": 0.80,
        })
        assert result["sentiment_score"] == -15

    def test_normal_contango(self):
        result = compute_sentiment_score({
            "vix_term_structure": "contango",
            "vix_ratio": 0.95,
        })
        assert result["sentiment_score"] == 0


class TestCombinedScore:
    def test_combined_bullish(self):
        result = compute_sentiment_score({
            "fear_greed_index": 10,   # +40
            "put_call_ratio": 1.4,    # +25
            "vix_term_structure": "backwardation",
            "vix_ratio": 1.2,         # +20
        })
        assert result["sentiment_score"] == 85

    def test_combined_bearish(self):
        result = compute_sentiment_score({
            "fear_greed_index": 85,    # -40
            "put_call_ratio": 0.5,     # -25
            "vix_term_structure": "contango",
            "vix_ratio": 0.80,         # -15
        })
        assert result["sentiment_score"] == -80

    def test_score_clamped_at_100(self):
        result = compute_sentiment_score({
            "fear_greed_index": 5,
            "put_call_ratio": 1.5,
            "vix_term_structure": "backwardation",
            "vix_ratio": 1.3,
        })
        assert result["sentiment_score"] <= 100

    def test_score_clamped_at_minus_100(self):
        result = compute_sentiment_score({
            "fear_greed_index": 95,
            "put_call_ratio": 0.3,
            "vix_term_structure": "contango",
            "vix_ratio": 0.70,
        })
        assert result["sentiment_score"] >= -100

    def test_components_present(self):
        result = compute_sentiment_score({
            "fear_greed_index": 30,
            "put_call_ratio": 1.1,
        })
        assert "fear_greed" in result["components"]
        assert "put_call_ratio" in result["components"]

    def test_contribution_is_isolated(self):
        """Contribution should be the isolated score, not cumulative."""
        result = compute_sentiment_score({
            "fear_greed_index": 10,   # +40
            "put_call_ratio": 1.4,    # +25
        })
        fg_contrib = result["components"]["fear_greed"]["contribution"]
        pcr_contrib = result["components"]["put_call_ratio"]["contribution"]
        assert fg_contrib == 40
        assert pcr_contrib == 25
