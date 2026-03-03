"""US Fund Flow collectors - ETF flow proxy, short interest."""

import logging
from typing import Any

logger = logging.getLogger("vibe.collectors.us_fund_flow")


async def fetch_short_interest(symbol: str) -> dict[str, Any]:
    """Fetch short interest data via yfinance."""
    import asyncio

    def _fetch():
        try:
            import yfinance as yf

            ticker = yf.Ticker(symbol)
            info = ticker.info

            result = {}
            if info.get("sharesShort"):
                result["short_interest_shares"] = info["sharesShort"]
            if info.get("shortRatio"):
                result["short_ratio"] = round(info["shortRatio"], 2)
            if info.get("shortPercentOfFloat"):
                result["short_pct_float"] = round(info["shortPercentOfFloat"] * 100, 2)
            if info.get("sharesShortPriorMonth"):
                result["short_prior_month"] = info["sharesShortPriorMonth"]
                if result.get("short_interest_shares"):
                    change = result["short_interest_shares"] - result["short_prior_month"]
                    result["short_change"] = change
                    result["short_change_pct"] = round(
                        change / result["short_prior_month"] * 100, 2
                    ) if result["short_prior_month"] > 0 else 0

            return result
        except Exception as e:
            logger.warning("Short interest fetch failed for %s: %s", symbol, e)
            return {}

    return await asyncio.to_thread(_fetch)


async def fetch_etf_flow_proxy() -> dict[str, Any]:
    """Estimate fund flow from major ETF volume and price action."""
    import asyncio

    def _fetch():
        try:
            import yfinance as yf

            etfs = {
                "SPY": "S&P 500",
                "QQQ": "NASDAQ 100",
                "IWM": "Russell 2000",
                "HYG": "High Yield Bond",
                "TLT": "20+ Year Treasury",
            }

            result = {}
            for ticker_sym, name in etfs.items():
                try:
                    t = yf.Ticker(ticker_sym)
                    hist = t.history(period="5d")
                    if hist.empty or len(hist) < 2:
                        continue

                    latest = hist.iloc[-1]
                    prev = hist.iloc[-2]

                    price_change = (latest["Close"] - prev["Close"]) / prev["Close"] * 100
                    vol_avg = hist["Volume"].mean()
                    vol_ratio = latest["Volume"] / vol_avg if vol_avg > 0 else 1

                    result[ticker_sym] = {
                        "name": name,
                        "price_change_pct": round(price_change, 2),
                        "volume_ratio": round(vol_ratio, 2),
                        "latest_close": round(float(latest["Close"]), 2),
                    }
                except Exception:
                    continue

            # Compute risk appetite score
            risk_on = 0
            if result.get("SPY", {}).get("price_change_pct", 0) > 0:
                risk_on += 1
            if result.get("HYG", {}).get("price_change_pct", 0) > 0:
                risk_on += 1
            if result.get("TLT", {}).get("price_change_pct", 0) < 0:
                risk_on += 1  # Money leaving bonds = risk on

            result["risk_appetite"] = "risk_on" if risk_on >= 2 else "risk_off"

            return result
        except Exception as e:
            logger.warning("ETF flow proxy fetch failed: %s", e)
            return {}

    return await asyncio.to_thread(_fetch)
