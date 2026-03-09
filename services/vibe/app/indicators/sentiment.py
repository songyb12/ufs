"""Sentiment indicator scoring - contrarian approach."""

import logging

logger = logging.getLogger("vibe.indicators.sentiment")


def compute_sentiment_score(data: dict) -> dict:
    """Compute sentiment score using contrarian logic.

    Extreme fear -> bullish (buy opportunity)
    Extreme greed -> bearish (sell signal)

    Returns dict with: sentiment_score, components
    Score range: [-100, +100]
    """
    score = 0.0
    components = {}

    # Fear & Greed Index (0-100, contrarian)
    fg = data.get("fear_greed_index")
    if fg is not None:
        fg_score = 0
        if fg < 20:
            fg_score = 40  # Extreme fear = strong buy signal
        elif fg < 35:
            fg_score = 20
        elif fg < 50:
            fg_score = 5
        elif fg < 65:
            fg_score = -5
        elif fg < 80:
            fg_score = -20
        else:
            fg_score = -40  # Extreme greed = strong sell signal
        score += fg_score
        components["fear_greed"] = {"value": fg, "contribution": fg_score}

    # Put/Call Ratio (contrarian)
    pcr = data.get("put_call_ratio")
    if pcr is not None:
        pcr_score = 0
        if pcr > 1.3:
            pcr_score = 25  # High puts = fear = bullish
        elif pcr > 1.1:
            pcr_score = 15
        elif pcr > 0.9:
            pcr_score = 0  # Neutral
        elif pcr > 0.7:
            pcr_score = -15
        else:
            pcr_score = -25  # Low puts = complacency = bearish
        score += pcr_score
        components["put_call_ratio"] = {"value": pcr, "contribution": pcr_score}

    # VIX Term Structure
    vix_structure = data.get("vix_term_structure")
    if vix_structure:
        vix_score = 0
        vix_ratio = data.get("vix_ratio", 1.0)
        if vix_structure == "backwardation":
            if vix_ratio > 1.1:
                vix_score = 20  # Severe backwardation = extreme fear = buy
            else:
                vix_score = 10
        else:  # contango
            if vix_ratio < 0.85:
                vix_score = -15  # Deep contango = complacency
            else:
                vix_score = 0  # Normal
        score += vix_score
        components["vix_term_structure"] = {
            "structure": vix_structure,
            "ratio": vix_ratio,
            "contribution": vix_score,
        }

    score = max(-100, min(100, score))

    return {
        "sentiment_score": round(score, 2),
        "components": components,
    }
