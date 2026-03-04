"""Tests for news sentiment scoring."""

from app.indicators.news_scoring import compute_news_score, score_article


class TestScoreArticle:
    """Test individual article scoring."""

    def test_bullish_kr_title(self):
        score = score_article("삼성전자 실적 호실적 매출증가")
        assert score > 0

    def test_bearish_kr_title(self):
        score = score_article("LG전자 적자 매출감소 실적 부진")
        assert score < 0

    def test_bullish_en_title(self):
        score = score_article("Apple stock surges to record high after strong earnings")
        assert score > 0

    def test_bearish_en_title(self):
        score = score_article("Tesla stock plunges after earnings miss, downgrade issued")
        assert score < 0

    def test_neutral_title(self):
        score = score_article("Market closes mixed on Wednesday")
        assert score == 0.0

    def test_mixed_title_balanced(self):
        # Contains both bullish and bearish keywords
        score = score_article("Stock surges despite loss concerns")
        assert -1.0 <= score <= 1.0

    def test_empty_title(self):
        score = score_article("")
        assert score == 0.0

    def test_score_range(self):
        score = score_article("대규모 수주 성장 확대 호실적 급등 상승 돌파")
        assert -1.0 <= score <= 1.0


class TestComputeNewsScore:
    """Test aggregate news score computation."""

    def test_empty_articles_returns_zero(self):
        result = compute_news_score([])
        assert result["news_score"] == 0.0
        assert result["article_count"] == 0

    def test_all_bullish_articles(self):
        articles = [
            {"title": "주가 급등 호실적"},
            {"title": "매출증가 성장 확대"},
            {"title": "Stock surges to record high"},
        ]
        result = compute_news_score(articles)
        assert result["news_score"] > 0
        assert result["bullish_count"] > 0

    def test_all_bearish_articles(self):
        articles = [
            {"title": "주가 급락 실적 부진"},
            {"title": "매출감소 적자 우려"},
            {"title": "Stock plunges after earnings miss"},
        ]
        result = compute_news_score(articles)
        assert result["news_score"] < 0
        assert result["bearish_count"] > 0

    def test_score_bounded(self):
        articles = [{"title": f"급등 상승 호실적 돌파 {i}"} for i in range(10)]
        result = compute_news_score(articles)
        assert -100 <= result["news_score"] <= 100

    def test_article_count(self):
        articles = [{"title": f"News {i}"} for i in range(7)]
        result = compute_news_score(articles)
        assert result["article_count"] == 7

    def test_headlines_capped_at_5(self):
        articles = [{"title": f"News headline {i}"} for i in range(10)]
        result = compute_news_score(articles)
        assert len(result["headlines"]) <= 5
