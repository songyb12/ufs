"""Macro indicator scoring and classification."""


def classify_vix(vix: float | None) -> tuple[str, float]:
    """Classify VIX level and return (label, score).

    Score: -1.0 (extreme fear) to +1.0 (complacency)
    For investment scoring, lower VIX = more favorable for buying.
    """
    if vix is None:
        return "unknown", 0.0

    if vix < 12:
        return "complacent", 0.5  # Too calm, potential reversal
    elif vix < 20:
        return "low", 1.0  # Normal, favorable
    elif vix < 25:
        return "elevated", 0.0  # Caution
    elif vix < 30:
        return "high", -0.5  # Risk-off environment
    else:
        return "extreme", -1.0  # Crisis-level volatility


def classify_yield_curve(spread: float | None) -> tuple[str, float]:
    """Classify yield curve (10Y - 2Y spread).

    Score: -1.0 (deeply inverted) to +1.0 (healthy steepening)
    """
    if spread is None:
        return "unknown", 0.0

    if spread > 1.5:
        return "steep", 1.0  # Healthy expansion
    elif spread > 0.5:
        return "normal", 0.7
    elif spread > 0.0:
        return "flat", 0.0  # Caution
    elif spread > -0.5:
        return "inverted", -0.7  # Recession warning
    else:
        return "deeply_inverted", -1.0  # Strong recession signal


def classify_usd_krw_trend(usd_krw: float | None) -> tuple[str, float]:
    """Classify USD/KRW level for KR market impact.

    Higher USD/KRW = weaker won = generally negative for KR stocks.
    """
    if usd_krw is None:
        return "unknown", 0.0

    if usd_krw < 1200:
        return "strong_won", 0.8
    elif usd_krw < 1300:
        return "normal", 0.3
    elif usd_krw < 1350:
        return "weak_won", -0.3
    elif usd_krw < 1400:
        return "very_weak", -0.7
    else:
        return "crisis", -1.0


def compute_macro_score(macro_data: dict) -> dict:
    """Compute aggregate macro score from indicator data.

    Returns dict with individual scores and aggregate.
    """
    vix_label, vix_score = classify_vix(macro_data.get("vix"))
    yield_label, yield_score = classify_yield_curve(macro_data.get("us_yield_spread"))
    fx_label, fx_score = classify_usd_krw_trend(macro_data.get("usd_krw"))

    # Weighted aggregate (VIX is most actionable for timing)
    weights = {"vix": 0.4, "yield_curve": 0.3, "fx": 0.3}
    aggregate = (
        vix_score * weights["vix"]
        + yield_score * weights["yield_curve"]
        + fx_score * weights["fx"]
    )

    return {
        "vix": {"label": vix_label, "score": vix_score, "value": macro_data.get("vix")},
        "yield_curve": {"label": yield_label, "score": yield_score, "value": macro_data.get("us_yield_spread")},
        "fx": {"label": fx_label, "score": fx_score, "value": macro_data.get("usd_krw")},
        "aggregate_score": round(aggregate, 4),
    }
