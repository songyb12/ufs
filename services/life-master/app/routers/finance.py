"""Finance Manager — Cards, Subscriptions, Expenses, Assets, Budget."""

import re

from fastapi import APIRouter, HTTPException, Query

from app.database import finance_repo as repo
from app.models.schemas_finance import (
    AssetCreate, AssetUpdate,
    BenefitCreate, BenefitUpdate,
    BudgetEntry,
    CardCreate, CardUpdate,
    ExpenseCreate, ExpenseUpdate,
    SubscriptionCreate, SubscriptionUpdate,
    UsageLog,
)

router = APIRouter(prefix="/finance", tags=["finance"])


# ── Dashboard ─────────────────────────────────────────────


@router.get("/dashboard")
async def finance_dashboard():
    return await repo.get_finance_dashboard()


# ── Cards ──────────────────────────────────────────────────


@router.get("/cards")
async def list_cards(active_only: bool = True):
    return await repo.get_cards(active_only)


@router.post("/cards")
async def create_card(body: CardCreate):
    return await repo.create_card(body.model_dump())


@router.get("/cards/recommend")
async def recommend_card(
    category: str = Query(...),
    merchant: str | None = Query(default=None),
):
    results = await repo.recommend_card(category, merchant)
    return {"recommendations": results}


@router.get("/cards/{card_id}")
async def get_card(card_id: int):
    card = await repo.get_card(card_id)
    if not card:
        raise HTTPException(404, "Card not found")
    card["benefits"] = await repo.get_card_benefits(card_id)
    return card


@router.put("/cards/{card_id}")
async def update_card(card_id: int, body: CardUpdate):
    data = body.model_dump(exclude_unset=True)
    result = await repo.update_card(card_id, data)
    if not result:
        raise HTTPException(404, "Card not found")
    return result


@router.delete("/cards/{card_id}")
async def delete_card(card_id: int):
    await repo.delete_card(card_id)
    return {"status": "deleted"}


@router.get("/cards/{card_id}/benefits")
async def list_benefits(card_id: int):
    return await repo.get_card_benefits(card_id)


@router.post("/cards/{card_id}/benefits")
async def add_benefit(card_id: int, body: BenefitCreate):
    return await repo.create_benefit(card_id, body.model_dump())


@router.put("/cards/benefits/{benefit_id}")
async def update_benefit(benefit_id: int, body: BenefitUpdate):
    data = body.model_dump(exclude_unset=True)
    result = await repo.update_benefit(benefit_id, data)
    if not result:
        raise HTTPException(404, "Benefit not found")
    return result


@router.delete("/cards/benefits/{benefit_id}")
async def delete_benefit(benefit_id: int):
    await repo.delete_benefit(benefit_id)
    return {"status": "deleted"}


# ── Subscriptions ──────────────────────────────────────────


@router.get("/subscriptions")
async def list_subscriptions(active_only: bool = True):
    return await repo.get_subscriptions(active_only)


@router.post("/subscriptions")
async def create_subscription(body: SubscriptionCreate):
    return await repo.create_subscription(body.model_dump())


@router.get("/subscriptions/alerts")
async def subscription_alerts():
    return await repo.get_unused_alerts()


@router.get("/subscriptions/summary")
async def subscription_summary():
    return await repo.get_subscription_summary()


@router.get("/subscriptions/{sub_id}")
async def get_subscription(sub_id: int):
    sub = await repo.get_subscription(sub_id)
    if not sub:
        raise HTTPException(404, "Subscription not found")
    return sub


@router.put("/subscriptions/{sub_id}")
async def update_subscription(sub_id: int, body: SubscriptionUpdate):
    data = body.model_dump(exclude_unset=True)
    result = await repo.update_subscription(sub_id, data)
    if not result:
        raise HTTPException(404, "Subscription not found")
    return result


@router.delete("/subscriptions/{sub_id}")
async def delete_subscription(sub_id: int):
    await repo.delete_subscription(sub_id)
    return {"status": "deleted"}


@router.post("/subscriptions/{sub_id}/use")
async def log_subscription_usage(sub_id: int, body: UsageLog | None = None):
    benefit_used = body.benefit_used if body else None
    note = body.note if body else None
    return await repo.log_usage(sub_id, benefit_used, note)


@router.get("/subscriptions/{sub_id}/usage")
async def get_usage_history(sub_id: int, limit: int = 30):
    return await repo.get_usage_history(sub_id, limit)


# ── Expenses ──────────────────────────────────────────────


@router.get("/expenses")
async def list_expenses(
    date_from: str | None = None,
    date_to: str | None = None,
    category: str | None = None,
    card_id: int | None = None,
    limit: int = 100,
):
    return await repo.get_expenses(date_from, date_to, category, card_id, limit)


@router.post("/expenses")
async def create_expense(body: ExpenseCreate):
    return await repo.create_expense(body.model_dump())


def _resolve_month(year_month: str | None) -> str:
    from datetime import datetime, timezone
    if not year_month:
        return datetime.now(timezone.utc).strftime("%Y-%m")
    if not re.match(r"^\d{4}-\d{2}$", year_month):
        raise HTTPException(400, "year_month must be YYYY-MM format")
    return year_month


@router.get("/expenses/summary")
async def expense_summary(year_month: str | None = None):
    return await repo.get_expense_summary(_resolve_month(year_month))


@router.get("/expenses/trend")
async def expense_trend(months: int = Query(default=6, ge=1, le=24)):
    return await repo.get_expense_trend(months)


@router.get("/expenses/by-card")
async def expense_by_card(year_month: str | None = None):
    return await repo.get_expense_by_card(_resolve_month(year_month))


@router.put("/expenses/{expense_id}")
async def update_expense(expense_id: int, body: ExpenseUpdate):
    data = body.model_dump(exclude_unset=True)
    result = await repo.update_expense(expense_id, data)
    if not result:
        raise HTTPException(404, "Expense not found")
    return result


@router.delete("/expenses/{expense_id}")
async def delete_expense(expense_id: int):
    await repo.delete_expense(expense_id)
    return {"status": "deleted"}


# ── Assets ────────────────────────────────────────────────


@router.get("/assets")
async def list_assets(active_only: bool = True):
    return await repo.get_assets(active_only)


@router.post("/assets")
async def create_asset(body: AssetCreate):
    return await repo.create_asset(body.model_dump())


@router.get("/assets/overview")
async def asset_overview():
    return await repo.get_asset_overview()


@router.put("/assets/{asset_id}")
async def update_asset(asset_id: int, body: AssetUpdate):
    data = body.model_dump(exclude_unset=True)
    result = await repo.update_asset(asset_id, data)
    if not result:
        raise HTTPException(404, "Asset not found")
    return result


@router.delete("/assets/{asset_id}")
async def delete_asset(asset_id: int):
    await repo.delete_asset(asset_id)
    return {"status": "deleted"}


# ── Budget ────────────────────────────────────────────────


@router.get("/budget/{year_month}")
async def get_budget(year_month: str):
    return await repo.get_budget(year_month)


@router.put("/budget/{year_month}")
async def set_budget(year_month: str, entries: list[BudgetEntry]):
    return await repo.set_budget(year_month, [e.model_dump() for e in entries])


@router.get("/budget/{year_month}/status")
async def budget_status(year_month: str):
    return await repo.get_budget_status(year_month)


# ── Seed ──────────────────────────────────────────────────


@router.post("/seed")
async def seed_data():
    return await repo.seed_finance_data()
