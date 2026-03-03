"""Stage 3: Macro Analysis - Score global macro environment."""

import logging
from typing import Any

from app.config import Settings
from app.database import repositories as repo
from app.indicators.macro import compute_macro_score
from app.pipeline.base import BaseStage, StageResult

logger = logging.getLogger("vibe.pipeline.s3")


class MacroAnalysisStage(BaseStage):
    def __init__(self, config: Settings):
        self.config = config

    @property
    def name(self) -> str:
        return "s3_macro_analysis"

    async def execute(self, context: dict[str, Any], market: str) -> StageResult:
        # Get macro data from S1 context or DB
        s1_data = context.get("s1_data_collection")
        macro_data = None

        if s1_data and s1_data.data.get("macro_data"):
            macro_data = s1_data.data["macro_data"]
        else:
            macro_data = await repo.get_latest_macro()

        if not macro_data:
            logger.warning("[S3] No macro data available")
            return StageResult(
                stage_name=self.name,
                status="partial",
                data={"macro_score": 0.0, "details": {}},
                warnings=["No macro data available, using neutral score"],
            )

        score_result = compute_macro_score(macro_data)

        logger.info(
            "[S3] Macro score: %.2f (VIX=%s, Yield=%s, FX=%s)",
            score_result["aggregate_score"],
            score_result["vix"]["label"],
            score_result["yield_curve"]["label"],
            score_result["fx"]["label"],
        )

        return StageResult(
            stage_name=self.name,
            status="success",
            data={
                "macro_score": score_result["aggregate_score"],
                "details": score_result,
                "raw_data": macro_data,
            },
        )
