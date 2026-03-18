"""Japanese learning analytics — weakness, learning curve, SRS forecast, mastery, streak."""

import logging
from datetime import date, timedelta

from app.database.connection import get_db

logger = logging.getLogger("life-master.analytics")


# ── Weakness Analysis ─────────────────────────────────────


async def get_weakness_analysis() -> dict:
    """Analyze weak areas across vocab, grammar, kanji, reading."""
    db = await get_db()

    areas: dict[str, dict] = {}

    # 1) Vocab — from jp_quiz_results
    cursor = await db.execute(
        """SELECT jlpt_level,
                  COUNT(*) as quiz_count,
                  AVG(correct * 100.0 / total_questions) as avg_accuracy
           FROM jp_quiz_results
           WHERE quiz_type IN ('flashcard','reading_quiz','listening')
             AND total_questions > 0
           GROUP BY jlpt_level
           ORDER BY avg_accuracy ASC"""
    )
    vocab_by_level = [dict(r) for r in await cursor.fetchall()]
    total_vocab_acc = _safe_avg([r["avg_accuracy"] for r in vocab_by_level])
    areas["vocab"] = {"accuracy": round(total_vocab_acc, 1), "by_level": vocab_by_level}

    # 2) Grammar — from quiz results with grammar quiz types
    cursor = await db.execute(
        """SELECT jlpt_level,
                  COUNT(*) as quiz_count,
                  AVG(correct * 100.0 / total_questions) as avg_accuracy
           FROM jp_quiz_results
           WHERE quiz_type IN ('fill_blank','sentence_order')
             AND total_questions > 0
           GROUP BY jlpt_level
           ORDER BY avg_accuracy ASC"""
    )
    grammar_by_level = [dict(r) for r in await cursor.fetchall()]
    total_grammar_acc = _safe_avg([r["avg_accuracy"] for r in grammar_by_level])
    areas["grammar"] = {"accuracy": round(total_grammar_acc, 1), "by_level": grammar_by_level}

    # 3) Kanji — from quiz results with kanji quiz types
    cursor = await db.execute(
        """SELECT jlpt_level,
                  COUNT(*) as quiz_count,
                  AVG(correct * 100.0 / total_questions) as avg_accuracy
           FROM jp_quiz_results
           WHERE quiz_type IN ('kanji_reading','kanji_meaning')
             AND total_questions > 0
           GROUP BY jlpt_level
           ORDER BY avg_accuracy ASC"""
    )
    kanji_by_level = [dict(r) for r in await cursor.fetchall()]
    total_kanji_acc = _safe_avg([r["avg_accuracy"] for r in kanji_by_level])
    areas["kanji"] = {"accuracy": round(total_kanji_acc, 1), "by_level": kanji_by_level}

    # 4) Reading — not tracked in quiz_results yet, so use jp_review_logs accuracy
    #    If no quiz data, report as "no data"
    areas["reading"] = {"accuracy": None, "by_level": [], "note": "reading scores from submit endpoint"}

    # 5) Weakest vocab (lowest SRS ease_factor)
    cursor = await db.execute(
        """SELECT v.id, v.word, v.reading, v.meaning, v.jlpt_level,
                  c.ease_factor, c.interval_days, c.repetitions
           FROM jp_srs_cards c
           JOIN jp_vocabulary v ON v.id = c.vocab_id
           WHERE c.repetitions > 0
           ORDER BY c.ease_factor ASC, c.interval_days ASC
           LIMIT 10"""
    )
    weak_vocab = [dict(r) for r in await cursor.fetchall()]

    # 6) Weakest grammar (lowest SRS ease_factor)
    cursor = await db.execute(
        """SELECT g.id, g.grammar_point, g.meaning_ko, g.jlpt_level,
                  s.ease_factor, s.interval_days, s.repetitions
           FROM jp_grammar_srs s
           JOIN jp_grammar g ON g.id = s.grammar_id
           WHERE s.repetitions > 0
           ORDER BY s.ease_factor ASC, s.interval_days ASC
           LIMIT 10"""
    )
    weak_grammar = [dict(r) for r in await cursor.fetchall()]

    # Determine overall weakest area
    area_scores = {k: v["accuracy"] for k, v in areas.items() if v["accuracy"] is not None}
    weakest_area = min(area_scores, key=area_scores.get) if area_scores else None

    return {
        "areas": areas,
        "weakest_area": weakest_area,
        "weak_vocab_top10": weak_vocab,
        "weak_grammar_top10": weak_grammar,
        "recommendation": _build_recommendation(weakest_area, weak_vocab, weak_grammar),
    }


def _build_recommendation(weakest: str | None, weak_vocab: list, weak_grammar: list) -> list[str]:
    recs = []
    if weakest == "vocab":
        recs.append("단어 복습에 집중하세요. 플래시카드 퀴즈를 매일 진행하세요.")
    elif weakest == "grammar":
        recs.append("문법 빈칸 채우기 퀴즈로 약한 문법 포인트를 복습하세요.")
    elif weakest == "kanji":
        recs.append("한자 읽기/뜻 퀴즈를 통해 한자를 강화하세요.")
    if weak_vocab:
        words = ", ".join(v["word"] for v in weak_vocab[:5])
        recs.append(f"약한 단어 복습 필요: {words}")
    if weak_grammar:
        points = ", ".join(g["grammar_point"] for g in weak_grammar[:5])
        recs.append(f"약한 문법 복습 필요: {points}")
    if not recs:
        recs.append("학습 데이터가 부족합니다. 퀴즈와 복습을 시작하세요!")
    return recs


def _safe_avg(values: list) -> float:
    clean = [v for v in values if v is not None]
    return sum(clean) / len(clean) if clean else 0.0


# ── Learning Curve ────────────────────────────────────────


async def get_learning_curve(days: int = 30) -> dict:
    """Daily learning activity over the past N days."""
    db = await get_db()

    cursor = await db.execute(
        """SELECT date(created_at) as study_date,
                  COUNT(*) as total_reviews,
                  SUM(CASE WHEN quality >= 3 THEN 1 ELSE 0 END) as correct,
                  SUM(xp_earned) as xp_earned
           FROM jp_review_logs
           WHERE created_at >= date('now', ?)
           GROUP BY date(created_at)
           ORDER BY study_date""",
        (f"-{days} days",),
    )
    review_data = {r[0]: {"reviews": r[1], "correct": r[2], "xp": r[3]} for r in await cursor.fetchall()}

    # New words learned per day (first review = new)
    cursor = await db.execute(
        """SELECT date(MIN(created_at)) as first_date, COUNT(*) as new_count
           FROM jp_review_logs
           WHERE created_at >= date('now', ?)
           GROUP BY vocab_id
           HAVING date(MIN(created_at)) >= date('now', ?)""",
        (f"-{days} days", f"-{days} days"),
    )
    new_words_by_date: dict[str, int] = {}
    for r in await cursor.fetchall():
        new_words_by_date[r[0]] = new_words_by_date.get(r[0], 0) + r[1]

    # Build daily series
    today = date.today()
    daily = []
    for i in range(days):
        d = (today - timedelta(days=days - 1 - i)).isoformat()
        data = review_data.get(d, {"reviews": 0, "correct": 0, "xp": 0})
        accuracy = round(data["correct"] / data["reviews"] * 100, 1) if data["reviews"] > 0 else 0
        daily.append({
            "date": d,
            "reviews": data["reviews"],
            "correct": data["correct"],
            "accuracy": accuracy,
            "xp": data["xp"],
            "new_words": new_words_by_date.get(d, 0),
        })

    return {
        "period_days": days,
        "daily": daily,
        "summary": {
            "total_reviews": sum(d["reviews"] for d in daily),
            "total_correct": sum(d["correct"] for d in daily),
            "total_xp": sum(d["xp"] for d in daily),
            "total_new_words": sum(d["new_words"] for d in daily),
            "study_days": sum(1 for d in daily if d["reviews"] > 0),
            "avg_daily_reviews": round(sum(d["reviews"] for d in daily) / days, 1),
        },
    }


# ── SRS Forecast ──────────────────────────────────────────


async def get_srs_forecast(days: int = 14) -> dict:
    """Forecast upcoming SRS review load for the next N days."""
    db = await get_db()
    today = date.today()
    forecast = []

    for i in range(days):
        target = (today + timedelta(days=i)).isoformat()

        # Vocab SRS cards due
        cursor = await db.execute(
            "SELECT COUNT(*) FROM jp_srs_cards WHERE next_review <= ?",
            (target,),
        )
        vocab_due = (await cursor.fetchone())[0]

        # Grammar SRS cards due
        cursor = await db.execute(
            "SELECT COUNT(*) FROM jp_grammar_srs WHERE next_review <= ?",
            (target,),
        )
        grammar_due = (await cursor.fetchone())[0]

        forecast.append({
            "date": target,
            "vocab_due": vocab_due,
            "grammar_due": grammar_due,
            "total_due": vocab_due + grammar_due,
        })

    return {
        "forecast_days": days,
        "daily": forecast,
        "peak_day": max(forecast, key=lambda x: x["total_due"])["date"] if forecast else None,
        "avg_daily": round(sum(f["total_due"] for f in forecast) / days, 1) if forecast else 0,
    }


# ── Mastery Breakdown ────────────────────────────────────


async def get_mastery_breakdown() -> dict:
    """Mastery distribution per JLPT level for vocab, grammar, kanji."""
    db = await get_db()
    result: dict[str, dict] = {}

    for level in ["N5", "N4", "N3", "N2", "N1"]:
        level_data: dict[str, dict] = {}

        # Vocab mastery
        cursor = await db.execute(
            "SELECT COUNT(*) FROM jp_vocabulary WHERE jlpt_level = ? AND is_active = 1",
            (level,),
        )
        total_vocab = (await cursor.fetchone())[0]

        cursor = await db.execute(
            """SELECT COUNT(*) FROM jp_srs_cards c
               JOIN jp_vocabulary v ON v.id = c.vocab_id
               WHERE v.jlpt_level = ? AND c.interval_days >= 21""",
            (level,),
        )
        mastered_vocab = (await cursor.fetchone())[0]

        cursor = await db.execute(
            """SELECT COUNT(*) FROM jp_srs_cards c
               JOIN jp_vocabulary v ON v.id = c.vocab_id
               WHERE v.jlpt_level = ? AND c.interval_days > 0 AND c.interval_days < 21""",
            (level,),
        )
        learning_vocab = (await cursor.fetchone())[0]

        not_started_vocab = total_vocab - mastered_vocab - learning_vocab
        level_data["vocab"] = {
            "total": total_vocab,
            "mastered": mastered_vocab,
            "learning": learning_vocab,
            "not_started": max(not_started_vocab, 0),
        }

        # Grammar mastery
        cursor = await db.execute(
            "SELECT COUNT(*) FROM jp_grammar WHERE jlpt_level = ? AND is_active = 1",
            (level,),
        )
        total_grammar = (await cursor.fetchone())[0]

        cursor = await db.execute(
            """SELECT COUNT(*) FROM jp_grammar_srs s
               JOIN jp_grammar g ON g.id = s.grammar_id
               WHERE g.jlpt_level = ? AND s.interval_days >= 21""",
            (level,),
        )
        mastered_grammar = (await cursor.fetchone())[0]

        cursor = await db.execute(
            """SELECT COUNT(*) FROM jp_grammar_srs s
               JOIN jp_grammar g ON g.id = s.grammar_id
               WHERE g.jlpt_level = ? AND s.interval_days > 0 AND s.interval_days < 21""",
            (level,),
        )
        learning_grammar = (await cursor.fetchone())[0]

        not_started_grammar = total_grammar - mastered_grammar - learning_grammar
        level_data["grammar"] = {
            "total": total_grammar,
            "mastered": mastered_grammar,
            "learning": learning_grammar,
            "not_started": max(not_started_grammar, 0),
        }

        # Kanji count
        cursor = await db.execute(
            "SELECT COUNT(*) FROM jp_kanji WHERE jlpt_level = ? AND is_active = 1",
            (level,),
        )
        total_kanji = (await cursor.fetchone())[0]
        level_data["kanji"] = {
            "total": total_kanji,
            "mastered": 0,  # No kanji SRS yet
            "learning": 0,
            "not_started": total_kanji,
        }

        if total_vocab > 0 or total_grammar > 0 or total_kanji > 0:
            result[level] = level_data

    return {"levels": result}


# ── Streak Info ───────────────────────────────────────────


async def get_streak_info() -> dict:
    """Study streak based on jp_review_logs dates."""
    db = await get_db()

    # Get all unique study dates
    cursor = await db.execute(
        "SELECT DISTINCT date(created_at) as study_date FROM jp_review_logs ORDER BY study_date DESC"
    )
    date_strs = [r[0] for r in await cursor.fetchall()]

    if not date_strs:
        return {
            "current_streak": 0,
            "longest_streak": 0,
            "this_week_days": 0,
            "total_study_days": 0,
            "last_study_date": None,
        }

    study_dates = sorted(date.fromisoformat(d) for d in date_strs)
    today = date.today()

    # Current streak: consecutive days ending today or yesterday
    current_streak = 0
    check = today
    study_set = set(study_dates)
    if check not in study_set:
        check = today - timedelta(days=1)
    while check in study_set:
        current_streak += 1
        check -= timedelta(days=1)

    # Longest streak
    longest = 1
    run = 1
    for i in range(1, len(study_dates)):
        if study_dates[i] - study_dates[i - 1] == timedelta(days=1):
            run += 1
            longest = max(longest, run)
        else:
            run = 1
    if len(study_dates) == 1:
        longest = 1

    # This week (Mon-Sun)
    week_start = today - timedelta(days=today.weekday())
    this_week = sum(1 for d in study_set if d >= week_start)

    return {
        "current_streak": current_streak,
        "longest_streak": longest,
        "this_week_days": this_week,
        "total_study_days": len(study_dates),
        "last_study_date": study_dates[-1].isoformat() if study_dates else None,
    }
