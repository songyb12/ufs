"""Data access layer for Finance Manager module."""

import json
from datetime import datetime, timedelta, timezone

from app.database.connection import get_db


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _this_month() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


# Column whitelists for safe dynamic updates
_CARD_COLS = {"name", "issuer", "card_type", "last_four", "billing_day",
              "annual_fee", "annual_fee_waived", "color", "icon", "memo", "is_active"}
_BENEFIT_COLS = {"category", "merchant", "benefit_type", "benefit_value",
                 "benefit_unit", "monthly_limit", "min_spend", "conditions", "is_active"}
_SUB_COLS = {"name", "category", "price", "billing_cycle", "billing_day", "card_id",
             "is_free_bundled", "bundled_via", "benefits_json", "usage_check_interval",
             "url", "icon", "memo", "is_active", "start_date", "last_used_at"}
_EXPENSE_COLS = {"date", "amount", "category", "subcategory", "merchant",
                 "card_id", "description", "is_recurring"}
_ASSET_COLS = {"name", "asset_type", "institution", "balance", "currency", "memo", "is_active"}


def _safe_update(data: dict, allowed: set) -> tuple[list[str], list]:
    """Build SET clause from data, whitelisting column names."""
    sets = []
    vals = []
    for k, v in data.items():
        if k in allowed:
            sets.append(f"{k} = ?")
            vals.append(v)
    return sets, vals


# ── Cards ──────────────────────────────────────────────────


async def get_cards(active_only: bool = True) -> list[dict]:
    db = await get_db()
    q = "SELECT * FROM fin_cards"
    if active_only:
        q += " WHERE is_active = 1"
    q += " ORDER BY name"
    cursor = await db.execute(q)
    return [dict(r) for r in await cursor.fetchall()]


async def get_card(card_id: int) -> dict | None:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM fin_cards WHERE id = ?", (card_id,))
    row = await cursor.fetchone()
    return dict(row) if row else None


async def create_card(data: dict) -> dict:
    db = await get_db()
    cols = ["name", "issuer", "card_type", "last_four", "billing_day",
            "annual_fee", "annual_fee_waived", "color", "icon", "memo"]
    vals = [data.get(c) for c in cols]
    placeholders = ", ".join(["?"] * len(cols))
    col_names = ", ".join(cols)
    cursor = await db.execute(
        f"INSERT INTO fin_cards ({col_names}) VALUES ({placeholders})", vals
    )
    await db.commit()
    return await get_card(cursor.lastrowid)  # type: ignore


async def update_card(card_id: int, data: dict) -> dict | None:
    db = await get_db()
    sets, vals = _safe_update(data, _CARD_COLS)
    if not sets:
        return await get_card(card_id)
    sets.append("updated_at = ?")
    vals.append(_now())
    vals.append(card_id)
    await db.execute(f"UPDATE fin_cards SET {', '.join(sets)} WHERE id = ?", vals)
    await db.commit()
    return await get_card(card_id)


async def delete_card(card_id: int) -> bool:
    db = await get_db()
    await db.execute("UPDATE fin_cards SET is_active = 0, updated_at = ? WHERE id = ?",
                     (_now(), card_id))
    await db.commit()
    return True


# ── Card Benefits ──────────────────────────────────────────


async def get_card_benefits(card_id: int) -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM fin_card_benefits WHERE card_id = ? AND is_active = 1 ORDER BY category", (card_id,)
    )
    return [dict(r) for r in await cursor.fetchall()]


async def create_benefit(card_id: int, data: dict) -> dict:
    db = await get_db()
    cursor = await db.execute(
        """INSERT INTO fin_card_benefits
           (card_id, category, merchant, benefit_type, benefit_value, benefit_unit, monthly_limit, min_spend, conditions)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (card_id, data["category"], data.get("merchant"), data.get("benefit_type", "DISCOUNT"),
         data.get("benefit_value", 0), data.get("benefit_unit", "PERCENT"),
         data.get("monthly_limit"), data.get("min_spend"), data.get("conditions"))
    )
    await db.commit()
    row = await db.execute("SELECT * FROM fin_card_benefits WHERE id = ?", (cursor.lastrowid,))
    return dict(await row.fetchone())


async def update_benefit(benefit_id: int, data: dict) -> dict | None:
    db = await get_db()
    sets, vals = _safe_update(data, _BENEFIT_COLS)
    if not sets:
        return None
    vals.append(benefit_id)
    await db.execute(f"UPDATE fin_card_benefits SET {', '.join(sets)} WHERE id = ?", vals)
    await db.commit()
    cursor = await db.execute("SELECT * FROM fin_card_benefits WHERE id = ?", (benefit_id,))
    row = await cursor.fetchone()
    return dict(row) if row else None


async def delete_benefit(benefit_id: int) -> bool:
    db = await get_db()
    await db.execute("UPDATE fin_card_benefits SET is_active = 0 WHERE id = ?", (benefit_id,))
    await db.commit()
    return True


async def recommend_card(category: str, merchant: str | None = None) -> list[dict]:
    db = await get_db()
    q = """SELECT b.*, c.name as card_name, c.color as card_color, c.icon as card_icon
           FROM fin_card_benefits b
           JOIN fin_cards c ON c.id = b.card_id
           WHERE b.is_active = 1 AND c.is_active = 1 AND b.category = ?"""
    params: list = [category]
    if merchant:
        q += " AND (b.merchant = ? OR b.merchant IS NULL)"
        params.append(merchant)
    q += " ORDER BY b.benefit_value DESC"
    cursor = await db.execute(q, params)
    return [dict(r) for r in await cursor.fetchall()]


# ── Subscriptions ──────────────────────────────────────────


async def get_subscriptions(active_only: bool = True) -> list[dict]:
    db = await get_db()
    q = """SELECT s.*, c.name as card_name
           FROM fin_subscriptions s
           LEFT JOIN fin_cards c ON c.id = s.card_id"""
    if active_only:
        q += " WHERE s.is_active = 1"
    q += " ORDER BY s.name"
    cursor = await db.execute(q)
    rows = [dict(r) for r in await cursor.fetchall()]
    for r in rows:
        try:
            r["benefits"] = json.loads(r.get("benefits_json") or "[]")
        except (json.JSONDecodeError, TypeError):
            r["benefits"] = []
    return rows


async def get_subscription(sub_id: int) -> dict | None:
    db = await get_db()
    cursor = await db.execute(
        """SELECT s.*, c.name as card_name
           FROM fin_subscriptions s
           LEFT JOIN fin_cards c ON c.id = s.card_id
           WHERE s.id = ?""", (sub_id,)
    )
    row = await cursor.fetchone()
    if not row:
        return None
    d = dict(row)
    try:
        d["benefits"] = json.loads(d.get("benefits_json") or "[]")
    except (json.JSONDecodeError, TypeError):
        d["benefits"] = []
    return d


async def create_subscription(data: dict) -> dict:
    db = await get_db()
    cols = ["name", "category", "price", "billing_cycle", "billing_day", "card_id",
            "is_free_bundled", "bundled_via", "benefits_json", "usage_check_interval",
            "url", "icon", "memo", "start_date"]
    vals = [data.get(c) for c in cols]
    placeholders = ", ".join(["?"] * len(cols))
    col_names = ", ".join(cols)
    cursor = await db.execute(
        f"INSERT INTO fin_subscriptions ({col_names}) VALUES ({placeholders})", vals
    )
    await db.commit()
    return await get_subscription(cursor.lastrowid)  # type: ignore


async def update_subscription(sub_id: int, data: dict) -> dict | None:
    db = await get_db()
    sets, vals = _safe_update(data, _SUB_COLS)
    if not sets:
        return await get_subscription(sub_id)
    sets.append("updated_at = ?")
    vals.append(_now())
    vals.append(sub_id)
    await db.execute(f"UPDATE fin_subscriptions SET {', '.join(sets)} WHERE id = ?", vals)
    await db.commit()
    return await get_subscription(sub_id)


async def delete_subscription(sub_id: int) -> bool:
    db = await get_db()
    await db.execute("UPDATE fin_subscriptions SET is_active = 0, updated_at = ? WHERE id = ?",
                     (_now(), sub_id))
    await db.commit()
    return True


async def log_usage(sub_id: int, benefit_used: str | None = None, note: str | None = None) -> dict:
    db = await get_db()
    now = _now()
    cursor = await db.execute(
        "INSERT INTO fin_subscription_usage (subscription_id, used_at, benefit_used, note) VALUES (?, ?, ?, ?)",
        (sub_id, now, benefit_used, note)
    )
    await db.execute("UPDATE fin_subscriptions SET last_used_at = ?, updated_at = ? WHERE id = ?",
                     (now, now, sub_id))
    await db.commit()
    row = await db.execute("SELECT * FROM fin_subscription_usage WHERE id = ?", (cursor.lastrowid,))
    return dict(await row.fetchone())


async def get_usage_history(sub_id: int, limit: int = 30) -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM fin_subscription_usage WHERE subscription_id = ? ORDER BY used_at DESC LIMIT ?",
        (sub_id, limit)
    )
    return [dict(r) for r in await cursor.fetchall()]


async def get_unused_alerts() -> list[dict]:
    db = await get_db()
    cursor = await db.execute("""
        SELECT s.*, c.name as card_name,
            COALESCE(
                (SELECT MAX(used_at) FROM fin_subscription_usage WHERE subscription_id = s.id),
                s.start_date,
                s.created_at
            ) as last_activity,
            julianday('now') - julianday(COALESCE(
                (SELECT MAX(used_at) FROM fin_subscription_usage WHERE subscription_id = s.id),
                s.start_date,
                s.created_at
            )) as days_inactive
        FROM fin_subscriptions s
        LEFT JOIN fin_cards c ON c.id = s.card_id
        WHERE s.is_active = 1
        ORDER BY days_inactive DESC
    """)
    rows = [dict(r) for r in await cursor.fetchall()]
    alerts = []
    for r in rows:
        days = r.get("days_inactive") or 0
        interval = r.get("usage_check_interval") or 7
        if days > interval:
            severity = "WARNING"
            if days > interval * 2:
                severity = "CRITICAL"
            if days > interval * 3 and (r.get("price") or 0) > 0:
                severity = "WASTE"
            try:
                r["benefits"] = json.loads(r.get("benefits_json") or "[]")
            except (json.JSONDecodeError, TypeError):
                r["benefits"] = []
            r["severity"] = severity
            r["days_inactive"] = round(days, 1)
            alerts.append(r)
    return alerts


async def get_subscription_summary() -> dict:
    db = await get_db()
    cursor = await db.execute(
        "SELECT SUM(price) as total, COUNT(*) as count FROM fin_subscriptions WHERE is_active = 1 AND is_free_bundled = 0"
    )
    row = dict(await cursor.fetchone())
    cursor2 = await db.execute(
        "SELECT SUM(price) as saved, COUNT(*) as cnt FROM fin_subscriptions WHERE is_active = 1 AND is_free_bundled = 1"
    )
    saved_row = dict(await cursor2.fetchone())
    return {
        "monthly_total": row.get("total") or 0,
        "active_count": (row.get("count") or 0) + (saved_row.get("cnt") or 0),
        "free_bundled_savings": saved_row.get("saved") or 0,
    }


# ── Expenses ──────────────────────────────────────────────


async def get_expenses(
    date_from: str | None = None,
    date_to: str | None = None,
    category: str | None = None,
    card_id: int | None = None,
    limit: int = 100,
) -> list[dict]:
    db = await get_db()
    q = """SELECT e.*, c.name as card_name
           FROM fin_expenses e
           LEFT JOIN fin_cards c ON c.id = e.card_id
           WHERE 1=1"""
    params: list = []
    if date_from:
        q += " AND e.date >= ?"
        params.append(date_from)
    if date_to:
        q += " AND e.date <= ?"
        params.append(date_to)
    if category:
        q += " AND e.category = ?"
        params.append(category)
    if card_id:
        q += " AND e.card_id = ?"
        params.append(card_id)
    q += " ORDER BY e.date DESC, e.created_at DESC LIMIT ?"
    params.append(limit)
    cursor = await db.execute(q, params)
    return [dict(r) for r in await cursor.fetchall()]


async def create_expense(data: dict) -> dict:
    db = await get_db()
    cols = ["date", "amount", "category", "subcategory", "merchant", "card_id", "description", "is_recurring"]
    vals = [data.get(c) for c in cols]
    placeholders = ", ".join(["?"] * len(cols))
    col_names = ", ".join(cols)
    cursor = await db.execute(
        f"INSERT INTO fin_expenses ({col_names}) VALUES ({placeholders})", vals
    )
    await db.commit()
    row = await db.execute(
        "SELECT e.*, c.name as card_name FROM fin_expenses e LEFT JOIN fin_cards c ON c.id = e.card_id WHERE e.id = ?",
        (cursor.lastrowid,)
    )
    return dict(await row.fetchone())


async def update_expense(expense_id: int, data: dict) -> dict | None:
    db = await get_db()
    sets, vals = _safe_update(data, _EXPENSE_COLS)
    if not sets:
        return None
    vals.append(expense_id)
    await db.execute(f"UPDATE fin_expenses SET {', '.join(sets)} WHERE id = ?", vals)
    await db.commit()
    cursor = await db.execute(
        "SELECT e.*, c.name as card_name FROM fin_expenses e LEFT JOIN fin_cards c ON c.id = e.card_id WHERE e.id = ?",
        (expense_id,)
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def delete_expense(expense_id: int) -> bool:
    db = await get_db()
    await db.execute("DELETE FROM fin_expenses WHERE id = ?", (expense_id,))
    await db.commit()
    return True


async def get_expense_summary(year_month: str) -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        """SELECT category, SUM(amount) as total, COUNT(*) as count
           FROM fin_expenses WHERE date LIKE ? || '%'
           GROUP BY category ORDER BY total DESC""",
        (year_month,)
    )
    return [dict(r) for r in await cursor.fetchall()]


async def get_expense_trend(months: int = 6) -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        """SELECT strftime('%Y-%m', date) as month, SUM(amount) as total, COUNT(*) as count
           FROM fin_expenses
           GROUP BY month ORDER BY month DESC LIMIT ?""",
        (months,)
    )
    return [dict(r) for r in await cursor.fetchall()]


async def get_expense_by_card(year_month: str) -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        """SELECT c.id, c.name, c.color, c.icon, SUM(e.amount) as total, COUNT(e.id) as count
           FROM fin_expenses e
           LEFT JOIN fin_cards c ON c.id = e.card_id
           WHERE e.date LIKE ? || '%'
           GROUP BY e.card_id ORDER BY total DESC""",
        (year_month,)
    )
    return [dict(r) for r in await cursor.fetchall()]


# ── Assets ────────────────────────────────────────────────


async def get_assets(active_only: bool = True) -> list[dict]:
    db = await get_db()
    q = "SELECT * FROM fin_assets"
    if active_only:
        q += " WHERE is_active = 1"
    q += " ORDER BY asset_type, name"
    cursor = await db.execute(q)
    return [dict(r) for r in await cursor.fetchall()]


async def create_asset(data: dict) -> dict:
    db = await get_db()
    cols = ["name", "asset_type", "institution", "balance", "currency", "memo"]
    vals = [data.get(c) for c in cols]
    placeholders = ", ".join(["?"] * len(cols))
    col_names = ", ".join(cols)
    cursor = await db.execute(
        f"INSERT INTO fin_assets ({col_names}) VALUES ({placeholders})", vals
    )
    await db.commit()
    row = await db.execute("SELECT * FROM fin_assets WHERE id = ?", (cursor.lastrowid,))
    return dict(await row.fetchone())


async def update_asset(asset_id: int, data: dict) -> dict | None:
    db = await get_db()
    sets, vals = _safe_update(data, _ASSET_COLS)
    if not sets:
        return None
    sets.append("updated_at = ?")
    vals.append(_now())
    if "balance" in data:
        sets.append("last_updated = ?")
        vals.append(_now())
    vals.append(asset_id)
    await db.execute(f"UPDATE fin_assets SET {', '.join(sets)} WHERE id = ?", vals)
    await db.commit()
    cursor = await db.execute("SELECT * FROM fin_assets WHERE id = ?", (asset_id,))
    row = await cursor.fetchone()
    return dict(row) if row else None


async def delete_asset(asset_id: int) -> bool:
    db = await get_db()
    await db.execute("UPDATE fin_assets SET is_active = 0, updated_at = ? WHERE id = ?",
                     (_now(), asset_id))
    await db.commit()
    return True


async def get_asset_overview() -> dict:
    db = await get_db()
    cursor = await db.execute(
        """SELECT asset_type, SUM(balance) as total, COUNT(*) as count
           FROM fin_assets WHERE is_active = 1
           GROUP BY asset_type ORDER BY total DESC"""
    )
    groups = [dict(r) for r in await cursor.fetchall()]
    net_worth = sum(g["total"] or 0 for g in groups)
    return {"net_worth": net_worth, "groups": groups}


# ── Budget ────────────────────────────────────────────────


async def get_budget(year_month: str) -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM fin_budget WHERE year_month = ? ORDER BY budget_amount DESC",
        (year_month,)
    )
    return [dict(r) for r in await cursor.fetchall()]


async def set_budget(year_month: str, entries: list[dict]) -> list[dict]:
    db = await get_db()
    for entry in entries:
        await db.execute(
            """INSERT INTO fin_budget (year_month, category, budget_amount)
               VALUES (?, ?, ?)
               ON CONFLICT(year_month, category) DO UPDATE SET budget_amount = excluded.budget_amount""",
            (year_month, entry["category"], entry["budget_amount"])
        )
    await db.commit()
    return await get_budget(year_month)


async def get_budget_status(year_month: str) -> list[dict]:
    db = await get_db()
    budget = await get_budget(year_month)
    expenses = await get_expense_summary(year_month)
    expense_map = {e["category"]: e["total"] for e in expenses}
    result = []
    for b in budget:
        spent = expense_map.get(b["category"], 0)
        result.append({
            "category": b["category"],
            "budget": b["budget_amount"],
            "spent": spent,
            "remaining": b["budget_amount"] - spent,
            "percent": round(spent / b["budget_amount"] * 100, 1) if b["budget_amount"] > 0 else 0,
        })
    # Add categories with spending but no budget
    for e in expenses:
        if e["category"] not in [b["category"] for b in budget]:
            result.append({
                "category": e["category"],
                "budget": 0,
                "spent": e["total"],
                "remaining": -e["total"],
                "percent": 100,
            })
    return result


# ── Dashboard ─────────────────────────────────────────────


async def get_finance_dashboard() -> dict:
    month = _this_month()
    expenses = await get_expense_summary(month)
    monthly_spend = sum(e["total"] for e in expenses)

    budget = await get_budget(month)
    monthly_budget = sum(b["budget_amount"] for b in budget)

    sub_summary = await get_subscription_summary()
    asset_overview = await get_asset_overview()
    alerts = await get_unused_alerts()
    card_spend = await get_expense_by_card(month)

    return {
        "monthly_spend": monthly_spend,
        "monthly_budget": monthly_budget,
        "budget_remaining": monthly_budget - monthly_spend,
        "subscription_total": sub_summary["monthly_total"],
        "subscription_count": sub_summary["active_count"],
        "free_bundled_savings": sub_summary["free_bundled_savings"],
        "net_worth": asset_overview["net_worth"],
        "unused_alerts": [{"id": a["id"], "name": a["name"], "severity": a["severity"],
                           "days_inactive": a["days_inactive"], "price": a.get("price", 0),
                           "icon": a.get("icon")} for a in alerts[:5]],
        "top_categories": expenses[:5],
        "card_spend": card_spend,
    }


# ── Seed ──────────────────────────────────────────────────


async def seed_finance_data() -> dict:
    db = await get_db()

    # Check if already seeded
    cursor = await db.execute("SELECT COUNT(*) as cnt FROM fin_cards")
    if (await cursor.fetchone())["cnt"] > 0:
        return {"status": "already_seeded"}

    # Cards
    cards = [
        ("SK하이닉스 패밀리 카드", "KB국민카드", "CREDIT", "#00A0E0", "💙"),
        ("현대 네이버 카드", "현대카드", "CREDIT", "#1EC800", "💚"),
    ]
    card_ids = {}
    for name, issuer, ctype, color, icon in cards:
        cursor = await db.execute(
            "INSERT INTO fin_cards (name, issuer, card_type, color, icon) VALUES (?, ?, ?, ?, ?)",
            (name, issuer, ctype, color, icon)
        )
        card_ids[name] = cursor.lastrowid

    hynix_id = card_ids["SK하이닉스 패밀리 카드"]
    naver_id = card_ids["현대 네이버 카드"]

    # Card benefits (sample)
    benefits = [
        (hynix_id, "SHOPPING", None, "DISCOUNT", 5, "PERCENT", 50000, None),
        (hynix_id, "FOOD", None, "DISCOUNT", 5, "PERCENT", 30000, None),
        (hynix_id, "TRANSPORT", None, "DISCOUNT", 5, "PERCENT", 20000, None),
        (naver_id, "ONLINE", "네이버페이", "POINT", 1, "PERCENT", None, None),
        (naver_id, "MEMBERSHIP", "네이버 멤버십", "FREE_SERVICE", 100, "FREE", None, None),
        (naver_id, "SHOPPING", None, "POINT", 1.5, "PERCENT", None, 300000),
    ]
    for card_id, cat, merchant, btype, val, unit, limit, min_spend in benefits:
        await db.execute(
            """INSERT INTO fin_card_benefits
               (card_id, category, merchant, benefit_type, benefit_value, benefit_unit, monthly_limit, min_spend)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (card_id, cat, merchant, btype, val, unit, limit, min_spend)
        )

    # Subscriptions
    subs = [
        ("라프텔 (베이직)", "STREAMING", 5900, "MONTHLY", None, 0, None,
         '["애니 스트리밍 무제한"]', 7, "🎬"),
        ("넷플릭스", "STREAMING", 13500, "MONTHLY", None, 0, None,
         '["영상 스트리밍 무제한", "동시 2기기"]', 7, "📺"),
        ("네이버 멤버십", "MEMBERSHIP", 4900, "MONTHLY", naver_id, 1, "현대 네이버 카드",
         '["네이버 플러스 적립 추가 4%", "쿠키 무료", "네이버 웹툰 쿠키", "VIBE 이용권"]', 3, "💚"),
        ("쿠팡 로켓와우", "SHOPPING", 4990, "MONTHLY", None, 0, None,
         '["로켓배송 무료", "로켓프레시 무료배송", "쿠팡플레이"]', 7, "🚀"),
        ("T멤버십 할인형 VIP", "TELECOM", 0, "MONTHLY", None, 1, "SK텔레콤 요금제",
         '["영화관 할인", "편의점 할인", "카페 할인", "음식점 할인"]', 7, "📱"),
        ("T우주 패스 편의점&카페", "MEMBERSHIP", 13900, "MONTHLY", None, 0, None,
         '["유튜브 프리미엄", "편의점 할인 (CU/GS)", "카페 할인 (스타벅스/투썸)"]', 3, "🌌"),
    ]
    for name, cat, price, cycle, card_id, free, bundled, benefits_json, interval, icon in subs:
        await db.execute(
            """INSERT INTO fin_subscriptions
               (name, category, price, billing_cycle, card_id, is_free_bundled, bundled_via,
                benefits_json, usage_check_interval, icon, start_date)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (name, cat, price, cycle, card_id, free, bundled, benefits_json, interval, icon,
             (datetime.now(timezone.utc) - timedelta(days=15)).strftime("%Y-%m-%d"))
        )

    await db.commit()
    return {
        "status": "seeded",
        "cards": len(cards),
        "benefits": len(benefits),
        "subscriptions": len(subs),
    }
