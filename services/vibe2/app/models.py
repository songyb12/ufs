"""Pydantic models for request/response schemas."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class SignalLevel(str, Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"


class PriceRecord(BaseModel):
    symbol: str
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int


class MacroRecord(BaseModel):
    date: str
    vix: float | None = None
    dxy: float | None = None
    us_10y: float | None = None
    us_2y: float | None = None
    yield_spread: float | None = None


class SentimentRecord(BaseModel):
    date: str
    fear_greed: int | None = None
    put_call_ratio: float | None = None
    vix_term: str | None = None


class SignalResult(BaseModel):
    signal: SignalLevel
    score: float = Field(..., ge=-100, le=100)
    summary: str
    details: dict = Field(default_factory=dict)
    action: str
    risks: list[str] = Field(default_factory=list)


class BriefingResponse(BaseModel):
    date: str
    signal: SignalResult
    macro: MacroRecord | None = None
    sentiment: SentimentRecord | None = None
    commentary: str | None = None
    generated_at: datetime | None = None


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    token: str
    username: str
    expires_in: int
