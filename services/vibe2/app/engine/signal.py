"""Signal pipeline — orchestrates collectors and engines into a final signal."""

import json
import logging
from datetime import datetime

from app.collector.macro import collect_all_macro, get_latest_macro
from app.collector.price import collect_all_prices, fetch_prices
from app.collector.sentiment import collect_sentiment, fetch_fear_greed
from app.db import get_sync_db
from app.engine.leverage import LeverageScore, calculate_leverage
from app.engine.macro_score import MacroScore, calculate_macro
from app.engine.technical import TechnicalScore, calculate_technical
from app.models import SignalLevel, SignalResult

logger = logging.getLogger("vibe2.engine.signal")

# Engine weights
W_TECHNICAL = 0.4
W_LEVERAGE = 0.3
W_MACRO = 0.3


def generate_signal(
    technical: TechnicalScore,
    leverage: LeverageScore,
    macro: MacroScore,
) -> SignalResult:
    """Combine engine scores into a final signal.

    Weighted: technical*0.4 + leverage*0.3 + macro*0.3.
    >= 0.3 → GREEN, -0.3~0.3 → YELLOW, < -0.3 → RED.
    """
    final_score = (
        technical.total * W_TECHNICAL
        + leverage.total * W_LEVERAGE
        + macro.total * W_MACRO
    )
    final_score = max(-1.0, min(1.0, round(final_score, 4)))

    if final_score >= 0.3:
        level = SignalLevel.GREEN
        action = "매수/홀드 유리한 구간"
    elif final_score <= -0.3:
        level = SignalLevel.RED
        action = "매도 또는 신규 진입 회피 권장"
    else:
        level = SignalLevel.YELLOW
        action = "관망 또는 소량 포지션만 유지"

    summary = (
        f"종합 {final_score:+.3f} "
        f"(기술={technical.total:+.3f} "
        f"레버리지={leverage.total:+.3f} "
        f"매크로={macro.total:+.3f})"
    )

    details = {
        "technical": technical.details,
        "leverage": leverage.details,
        "macro": macro.details,
        "weights": {"technical": W_TECHNICAL, "leverage": W_LEVERAGE, "macro": W_MACRO},
    }

    return SignalResult(
        signal=level,
        score=final_score,
        summary=summary,
        details=details,
        action=action,
        risks=[],  # Phase 4 LLM fills this
    )


def _save_signal(result: SignalResult) -> None:
    """Persist signal to the signals table."""
    conn = get_sync_db()
    try:
        conn.execute(
            """INSERT INTO signals
               (signal_date, signal_level, score, summary, details_json, action, risks_json)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                datetime.now().strftime("%Y-%m-%d"),
                result.signal.value,
                result.score,
                result.summary,
                json.dumps(result.details, ensure_ascii=False, default=str),
                result.action,
                json.dumps(result.risks, ensure_ascii=False),
            ),
        )
        conn.commit()
        logger.info("Signal saved: %s (%.3f)", result.signal.value, result.score)
    except Exception as e:
        logger.error("Failed to save signal: %s", e)
    finally:
        conn.close()


def _get_rate_change_5d() -> float | None:
    """Get 10-year yield from 5 trading days ago for rate direction."""
    conn = get_sync_db()
    try:
        cursor = conn.execute(
            """SELECT us_10y_yield FROM macro_data
               WHERE us_10y_yield IS NOT NULL
               ORDER BY indicator_date DESC
               LIMIT 1 OFFSET 5"""
        )
        row = cursor.fetchone()
        return float(row["us_10y_yield"]) if row else None
    except Exception:
        return None
    finally:
        conn.close()


def _get_fear_greed() -> float | None:
    """Get latest fear & greed index from DB or live fetch."""
    conn = get_sync_db()
    try:
        cursor = conn.execute(
            """SELECT fear_greed_index FROM sentiment_data
               WHERE fear_greed_index IS NOT NULL
               ORDER BY indicator_date DESC LIMIT 1"""
        )
        row = cursor.fetchone()
        if row:
            return float(row["fear_greed_index"])
    except Exception:
        pass
    finally:
        conn.close()

    # Fallback: live fetch
    fg = fetch_fear_greed()
    return fg.get("fear_greed_index") if fg else None


def run_signal_pipeline() -> SignalResult:
    """Full pipeline: collect data → run engines → generate signal → save.

    This is the single entry point for the entire VIBE 2.0 signal engine.
    """
    logger.info("=== Signal pipeline start ===")

    # --- Step 1: Collect data ---
    logger.info("Step 1: Collecting price data...")
    collect_all_prices(days=200)

    logger.info("Step 1: Collecting macro data...")
    collect_all_macro(days=30)

    logger.info("Step 1: Collecting sentiment data...")
    collect_sentiment()

    # --- Step 2: Load data for engines ---
    logger.info("Step 2: Loading data for engines...")
    soxl_df = fetch_prices("SOXL", days=200)
    soxx_df = fetch_prices("SOXX", days=200)

    macro = get_latest_macro()
    if macro:
        # Enrich with 5-day-ago yield for rate direction
        rate_5d = _get_rate_change_5d()
        if rate_5d is not None:
            macro["us_10y_yield_5d_ago"] = rate_5d

    fear_greed = _get_fear_greed()
    vix = macro.get("vix") if macro else None

    # --- Step 3: Run engines ---
    logger.info("Step 3: Running engines...")
    technical = calculate_technical(soxl_df)
    leverage = calculate_leverage(soxl_df, soxx_df, vix)
    macro_score = calculate_macro(macro, fear_greed)

    # --- Step 4: Generate and save signal ---
    logger.info("Step 4: Generating signal...")
    result = generate_signal(technical, leverage, macro_score)

    _save_signal(result)

    logger.info("=== Signal pipeline complete: %s (%.3f) ===", result.signal.value, result.score)
    return result
