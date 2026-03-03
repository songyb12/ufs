"""Base pipeline stage interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class StageResult:
    """Result of a pipeline stage execution."""

    stage_name: str
    status: str  # success, partial, failed, skipped
    data: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class BaseStage(ABC):
    """Base class for all pipeline stages."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Stage identifier, e.g. 's1_data_collection'."""
        ...

    @abstractmethod
    async def execute(self, context: dict[str, Any], market: str) -> StageResult:
        """Run this stage. Returns StageResult with data for next stage."""
        ...

    def validate_input(self, context: dict[str, Any]) -> bool:
        """Check that required data from prior stages exists.
        Override in subclasses to add specific validation.
        Returns True by default (stage will run).
        """
        return True
