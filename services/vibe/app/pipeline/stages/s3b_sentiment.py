"""Stage 3b: Sentiment Analysis - Fear & Greed, Put/Call, VIX structure."""

import logging
from typing import Any

from app.collectors.sentiment import (
    fetch_fear_greed_index,
    fetch_put_call_ratio,
    fetch_vix_term_structure,
)
from app.config import Settings
from app.database import repositories as repo
from app.indicators.sentiment import compute_sentiment_score
from app.pipeline.base import BaseStage, StageResult

logger = logging.getLogger("vibe.pipeline.s3b")


class SentimentAnalysisStage(BaseStage):
    """Stage 3b: Collect sentiment data and compute score."""

    def __init__(self, config: Settings):
        self.config = config

    @property
    def name(self) -> str:
        return "s3b_sentiment_analysis"

    def validate_input(self, context: dict[str, Any]) -> bool:
        return self.config.SENTIMENT_FETCH_ENABLED

    async def execute(self, context: dict[str, Any], market: str) -> StageResult:
        warnings = []
        raw_data = {}

        # Fetch sentiment data sources
        try:
            fg_data = await fetch_fear_greed_index()
            raw_data.update(fg_data)
            if fg_data:
                logger.info("[S3b] Fear & Greed: %s (%s)",
                           fg_data.get("fear_greed_index"),
                           fg_data.get("fear_greed_label"))
        except Exception as e:
            warnings.append(f"Fear & Greed fetch failed: {e}")

        try:
            vix_data = await fetch_vix_term_structure()
            raw_data.update(vix_data)
            if vix_data:
                logger.info("[S3b] VIX structure: %s (ratio=%.3f)",
                           vix_data.get("vix_term_structure"),
                           vix_data.get("vix_ratio", 0))
        except Exception as e:
            warnings.append(f"VIX term structure fetch failed: {e}")

        try:
            pcr_data = await fetch_put_call_ratio()
            raw_data.update(pcr_data)
            if pcr_data:
                logger.info("[S3b] Put/Call ratio: %.3f",
                           pcr_data.get("put_call_ratio", 0))
        except Exception as e:
            warnings.append(f"Put/Call ratio fetch failed: {e}")

        if not raw_data:
            return StageResult(
                stage_name=self.name,
                status="skipped",
                data={},
                warnings=["No sentiment data available"],
            )

        # Compute sentiment score
        result = compute_sentiment_score(raw_data)

        # Store to DB
        try:
            trade_date = context.get("date", "")
            await repo.upsert_sentiment_data({
                "indicator_date": trade_date,
                "fear_greed_index": raw_data.get("fear_greed_index"),
                "put_call_ratio": raw_data.get("put_call_ratio"),
                "vix_term_structure": raw_data.get("vix_term_structure"),
            })
        except Exception as e:
            warnings.append(f"Sentiment DB store failed: {e}")

        logger.info("[S3b] Sentiment score: %+.1f", result["sentiment_score"])

        return StageResult(
            stage_name=self.name,
            status="success",
            data={
                "sentiment_score": result["sentiment_score"],
                "raw_data": raw_data,
                "components": result["components"],
            },
            warnings=warnings,
        )
