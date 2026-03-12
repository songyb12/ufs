"""Pydantic schemas for POLARIS."""

from __future__ import annotations

from pydantic import BaseModel, Field


# ── Figure (인물) ──


class FigureCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    name_ko: str = Field("", max_length=200)
    role: str = Field("", max_length=200)
    country: str = Field("", max_length=10)
    party: str = Field("", max_length=100)


class FigureOut(BaseModel):
    id: str
    name: str
    name_ko: str
    role: str
    country: str
    party: str
    status: str
    created_at: str
    latest_profile_version: int | None = None


# ── Profile (인격 프로파일) ──


class PersonalityTraits(BaseModel):
    negotiation_style: str = ""
    decision_pattern: str = ""
    communication_style: str = ""
    risk_appetite: str = ""


class Relationship(BaseModel):
    name: str
    type: str = ""  # ally / rival / neutral / complex
    strength: str = ""  # strong / moderate / weak
    notes: str = ""


class BehavioralPattern(BaseModel):
    pattern: str
    description: str = ""


class HistoricalPrecedent(BaseModel):
    event: str
    action: str = ""
    outcome: str = ""
    date: str = ""


class MarketSensitivity(BaseModel):
    sectors: list[str] = []
    direction: str = ""  # positive / negative / mixed
    magnitude: str = ""  # high / medium / low


class ProfileData(BaseModel):
    """Structured personality profile — stored as JSON in DB."""

    core_values: list[str] = []
    personality_traits: PersonalityTraits = PersonalityTraits()
    political_positions: dict[str, str] = {}
    key_relationships: list[Relationship] = []
    behavioral_patterns: list[BehavioralPattern] = []
    historical_precedents: list[HistoricalPrecedent] = []
    market_sensitivities: dict[str, MarketSensitivity] = {}


class ProfileOut(BaseModel):
    id: str
    figure_id: str
    version: int
    profile_data: ProfileData
    changelog: str
    created_at: str


class ProfileHistoryItem(BaseModel):
    version: int
    changelog: str
    created_at: str


# ── Event ──


class EventCreate(BaseModel):
    event_type: str = Field("statement", max_length=50)
    title: str = Field(..., min_length=1, max_length=500)
    summary: str = ""
    source_url: str = ""
    event_date: str = ""
    significance: int = Field(2, ge=1, le=5)
    categories: list[str] = []


class EventOut(BaseModel):
    id: str
    figure_id: str
    event_type: str
    title: str
    summary: str
    source_url: str
    event_date: str
    significance: int
    categories: list[str] = []
    created_at: str


# ── Prediction ──


class MarketImpact(BaseModel):
    sectors: list[str] = []
    direction: str = ""
    magnitude: str = ""
    description: str = ""


class PredictionOut(BaseModel):
    id: str
    figure_id: str
    trigger_event_id: str | None = None
    prediction_type: str
    prediction: str
    reasoning: str
    confidence: float
    timeframe: str
    market_impact: MarketImpact | None = None
    status: str
    outcome: str | None = None
    created_at: str


class PredictionOutcomeUpdate(BaseModel):
    status: str = Field(..., pattern=r"^(confirmed|partially_confirmed|wrong)$")
    outcome: str = Field(..., min_length=1)


class PredictRequest(BaseModel):
    """Manual prediction trigger — optionally scope to a topic."""

    topic: str = ""
    context: str = ""


# ── News Scan ──


class NewsScanRequest(BaseModel):
    """Trigger manual news scan for a specific figure."""

    extra_keywords: list[str] = []
    max_articles: int = Field(10, ge=1, le=30)
    min_significance: int = Field(2, ge=1, le=5)


# ── Signal Bridge ──


class GeopoliticalAdjustmentRequest(BaseModel):
    symbol: str
    market: str
    sector: str = ""
