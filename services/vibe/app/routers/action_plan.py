"""Action Plan Router — /action-plan endpoints."""

import logging

from fastapi import APIRouter, HTTPException

from app.config import settings
from app.database import repositories as repo
from app.indicators.action_plan import (
    generate_daily_strategy,
    generate_portfolio_actions,
    rank_top_picks,
)
from app.indicators.fear_gauge import compute_fear_gauge
from app.indicators.guru_insights import analyze_all_gurus
from app.indicators.market_season import (
    compute_investment_clock,
    compute_unified_risk_score,
    detect_market_season,
)
from app.indicators.regime import (
    compute_stagflation_index,
    detect_combined_regime,
    detect_risk_regime,
)

logger = logging.getLogger("vibe.routers.action_plan")

router = APIRouter(prefix="/action-plan", tags=["action-plan"])


async def _build_context() -> dict:
    """Gather all data needed for action plan generation."""
    config = settings

    macro = await repo.get_latest_macro() or {}
    sentiment = await repo.get_latest_sentiment()
    signals_kr = await repo.get_latest_signals("KR")
    signals_us = await repo.get_latest_signals("US")
    all_signals = signals_kr + signals_us

    # Portfolio positions across all groups
    groups = await repo.get_portfolio_groups()  # list[dict]
    all_positions = []
    for g in groups:
        positions = await repo.get_portfolio_state(portfolio_id=g["id"], include_hidden=False)
        all_positions.extend(positions)

    # Regime analysis (simple risk regime)
    vix = macro.get("vix")
    fg = (sentiment or {}).get("fear_greed_index")
    put_call = (sentiment or {}).get("put_call_ratio")
    vix_term = (sentiment or {}).get("vix_term_structure")
    spread = macro.get("us_yield_spread")

    regime = detect_risk_regime(
        vix=vix,
        fear_greed=fg,
        put_call_ratio=put_call,
        vix_term_structure=vix_term,
        yield_spread=spread,
    )

    # Combined regime for risk score
    signal_stats = await repo.get_signal_stats_by_market()
    combined_regime = detect_combined_regime(macro, sentiment, signal_stats)
    risk_regime_score = combined_regime.get("risk_regime", {}).get("score", 0.0)

    # Season & clock (with macro history)
    macro_history = await repo.get_macro_history(days=90)
    kr_foreign = await repo.get_kr_daily_foreign_total(days=30)
    etf_momentum = await repo.get_etf_momentum()
    season = detect_market_season(macro_history, kr_foreign, etf_momentum)
    clock = compute_investment_clock(macro, macro_history)

    # Unified risk score (needs stagflation index + risk regime score + clock quadrant)
    stag = compute_stagflation_index(
        gold_price=macro.get("gold_price"),
        copper_price=macro.get("copper_price"),
        wti_crude=macro.get("wti_crude"),
        yield_spread=macro.get("us_yield_spread"),
        dxy_index=macro.get("dxy_index"),
    )
    risk_score_data = compute_unified_risk_score(
        stagflation_index=stag["index"],
        risk_regime_score=risk_regime_score,
        clock_quadrant=clock["quadrant"],
    )

    # Fear gauge
    sentiment_history = await repo.get_sentiment_history(days=30)
    sentiment_history.sort(key=lambda x: x.get("indicator_date", ""))
    fear_gauge = compute_fear_gauge(macro_history, sentiment_history)

    return {
        "config": config,
        "macro": macro,
        "sentiment": sentiment,
        "signals": all_signals,
        "signals_kr": signals_kr,
        "signals_us": signals_us,
        "positions": all_positions,
        "regime": regime,
        "season": season,
        "clock": clock,
        "risk_score": risk_score_data,
        "fear_gauge": fear_gauge,
    }


@router.get("/daily")
async def get_daily_action_plan():
    """Full daily action plan with strategy, picks, and portfolio actions."""
    try:
        ctx = await _build_context()
        config = ctx["config"]

        # Signal summary
        buy_count = sum(1 for s in ctx["signals"] if s.get("final_signal") == "BUY")
        sell_count = sum(1 for s in ctx["signals"] if s.get("final_signal") == "SELL")
        signal_summary = {
            "total": len(ctx["signals"]),
            "buy_count": buy_count,
            "sell_count": sell_count,
            "hold_count": len(ctx["signals"]) - buy_count - sell_count,
        }

        # Guru consensus (optional)
        guru_data = None
        try:
            guru_data = analyze_all_gurus(ctx["macro"], ctx["signals"])
        except Exception as exc:
            logger.warning("Guru consensus skipped in action plan: %s", exc)

        # Generate strategy
        strategy = generate_daily_strategy(
            macro_data=ctx["macro"],
            regime={"risk_score": ctx["risk_score"], **ctx["regime"]},
            season={"season": ctx["season"].get("season", "unknown"), "clock": ctx["clock"]},
            fear_gauge=ctx["fear_gauge"],
            signal_summary=signal_summary,
            guru_consensus=guru_data,
        )

        # Enrich signals with current price from price_history
        enriched_signals = []
        price_cache = {}
        for s in ctx["signals"]:
            enriched = dict(s)
            if not enriched.get("close") and not enriched.get("current_price"):
                sym = s.get("symbol", "")
                mkt = s.get("market", "")
                cache_key = f"{sym}:{mkt}"
                if cache_key not in price_cache:
                    hist = await repo.get_price_history(sym, mkt, limit=1)
                    price_cache[cache_key] = hist[0]["close"] if hist else None
                enriched["close"] = price_cache[cache_key]
            elif not enriched.get("close"):
                enriched["close"] = enriched.get("current_price")
            enriched_signals.append(enriched)

        # Resolve total capital: runtime_config > env > default
        rt_cfg = await repo.get_runtime_config()
        try:
            raw = rt_cfg.get("portfolio_total", config.PORTFOLIO_TOTAL)
            total_capital = float(str(raw).replace(",", "").replace(" ", ""))
        except (ValueError, TypeError):
            total_capital = float(config.PORTFOLIO_TOTAL)

        # Top picks
        top_picks = rank_top_picks(
            signals=enriched_signals,
            positions=ctx["positions"],
            total_capital=total_capital,
        )

        # Portfolio actions
        portfolio_actions = generate_portfolio_actions(
            positions=ctx["positions"],
            signals=ctx["signals"],
        )

        return {
            "date": ctx["macro"].get("indicator_date", ""),
            "strategy": strategy,
            "signal_summary": signal_summary,
            "top_picks": top_picks,
            "portfolio_actions": portfolio_actions,
            "market_context": {
                "vix": ctx["macro"].get("vix"),
                "fear_greed": (ctx["sentiment"] or {}).get("fear_greed_index"),
                "usd_krw": ctx["macro"].get("usd_krw"),
                "risk_score": ctx["risk_score"].get("score"),
                "season": ctx["season"].get("season"),
                "fear_phase": ctx["fear_gauge"].get("phase"),
            },
        }

    except Exception as e:
        logger.error("Action plan generation failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Action plan generation failed. Check server logs for details.")
