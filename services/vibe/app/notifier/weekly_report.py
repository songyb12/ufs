"""Weekly performance report generator for Discord.

Aggregates the past 7 days of pipeline data into a summary:
- Signal accuracy (hit rate)
- Portfolio P&L
- Top/bottom performing signals
- Market summary
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from app.database.connection import get_db

logger = logging.getLogger("vibe.notifier.weekly")


async def build_weekly_report_payloads() -> list[dict]:
    """Generate weekly report embed payloads for Discord."""
    now = datetime.now(timezone.utc)
    end_date = now.strftime("%Y-%m-%d")
    start_date = (now - timedelta(days=7)).strftime("%Y-%m-%d")

    data = await _gather_weekly_data(start_date, end_date)

    embeds = []

    # ── Header ──
    embeds.append({
        "title": "\U0001f4ca VIBE 주간 리포트",
        "description": f"**{start_date} ~ {end_date}**",
        "color": 0x5865F2,
    })

    # ── Pipeline Summary ──
    runs = data["pipeline_runs"]
    kr_runs = sum(1 for r in runs if r["market"] == "KR")
    us_runs = sum(1 for r in runs if r["market"] == "US")
    failed = sum(1 for r in runs if r["status"] == "failed")

    embeds.append({
        "title": "\U0001f504 파이프라인",
        "description": (
            f"KR: {kr_runs}회 | US: {us_runs}회 | 실패: {failed}회\n"
            f"총 {len(runs)}회 실행"
        ),
        "color": 0x03B2F8,
    })

    # ── Signal Summary ──
    signals = data["signals"]
    if signals:
        buy_count = sum(1 for s in signals if s["final_signal"] == "BUY")
        sell_count = sum(1 for s in signals if s["final_signal"] == "SELL")
        hold_count = sum(1 for s in signals if s["final_signal"] == "HOLD")
        hl_count = sum(1 for s in signals if s["hard_limit_triggered"])

        embeds.append({
            "title": "\U0001f4e1 시그널 요약",
            "description": (
                f"\U0001f7e2 BUY: {buy_count} | \U0001f534 SELL: {sell_count} | "
                f"\U0001f7e1 HOLD: {hold_count}\n"
                f"\U0001f6d1 Hard Limit: {hl_count}건"
            ),
            "color": 0x2ECC71,
        })

    # ── Performance Tracking ──
    perf = data["performance"]
    if perf["total"] > 0:
        perf_lines = [
            f"추적 시그널: {perf['total']}건",
        ]
        if perf["hit_rate_t5"] is not None:
            perf_lines.append(f"T+5 적중률: {perf['hit_rate_t5']:.0%}")
        if perf["hit_rate_t20"] is not None:
            perf_lines.append(f"T+20 적중률: {perf['hit_rate_t20']:.0%}")
        if perf["avg_return_t5"] is not None:
            perf_lines.append(f"T+5 평균수익: {perf['avg_return_t5']:+.2f}%")
        if perf["avg_return_t20"] is not None:
            perf_lines.append(f"T+20 평균수익: {perf['avg_return_t20']:+.2f}%")

        embeds.append({
            "title": "\U0001f3af 시그널 성과",
            "description": "\n".join(perf_lines),
            "color": 0xF1C40F,
        })

    # ── Top BUY Signals ──
    top_buys = [s for s in signals if s["final_signal"] == "BUY"]
    top_buys.sort(key=lambda s: s.get("raw_score") if s.get("raw_score") is not None else 0, reverse=True)
    if top_buys[:5]:
        lines = []
        for s in top_buys[:5]:
            name = s.get("name", s["symbol"])
            raw = s.get("raw_score") if s.get("raw_score") is not None else 0
            rsi = s.get("rsi_value") if s.get("rsi_value") is not None else 0
            lines.append(f"**{name}** (score: {raw:+.1f}, RSI: {rsi:.0f})")
        embeds.append({
            "title": "\U0001f7e2 주간 Top BUY",
            "description": "\n".join(lines),
            "color": 0x2ECC71,
        })

    # ── Footer ──
    embeds.append({
        "description": f"Generated: {now.strftime('%Y-%m-%d %H:%M')} UTC",
        "color": 0x888888,
        "footer": {"text": "VIBE Weekly Report | UFS"},
    })

    return [{"username": "VIBE", "embeds": embeds}]


async def _gather_weekly_data(start_date: str, end_date: str) -> dict[str, Any]:
    """Gather all data needed for the weekly report."""
    db = await get_db()

    # Pipeline runs
    cursor = await db.execute(
        """SELECT market, status, started_at FROM pipeline_runs
           WHERE started_at >= ? AND started_at <= ?
           ORDER BY started_at""",
        (start_date, end_date + "T23:59:59"),
    )
    pipeline_runs = [dict(r) for r in await cursor.fetchall()]

    # Signals
    cursor = await db.execute(
        """SELECT s.*, w.name FROM signals s
           LEFT JOIN watchlist w ON s.symbol = w.symbol AND s.market = w.market
           WHERE s.signal_date >= ? AND s.signal_date <= ?
           ORDER BY s.raw_score DESC""",
        (start_date, end_date),
    )
    signals = [dict(r) for r in await cursor.fetchall()]

    # Performance
    cursor = await db.execute(
        """SELECT
            COUNT(*) as total,
            AVG(CASE WHEN is_correct_t5 IS NOT NULL THEN is_correct_t5 END) as hit_rate_t5,
            AVG(CASE WHEN is_correct_t20 IS NOT NULL THEN is_correct_t20 END) as hit_rate_t20,
            AVG(return_t5) as avg_return_t5,
            AVG(return_t20) as avg_return_t20
           FROM signal_performance
           WHERE signal_date >= ? AND signal_date <= ?""",
        (start_date, end_date),
    )
    perf_row = await cursor.fetchone()
    performance = dict(perf_row) if perf_row else {}
    # Ensure total is always numeric (COUNT(*) returns 0 for empty, but guard against None)
    if performance.get("total") is None:
        performance["total"] = 0

    return {
        "pipeline_runs": pipeline_runs,
        "signals": signals,
        "performance": performance,
    }
