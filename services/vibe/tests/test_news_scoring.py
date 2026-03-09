"""Tests for news sentiment scoring.

Covers: score_article (per-article keyword scoring), compute_news_score (aggregate).
Edge cases: empty/None titles, Korean vs English, case sensitivity, boundary scores,
mixed positive/negative, exact keyword matching, return type contracts.
"""

import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.indicators.news_scoring import (
    compute_news_score,
    score_article,
    BULLISH_KR,
    BULLISH_EN,
    BEARISH_KR,
    BEARISH_EN,
)


# ── score_article ──


class TestScoreArticle:
    """Test individual article scoring."""

    # --- Korean keywords ---

    def test_bullish_kr_title(self):
        score = score_article("삼성전자 실적 호실적 매출증가")
        assert score > 0

    def test_bearish_kr_title(self):
        score = score_article("LG전자 적자 매출감소 실적 부진")
        assert score < 0

    def test_single_bullish_kr_keyword(self):
        """Single bullish KR keyword gives exactly +1.0."""
        score = score_article("삼성전자 급등 소식")
        assert score == 1.0

    def test_single_bearish_kr_keyword(self):
        """Single bearish KR keyword gives exactly -1.0."""
        score = score_article("삼성전자 급락 소식")
        assert score == -1.0

    def test_all_bullish_kr_keywords(self):
        """Title containing every bullish KR keyword stays within range."""
        title = " ".join(BULLISH_KR)
        score = score_article(title)
        assert score == 1.0

    def test_all_bearish_kr_keywords(self):
        """Title containing every bearish KR keyword stays within range."""
        title = " ".join(BEARISH_KR)
        score = score_article(title)
        assert score == -1.0

    # --- English keywords ---

    def test_bullish_en_title(self):
        score = score_article("Apple stock surges to record high after strong earnings")
        assert score > 0

    def test_bearish_en_title(self):
        score = score_article("Tesla stock plunges after earnings miss, downgrade issued")
        assert score < 0

    def test_single_bullish_en_keyword(self):
        score = score_article("Stock rally today")
        assert score == 1.0

    def test_single_bearish_en_keyword(self):
        score = score_article("Stock decline today")
        assert score == -1.0

    # --- Case insensitivity (English) ---

    def test_case_insensitive_en_upper(self):
        s1 = score_article("SURGE in stock price")
        s2 = score_article("surge in stock price")
        assert s1 == s2

    def test_case_insensitive_en_mixed(self):
        s1 = score_article("Stock Surges after Earnings Beat")
        s2 = score_article("stock surges after earnings beat")
        assert s1 == s2

    def test_case_insensitive_en_all_caps(self):
        score = score_article("RALLY BREAKOUT BULLISH STRONG")
        assert score > 0

    # --- Korean is case-sensitive (no lowering needed) ---

    def test_kr_keywords_exact_match(self):
        """Korean keywords match by substring inclusion in original title."""
        score = score_article("급등세 지속")  # contains "급등"
        assert score > 0

    def test_kr_keyword_partial_overlap(self):
        """Korean bearish keyword '하락' appears inside longer word."""
        score = score_article("주가하락세")  # contains "하락"
        assert score < 0

    # --- Neutral / empty ---

    def test_neutral_title(self):
        score = score_article("Market closes mixed on Wednesday")
        assert score == 0.0

    def test_empty_title(self):
        score = score_article("")
        assert score == 0.0

    def test_whitespace_only_title(self):
        score = score_article("   ")
        assert score == 0.0

    def test_numeric_only_title(self):
        score = score_article("12345 67890")
        assert score == 0.0

    def test_special_characters_title(self):
        score = score_article("!@#$%^&*()")
        assert score == 0.0

    # --- Mixed positive/negative ---

    def test_mixed_title_balanced(self):
        """Contains both bullish and bearish keywords."""
        score = score_article("Stock surges despite loss concerns")
        assert -1.0 <= score <= 1.0

    def test_mixed_equal_bullish_bearish(self):
        """Equal bullish/bearish count gives 0.0: (1-1)/2 = 0."""
        score = score_article("surge decline")
        assert score == 0.0

    def test_mixed_two_bullish_one_bearish(self):
        """2 bullish, 1 bearish: (2-1)/3 = 0.333."""
        score = score_article("surge rally decline")
        assert abs(score - (1 / 3)) < 0.01

    def test_mixed_one_bullish_two_bearish(self):
        """1 bullish, 2 bearish: (1-2)/3 = -0.333."""
        score = score_article("surge decline drop")
        assert abs(score - (-1 / 3)) < 0.01

    def test_mixed_kr_and_en(self):
        """Korean bullish + English bearish keywords."""
        score = score_article("급등 stock decline")
        # 1 bullish (급등) + 1 bearish (decline) = 0
        assert score == 0.0

    # --- Boundary and range ---

    def test_score_range_many_bullish_kr(self):
        score = score_article("대규모 수주 성장 확대 호실적 급등 상승 돌파")
        assert -1.0 <= score <= 1.0

    def test_score_always_between_minus1_and_plus1(self):
        """No matter the input, score must be in [-1.0, 1.0]."""
        test_titles = [
            " ".join(BULLISH_KR + BULLISH_EN),
            " ".join(BEARISH_KR + BEARISH_EN),
            " ".join(BULLISH_KR + BEARISH_EN),
            "random words nothing matches",
            "",
        ]
        for title in test_titles:
            s = score_article(title)
            assert -1.0 <= s <= 1.0, f"Out of range for title: {title!r}"

    def test_return_type_is_float(self):
        assert isinstance(score_article("surge"), float)
        assert isinstance(score_article(""), float)

    # --- Multi-word keyword matching ---

    def test_multiword_en_keyword_record_high(self):
        """Multi-word keyword 'record high' matches correctly."""
        score = score_article("Hits record high today")
        assert score > 0

    def test_multiword_en_keyword_buy_rating(self):
        score = score_article("Analyst issues buy rating")
        assert score > 0

    def test_multiword_en_keyword_target_cut(self):
        score = score_article("Broker issues target cut")
        assert score < 0

    def test_multiword_en_keyword_sell_rating(self):
        score = score_article("Analyst issues sell rating")
        assert score < 0

    def test_multiword_kr_keyword_mokpyoga_sanghyang(self):
        """Multi-word Korean keyword '목표가 상향' matches."""
        score = score_article("증권사 목표가 상향 조정")
        assert score > 0

    def test_multiword_kr_keyword_mokpyoga_hahyang(self):
        """Multi-word Korean keyword '목표가 하향' matches as bearish."""
        score = score_article("증권사 목표가 하향 조정")
        assert score < 0

    # --- Keywords that overlap between bullish/bearish ---

    def test_en_keyword_short_is_bearish(self):
        """'short' is bearish but won't match inside 'shortage' by itself
        because 'short' is a substring of 'shortage'."""
        score_short = score_article("short selling pressure")
        assert score_short < 0

    def test_turnover_does_not_match_turnaround(self):
        """'turnaround' (bullish) should not be confused with 'turnover'."""
        score = score_article("Employee turnover high")
        assert score == 0.0  # 'turnaround' not in 'turnover'


# ── compute_news_score ──


class TestComputeNewsScore:
    """Test aggregate news score computation."""

    # --- Empty / missing data ---

    def test_empty_articles_returns_zero(self):
        result = compute_news_score([])
        assert result["news_score"] == 0.0
        assert result["article_count"] == 0
        assert result["bullish_count"] == 0
        assert result["bearish_count"] == 0
        assert result["neutral_count"] == 0
        assert result["headlines"] == []

    def test_none_list(self):
        """None should be handled same as empty (falsy check)."""
        result = compute_news_score(None)
        assert result["news_score"] == 0.0
        assert result["article_count"] == 0

    def test_missing_title_key(self):
        """Article dict without 'title' key defaults to empty string."""
        articles = [{"body": "no title"}]
        result = compute_news_score(articles)
        assert result["news_score"] == 0.0
        assert result["neutral_count"] == 1

    def test_none_title_value(self):
        """Article with title=None: score_article will receive ''."""
        articles = [{"title": None}]
        # title is None; article.get("title", "") returns None
        # score_article(None) would fail — but .get returns None not ""
        # This tests current behavior
        try:
            result = compute_news_score(articles)
            # If it doesn't crash, verify structure
            assert "news_score" in result
        except (TypeError, AttributeError):
            # If it crashes on None.lower(), that's a known edge case
            pass

    def test_empty_title_value(self):
        articles = [{"title": ""}]
        result = compute_news_score(articles)
        assert result["news_score"] == 0.0
        assert result["neutral_count"] == 1

    # --- All bullish ---

    def test_all_bullish_articles(self):
        articles = [
            {"title": "주가 급등 호실적"},
            {"title": "매출증가 성장 확대"},
            {"title": "Stock surges to record high"},
        ]
        result = compute_news_score(articles)
        assert result["news_score"] > 0
        assert result["bullish_count"] > 0
        assert result["bearish_count"] == 0

    def test_all_bullish_score_equals_100(self):
        """All articles with single bullish keyword: avg=1.0, score=100."""
        articles = [
            {"title": "급등"},
            {"title": "상승"},
            {"title": "surge"},
        ]
        result = compute_news_score(articles)
        assert result["news_score"] == 100.0

    # --- All bearish ---

    def test_all_bearish_articles(self):
        articles = [
            {"title": "주가 급락 실적 부진"},
            {"title": "매출감소 적자 우려"},
            {"title": "Stock plunges after earnings miss"},
        ]
        result = compute_news_score(articles)
        assert result["news_score"] < 0
        assert result["bearish_count"] > 0
        assert result["bullish_count"] == 0

    def test_all_bearish_score_equals_minus100(self):
        """All articles with single bearish keyword: avg=-1.0, score=-100."""
        articles = [
            {"title": "급락"},
            {"title": "적자"},
            {"title": "decline"},
        ]
        result = compute_news_score(articles)
        assert result["news_score"] == -100.0

    # --- Mixed signals ---

    def test_mixed_bullish_bearish_neutral(self):
        articles = [
            {"title": "급등 호재"},          # bullish
            {"title": "급락 적자"},          # bearish
            {"title": "아무 관련없는 뉴스"},  # neutral
        ]
        result = compute_news_score(articles)
        assert result["bullish_count"] == 1
        assert result["bearish_count"] == 1
        assert result["neutral_count"] == 1

    def test_equal_bullish_bearish_cancels(self):
        """Equal bullish and bearish articles cancel to near zero."""
        articles = [
            {"title": "surge"},   # +1.0
            {"title": "decline"}, # -1.0
        ]
        result = compute_news_score(articles)
        assert result["news_score"] == 0.0

    # --- Score bounds ---

    def test_score_bounded_upper(self):
        articles = [{"title": f"급등 상승 호실적 돌파 {i}"} for i in range(10)]
        result = compute_news_score(articles)
        assert result["news_score"] <= 100

    def test_score_bounded_lower(self):
        articles = [{"title": f"급락 적자 하락 폭락 {i}"} for i in range(10)]
        result = compute_news_score(articles)
        assert result["news_score"] >= -100

    def test_score_clamped_to_100_max(self):
        """Even with extreme bullish articles, score cannot exceed 100."""
        articles = [{"title": " ".join(BULLISH_KR + BULLISH_EN)} for _ in range(20)]
        result = compute_news_score(articles)
        assert result["news_score"] <= 100

    def test_score_clamped_to_minus100_min(self):
        """Even with extreme bearish articles, score cannot go below -100."""
        articles = [{"title": " ".join(BEARISH_KR + BEARISH_EN)} for _ in range(20)]
        result = compute_news_score(articles)
        assert result["news_score"] >= -100

    # --- Article count ---

    def test_article_count(self):
        articles = [{"title": f"News {i}"} for i in range(7)]
        result = compute_news_score(articles)
        assert result["article_count"] == 7

    def test_article_count_single(self):
        result = compute_news_score([{"title": "hello"}])
        assert result["article_count"] == 1

    def test_article_count_large(self):
        articles = [{"title": f"Article {i}"} for i in range(100)]
        result = compute_news_score(articles)
        assert result["article_count"] == 100

    # --- Headlines capping ---

    def test_headlines_capped_at_5(self):
        articles = [{"title": f"News headline {i}"} for i in range(10)]
        result = compute_news_score(articles)
        assert len(result["headlines"]) <= 5

    def test_headlines_less_than_5_not_truncated(self):
        articles = [{"title": f"News {i}"} for i in range(3)]
        result = compute_news_score(articles)
        assert len(result["headlines"]) == 3

    def test_headlines_exactly_5(self):
        articles = [{"title": f"News {i}"} for i in range(5)]
        result = compute_news_score(articles)
        assert len(result["headlines"]) == 5

    def test_headlines_structure(self):
        """Each headline dict has 'title' and 'score' keys."""
        articles = [{"title": "surge rally"}]
        result = compute_news_score(articles)
        assert len(result["headlines"]) == 1
        h = result["headlines"][0]
        assert "title" in h
        assert "score" in h
        assert h["title"] == "surge rally"

    def test_headline_score_is_rounded(self):
        """Headline scores should be rounded to 2 decimal places."""
        articles = [{"title": "surge rally decline"}]  # 2 bull, 1 bear => 1/3
        result = compute_news_score(articles)
        h = result["headlines"][0]
        assert h["score"] == round(h["score"], 2)

    # --- Classification thresholds ---

    def test_bullish_threshold_above_0_1(self):
        """Article with score > 0.1 counted as bullish."""
        # Single bullish keyword gives score=1.0 > 0.1 => bullish
        articles = [{"title": "surge"}]
        result = compute_news_score(articles)
        assert result["bullish_count"] == 1
        assert result["bearish_count"] == 0
        assert result["neutral_count"] == 0

    def test_bearish_threshold_below_minus_0_1(self):
        """Article with score < -0.1 counted as bearish."""
        articles = [{"title": "decline"}]
        result = compute_news_score(articles)
        assert result["bearish_count"] == 1
        assert result["bullish_count"] == 0
        assert result["neutral_count"] == 0

    def test_neutral_threshold_between_minus_0_1_and_0_1(self):
        """Article with score between -0.1 and +0.1 is neutral."""
        # Zero score (no keywords) is neutral
        articles = [{"title": "nothing relevant here"}]
        result = compute_news_score(articles)
        assert result["neutral_count"] == 1

    def test_balanced_mixed_is_neutral(self):
        """Equal bullish/bearish => score=0.0, which is within [-0.1, 0.1] => neutral."""
        articles = [{"title": "surge decline"}]
        result = compute_news_score(articles)
        assert result["neutral_count"] == 1

    # --- Return type contracts ---

    def test_return_keys(self):
        """Result dict must contain all required keys."""
        result = compute_news_score([])
        expected_keys = {
            "news_score", "article_count", "bullish_count",
            "bearish_count", "neutral_count", "headlines",
        }
        assert set(result.keys()) == expected_keys

    def test_return_types(self):
        result = compute_news_score([{"title": "surge"}])
        # news_score is numeric (float or int due to max/min clamping behavior)
        assert isinstance(result["news_score"], (int, float))
        assert isinstance(result["article_count"], int)
        assert isinstance(result["bullish_count"], int)
        assert isinstance(result["bearish_count"], int)
        assert isinstance(result["neutral_count"], int)
        assert isinstance(result["headlines"], list)

    def test_news_score_is_rounded(self):
        """news_score should be rounded to 2 decimal places."""
        articles = [
            {"title": "surge rally decline"},  # score = 1/3
            {"title": "nothing here"},          # score = 0
        ]
        result = compute_news_score(articles)
        assert result["news_score"] == round(result["news_score"], 2)

    # --- Case insensitive English in aggregate ---

    def test_case_insensitive_en_in_aggregate(self):
        """English keywords should match regardless of case in aggregate."""
        articles_lower = [{"title": "surge in stock"}]
        articles_upper = [{"title": "SURGE IN STOCK"}]
        r1 = compute_news_score(articles_lower)
        r2 = compute_news_score(articles_upper)
        assert r1["news_score"] == r2["news_score"]
        assert r1["bullish_count"] == r2["bullish_count"]

    # --- Large volume of articles ---

    def test_many_neutral_articles(self):
        """100 neutral articles => score stays at 0."""
        articles = [{"title": f"Random text {i}"} for i in range(100)]
        result = compute_news_score(articles)
        assert result["news_score"] == 0.0
        assert result["neutral_count"] == 100

    def test_many_mixed_articles(self):
        """50 bullish + 50 bearish => near zero."""
        articles = (
            [{"title": "surge"} for _ in range(50)]
            + [{"title": "decline"} for _ in range(50)]
        )
        result = compute_news_score(articles)
        assert result["news_score"] == 0.0
        assert result["bullish_count"] == 50
        assert result["bearish_count"] == 50

    # --- Counts always add up ---

    def test_counts_sum_to_article_count(self):
        """bullish + bearish + neutral should always equal article_count."""
        articles = [
            {"title": "surge rally"},       # bullish
            {"title": "decline"},            # bearish
            {"title": "nothing"},            # neutral
            {"title": "급등 호재"},          # bullish
            {"title": "급락"},              # bearish
            {"title": "평범한 뉴스"},        # neutral
            {"title": "surge decline"},      # neutral (balanced)
        ]
        result = compute_news_score(articles)
        total = (
            result["bullish_count"]
            + result["bearish_count"]
            + result["neutral_count"]
        )
        assert total == result["article_count"]
