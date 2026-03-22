"""Pydantic schemas for Finance Manager module."""

import json as _json

from pydantic import BaseModel, Field, field_validator


# ── Cards ──────────────────────────────────────────────────

class CardCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    issuer: str = ""
    card_type: str = "CREDIT"
    last_four: str | None = None
    billing_day: int | None = Field(default=None, ge=1, le=31)
    annual_fee: int = 0
    annual_fee_waived: bool = False
    color: str = "#6366f1"
    icon: str | None = None
    memo: str | None = None


class CardUpdate(BaseModel):
    name: str | None = None
    issuer: str | None = None
    card_type: str | None = None
    last_four: str | None = None
    billing_day: int | None = None
    annual_fee: int | None = None
    annual_fee_waived: bool | None = None
    color: str | None = None
    icon: str | None = None
    memo: str | None = None
    is_active: bool | None = None


# ── Card Benefits ──────────────────────────────────────────

class BenefitCreate(BaseModel):
    category: str
    merchant: str | None = None
    benefit_type: str = "DISCOUNT"
    benefit_value: float = 0
    benefit_unit: str = "PERCENT"
    monthly_limit: int | None = None
    min_spend: int | None = None
    conditions: str | None = None


class BenefitUpdate(BaseModel):
    category: str | None = None
    merchant: str | None = None
    benefit_type: str | None = None
    benefit_value: float | None = None
    benefit_unit: str | None = None
    monthly_limit: int | None = None
    min_spend: int | None = None
    conditions: str | None = None
    is_active: bool | None = None


# ── Subscriptions ──────────────────────────────────────────

class SubscriptionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    category: str = "OTHER"
    price: int = 0
    billing_cycle: str = "MONTHLY"
    billing_day: int | None = None
    card_id: int | None = None
    is_free_bundled: bool = False
    bundled_via: str | None = None
    benefits_json: str = "[]"
    usage_check_interval: int = Field(default=7, ge=1, le=90)

    @field_validator("benefits_json")
    @classmethod
    def valid_json_array(cls, v: str) -> str:
        parsed = _json.loads(v)
        if not isinstance(parsed, list):
            raise ValueError("benefits_json must be a JSON array")
        return v
    url: str | None = None
    icon: str | None = None
    memo: str | None = None
    start_date: str | None = None


class SubscriptionUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    price: int | None = None
    billing_cycle: str | None = None
    billing_day: int | None = None
    card_id: int | None = None
    is_free_bundled: bool | None = None
    bundled_via: str | None = None
    benefits_json: str | None = None
    usage_check_interval: int | None = None
    url: str | None = None
    icon: str | None = None
    memo: str | None = None
    is_active: bool | None = None
    start_date: str | None = None


class UsageLog(BaseModel):
    benefit_used: str | None = None
    note: str | None = None


# ── Expenses ──────────────────────────────────────────────

class ExpenseCreate(BaseModel):
    date: str
    amount: int = Field(ge=0)
    category: str = "OTHER"
    subcategory: str | None = None
    merchant: str | None = None
    card_id: int | None = None
    description: str | None = None
    is_recurring: bool = False


class ExpenseUpdate(BaseModel):
    date: str | None = None
    amount: int | None = None
    category: str | None = None
    subcategory: str | None = None
    merchant: str | None = None
    card_id: int | None = None
    description: str | None = None
    is_recurring: bool | None = None


# ── Assets ────────────────────────────────────────────────

class AssetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    asset_type: str = "CASH"
    institution: str | None = None
    balance: int = 0
    currency: str = "KRW"
    memo: str | None = None


class AssetUpdate(BaseModel):
    name: str | None = None
    asset_type: str | None = None
    institution: str | None = None
    balance: int | None = None
    currency: str | None = None
    memo: str | None = None
    is_active: bool | None = None


# ── Budget ────────────────────────────────────────────────

class BudgetEntry(BaseModel):
    category: str
    budget_amount: int = Field(ge=0)
