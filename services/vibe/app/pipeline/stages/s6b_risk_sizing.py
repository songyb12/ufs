"""Stage 6b: Risk Sizing - Position sizing, sector exposure, event calendar."""

import logging
from typing import Any

from app.config import Settings
from app.pipeline.base import BaseStage, StageResult
from app.risk.correlation import check_concurrent_signals, compute_return_correlation
from app.risk.events import EventCalendar
from app.risk.position_sizing import PositionSizer
from app.risk.sector import get_sector

logger = logging.getLogger("vibe.pipeline.s6b")


class RiskSizingStage(BaseStage):
    """Stage 6b: Compute position sizing, check events, correlation."""

    def __init__(self, config: Settings):
        self.config = config
        self.sizer = PositionSizer(config)
        self.calendar = EventCalendar()

    @property
    def name(self) -> str:
        return "s6b_risk_sizing"

    def validate_input(self, context: dict) -> bool:
        return "s6_signal_generation" in context

    async def execute(self, context: dict, market: str) -> StageResult:
        s6 = context.get("s6_signal_generation")
        if not s6 or s6.status not in ("success", "partial"):
            return StageResult(stage_name=self.name, status="skipped", data={}, warnings=["No S6 data"])

        per_symbol = s6.data.get("per_symbol", {})
        warnings: list[str] = []

        # Get BUY signals
        buy_signals = {
            sym: sig for sym, sig in per_symbol.items()
            if sig.get("final_signal") == "BUY"
        }

        # Current portfolio (empty for now - will be populated as system tracks trades)
        current_positions: dict[str, float] = {}

        # ── Event Calendar Check ──
        if self.config.EVENT_SUPPRESS_ENABLED:
            market_events = await self.calendar.check_upcoming_events(market)
            if market_events:
                for event in market_events:
                    warnings.append(
                        f"Event D-3: {event['description']} ({event['event_date']})"
                    )
                suppress, reason = self.calendar.should_suppress_signal(market_events)
                if suppress:
                    for sym in buy_signals:
                        per_symbol[sym]["event_warning"] = reason
                        warnings.append(f"{sym}: {reason}")

        # ── Position Sizing for BUY signals ──
        for sym, sig in buy_signals.items():
            sig["symbol"] = sym  # Ensure symbol is in signal dict
            rec = self.sizer.compute(sig, current_positions)

            per_symbol[sym]["position_recommendation"] = {
                "recommended_pct": rec.recommended_pct,
                "recommended_amount": rec.recommended_amount,
                "sizing_method": rec.sizing_method,
                "confidence_factor": rec.confidence_factor,
                "sector": rec.sector,
                "sector_exposure_current": rec.sector_exposure_current,
                "sector_constraint_applied": rec.sector_constraint_applied,
                "rationale": rec.rationale,
            }

            # Update tracking of positions for sector limits
            current_positions[sym] = rec.recommended_pct

        # ── Correlation Check ──
        if len(buy_signals) >= 2:
            s1 = context.get("s1_data_collection")
            if s1 and s1.data.get("ohlcv_data"):
                buy_price_data = {
                    sym: s1.data["ohlcv_data"].get(sym)
                    for sym in buy_signals
                    if s1.data["ohlcv_data"].get(sym) is not None
                }
                if len(buy_price_data) >= 2:
                    corr_matrix = compute_return_correlation(buy_price_data)
                    corr_warnings = check_concurrent_signals(
                        list(buy_signals.keys()), corr_matrix
                    )
                    for w in corr_warnings:
                        warnings.append(f"Correlation: {w}")
                        # Annotate affected signals
                        for sym in buy_signals:
                            if sym in w:
                                per_symbol[sym]["correlation_warning"] = w

        # Add sector info to all signals
        for sym in per_symbol:
            per_symbol[sym]["sector"] = get_sector(sym)

        # Collect global event descriptions for formatter
        global_events = []
        if self.config.EVENT_SUPPRESS_ENABLED:
            try:
                market_events = await self.calendar.check_upcoming_events(market)
                global_events = [
                    f"{e['event_type'].upper()}: {e['description']} ({e['event_date']})"
                    for e in market_events[:5]
                ]
            except Exception:
                pass  # Already handled above

        return StageResult(
            stage_name=self.name,
            status="success",
            data={
                "per_symbol": per_symbol,
                "global_events": global_events,
            },
            warnings=warnings,
        )
