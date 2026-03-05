"""Price alert system - sends Discord alerts for critical conditions.

Checks:
1. Portfolio positions approaching stop-loss
2. RSI approaching hard limit (>60) for BUY signals
3. Significant intraday price moves (>3%)
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from app.config import Settings
from app.database.connection import get_db

logger = logging.getLogger("vibe.notifier.alerts")


async def check_and_send_alerts(config: Settings) -> int:
    """Check for alert conditions and send to Discord.

    Returns number of alerts sent.
    """
    if not config.DISCORD_WEBHOOK_URL:
        return 0

    from app.database import repositories as repo

    # Load alert thresholds from DB (fallback to config defaults)
    alert_config_rows = await repo.get_alert_config()
    alert_cfg = {r["key"]: r["value"] for r in alert_config_rows}

    alerts = []

    # 1. Check portfolio stop-loss proximity
    portfolio_alerts = await _check_portfolio_stops(config, alert_cfg)
    alerts.extend(portfolio_alerts)

    # 2. Check RSI approaching hard limit
    rsi_alerts = await _check_rsi_alerts(config, alert_cfg)
    alerts.extend(rsi_alerts)

    if not alerts:
        return 0

    # Build Discord embed
    alert_lines = alerts[:15]  # Max 15 alerts per check
    embed = {
        "title": "\u26a0\ufe0f VIBE 알림",
        "description": "\n".join(alert_lines),
        "color": 0xFF6600,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "footer": {"text": "VIBE Alert System"},
    }

    payload = {"username": "VIBE Alert", "embeds": [embed]}

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                config.DISCORD_WEBHOOK_URL,
                json=payload,
                timeout=15.0,
            )
            if resp.status_code == 204:
                logger.info("Sent %d price alerts", len(alerts))
            else:
                logger.error("Alert send failed: %d", resp.status_code)
    except Exception as e:
        logger.error("Alert send error: %s", e)

    # Log alerts to history
    for alert_msg in alerts[:15]:
        try:
            await repo.insert_alert_history({
                "alert_type": "price_alert",
                "condition": alert_msg[:200],
                "message": alert_msg,
                "sent_to": "discord",
            })
        except Exception as e:
            logger.warning("Failed to log alert history: %s", e)

    return len(alerts)


async def _check_portfolio_stops(config: Settings, alert_cfg: dict | None = None) -> list[str]:
    """Check if any portfolio positions are near stop-loss."""
    alerts = []
    db = await get_db()

    # Get portfolio positions with latest prices
    cursor = await db.execute(
        """SELECT ps.symbol, ps.market, ps.entry_price, ps.position_size,
                  w.name,
                  (SELECT close FROM price_history ph
                   WHERE ph.symbol = ps.symbol AND ph.market = ps.market
                   ORDER BY trade_date DESC LIMIT 1) as current_price
           FROM portfolio_state ps
           LEFT JOIN watchlist w ON ps.symbol = w.symbol AND ps.market = w.market
           WHERE ps.position_size > 0"""
    )
    rows = await cursor.fetchall()

    stop_pct = float((alert_cfg or {}).get("stop_loss_pct", str(config.BACKTEST_STOP_LOSS_PCT)))

    for row in rows:
        r = dict(row)
        entry = r.get("entry_price")
        current = r.get("current_price")
        name = r.get("name", r["symbol"])

        if not entry or not current:
            continue

        pnl_pct = (current - entry) / entry * 100
        stop_price = entry * (1 + stop_pct / 100)
        distance_to_stop = (current - stop_price) / current * 100

        if pnl_pct <= stop_pct:
            alerts.append(
                f"\U0001f6a8 **{name}**: 손절가 하회! "
                f"P&L {pnl_pct:+.1f}% (현재 \u20a9{current:,.0f})"
            )
        elif distance_to_stop <= 2.0:
            alerts.append(
                f"\u26a0\ufe0f **{name}**: 손절가 접근 "
                f"(현재 {pnl_pct:+.1f}%, 손절까지 {distance_to_stop:.1f}%p)"
            )

    return alerts


async def _check_rsi_alerts(config: Settings, alert_cfg: dict | None = None) -> list[str]:
    """Check for RSI approaching hard limit on recent BUY signals."""
    alerts = []
    db = await get_db()

    rsi_threshold = float((alert_cfg or {}).get("rsi_warning_threshold", "58"))

    # Get latest signals with current RSI
    cursor = await db.execute(
        """SELECT s.symbol, s.market, s.final_signal, s.rsi_value, w.name
           FROM signals s
           LEFT JOIN watchlist w ON s.symbol = w.symbol AND s.market = w.market
           WHERE s.signal_date = (SELECT MAX(signal_date) FROM signals)
           AND s.final_signal = 'BUY'
           AND s.rsi_value > ?""",
        (rsi_threshold,),
    )
    rows = await cursor.fetchall()

    for row in rows:
        r = dict(row)
        name = r.get("name", r["symbol"])
        rsi = r.get("rsi_value", 0)
        alerts.append(
            f"\U0001f7e0 **{name}**: RSI {rsi:.0f} (Hard Limit 65 접근)"
        )

    return alerts
