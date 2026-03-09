"""Macro Intelligence API endpoints.

Provides regime detection, stagflation monitoring, cross-market recommendation,
macro trend data, fund flow aggregation, market season detection,
investment clock, yield phase tracking, and unified risk scoring.
All computation uses existing collected data — no new data collection required.
"""

import logging

from fastapi import APIRouter, HTTPException, Query

from app.database import repositories as repo
from app.indicators.market_season import (
    check_strategy_match,
    compute_investment_clock,
    compute_unified_risk_score,
    detect_market_season,
    detect_yield_phase,
)
from app.indicators.regime import (
    aggregate_sector_fund_flow,
    compute_cross_market_recommendation,
    compute_entry_scenarios,
    compute_relative_strength,
    compute_sector_rotation,
    compute_stagflation_index,
    detect_combined_regime,
    detect_risk_regime,
)
from app.indicators.sector_macro import compute_all_sector_impacts
from app.indicators.fear_gauge import compute_fear_gauge
from app.risk.sector import SECTOR_MAP

logger = logging.getLogger("vibe.routers.macro_intel")

router = APIRouter(prefix="/macro-intel", tags=["macro-intelligence"])


@router.get("/regime")
async def get_market_regime():
    """Get current market regime classification (risk + driver axes)."""
    try:
        macro = await repo.get_latest_macro()
        sentiment = await repo.get_latest_sentiment()
        signal_stats = await repo.get_signal_stats_by_market()

        regime = detect_combined_regime(macro, sentiment, signal_stats)
        regime["macro_snapshot"] = {
            "vix": macro.get("vix") if macro else None,
            "dxy": macro.get("dxy_index") if macro else None,
            "usd_krw": macro.get("usd_krw") if macro else None,
            "yield_spread": macro.get("us_yield_spread") if macro else None,
            "date": macro.get("indicator_date") if macro else None,
        }
        regime["sentiment_snapshot"] = {
            "fear_greed": sentiment.get("fear_greed_index") if sentiment else None,
            "put_call": sentiment.get("put_call_ratio") if sentiment else None,
            "vix_term": sentiment.get("vix_term_structure") if sentiment else None,
            "date": sentiment.get("indicator_date") if sentiment else None,
        }
        return regime
    except Exception as e:
        logger.error("Regime detection failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Regime detection failed. Check server logs for details.")


@router.get("/stagflation")
async def get_stagflation_index():
    """Get stagflation composite index and component breakdown."""
    try:
        macro = await repo.get_latest_macro()
        if not macro:
            return {"index": 0, "level": "Unknown", "level_kr": "데이터 없음", "components": {}}

        result = compute_stagflation_index(
            gold_price=macro.get("gold_price"),
            copper_price=macro.get("copper_price"),
            wti_crude=macro.get("wti_crude"),
            yield_spread=macro.get("us_yield_spread"),
            dxy_index=macro.get("dxy_index"),
        )
        result["date"] = macro.get("indicator_date")

        # Add 30-day history for trend
        history = await repo.get_macro_history(days=30)
        result["history"] = [
            {
                "date": h["indicator_date"],
                **compute_stagflation_index(
                    gold_price=h.get("gold_price"),
                    copper_price=h.get("copper_price"),
                    wti_crude=h.get("wti_crude"),
                    yield_spread=h.get("us_yield_spread"),
                    dxy_index=h.get("dxy_index"),
                ),
            }
            for h in history
        ]
        # Only keep index/level in history (not full components)
        for item in result["history"]:
            item.pop("components", None)

        return result
    except Exception as e:
        logger.error("Stagflation index failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Stagflation index computation failed. Check server logs for details.")


@router.get("/cross-market")
async def get_cross_market_recommendation():
    """Get KR vs US market comparison and allocation recommendation."""
    try:
        macro = await repo.get_latest_macro()
        sentiment = await repo.get_latest_sentiment()
        signal_stats = await repo.get_signal_stats_by_market()

        # KR fund flow summary (last 5 days total)
        kr_flow_rows = await repo.get_sector_fund_flow_kr(days=5)
        kr_flow_summary = {"total_foreign_net": 0}
        for row in kr_flow_rows:
            val = row.get("foreign_net_buy")
            kr_flow_summary["total_foreign_net"] += val if val is not None else 0

        # US ETF flow proxy summary (computed from price_history)
        us_flow_rows = await repo.get_us_fund_flow_recent(days=5)
        us_flow_summary = {"risk_appetite_score": 0}
        if us_flow_rows:
            scores = [r.get("risk_appetite_score", 0) for r in us_flow_rows]
            us_flow_summary["risk_appetite_score"] = sum(scores) / len(scores) if scores else 0

        result = compute_cross_market_recommendation(
            macro_data=macro,
            sentiment_data=sentiment,
            kr_fund_flow_summary=kr_flow_summary,
            us_etf_flow_summary=us_flow_summary,
            kr_signal_stats=signal_stats.get("KR", {}),
            us_signal_stats=signal_stats.get("US", {}),
        )
        result["date"] = macro.get("indicator_date") if macro else None
        return result
    except Exception as e:
        logger.error("Cross-market recommendation failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Cross-market recommendation failed. Check server logs for details.")


@router.get("/macro-trends")
async def get_macro_trends(days: int = Query(30, ge=7, le=180)):
    """Get macro indicator time series for charting."""
    try:
        macro_history = await repo.get_macro_history(days=days)
        sentiment_history = await repo.get_sentiment_history(days=days)

        # Build sentiment lookup by date
        sent_by_date = {}
        for s in sentiment_history:
            sent_by_date[s.get("indicator_date")] = s

        # Merge macro + sentiment by date
        trends = []
        for m in macro_history:
            date = m.get("indicator_date")
            s = sent_by_date.get(date, {})
            trends.append({
                "date": date,
                "vix": m.get("vix"),
                "dxy": m.get("dxy_index"),
                "usd_krw": m.get("usd_krw"),
                "wti": m.get("wti_crude"),
                "gold": m.get("gold_price"),
                "copper": m.get("copper_price"),
                "us_10y": m.get("us_10y_yield"),
                "us_2y": m.get("us_2y_yield"),
                "yield_spread": m.get("us_yield_spread"),
                "fear_greed": s.get("fear_greed_index"),
                "put_call": s.get("put_call_ratio"),
            })
        return {"trends": trends, "count": len(trends), "days": days}
    except Exception as e:
        logger.error("Macro trends failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Macro trends retrieval failed. Check server logs for details.")


@router.get("/fund-flow/sectors")
async def get_sector_fund_flow(days: int = Query(5, ge=1, le=30)):
    """Get fund flow aggregated by sector for KR market.

    Falls back to signal-based sector data when fund_flow_kr is empty.
    """
    try:
        kr_rows = await repo.get_sector_fund_flow_kr(days=days)

        if kr_rows:
            sectors = aggregate_sector_fund_flow(kr_rows, SECTOR_MAP)
            return {"sectors": sectors, "days": days, "total_rows": len(kr_rows), "source": "fund_flow"}

        # Fallback: Build sector data from signals (no fund flow, but still useful)
        from app.database.connection import get_db
        db = await get_db()
        cursor = await db.execute(
            """SELECT s.symbol, s.market, s.raw_score, s.final_signal,
                      s.technical_score, s.fund_flow_score
               FROM signals s
               WHERE s.signal_date = (SELECT MAX(signal_date) FROM signals)"""
        )
        rows = [dict(r) for r in await cursor.fetchall()]

        sector_agg: dict[str, dict] = {}
        for r in rows:
            sector = SECTOR_MAP.get(r["symbol"], "기타")
            if sector == "ETF":
                continue
            if sector not in sector_agg:
                sector_agg[sector] = {
                    "sector": sector,
                    "foreign_net": 0, "institution_net": 0, "individual_net": 0,
                    "total_net": 0, "symbol_count": 0,
                    "avg_score": 0, "scores": [],
                    "buy_count": 0, "sell_count": 0,
                }
            sector_agg[sector]["symbol_count"] += 1
            sector_agg[sector]["scores"].append(r.get("raw_score") or 0)
            if r.get("final_signal") == "BUY":
                sector_agg[sector]["buy_count"] += 1
            elif r.get("final_signal") == "SELL":
                sector_agg[sector]["sell_count"] += 1

        sectors = []
        for s in sector_agg.values():
            s["avg_score"] = round(sum(s["scores"]) / len(s["scores"]), 1) if s["scores"] else 0
            del s["scores"]
            sectors.append(s)
        sectors.sort(key=lambda x: x["avg_score"], reverse=True)

        return {"sectors": sectors, "days": days, "total_rows": 0, "source": "signals"}
    except Exception as e:
        logger.error("Sector fund flow failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Sector fund flow retrieval failed. Check server logs for details.")


@router.get("/fund-flow/cross-market")
async def get_cross_market_flow(days: int = Query(30, ge=5, le=90)):
    """Get cross-market fund flow comparison time series."""
    try:
        kr_daily = await repo.get_kr_daily_foreign_total(days=days)
        us_etf_data = await repo.get_us_fund_flow_recent(days=days)

        # Build lookup dicts
        kr_by_date = {kr["trade_date"]: kr for kr in kr_daily}
        us_by_date = {us["trade_date"]: us for us in us_etf_data}

        # Merge all available dates from both sources
        all_dates = sorted(set(kr_by_date.keys()) | set(us_by_date.keys()))

        series = []
        for date in all_dates:
            kr = kr_by_date.get(date, {})
            us = us_by_date.get(date, {})
            series.append({
                "date": date,
                "kr_foreign_net": kr.get("total_foreign_net"),
                "kr_institution_net": kr.get("total_institution_net"),
                "kr_individual_net": kr.get("total_individual_net"),
                "us_risk_appetite": us.get("risk_appetite_score"),
                "spy_change": us.get("spy_change"),
                "qqq_change": us.get("qqq_change"),
                "iwm_change": us.get("iwm_change"),
                "tlt_change": us.get("tlt_change"),
            })

        return {"series": series, "count": len(series), "days": days}
    except Exception as e:
        logger.error("Cross-market flow failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Cross-market flow retrieval failed. Check server logs for details.")


@router.get("/sector-rotation")
async def get_sector_rotation():
    """Get sector rotation signals comparing current vs previous period.

    Uses fund_flow_kr data when available, otherwise falls back to
    signal-based sector strength comparison.
    """
    try:
        current_rows = await repo.get_sector_fund_flow_kr(days=5)
        previous_rows = await repo.get_sector_fund_flow_kr(days=10)

        if current_rows:
            # Fund flow based rotation
            current_dates = {r.get("trade_date") for r in current_rows}
            prev_only = [r for r in previous_rows if r.get("trade_date") not in current_dates]

            current_sectors = aggregate_sector_fund_flow(current_rows, SECTOR_MAP)
            previous_sectors = aggregate_sector_fund_flow(prev_only, SECTOR_MAP)

            rotation = compute_sector_rotation(current_sectors, previous_sectors)
            return {"rotation": rotation, "period": "5d vs prev 5d", "source": "fund_flow"}

        # Fallback: signal-based sector strength
        from app.database.connection import get_db
        db = await get_db()
        cursor = await db.execute(
            """SELECT s.symbol, s.market, s.raw_score, s.final_signal
               FROM signals s
               WHERE s.signal_date = (SELECT MAX(signal_date) FROM signals)"""
        )
        rows = [dict(r) for r in await cursor.fetchall()]

        sector_scores: dict[str, dict] = {}
        for row in rows:
            sector = SECTOR_MAP.get(row["symbol"], "기타")
            if sector == "ETF":
                continue
            if sector not in sector_scores:
                sector_scores[sector] = {"scores": [], "buy": 0, "sell": 0}
            sector_scores[sector]["scores"].append(row.get("raw_score") or 0)
            if row.get("final_signal") == "BUY":
                sector_scores[sector]["buy"] += 1
            elif row.get("final_signal") == "SELL":
                sector_scores[sector]["sell"] += 1

        # Rank sectors by average score
        ranked = []
        for sector, data in sector_scores.items():
            avg = sum(data["scores"]) / len(data["scores"]) if data["scores"] else 0
            ranked.append({
                "sector": sector,
                "avg_score": round(avg, 1),
                "buy_count": data["buy"],
                "sell_count": data["sell"],
                "symbol_count": len(data["scores"]),
            })
        ranked.sort(key=lambda x: x["avg_score"], reverse=True)

        rotation = []
        for i, r in enumerate(ranked):
            rotation.append({
                "sector": r["sector"],
                "current_rank": i + 1,
                "previous_rank": None,
                "rank_change": 0,
                "current_net": 0,
                "flow_change": 0,
                "signal": "Buy-Dominant" if r["buy_count"] > r["sell_count"] else
                          "Sell-Dominant" if r["sell_count"] > r["buy_count"] else "Mixed",
                "avg_score": r["avg_score"],
                "symbol_count": r["symbol_count"],
            })

        return {"rotation": rotation, "period": "signal-based", "source": "signals"}
    except Exception as e:
        logger.error("Sector rotation failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Sector rotation computation failed. Check server logs for details.")


@router.get("/theme-ranking")
async def get_theme_ranking():
    """Get investment theme ranking combining fund flow + signal strength."""
    try:
        # Sector fund flow (last 5 days) — may be empty if fund_flow_kr has no data
        kr_rows = await repo.get_sector_fund_flow_kr(days=5)
        sector_flow = aggregate_sector_fund_flow(kr_rows, SECTOR_MAP)
        sector_flow_map = {sf["sector"]: sf for sf in sector_flow}

        # Build sector signal scores from latest signals (KR + US)
        from app.database.connection import get_db
        db = await get_db()
        cursor = await db.execute(
            """SELECT s.symbol, s.market, s.final_signal, s.raw_score
               FROM signals s
               WHERE s.signal_date = (SELECT MAX(signal_date) FROM signals)"""
        )
        signal_rows = [dict(r) for r in await cursor.fetchall()]
        sector_signals: dict[str, dict] = {}
        for sr in signal_rows:
            sector = SECTOR_MAP.get(sr["symbol"], "기타")
            if sector == "ETF":
                continue  # Skip ETFs from theme ranking
            if sector not in sector_signals:
                sector_signals[sector] = {"scores": [], "buy": 0, "sell": 0, "symbols": 0, "market": sr.get("market", "")}
            sector_signals[sector]["scores"].append(sr.get("raw_score") or 0)
            sector_signals[sector]["symbols"] += 1
            if sr.get("final_signal") == "BUY":
                sector_signals[sector]["buy"] += 1
            elif sr.get("final_signal") == "SELL":
                sector_signals[sector]["sell"] += 1

        # Combine flow + signal into theme ranking
        all_sectors = set(sector_flow_map.keys()) | set(sector_signals.keys())
        themes = []
        for sector in all_sectors:
            sf = sector_flow_map.get(sector, {})
            sig = sector_signals.get(sector, {"scores": [], "buy": 0, "sell": 0, "symbols": 0})
            avg_signal = sum(sig["scores"]) / len(sig["scores"]) if sig["scores"] else 0
            flow_net = sf.get("total_net", 0)

            # When fund flow data exists: 50/50 blend; otherwise 100% signal
            signal_norm = max(-1, min(1, avg_signal / 30))
            if flow_net != 0:
                flow_norm = max(-1, min(1, flow_net / max(abs(flow_net), 1e9) * 5))
                theme_score = round(flow_norm * 0.5 + signal_norm * 0.5, 2)
            else:
                theme_score = round(signal_norm, 2)

            themes.append({
                "sector": sector,
                "theme_score": theme_score,
                "flow_net": flow_net,
                "foreign_net": sf.get("foreign_net", 0),
                "institution_net": sf.get("institution_net", 0),
                "avg_signal_score": round(avg_signal, 1),
                "buy_signals": sig["buy"],
                "sell_signals": sig["sell"],
                "symbol_count": sig.get("symbols", sf.get("symbol_count", 0)),
                "signal": "Hot" if theme_score > 0.3 else "Cold" if theme_score < -0.3 else "Neutral",
            })

        themes.sort(key=lambda x: x["theme_score"], reverse=True)
        return {"themes": themes, "count": len(themes)}
    except Exception as e:
        logger.error("Theme ranking failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Theme ranking computation failed. Check server logs for details.")


# ── Phase J: Market Season / Investment Clock / Yield Phase / Risk Score ──


@router.post("/macro-backfill")
async def backfill_macro_data(days: int = Query(90, ge=30, le=365)):
    """Backfill historical macro data using FinanceDataReader.

    Fetches multi-day time-series and bulk-upserts into macro_indicators.
    Use this once to seed enough history for market season detection (min 20 days).
    """
    try:
        from app.collectors.macro import MacroCollector
        from app.config import settings

        collector = MacroCollector(config=settings)
        rows = await collector.backfill(days_back=days)
        inserted = 0
        for row in rows:
            await repo.upsert_macro_indicators(row)
            inserted += 1
        logger.info("Macro backfill complete: %d days inserted", inserted)
        date_range = f"{rows[0]['indicator_date']} ~ {rows[-1]['indicator_date']}" if rows else "empty"
        return {"status": "ok", "days_inserted": inserted, "range": date_range}
    except Exception as e:
        logger.error("Macro backfill failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Macro data backfill failed. Check server logs for details.")


@router.get("/market-season")
async def get_market_season():
    """Detect current market season (Uragami Kunio proxy model).

    Uses rate direction × growth proxy to classify into 4 seasons:
    Spring (금융장세), Summer (실적장세), Autumn (역금융장세), Winter (역실적장세).

    Falls back to Investment Clock when season data is insufficient.
    """
    try:
        macro_history = await repo.get_macro_history(days=90)
        kr_foreign = await repo.get_kr_daily_foreign_total(days=30)
        etf_momentum = await repo.get_etf_momentum()

        result = detect_market_season(
            macro_history=macro_history,
            kr_foreign_trend=kr_foreign,
            etf_momentum=etf_momentum,
        )

        # Fallback: if season is Unknown, try Investment Clock for partial insight
        if result.get("season") == "Unknown":
            macro = await repo.get_latest_macro()
            if macro:
                clock = compute_investment_clock(macro, macro_history)
                result["fallback_clock"] = {
                    "quadrant": clock.get("quadrant", "Unknown"),
                    "quadrant_kr": clock.get("quadrant_kr", ""),
                    "growth_score": clock.get("growth_score", 0),
                    "inflation_score": clock.get("inflation_score", 0),
                }
                # Map clock quadrant to approximate season
                clock_to_season = {
                    "Recovery": {"season_hint": "Spring", "hint_kr": "금융장세 (추정)"},
                    "Overheat": {"season_hint": "Summer", "hint_kr": "실적장세 (추정)"},
                    "Stagflation": {"season_hint": "Autumn", "hint_kr": "역금융장세 (추정)"},
                    "Reflation": {"season_hint": "Winter", "hint_kr": "역실적장세 (추정)"},
                }
                hint = clock_to_season.get(clock.get("quadrant", ""), {})
                result["season_hint"] = hint.get("season_hint", "Unknown")
                result["season_hint_kr"] = hint.get("hint_kr", "추정 불가")
                result["description_kr"] = (
                    f"데이터 부족으로 정밀 판별 불가. "
                    f"Investment Clock 기준 {clock.get('quadrant_kr', '')} 국면 추정."
                )

        result["date"] = macro_history[-1].get("indicator_date") if macro_history else None
        result["data_days"] = len(macro_history)
        return result
    except Exception as e:
        logger.error("Market season detection failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Market season detection failed. Check server logs for details.")


@router.get("/investment-clock")
async def get_investment_clock():
    """Get Investment Clock quadrant (Recovery/Overheat/Stagflation/Reflation).

    Based on growth × inflation axes derived from existing macro indicators.
    """
    try:
        macro = await repo.get_latest_macro()
        macro_history = await repo.get_macro_history(days=30)

        result = compute_investment_clock(macro, macro_history)
        result["date"] = macro.get("indicator_date") if macro else None
        return result
    except Exception as e:
        logger.error("Investment clock failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Investment clock computation failed. Check server logs for details.")


@router.get("/yield-phase")
async def get_yield_phase():
    """Get yield curve phase and risk flag.

    Tracks phases: Normal → Flattening → Inverted → Normalizing → Normal.
    The Normalizing phase (un-inversion) historically precedes recessions.
    """
    try:
        macro_history = await repo.get_macro_history(days=90)
        spreads = [
            h.get("us_yield_spread")
            for h in macro_history
        ]

        result = detect_yield_phase(spreads)
        result["date"] = macro_history[-1].get("indicator_date") if macro_history else None
        return result
    except Exception as e:
        logger.error("Yield phase detection failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Yield phase detection failed. Check server logs for details.")


@router.get("/strategy-match")
async def get_strategy_match():
    """Check portfolio alignment with current market season and investment clock.

    Returns warnings when positioning conflicts with macro conditions.
    """
    try:
        # Get current season and clock
        macro_history = await repo.get_macro_history(days=90)
        kr_foreign = await repo.get_kr_daily_foreign_total(days=30)
        etf_momentum = await repo.get_etf_momentum()

        season_data = detect_market_season(macro_history, kr_foreign, etf_momentum)

        macro = await repo.get_latest_macro()
        macro_hist_30 = await repo.get_macro_history(days=30)
        clock_data = compute_investment_clock(macro, macro_hist_30)

        # Get portfolio and signal summaries
        portfolio_summary = await repo.get_portfolio_season_summary()
        signal_summary = await repo.get_signal_season_summary()

        result = check_strategy_match(
            season=season_data.get("season", "Unknown"),
            clock_quadrant=clock_data.get("quadrant", "Recovery"),
            portfolio_summary=portfolio_summary,
            signal_summary=signal_summary,
        )
        result["date"] = macro.get("indicator_date") if macro else None
        return result
    except Exception as e:
        logger.error("Strategy match failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Strategy match analysis failed. Check server logs for details.")


@router.get("/risk-score")
async def get_unified_risk_score():
    """Get unified Macro Risk Score (0-100).

    Combines stagflation index (40%), risk regime (30%), and investment clock (30%).
    """
    try:
        macro = await repo.get_latest_macro()
        if not macro:
            return {"score": 0, "level": "Unknown", "level_kr": "데이터 없음", "components": {}}

        # Stagflation index
        stag = compute_stagflation_index(
            gold_price=macro.get("gold_price"),
            copper_price=macro.get("copper_price"),
            wti_crude=macro.get("wti_crude"),
            yield_spread=macro.get("us_yield_spread"),
            dxy_index=macro.get("dxy_index"),
        )

        # Risk regime
        sentiment = await repo.get_latest_sentiment()
        signal_stats = await repo.get_signal_stats_by_market()
        regime = detect_combined_regime(macro, sentiment, signal_stats)
        risk_score = regime.get("risk_regime", {}).get("score", 0.0)

        # Investment clock
        macro_hist = await repo.get_macro_history(days=30)
        clock = compute_investment_clock(macro, macro_hist)

        result = compute_unified_risk_score(
            stagflation_index=stag["index"],
            risk_regime_score=risk_score,
            clock_quadrant=clock["quadrant"],
        )
        result["date"] = macro.get("indicator_date")
        return result
    except Exception as e:
        logger.error("Unified risk score failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Unified risk score computation failed. Check server logs for details.")


# ── Phase K: Crisis Analysis Endpoints ──


@router.get("/sector-impact")
async def get_sector_macro_impact():
    """Get macro cross-impact analysis for all sectors.

    Shows how current macro conditions (oil, rates, FX, DXY) affect each sector
    differently, with adjustment scores and warnings.
    """
    try:
        macro = await repo.get_latest_macro()
        if not macro:
            return {"sectors": [], "date": None}

        sectors = compute_all_sector_impacts(macro)
        return {"sectors": sectors, "date": macro.get("indicator_date")}
    except Exception as e:
        logger.error("Sector impact failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Sector macro impact analysis failed. Check server logs for details.")


@router.get("/fear-gauge")
async def get_fear_gauge():
    """Get Peak Fear phase analysis.

    Classifies current fear phase (Calm / Initial Panic / Peak Fear / Post-Peak)
    from VIX velocity, Fear&Greed momentum, and Put/Call ratio dynamics.
    """
    try:
        macro_history = await repo.get_macro_history(days=30)
        sentiment_history = await repo.get_sentiment_history(days=30)
        # Ensure chronological order (oldest→newest)
        sentiment_history.sort(key=lambda x: x.get("indicator_date", ""))
        result = compute_fear_gauge(macro_history, sentiment_history)
        return result
    except Exception as e:
        logger.error("Fear gauge failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Fear gauge computation failed. Check server logs for details.")


@router.get("/capitulation-scan")
async def get_capitulation_scan(market: str = Query("KR", pattern="^(KR|US)$")):
    """Scan for capitulation volume signals.

    Detects panic selling: volume > 2x average + price drop > 3% in 5 days.
    Returns potential "true bottom" candidates.
    """
    try:
        from app.screening.scanner import DynamicScreener
        screener = DynamicScreener()
        all_candidates = await screener.scan(market, days_back=10)
        capitulations = [c for c in all_candidates if c["trigger_type"] == "capitulation"]
        return {"candidates": capitulations, "count": len(capitulations), "market": market}
    except Exception as e:
        logger.error("Capitulation scan failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Capitulation scan failed. Check server logs for details.")


@router.get("/crisis-hedge")
async def get_crisis_hedge_candidates(days: int = Query(20, ge=5, le=60)):
    """Get defense/energy relative strength and hedge candidates.

    Computes relative strength for all stocks vs benchmark.
    In risk-off environments, defense sectors with RS > 1.0 are flagged as hedge candidates.
    """
    try:
        kr_returns = await repo.get_symbol_returns("KR", days=days)
        us_returns = await repo.get_symbol_returns("US", days=days)
        all_returns = {**kr_returns, **us_returns}

        benchmark_returns = {
            "KR": kr_returns.get("069500", 0.0),
            "US": us_returns.get("SPY", 0.0),
        }

        # Get risk regime for hedge candidate flagging
        macro = await repo.get_latest_macro()
        sentiment = await repo.get_latest_sentiment()
        risk = detect_risk_regime(
            vix=macro.get("vix") if macro else None,
            fear_greed=sentiment.get("fear_greed_index") if sentiment else None,
            put_call_ratio=sentiment.get("put_call_ratio") if sentiment else None,
            vix_term_structure=sentiment.get("vix_term_structure") if sentiment else None,
            yield_spread=macro.get("us_yield_spread") if macro else None,
        )

        all_rs = compute_relative_strength(
            all_returns, benchmark_returns, SECTOR_MAP,
            risk_regime_score=risk["score"],
        )

        hedge_candidates = [r for r in all_rs if r["is_hedge_candidate"]]
        return {
            "all_rs": all_rs,
            "hedge_candidates": hedge_candidates,
            "risk_regime_score": risk["score"],
            "risk_regime": risk["regime"],
            "benchmark_returns": benchmark_returns,
            "lookback_days": days,
        }
    except Exception as e:
        logger.error("Crisis hedge failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Crisis hedge analysis failed. Check server logs for details.")


@router.get("/entry-scenarios")
async def get_entry_scenarios():
    """Get 3-scenario entry levels with MA reference.

    Computes MA20/60/120 support/resistance zones for KOSPI and SPY,
    then builds Best/Base/Worst scenario matrix with specific entry levels.
    """
    try:
        benchmark_prices = await repo.get_benchmark_prices(days=200)
        fx_history = await repo.get_fx_history(days=200)
        macro = await repo.get_latest_macro()

        # Get unified risk score for probability bias
        risk_score_val = None
        try:
            stag = compute_stagflation_index(
                gold_price=macro.get("gold_price") if macro else None,
                copper_price=macro.get("copper_price") if macro else None,
                wti_crude=macro.get("wti_crude") if macro else None,
                yield_spread=macro.get("us_yield_spread") if macro else None,
                dxy_index=macro.get("dxy_index") if macro else None,
            )
            sentiment = await repo.get_latest_sentiment()
            signal_stats = await repo.get_signal_stats_by_market()
            regime = detect_combined_regime(macro, sentiment, signal_stats)
            macro_hist = await repo.get_macro_history(days=30)
            clock = compute_investment_clock(macro, macro_hist)
            risk_data = compute_unified_risk_score(
                stag["index"],
                regime.get("risk_regime", {}).get("score", 0.0),
                clock["quadrant"],
            )
            risk_score_val = risk_data["score"]
        except Exception as exc:
            logger.warning("Risk score computation skipped in entry scenarios: %s", exc)

        result = compute_entry_scenarios(
            benchmark_prices=benchmark_prices,
            fx_prices=fx_history,
            macro_data=macro,
            risk_score=risk_score_val,
        )
        result["date"] = macro.get("indicator_date") if macro else None
        return result
    except Exception as e:
        logger.error("Entry scenarios failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Entry scenarios computation failed. Check server logs for details.")
