"""Fundamental indicator calculations."""

import logging
from typing import Any

logger = logging.getLogger("vibe.indicators.fundamental")


def compute_fundamental_score(data: dict, market: str = "KR") -> dict:
    """Compute fundamental score from financial data.

    Input data keys: per, pbr, roe, operating_margin, div_yield, eps, market_cap

    Returns dict with: fundamental_score, value_score, quality_score, components
    Score range: [-100, +100]
    """
    value_score = _compute_value_score(data, market)
    quality_score = _compute_quality_score(data, market)

    # Combined score: value 50% + quality 50%
    fundamental_score = value_score + quality_score
    fundamental_score = max(-100, min(100, fundamental_score))

    return {
        "fundamental_score": round(fundamental_score, 2),
        "value_score": round(value_score, 2),
        "quality_score": round(quality_score, 2),
        "components": {
            "per": data.get("per"),
            "pbr": data.get("pbr"),
            "roe": data.get("roe"),
            "operating_margin": data.get("operating_margin"),
            "div_yield": data.get("div_yield"),
        },
    }


def _compute_value_score(data: dict, market: str) -> float:
    """Value score from PER and PBR. Range: [-50, +50]."""
    score = 0.0

    # PER scoring [-25, +25]
    per = data.get("per")
    if per is not None and per > 0:
        if market == "KR":
            if per < 8:
                score += 25
            elif per < 12:
                score += 15
            elif per < 18:
                score += 5
            elif per < 25:
                score -= 10
            else:
                score -= 25
        else:  # US - typically higher PER
            if per < 12:
                score += 25
            elif per < 18:
                score += 15
            elif per < 25:
                score += 5
            elif per < 35:
                score -= 10
            else:
                score -= 25

    # PBR scoring [-25, +25]
    pbr = data.get("pbr")
    if pbr is not None and pbr > 0:
        if market == "KR":
            if pbr < 0.7:
                score += 25
            elif pbr < 1.0:
                score += 15
            elif pbr < 1.5:
                score += 5
            elif pbr < 3.0:
                score -= 10
            else:
                score -= 25
        else:  # US
            if pbr < 1.5:
                score += 25
            elif pbr < 3.0:
                score += 15
            elif pbr < 5.0:
                score += 5
            elif pbr < 10.0:
                score -= 10
            else:
                score -= 25

    return max(-50, min(50, score))


def _compute_quality_score(data: dict, market: str) -> float:
    """Quality score from ROE, operating margin, dividend yield. Range: [-50, +50]."""
    score = 0.0

    # ROE scoring [-20, +20]
    roe = data.get("roe")
    if roe is not None:
        if roe > 20:
            score += 20
        elif roe > 15:
            score += 15
        elif roe > 10:
            score += 10
        elif roe > 5:
            score += 5
        elif roe > 0:
            score -= 5
        else:
            score -= 15

    # Operating margin scoring [-15, +15]
    op_margin = data.get("operating_margin")
    if op_margin is not None:
        if op_margin > 25:
            score += 15
        elif op_margin > 15:
            score += 10
        elif op_margin > 10:
            score += 5
        elif op_margin > 5:
            score += 0
        elif op_margin > 0:
            score -= 5
        else:
            score -= 15

    # Dividend yield scoring [-5, +15] (bonus for yield, mild penalty for none)
    div_yield = data.get("div_yield")
    if div_yield is not None:
        if div_yield > 5:
            score += 15
        elif div_yield > 3:
            score += 10
        elif div_yield > 1:
            score += 5
        elif div_yield > 0:
            score += 2
        else:
            score -= 5

    return max(-50, min(50, score))


async def fetch_fundamental_data_yfinance(symbol: str, market: str) -> dict[str, Any]:
    """Fetch fundamental data using yfinance.

    Returns dict with: per, pbr, roe, operating_margin, div_yield, eps, market_cap
    """
    import asyncio

    def _fetch():
        try:
            import yfinance as yf

            # Build ticker symbol
            if market == "KR":
                ticker_symbol = f"{symbol}.KS"
            else:
                ticker_symbol = symbol

            ticker = yf.Ticker(ticker_symbol)
            info = ticker.info

            if not info or info.get("regularMarketPrice") is None:
                # Try .KQ for KOSDAQ
                if market == "KR":
                    ticker_symbol = f"{symbol}.KQ"
                    ticker = yf.Ticker(ticker_symbol)
                    info = ticker.info

            if not info:
                return {}

            result = {
                "per": info.get("trailingPE") or info.get("forwardPE"),
                "pbr": info.get("priceToBook"),
                "eps": info.get("trailingEps"),
                "roe": None,
                "operating_margin": None,
                "div_yield": None,
                "market_cap": info.get("marketCap"),
            }

            # ROE = returnOnEquity (comes as decimal, convert to %)
            roe = info.get("returnOnEquity")
            if roe is not None:
                result["roe"] = round(roe * 100, 2)

            # Operating margin (comes as decimal, convert to %)
            op_margin = info.get("operatingMargins")
            if op_margin is not None:
                result["operating_margin"] = round(op_margin * 100, 2)

            # Dividend yield (comes as decimal, convert to %)
            div_yield = info.get("dividendYield")
            if div_yield is not None:
                result["div_yield"] = round(div_yield * 100, 2)

            return result

        except Exception as e:
            logger.warning("yfinance fundamental fetch failed for %s: %s", symbol, e)
            return {}

    return await asyncio.to_thread(_fetch)
