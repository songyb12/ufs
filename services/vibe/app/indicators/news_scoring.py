"""News sentiment scoring using keyword-based analysis.

Rule-based approach: no LLM required.
Scores each article title for bullish/bearish keywords,
then aggregates into a per-symbol news score (-100 to +100).
"""

import re

# Bullish keywords (KR + EN)
BULLISH_KR = [
    "상승", "급등", "최고", "호실적", "흑자", "매출증가", "영업이익",
    "신고가", "돌파", "수혜", "성장", "확대", "긍정", "호재",
    "매수", "목표가 상향", "투자의견 상향", "실적 개선", "턴어라운드",
    "배당", "자사주", "대규모 수주", "반등", "회복",
]
BULLISH_EN = [
    "surge", "rally", "soar", "beat", "upgrade", "outperform",
    "record high", "bullish", "growth", "profit", "revenue beat",
    "buy rating", "target raised", "breakout", "positive",
    "dividend", "buyback", "recovery", "turnaround", "strong",
]

# Bearish keywords (KR + EN)
BEARISH_KR = [
    "하락", "급락", "폭락", "적자", "매출감소", "실적 부진",
    "하향", "리스크", "우려", "손실", "부채", "악재", "매도",
    "목표가 하향", "투자의견 하향", "실적 쇼크", "경고",
    "공매도", "감자", "상장폐지", "파산", "부도",
]
BEARISH_EN = [
    "decline", "drop", "plunge", "fall", "miss", "downgrade",
    "underperform", "bearish", "loss", "revenue miss", "warning",
    "sell rating", "target cut", "risk", "negative", "debt",
    "short", "bankruptcy", "layoff", "weak", "concern",
]


def score_article(title: str) -> float:
    """Score a single article title. Returns -1.0 to +1.0."""
    title_lower = title.lower()
    bullish = 0
    bearish = 0

    # Check Korean keywords
    for kw in BULLISH_KR:
        if kw in title:
            bullish += 1
    for kw in BEARISH_KR:
        if kw in title:
            bearish += 1

    # Check English keywords
    for kw in BULLISH_EN:
        if kw in title_lower:
            bullish += 1
    for kw in BEARISH_EN:
        if kw in title_lower:
            bearish += 1

    total = bullish + bearish
    if total == 0:
        return 0.0

    # Net score normalized to -1 to +1
    return (bullish - bearish) / total


def compute_news_score(articles: list[dict]) -> dict:
    """Compute aggregate news score from a list of articles.

    Returns:
        {
            "news_score": float (-100 to +100),
            "article_count": int,
            "bullish_count": int,
            "bearish_count": int,
            "neutral_count": int,
            "headlines": list of scored headlines,
        }
    """
    if not articles:
        return {
            "news_score": 0.0,
            "article_count": 0,
            "bullish_count": 0,
            "bearish_count": 0,
            "neutral_count": 0,
            "headlines": [],
        }

    scored = []
    bullish = 0
    bearish = 0
    neutral = 0

    for article in articles:
        title = article.get("title", "")
        s = score_article(title)
        scored.append({"title": title, "score": round(s, 2)})

        if s > 0.1:
            bullish += 1
        elif s < -0.1:
            bearish += 1
        else:
            neutral += 1

    # Aggregate: weighted average scaled to -100..+100
    if scored:
        avg = sum(h["score"] for h in scored) / len(scored)
        news_score = round(avg * 100, 2)
    else:
        news_score = 0.0

    # Clamp
    news_score = max(-100, min(100, news_score))

    return {
        "news_score": news_score,
        "article_count": len(articles),
        "bullish_count": bullish,
        "bearish_count": bearish,
        "neutral_count": neutral,
        "headlines": scored[:5],  # Top 5 for display
    }
