"""Signal scoring functions for Stage 6."""

from app.config import Settings
from app.models.enums import Market, SignalType


def compute_technical_score(indicators: dict) -> float:
    """Score technical indicators. Range: -100 to +100.

    Positive = bullish, Negative = bearish.
    """
    score = 0.0
    count = 0

    # RSI scoring (-30 to +30)
    rsi = indicators.get("rsi_14")
    if rsi is not None:
        if rsi < 30:
            score += 30  # Oversold = strong buy signal
        elif rsi < 40:
            score += 15
        elif rsi < 50:
            score += 5
        elif rsi < 60:
            score -= 5
        elif rsi < 70:
            score -= 15
        else:
            score -= 30  # Overbought = strong sell signal
        count += 1

    # MACD scoring (-20 to +20)
    macd_hist = indicators.get("macd_histogram")
    if macd_hist is not None:
        if macd_hist > 0:
            score += min(20, macd_hist * 10)
        else:
            score += max(-20, macd_hist * 10)
        count += 1

    # Bollinger Band position (-20 to +20)
    close = indicators.get("close")
    bb_upper = indicators.get("bollinger_upper")
    bb_lower = indicators.get("bollinger_lower")
    bb_middle = indicators.get("bollinger_middle")
    if all(v is not None for v in [close, bb_upper, bb_lower, bb_middle]):
        bb_range = bb_upper - bb_lower
        if bb_range > 0:
            bb_position = (close - bb_lower) / bb_range  # 0 to 1
            score += (0.5 - bb_position) * 40  # -20 to +20
            count += 1

    # Disparity scoring (-15 to +15)
    disparity = indicators.get("disparity_20")
    if disparity is not None:
        deviation = disparity - 100  # 0 = at MA20
        score -= deviation * 3  # Overextended = negative
        score = max(min(score, score), score)  # Keep total bounded
        count += 1

    # Volume ratio scoring (-15 to +15)
    vol_ratio = indicators.get("volume_ratio")
    if vol_ratio is not None:
        if vol_ratio > 2.0:
            score += 10  # High volume = confirms trend
        elif vol_ratio > 1.5:
            score += 5
        elif vol_ratio < 0.5:
            score -= 5  # Low volume = weak move
        count += 1

    return round(max(-100, min(100, score)), 2)


def compute_fund_flow_score(fund_flow: dict) -> float:
    """Score fund flow data (KR only). Range: -100 to +100."""
    score = 0.0

    foreign = fund_flow.get("foreign_net_buy")
    institution = fund_flow.get("institution_net_buy")

    # Foreign net buying is strongest signal
    if foreign is not None:
        if foreign > 0:
            score += min(50, foreign / 1e9 * 10)  # Scale by billions
        else:
            score += max(-50, foreign / 1e9 * 10)

    # Institutional buying
    if institution is not None:
        if institution > 0:
            score += min(30, institution / 1e9 * 5)
        else:
            score += max(-30, institution / 1e9 * 5)

    return round(max(-100, min(100, score)), 2)


def compute_aggregate_signal(
    technical_score: float,
    macro_score: float,
    fund_flow_score: float | None,
    market: str,
    config: Settings,
) -> tuple[SignalType, float]:
    """Compute final weighted signal.

    Returns (signal_type, raw_score).
    """
    if market == Market.KR:
        weights = {
            "technical": config.WEIGHT_TECHNICAL,
            "macro": config.WEIGHT_MACRO,
            "fund_flow": config.WEIGHT_FUND_FLOW,
            "fundamental": config.WEIGHT_FUNDAMENTAL,
        }
        fund_flow_val = fund_flow_score or 0.0
    else:
        # US: redistribute fund_flow weight to technical and macro
        tech_w = config.WEIGHT_TECHNICAL + config.WEIGHT_FUND_FLOW * 0.6
        macro_w = config.WEIGHT_MACRO + config.WEIGHT_FUND_FLOW * 0.4
        weights = {
            "technical": tech_w,
            "macro": macro_w,
            "fund_flow": 0.0,
            "fundamental": config.WEIGHT_FUNDAMENTAL,
        }
        fund_flow_val = 0.0

    # Weighted score
    raw_score = (
        technical_score * weights["technical"]
        + macro_score * weights["macro"]
        + fund_flow_val * weights["fund_flow"]
        # fundamental score placeholder (0 for now)
    )

    raw_score = round(raw_score, 2)

    # Signal thresholds
    if raw_score > 15:
        signal = SignalType.BUY
    elif raw_score < -15:
        signal = SignalType.SELL
    else:
        signal = SignalType.HOLD

    return signal, raw_score
