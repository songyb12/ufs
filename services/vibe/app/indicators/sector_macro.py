"""Sector-Macro cross-impact scoring.

Maps sector exposure to macro factor sensitivities. Each sector has a
sensitivity vector; the dot product with current macro conditions yields
an adjustment score applied in S6 signal generation.

All functions are pure (no DB access).
"""

from __future__ import annotations

# ── Sensitivity Matrix ──
# sector → {factor: sensitivity}
# Sensitivity range: -1.0 to +1.0
# Positive = sector BENEFITS from higher values of that factor.
#
# Factors:
#   oil  — WTI crude level (high = +condition)
#   rate — US 10Y yield level (high = +condition)
#   fx   — USD/KRW level (high = weak KRW = +condition)
#   dxy  — DXY strength (high = +condition)

SECTOR_SENSITIVITY: dict[str, dict[str, float]] = {
    # ── KR Sectors ──
    "유틸리티":       {"oil": -0.8, "rate": -0.3, "fx":  0.0, "dxy":  0.0},
    "에너지/플랜트":  {"oil":  0.5, "rate": -0.2, "fx":  0.3, "dxy": -0.1},
    "반도체":         {"oil": -0.1, "rate": -0.3, "fx":  0.5, "dxy": -0.3},
    "자동차":         {"oil": -0.3, "rate": -0.1, "fx":  0.5, "dxy": -0.2},
    "배터리":         {"oil": -0.2, "rate": -0.4, "fx":  0.3, "dxy": -0.2},
    "바이오":         {"oil":  0.0, "rate": -0.5, "fx":  0.0, "dxy":  0.0},
    "인터넷":         {"oil":  0.0, "rate": -0.4, "fx":  0.0, "dxy":  0.0},
    "금융":           {"oil": -0.1, "rate":  0.3, "fx": -0.1, "dxy":  0.0},
    "보험":           {"oil":  0.0, "rate":  0.3, "fx":  0.0, "dxy":  0.0},
    "철강":           {"oil": -0.2, "rate": -0.1, "fx":  0.3, "dxy": -0.2},
    "화학":           {"oil": -0.3, "rate": -0.2, "fx":  0.3, "dxy": -0.2},
    "통신":           {"oil":  0.0, "rate":  0.1, "fx":  0.0, "dxy":  0.0},
    "소비재":         {"oil": -0.1, "rate": -0.1, "fx": -0.2, "dxy":  0.0},
    "전자":           {"oil": -0.1, "rate": -0.2, "fx":  0.4, "dxy": -0.2},
    "조선/중공업":    {"oil":  0.3, "rate": -0.1, "fx":  0.4, "dxy": -0.2},
    "방산/항공":      {"oil":  0.1, "rate":  0.0, "fx":  0.2, "dxy":  0.0},
    "전기/전력장비":  {"oil": -0.3, "rate": -0.2, "fx":  0.3, "dxy": -0.1},
    "지주":           {"oil": -0.1, "rate":  0.0, "fx":  0.1, "dxy":  0.0},
    # ── US Sectors ──
    "Tech":           {"oil":  0.0, "rate": -0.4, "fx":  0.0, "dxy":  0.2},
    "Semiconductor":  {"oil": -0.1, "rate": -0.3, "fx":  0.0, "dxy":  0.1},
    "Energy":         {"oil":  0.7, "rate":  0.1, "fx":  0.0, "dxy": -0.3},
    "Finance":        {"oil": -0.1, "rate":  0.3, "fx":  0.0, "dxy":  0.1},
    "Healthcare":     {"oil":  0.0, "rate": -0.2, "fx":  0.0, "dxy":  0.1},
    "Consumer":       {"oil": -0.2, "rate": -0.2, "fx":  0.0, "dxy":  0.1},
    "Auto":           {"oil": -0.3, "rate": -0.2, "fx":  0.0, "dxy":  0.0},
    "Infrastructure": {"oil": -0.1, "rate": -0.2, "fx":  0.0, "dxy":  0.0},
}

DEFAULT_SENSITIVITY = {"oil": 0.0, "rate": 0.0, "fx": 0.0, "dxy": 0.0}

# Scaling factor: maps sensitivity × condition (-1..+1 each) to score range
# Theoretical max per factor = 1.0 * 1.0 * SCALE = SCALE
# 4 factors → theoretical max = 4 * SCALE; practical range ~-30..+30
_FACTOR_SCALE = 15.0

# ── Warning templates ──
_WARNINGS_KR: dict[str, dict[str, str]] = {
    "oil": {
        "negative": "{sector}: 유가 고수준(${value:.0f}), 비용 부담 증가",
        "positive": "{sector}: 유가 저수준(${value:.0f}), 비용 절감 기대",
    },
    "rate": {
        "negative": "{sector}: 금리 고수준({value:.2f}%), 밸류에이션 부담",
        "positive": "{sector}: 금리 저수준({value:.2f}%), 성장주 유리",
    },
    "fx": {
        "negative": "{sector}: 원화 강세({value:.0f}원), 수출 불리",
        "positive": "{sector}: 원화 약세({value:.0f}원), 수출 환차익",
    },
    "dxy": {
        "negative": "{sector}: 달러 강세(DXY {value:.1f}), 이머징 불리",
        "positive": "{sector}: 달러 약세(DXY {value:.1f}), 이머징 유리",
    },
}

# Raw value keys for warning generation
_FACTOR_VALUE_KEYS = {
    "oil": "wti_crude",
    "rate": "us_10y_yield",
    "fx": "usd_krw",
    "dxy": "dxy_index",
}


def _compute_factor_conditions(macro_data: dict) -> dict[str, float]:
    """Convert raw macro values to factor condition scores (-1 to +1).

    Each factor maps a specific macro indicator to a normalized condition:
      oil:  WTI relative to sweet spot. >90=+0.7, 55-75=0.0, <45=-0.5
      rate: US 10Y yield level. >5.0=+0.8, 3.5-4.5=0.0, <3.0=-0.6
      fx:   USD/KRW strength. >1400=+0.8, 1280-1350=0.0, <1250=-0.5
      dxy:  DXY index. >107=+0.7, 100-103=0.0, <97=-0.5
    """
    conditions: dict[str, float] = {}

    # Oil condition
    wti = macro_data.get("wti_crude")
    if wti is None:
        conditions["oil"] = 0.0
    elif wti > 100:
        conditions["oil"] = 0.8
    elif wti > 90:
        conditions["oil"] = 0.6
    elif wti > 75:
        conditions["oil"] = 0.2
    elif wti > 55:
        conditions["oil"] = 0.0
    elif wti > 45:
        conditions["oil"] = -0.3
    else:
        conditions["oil"] = -0.5

    # Rate condition
    rate = macro_data.get("us_10y_yield")
    if rate is None:
        conditions["rate"] = 0.0
    elif rate > 5.0:
        conditions["rate"] = 0.8
    elif rate > 4.5:
        conditions["rate"] = 0.5
    elif rate > 4.0:
        conditions["rate"] = 0.2
    elif rate > 3.5:
        conditions["rate"] = 0.0
    elif rate > 3.0:
        conditions["rate"] = -0.3
    else:
        conditions["rate"] = -0.6

    # FX condition (USD/KRW — higher = weaker KRW)
    fx = macro_data.get("usd_krw")
    if fx is None:
        conditions["fx"] = 0.0
    elif fx > 1400:
        conditions["fx"] = 0.8
    elif fx > 1380:
        conditions["fx"] = 0.6
    elif fx > 1350:
        conditions["fx"] = 0.3
    elif fx > 1280:
        conditions["fx"] = 0.0
    elif fx > 1250:
        conditions["fx"] = -0.3
    else:
        conditions["fx"] = -0.5

    # DXY condition
    dxy = macro_data.get("dxy_index")
    if dxy is None:
        conditions["dxy"] = 0.0
    elif dxy > 110:
        conditions["dxy"] = 0.8
    elif dxy > 107:
        conditions["dxy"] = 0.5
    elif dxy > 103:
        conditions["dxy"] = 0.2
    elif dxy > 100:
        conditions["dxy"] = 0.0
    elif dxy > 97:
        conditions["dxy"] = -0.3
    else:
        conditions["dxy"] = -0.5

    return conditions


def compute_sector_macro_adjustment(
    sector: str,
    macro_data: dict,
) -> dict:
    """Compute sector-specific macro adjustment for signal scoring.

    Args:
        sector: Sector label from SECTOR_MAP (e.g. "유틸리티", "Energy")
        macro_data: Latest macro_indicators row dict

    Returns:
        {
            "adjustment_score": float,  # -30 to +30 range
            "sector": str,
            "factors": {
                "oil": {"condition": float, "sensitivity": float, "contribution": float},
                ...
            },
            "warnings": list[str],
        }
    """
    sensitivity = SECTOR_SENSITIVITY.get(sector, DEFAULT_SENSITIVITY)
    conditions = _compute_factor_conditions(macro_data)
    warnings: list[str] = []
    factors: dict[str, dict] = {}
    total_score = 0.0

    for factor_name in ("oil", "rate", "fx", "dxy"):
        cond = conditions.get(factor_name, 0.0)
        sens = sensitivity.get(factor_name, 0.0)
        contribution = cond * sens * _FACTOR_SCALE

        factors[factor_name] = {
            "condition": round(cond, 2),
            "sensitivity": round(sens, 2),
            "contribution": round(contribution, 2),
        }
        total_score += contribution

        # Generate warning when impact is significant
        if abs(contribution) >= 4.0 and abs(sens) >= 0.3:
            raw_key = _FACTOR_VALUE_KEYS.get(factor_name)
            raw_value = macro_data.get(raw_key) if raw_key else None
            if raw_value is not None:
                templates = _WARNINGS_KR.get(factor_name, {})
                # Adverse = sensitivity and condition have opposite signs
                if contribution < -3.0 and "negative" in templates:
                    warnings.append(
                        templates["negative"].format(sector=sector, value=raw_value)
                    )
                elif contribution > 3.0 and "positive" in templates:
                    warnings.append(
                        templates["positive"].format(sector=sector, value=raw_value)
                    )

    total_score = round(max(-30.0, min(30.0, total_score)), 2)

    return {
        "adjustment_score": total_score,
        "sector": sector,
        "factors": factors,
        "warnings": warnings,
    }


def compute_all_sector_impacts(macro_data: dict) -> list[dict]:
    """Compute macro impact for all known sectors.

    Returns sorted list (by absolute adjustment_score descending).
    """
    results = []
    for sector in SECTOR_SENSITIVITY:
        impact = compute_sector_macro_adjustment(sector, macro_data)
        results.append(impact)

    results.sort(key=lambda x: abs(x["adjustment_score"]), reverse=True)
    return results
