"""Macro indicator scoring and classification.

7-factor model:
  VIX (20%), Yield Curve (15%), DXY (15%), WTI Oil (15%),
  Copper (15%), USD/KRW (10%), Gold (10%)
"""


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
    """Classify yield curve spread.

    NOTE: The actual data source uses 10Y minus 13-week T-bill (^TNX - ^IRX),
    not the traditional 10Y-2Y spread. The 10Y-3M spread is typically wider
    than 10Y-2Y by ~0.3-0.5pp, so thresholds are adjusted accordingly.

    Score: -1.0 (deeply inverted) to +1.0 (healthy steepening)
    """
    if spread is None:
        return "unknown", 0.0

    # Thresholds adjusted for 10Y-3M spread (wider than 10Y-2Y by ~0.3-0.5pp)
    if spread > 2.0:
        return "steep", 1.0  # Healthy expansion
    elif spread > 1.0:
        return "normal", 0.7
    elif spread > 0.3:
        return "flat", 0.0  # Caution
    elif spread > -0.3:
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


def classify_oil(wti: float | None) -> tuple[str, float]:
    """Classify WTI crude oil price impact on economy.

    Moderate oil = healthy economy. Extremes (too high or too low) are negative.
    U-shaped scoring: sweet spot around $55-75.
    """
    if wti is None:
        return "unknown", 0.0

    if wti < 40:
        return "deflationary", -0.5  # Demand destruction / economic weakness
    elif wti < 55:
        return "low", 0.3  # Manageable
    elif wti < 75:
        return "moderate", 0.8  # Sweet spot — growth without inflation pressure
    elif wti < 90:
        return "elevated", 0.0  # Mild inflationary headwind
    elif wti < 110:
        return "high", -0.5  # Inflationary pressure on margins
    else:
        return "extreme", -1.0  # Stagflation risk


def classify_gold(gold: float | None) -> tuple[str, float]:
    """Classify gold price as safe-haven demand indicator.

    Rising gold = risk-off sentiment = negative for equities.
    Thresholds calibrated for 2024-2026 regime.
    """
    if gold is None:
        return "unknown", 0.0

    if gold < 1900:
        return "low_demand", 0.6  # Risk-on, equities preferred
    elif gold < 2200:
        return "normal", 0.2  # Moderate allocation
    elif gold < 2500:
        return "elevated", -0.2  # Increasing uncertainty
    elif gold < 2800:
        return "high_demand", -0.5  # Significant risk-off
    else:
        return "extreme", -0.8  # Flight to safety


def classify_dxy(dxy: float | None) -> tuple[str, float]:
    """Classify US Dollar Index (DXY) impact.

    Strong dollar = EM/commodity headwind. Moderate dollar = favorable.
    Higher DXY generally negative for KR and commodity-linked assets.
    """
    if dxy is None:
        return "unknown", 0.0

    if dxy < 95:
        return "weak", 0.5  # Favorable for EM, commodities
    elif dxy < 100:
        return "normal", 0.3
    elif dxy < 103:
        return "firm", 0.0  # Neutral
    elif dxy < 107:
        return "strong", -0.4  # EM headwind
    else:
        return "very_strong", -0.8  # Significant drag on EM/commodities


def classify_copper(copper: float | None) -> tuple[str, float]:
    """Classify copper price as economic leading indicator (Dr. Copper).

    Copper demand = industrial activity = economic health.
    Higher copper = stronger global growth outlook.
    Thresholds in $/lb, calibrated for 2024-2026.
    HG=F from yfinance may return cents/lb — normalize to $/lb.
    """
    if copper is None:
        return "unknown", 0.0

    # HG=F COMEX quotes in cents/lb (e.g., 420 = $4.20/lb) — normalize
    if copper > 100:
        copper = copper / 100

    if copper < 3.0:
        return "contraction", -0.8  # Industrial demand collapse
    elif copper < 3.5:
        return "weak", -0.3  # Below-trend demand
    elif copper < 4.0:
        return "normal", 0.3  # Steady industrial demand
    elif copper < 4.5:
        return "strong", 0.7  # Healthy expansion
    else:
        return "boom", 0.5  # Overheating (may pull back)


def compute_macro_score(macro_data: dict) -> dict:
    """Compute aggregate macro score from 7-factor indicator data.

    Factors & weights:
      VIX (20%) — volatility / market fear
      Yield Curve (15%) — recession risk
      DXY (15%) — dollar strength / EM headwind
      WTI Oil (15%) — energy / inflation pressure
      Copper (15%) — industrial demand / growth outlook
      USD/KRW (10%) — KR-specific FX risk
      Gold (10%) — safe-haven demand / risk-off signal

    Returns dict with individual scores and aggregate.
    """
    vix_label, vix_score = classify_vix(macro_data.get("vix"))
    yield_label, yield_score = classify_yield_curve(macro_data.get("us_yield_spread"))
    fx_label, fx_score = classify_usd_krw_trend(macro_data.get("usd_krw"))
    oil_label, oil_score = classify_oil(macro_data.get("wti_crude"))
    gold_label, gold_score = classify_gold(macro_data.get("gold_price"))
    dxy_label, dxy_score = classify_dxy(macro_data.get("dxy_index"))
    copper_label, copper_score = classify_copper(macro_data.get("copper_price"))

    weights = {
        "vix": 0.20,
        "yield_curve": 0.15,
        "dxy": 0.15,
        "oil": 0.15,
        "copper": 0.15,
        "fx": 0.10,
        "gold": 0.10,
    }

    aggregate = (
        vix_score * weights["vix"]
        + yield_score * weights["yield_curve"]
        + dxy_score * weights["dxy"]
        + oil_score * weights["oil"]
        + copper_score * weights["copper"]
        + fx_score * weights["fx"]
        + gold_score * weights["gold"]
    )

    return {
        "vix": {"label": vix_label, "score": vix_score, "value": macro_data.get("vix")},
        "yield_curve": {"label": yield_label, "score": yield_score, "value": macro_data.get("us_yield_spread")},
        "fx": {"label": fx_label, "score": fx_score, "value": macro_data.get("usd_krw")},
        "oil": {"label": oil_label, "score": oil_score, "value": macro_data.get("wti_crude")},
        "gold": {"label": gold_label, "score": gold_score, "value": macro_data.get("gold_price")},
        "dxy": {"label": dxy_label, "score": dxy_score, "value": macro_data.get("dxy_index")},
        "copper": {"label": copper_label, "score": copper_score, "value": macro_data.get("copper_price")},
        "aggregate_score": round(aggregate, 4),
    }
