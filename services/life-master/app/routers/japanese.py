"""Japanese learning router — vocabulary, SRS, quiz, gamification."""

import json
import logging
import random
from datetime import date, datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.database.connection import get_db
from app.services.japanese import (
    ACHIEVEMENTS,
    MASTERY_TIERS,
    calculate_xp,
    check_achievements,
    generate_daily_quests,
    get_mastery_tier,
    get_player_title,
    get_weekly_challenge,
    level_from_xp,
    mastery_xp_bonus,
    sm2_update,
    total_xp_for_level,
    xp_for_level,
)

logger = logging.getLogger("life-master.japanese")

router = APIRouter(prefix="/japanese", tags=["japanese"])


# ── Schemas ──────────────────────────────────────────────


class VocabCreate(BaseModel):
    word: str = Field(min_length=1, max_length=100)
    reading: str = Field(min_length=1, max_length=100)
    meaning: str = Field(min_length=1, max_length=300)
    jlpt_level: str = Field(default="N5", pattern=r"^N[1-5]$")
    part_of_speech: str = Field(default="noun", max_length=50)
    example_ja: str | None = None
    example_ko: str | None = None
    tags: list[str] = []


class VocabResponse(BaseModel):
    id: int
    word: str
    reading: str
    meaning: str
    jlpt_level: str
    part_of_speech: str
    example_ja: str | None = None
    example_ko: str | None = None
    tags: list[str] | str = []
    is_active: int = 1
    created_at: str


class ReviewRequest(BaseModel):
    quality: int = Field(ge=0, le=5, description="0=실패, 3=어려움, 4=좋음, 5=완벽")
    time_ms: int = Field(default=0, ge=0, description="응답 시간 (ms)")


class ReviewResponse(BaseModel):
    vocab: VocabResponse
    srs: dict
    xp: dict
    new_achievements: list[dict] = []
    player: dict


class SourceCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    artist: str | None = None
    source_type: str = Field(default="song")  # song, anime, game, drama, other
    content_ja: str = Field(min_length=1)
    content_ko: str | None = None
    difficulty: str = Field(default="N4", pattern=r"^N[1-5]$")
    tags: list[str] = []
    vocab_ids: list[int] = []


class SourceResponse(BaseModel):
    id: int
    title: str
    artist: str | None = None
    source_type: str
    content_ja: str
    content_ko: str | None = None
    difficulty: str
    tags: list[str] | str = []
    is_active: int = 1
    created_at: str
    vocab_count: int = 0


class QuizStartRequest(BaseModel):
    quiz_type: str = Field(default="flashcard")  # flashcard, meaning, reading, time_attack, boss
    jlpt_level: str | None = None
    count: int = Field(default=10, ge=1, le=50)
    source_id: int | None = None


class QuizSubmitRequest(BaseModel):
    quiz_type: str = Field(default="flashcard")
    answers: list[dict] = Field(min_length=1)
    time_seconds: int = Field(default=0, ge=0)
    jlpt_level: str | None = None


class PlayerStatsResponse(BaseModel):
    total_xp: int
    level: int
    xp_current_level: int
    xp_next_level: int
    current_streak: int
    longest_streak: int
    total_reviews: int
    total_correct: int
    accuracy: float
    combo_best: int
    achievements: list[dict]
    title: dict


# ── Helpers ──────────────────────────────────────────────


def _parse_tags(row: dict) -> dict:
    d = dict(row)
    if isinstance(d.get("tags"), str):
        try:
            d["tags"] = json.loads(d["tags"])
        except (json.JSONDecodeError, TypeError):
            d["tags"] = []
    return d


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _player_title(level: int) -> dict:
    """Return a title based on level (delegates to service)."""
    return get_player_title(level)


# ── Vocabulary CRUD ──────────────────────────────────────


@router.get("/vocab", response_model=list[VocabResponse])
async def list_vocab(
    jlpt_level: str | None = None,
    part_of_speech: str | None = None,
    search: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    """List vocabulary with optional filters."""
    db = await get_db()
    q = "SELECT * FROM jp_vocabulary WHERE is_active = 1"
    params: list = []
    if jlpt_level:
        q += " AND jlpt_level = ?"
        params.append(jlpt_level)
    if part_of_speech:
        q += " AND part_of_speech = ?"
        params.append(part_of_speech)
    if search:
        q += " AND (word LIKE ? OR reading LIKE ? OR meaning LIKE ?)"
        s = f"%{search}%"
        params.extend([s, s, s])
    q += " ORDER BY jlpt_level, word LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    cursor = await db.execute(q, params)
    rows = await cursor.fetchall()
    return [_parse_tags(r) for r in rows]


@router.get("/vocab/count")
async def vocab_count():
    """Count vocabulary by JLPT level."""
    db = await get_db()
    cursor = await db.execute(
        """SELECT jlpt_level, COUNT(*) as count
           FROM jp_vocabulary WHERE is_active = 1
           GROUP BY jlpt_level ORDER BY jlpt_level"""
    )
    rows = await cursor.fetchall()
    return {r["jlpt_level"]: r["count"] for r in rows}


@router.post("/vocab", response_model=VocabResponse, status_code=201)
async def add_vocab(data: VocabCreate):
    """Add a new vocabulary word."""
    db = await get_db()
    cursor = await db.execute(
        """INSERT INTO jp_vocabulary (word, reading, meaning, jlpt_level, part_of_speech, example_ja, example_ko, tags)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (data.word, data.reading, data.meaning, data.jlpt_level,
         data.part_of_speech, data.example_ja, data.example_ko,
         json.dumps(data.tags)),
    )
    vocab_id = cursor.lastrowid
    # Auto-create SRS card
    await db.execute(
        "INSERT INTO jp_srs_cards (vocab_id, next_review) VALUES (?, date('now'))",
        (vocab_id,),
    )
    await db.commit()
    cursor = await db.execute("SELECT * FROM jp_vocabulary WHERE id = ?", (vocab_id,))
    row = await cursor.fetchone()
    return _parse_tags(row)


@router.post("/vocab/bulk", status_code=201)
async def add_vocab_bulk(items: list[VocabCreate]):
    """Bulk add vocabulary."""
    db = await get_db()
    added = 0
    for data in items:
        try:
            cursor = await db.execute(
                """INSERT INTO jp_vocabulary (word, reading, meaning, jlpt_level, part_of_speech, example_ja, example_ko, tags)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (data.word, data.reading, data.meaning, data.jlpt_level,
                 data.part_of_speech, data.example_ja, data.example_ko,
                 json.dumps(data.tags)),
            )
            await db.execute(
                "INSERT INTO jp_srs_cards (vocab_id, next_review) VALUES (?, date('now'))",
                (cursor.lastrowid,),
            )
            added += 1
        except Exception as e:
            logger.warning("Skipping duplicate vocab %s: %s", data.word, e)
    await db.commit()
    return {"added": added, "total": len(items)}


@router.delete("/vocab/{vocab_id}")
async def delete_vocab(vocab_id: int):
    """Soft delete a vocabulary word."""
    db = await get_db()
    cursor = await db.execute(
        "UPDATE jp_vocabulary SET is_active = 0 WHERE id = ?", (vocab_id,)
    )
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Vocabulary not found")
    await db.commit()
    return {"status": "deleted", "id": vocab_id}


# ── SRS Review ───────────────────────────────────────────


@router.get("/review/due")
async def get_due_cards(
    jlpt_level: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
):
    """Get cards due for review today."""
    db = await get_db()
    today = date.today().isoformat()
    q = """SELECT v.*, c.ease_factor, c.interval_days, c.repetitions, c.next_review
           FROM jp_srs_cards c
           JOIN jp_vocabulary v ON v.id = c.vocab_id
           WHERE c.next_review <= ? AND v.is_active = 1"""
    params: list = [today]
    if jlpt_level:
        q += " AND v.jlpt_level = ?"
        params.append(jlpt_level)
    q += " ORDER BY c.next_review, c.repetitions LIMIT ?"
    params.append(limit)
    cursor = await db.execute(q, params)
    rows = await cursor.fetchall()
    return [_parse_tags(r) for r in rows]


@router.get("/review/due/count")
async def get_due_count():
    """Count of cards due for review by level."""
    db = await get_db()
    today = date.today().isoformat()
    cursor = await db.execute(
        """SELECT v.jlpt_level, COUNT(*) as count
           FROM jp_srs_cards c
           JOIN jp_vocabulary v ON v.id = c.vocab_id
           WHERE c.next_review <= ? AND v.is_active = 1
           GROUP BY v.jlpt_level ORDER BY v.jlpt_level""",
        (today,),
    )
    rows = await cursor.fetchall()
    total = sum(r["count"] for r in rows)
    return {"total": total, "by_level": {r["jlpt_level"]: r["count"] for r in rows}}


@router.post("/review/{vocab_id}", response_model=ReviewResponse)
async def submit_review(vocab_id: int, data: ReviewRequest):
    """Submit a review result for a vocabulary card."""
    db = await get_db()

    # Get vocab
    cursor = await db.execute("SELECT * FROM jp_vocabulary WHERE id = ?", (vocab_id,))
    vocab = await cursor.fetchone()
    if not vocab:
        raise HTTPException(status_code=404, detail="Vocabulary not found")

    # Get SRS card
    cursor = await db.execute("SELECT * FROM jp_srs_cards WHERE vocab_id = ?", (vocab_id,))
    card = await cursor.fetchone()
    if not card:
        raise HTTPException(status_code=404, detail="SRS card not found")

    # Update SRS
    srs_result = sm2_update(
        quality=data.quality,
        repetitions=card["repetitions"],
        ease_factor=card["ease_factor"],
        interval_days=card["interval_days"],
    )

    await db.execute(
        """UPDATE jp_srs_cards
           SET ease_factor = ?, interval_days = ?, repetitions = ?,
               next_review = ?, last_reviewed = ?
           WHERE vocab_id = ?""",
        (srs_result["ease_factor"], srs_result["interval_days"],
         srs_result["repetitions"], srs_result["next_review"], _now(), vocab_id),
    )

    # Get player stats
    cursor = await db.execute("SELECT * FROM jp_player_stats WHERE id = 1")
    player = await cursor.fetchone()
    if not player:
        await db.execute("INSERT INTO jp_player_stats (id) VALUES (1)")
        cursor = await db.execute("SELECT * FROM jp_player_stats WHERE id = 1")
        player = await cursor.fetchone()

    player = dict(player)

    # Update streak
    today_str = date.today().isoformat()
    is_streak = player["last_study_date"] == today_str or (
        player["last_study_date"] and
        (date.today() - date.fromisoformat(player["last_study_date"])).days <= 1
    )

    if player["last_study_date"] != today_str:
        if player["last_study_date"] and (date.today() - date.fromisoformat(player["last_study_date"])).days == 1:
            new_streak = player["current_streak"] + 1
        elif player["last_study_date"] == today_str:
            new_streak = player["current_streak"]
        else:
            new_streak = 1
    else:
        new_streak = player["current_streak"]

    # Calculate XP
    # Get today's review count for combo tracking
    cursor = await db.execute(
        """SELECT COUNT(*) as cnt FROM jp_review_logs
           WHERE created_at >= date('now') AND quality >= 3""",
    )
    today_correct = (await cursor.fetchone())["cnt"]

    xp_result = calculate_xp(
        quality=data.quality,
        combo=today_correct if data.quality >= 3 else 0,
        is_streak_bonus=new_streak >= 3,
        jlpt_level=vocab["jlpt_level"],
    )

    # Mastery tier check — bonus XP on tier-up
    old_tier = get_mastery_tier(card["repetitions"], card["interval_days"])
    new_tier = get_mastery_tier(srs_result["repetitions"], srs_result["interval_days"])
    tier_bonus = 0
    if new_tier != old_tier:
        tier_bonus = mastery_xp_bonus(new_tier)
        xp_result["mastery_tier_up"] = new_tier
        xp_result["mastery_bonus"] = tier_bonus
        xp_result["total_xp"] += tier_bonus

    new_total_xp = player["total_xp"] + xp_result["total_xp"]
    new_level = level_from_xp(new_total_xp)
    new_reviews = player["total_reviews"] + 1
    new_correct = player["total_correct"] + (1 if data.quality >= 3 else 0)
    new_combo_best = max(player["combo_best"], today_correct + 1 if data.quality >= 3 else 0)
    new_longest = max(player["longest_streak"], new_streak)

    # Log review
    await db.execute(
        """INSERT INTO jp_review_logs (vocab_id, quality, time_ms, xp_earned)
           VALUES (?, ?, ?, ?)""",
        (vocab_id, data.quality, data.time_ms, xp_result["total_xp"]),
    )

    # Get mastery tier counts for achievement checks
    cursor = await db.execute(
        """SELECT
            SUM(CASE WHEN repetitions >= 3 AND interval_days >= 7 THEN 1 ELSE 0 END) as bronze,
            SUM(CASE WHEN repetitions >= 5 AND interval_days >= 14 THEN 1 ELSE 0 END) as silver,
            SUM(CASE WHEN repetitions >= 8 AND interval_days >= 30 THEN 1 ELSE 0 END) as gold,
            SUM(CASE WHEN repetitions >= 12 AND interval_days >= 60 THEN 1 ELSE 0 END) as diamond,
            SUM(CASE WHEN repetitions >= 15 AND interval_days >= 90 THEN 1 ELSE 0 END) as master
           FROM jp_srs_cards"""
    )
    mastery_row = dict(await cursor.fetchone())
    mastery_counts = {
        "bronze": mastery_row["bronze"] or 0,
        "silver": mastery_row["silver"] or 0,
        "gold": mastery_row["gold"] or 0,
        "diamond": mastery_row["diamond"] or 0,
        "master": mastery_row["master"] or 0,
    }

    # Get quiz count
    cursor = await db.execute("SELECT COUNT(*) as cnt FROM jp_quiz_results")
    quiz_count = (await cursor.fetchone())["cnt"]

    # Get daily quests / weekly challenges completed counts
    dq_completed = player.get("daily_quests_completed", 0)
    wc_completed = player.get("weekly_challenges_completed", 0)

    # Check achievements
    current_achievements = json.loads(player["achievements"]) if isinstance(player["achievements"], str) else player["achievements"]
    new_achievement_ids = check_achievements(
        current=current_achievements,
        total_reviews=new_reviews,
        total_correct=new_correct,
        streak=new_streak,
        combo_best=new_combo_best,
        total_xp=new_total_xp,
        level=new_level,
        quiz_count=quiz_count,
        daily_quests_completed=dq_completed,
        weekly_challenges_completed=wc_completed,
        mastery_counts=mastery_counts,
    )

    # Hidden achievements — time-based triggers
    now_dt = datetime.now(timezone.utc)
    hour = now_dt.hour
    if hour >= 0 and hour < 5 and "night_owl" not in current_achievements and "night_owl" not in new_achievement_ids:
        new_achievement_ids.append("night_owl")
    if hour >= 4 and hour < 6 and "early_bird" not in current_achievements and "early_bird" not in new_achievement_ids:
        new_achievement_ids.append("early_bird")

    # Weekend warrior: 50+ reviews on a weekend day
    if now_dt.weekday() >= 5 and "weekend_warrior" not in current_achievements and "weekend_warrior" not in new_achievement_ids:
        cursor = await db.execute(
            "SELECT COUNT(*) as cnt FROM jp_review_logs WHERE created_at >= date('now')",
        )
        today_reviews = (await cursor.fetchone())["cnt"]
        if today_reviews >= 50:
            new_achievement_ids.append("weekend_warrior")

    # Comeback kid: streak broken then 3+ days again
    if new_streak >= 3 and "comeback_kid" not in current_achievements and "comeback_kid" not in new_achievement_ids:
        if player.get("longest_streak", 0) > player.get("current_streak", 0):
            new_achievement_ids.append("comeback_kid")

    achievement_xp = sum(ACHIEVEMENTS[a]["xp_bonus"] for a in new_achievement_ids)
    new_total_xp += achievement_xp
    new_level = level_from_xp(new_total_xp)

    all_achievements = current_achievements + new_achievement_ids

    # Update player stats
    await db.execute(
        """UPDATE jp_player_stats SET
           total_xp = ?, level = ?, current_streak = ?, longest_streak = ?,
           last_study_date = ?, total_reviews = ?, total_correct = ?,
           combo_best = ?, achievements = ?, updated_at = ?
           WHERE id = 1""",
        (new_total_xp, new_level, new_streak, new_longest,
         today_str, new_reviews, new_correct, new_combo_best,
         json.dumps(all_achievements), _now()),
    )

    # Auto-update daily quest progress
    today_quests_cursor = await db.execute(
        "SELECT * FROM jp_daily_quests WHERE date = ? AND is_completed = 0",
        (today_str,),
    )
    for quest in await today_quests_cursor.fetchall():
        quest = dict(quest)
        should_increment = False
        if quest["quest_type"] == "review_count":
            should_increment = True
        elif quest["quest_type"] == "perfect_reviews" and data.quality == 5:
            should_increment = True
        elif quest["quest_type"] == "combo_reach" and new_combo_best >= quest["target"]:
            should_increment = True
        elif quest["quest_type"] == "new_vocab_learn" and card["repetitions"] == 0:
            should_increment = True

        if should_increment:
            new_progress = quest["current_progress"] + 1
            completed = 1 if new_progress >= quest["target"] else 0
            completed_at = _now() if completed else None
            await db.execute(
                """UPDATE jp_daily_quests SET current_progress = ?, is_completed = ?,
                   completed_at = ? WHERE id = ?""",
                (new_progress, completed, completed_at, quest["id"]),
            )
            if completed and not quest["is_completed"]:
                new_total_xp += quest["xp_reward"]
                new_level = level_from_xp(new_total_xp)
                # Update player's daily quest completion count
                await db.execute(
                    """UPDATE jp_player_stats SET daily_quests_completed =
                       COALESCE(daily_quests_completed, 0) + 1 WHERE id = 1"""
                )

    # Re-update player XP if quest rewards were added
    await db.execute(
        "UPDATE jp_player_stats SET total_xp = ?, level = ? WHERE id = 1",
        (new_total_xp, new_level),
    )

    await db.commit()

    # Build response
    xp_needed = xp_for_level(new_level)
    xp_in_level = new_total_xp - total_xp_for_level(new_level - 1) if new_level > 1 else new_total_xp

    new_achievement_details = [
        {"id": a, **ACHIEVEMENTS[a]} for a in new_achievement_ids
    ]

    return {
        "vocab": _parse_tags(vocab),
        "srs": srs_result,
        "xp": xp_result,
        "new_achievements": new_achievement_details,
        "player": {
            "total_xp": new_total_xp,
            "level": new_level,
            "xp_in_level": xp_in_level,
            "xp_needed": xp_needed,
            "streak": new_streak,
            "combo_best": new_combo_best,
            "title": _player_title(new_level),
        },
    }


# ── Quiz ─────────────────────────────────────────────────


@router.post("/quiz/start")
async def start_quiz(data: QuizStartRequest):
    """Generate quiz questions."""
    db = await get_db()

    q = "SELECT * FROM jp_vocabulary WHERE is_active = 1"
    params: list = []

    if data.source_id:
        q = """SELECT v.* FROM jp_vocabulary v
               JOIN jp_source_vocab sv ON sv.vocab_id = v.id
               WHERE v.is_active = 1 AND sv.source_id = ?"""
        params = [data.source_id]
    elif data.jlpt_level:
        q += " AND jlpt_level = ?"
        params.append(data.jlpt_level)

    cursor = await db.execute(q, params)
    all_vocab = [_parse_tags(r) for r in await cursor.fetchall()]

    if len(all_vocab) < 2:
        raise HTTPException(status_code=400, detail="단어가 부족합니다 (최소 2개)")

    count = min(data.count, len(all_vocab))
    selected = random.sample(all_vocab, count)

    questions = []
    for vocab in selected:
        # Generate wrong answers from other vocab
        others = [v for v in all_vocab if v["id"] != vocab["id"]]
        wrong = random.sample(others, min(3, len(others)))

        if data.quiz_type in ("meaning", "flashcard"):
            question = {
                "vocab_id": vocab["id"],
                "question": vocab["word"],
                "reading": vocab["reading"],
                "correct_answer": vocab["meaning"],
                "options": _shuffle([vocab["meaning"]] + [w["meaning"] for w in wrong]),
            }
        elif data.quiz_type == "reading":
            question = {
                "vocab_id": vocab["id"],
                "question": vocab["word"],
                "correct_answer": vocab["reading"],
                "options": _shuffle([vocab["reading"]] + [w["reading"] for w in wrong]),
            }
        elif data.quiz_type in ("time_attack", "boss"):
            question = {
                "vocab_id": vocab["id"],
                "question": vocab["word"],
                "reading": vocab["reading"],
                "correct_answer": vocab["meaning"],
                "options": _shuffle([vocab["meaning"]] + [w["meaning"] for w in wrong]),
                "time_limit_ms": 5000 if data.quiz_type == "time_attack" else 8000,
            }
        else:
            question = {
                "vocab_id": vocab["id"],
                "question": vocab["word"],
                "correct_answer": vocab["meaning"],
                "options": _shuffle([vocab["meaning"]] + [w["meaning"] for w in wrong]),
            }

        questions.append(question)

    return {
        "quiz_type": data.quiz_type,
        "total_questions": len(questions),
        "jlpt_level": data.jlpt_level,
        "questions": questions,
    }


@router.post("/quiz/submit")
async def submit_quiz(data: QuizSubmitRequest):
    """Submit quiz results and earn XP."""
    db = await get_db()

    correct = sum(1 for a in data.answers if a.get("correct", False))
    total = len(data.answers)

    # Calculate max combo
    combo = 0
    max_combo = 0
    for a in data.answers:
        if a.get("correct", False):
            combo += 1
            max_combo = max(max_combo, combo)
        else:
            combo = 0

    # Base XP for quiz
    base_xp = correct * 15
    combo_bonus = max_combo * 5
    perfect_bonus = 50 if correct == total else 0
    time_bonus = 30 if data.quiz_type == "time_attack" and data.time_seconds < 30 else 0
    boss_bonus = 100 if data.quiz_type == "boss" and correct == total else 0
    total_xp = base_xp + combo_bonus + perfect_bonus + time_bonus + boss_bonus

    # Save quiz result
    await db.execute(
        """INSERT INTO jp_quiz_results (quiz_type, total_questions, correct, max_combo, xp_earned, time_seconds, jlpt_level)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (data.quiz_type, total, correct, max_combo, total_xp, data.time_seconds, data.jlpt_level),
    )

    # Update player XP
    cursor = await db.execute("SELECT * FROM jp_player_stats WHERE id = 1")
    player = await cursor.fetchone()
    if player:
        player = dict(player)
        new_xp = player["total_xp"] + total_xp
        new_level = level_from_xp(new_xp)
        new_combo_best = max(player["combo_best"], max_combo)

        current_achievements = json.loads(player["achievements"]) if isinstance(player["achievements"], str) else player["achievements"]
        new_achs = []
        if "first_quiz" not in current_achievements:
            new_achs.append("first_quiz")
        if correct == total and "quiz_perfect" not in current_achievements:
            new_achs.append("quiz_perfect")
        if data.quiz_type == "time_attack" and data.time_seconds < 30 and "time_attack_30" not in current_achievements:
            new_achs.append("time_attack_30")
        if data.quiz_type == "time_attack" and data.time_seconds < 15 and "time_attack_15" not in current_achievements:
            new_achs.append("time_attack_15")
        if data.quiz_type == "boss" and correct == total and "boss_clear" not in current_achievements:
            new_achs.append("boss_clear")

        # Boss clear 5 times
        if data.quiz_type == "boss" and correct == total and "boss_clear_5" not in current_achievements:
            cursor = await db.execute(
                """SELECT COUNT(*) as cnt FROM jp_quiz_results
                   WHERE quiz_type = 'boss' AND correct = total_questions"""
            )
            boss_clears = (await cursor.fetchone())["cnt"]
            if boss_clears >= 5:
                new_achs.append("boss_clear_5")

        # Quiz 3 perfect in a row
        if correct == total and "quiz_3_perfect" not in current_achievements:
            cursor = await db.execute(
                """SELECT correct, total_questions FROM jp_quiz_results
                   ORDER BY id DESC LIMIT 3"""
            )
            recent = await cursor.fetchall()
            if len(recent) >= 3 and all(r["correct"] == r["total_questions"] for r in recent):
                new_achs.append("quiz_3_perfect")

        # Quiz count achievements
        cursor = await db.execute("SELECT COUNT(*) as cnt FROM jp_quiz_results")
        total_quizzes = (await cursor.fetchone())["cnt"]
        if total_quizzes >= 10 and "quiz_10" not in current_achievements:
            new_achs.append("quiz_10")
        if total_quizzes >= 50 and "quiz_50" not in current_achievements:
            new_achs.append("quiz_50")
        if total_quizzes >= 100 and "quiz_100" not in current_achievements:
            new_achs.append("quiz_100")

        ach_xp = sum(ACHIEVEMENTS[a]["xp_bonus"] for a in new_achs)
        new_xp += ach_xp
        new_level = level_from_xp(new_xp)

        await db.execute(
            """UPDATE jp_player_stats SET total_xp = ?, level = ?,
               combo_best = ?, achievements = ?,
               total_quizzes = COALESCE(total_quizzes, 0) + 1,
               updated_at = ?
               WHERE id = 1""",
            (new_xp, new_level, new_combo_best,
             json.dumps(current_achievements + new_achs), _now()),
        )

        # Update daily quest progress for quiz-related quests
        today_str = date.today().isoformat()
        quiz_quest_cursor = await db.execute(
            """SELECT * FROM jp_daily_quests
               WHERE date = ? AND is_completed = 0
               AND quest_type IN ('quiz_complete', 'quiz_perfect', 'time_attack_clear', 'boss_clear')""",
            (today_str,),
        )
        for quest in await quiz_quest_cursor.fetchall():
            quest = dict(quest)
            should_complete = False
            if quest["quest_type"] == "quiz_complete":
                should_complete = True
            elif quest["quest_type"] == "quiz_perfect" and correct == total:
                should_complete = True
            elif quest["quest_type"] == "time_attack_clear" and data.quiz_type == "time_attack":
                should_complete = True
            elif quest["quest_type"] == "boss_clear" and data.quiz_type == "boss" and correct == total:
                should_complete = True

            if should_complete:
                new_prog = quest["current_progress"] + 1
                is_done = 1 if new_prog >= quest["target"] else 0
                await db.execute(
                    """UPDATE jp_daily_quests SET current_progress = ?,
                       is_completed = ?, completed_at = ? WHERE id = ?""",
                    (new_prog, is_done, _now() if is_done else None, quest["id"]),
                )
                if is_done:
                    new_xp += quest["xp_reward"]
                    await db.execute(
                        """UPDATE jp_player_stats SET total_xp = total_xp + ?,
                           daily_quests_completed = COALESCE(daily_quests_completed, 0) + 1
                           WHERE id = 1""",
                        (quest["xp_reward"],),
                    )

    await db.commit()

    return {
        "quiz_type": data.quiz_type,
        "total": total,
        "correct": correct,
        "accuracy": round(correct / total * 100, 1) if total > 0 else 0,
        "max_combo": max_combo,
        "xp_earned": total_xp,
        "xp_breakdown": {
            "base": base_xp,
            "combo_bonus": combo_bonus,
            "perfect_bonus": perfect_bonus,
            "time_bonus": time_bonus,
            "boss_bonus": boss_bonus,
        },
        "new_achievements": [{"id": a, **ACHIEVEMENTS[a]} for a in (new_achs if player else [])],
    }


# ── Sources (J-POP / Anime / Game) ──────────────────────


@router.get("/sources", response_model=list[SourceResponse])
async def list_sources(
    source_type: str | None = None,
    difficulty: str | None = None,
    search: str | None = None,
):
    """List content sources (songs, anime quotes, game dialogs)."""
    db = await get_db()
    q = """SELECT s.*, (SELECT COUNT(*) FROM jp_source_vocab sv WHERE sv.source_id = s.id) as vocab_count
           FROM jp_sources s WHERE s.is_active = 1"""
    params: list = []
    if source_type:
        q += " AND s.source_type = ?"
        params.append(source_type)
    if difficulty:
        q += " AND s.difficulty = ?"
        params.append(difficulty)
    if search:
        q += " AND (s.title LIKE ? OR s.artist LIKE ?)"
        s = f"%{search}%"
        params.extend([s, s])
    q += " ORDER BY s.created_at DESC"
    cursor = await db.execute(q, params)
    rows = await cursor.fetchall()
    return [_parse_tags(r) for r in rows]


@router.get("/sources/{source_id}")
async def get_source(source_id: int):
    """Get a source with its linked vocabulary."""
    db = await get_db()
    cursor = await db.execute("SELECT * FROM jp_sources WHERE id = ?", (source_id,))
    source = await cursor.fetchone()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    cursor = await db.execute(
        """SELECT v.*, sv.line_number, sv.context_ja
           FROM jp_source_vocab sv
           JOIN jp_vocabulary v ON v.id = sv.vocab_id
           WHERE sv.source_id = ?
           ORDER BY sv.line_number""",
        (source_id,),
    )
    vocab = [_parse_tags(r) for r in await cursor.fetchall()]

    result = _parse_tags(source)
    result["vocabulary"] = vocab
    return result


@router.post("/sources", response_model=SourceResponse, status_code=201)
async def add_source(data: SourceCreate):
    """Add a content source (song, anime quote, game dialog)."""
    db = await get_db()
    cursor = await db.execute(
        """INSERT INTO jp_sources (title, artist, source_type, content_ja, content_ko, difficulty, tags)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (data.title, data.artist, data.source_type, data.content_ja,
         data.content_ko, data.difficulty, json.dumps(data.tags)),
    )
    source_id = cursor.lastrowid

    # Link vocab
    for vid in data.vocab_ids:
        try:
            await db.execute(
                "INSERT INTO jp_source_vocab (source_id, vocab_id) VALUES (?, ?)",
                (source_id, vid),
            )
        except Exception:
            pass

    await db.commit()
    cursor = await db.execute(
        """SELECT s.*, (SELECT COUNT(*) FROM jp_source_vocab sv WHERE sv.source_id = s.id) as vocab_count
           FROM jp_sources s WHERE s.id = ?""",
        (source_id,),
    )
    row = await cursor.fetchone()
    return _parse_tags(row)


@router.post("/sources/{source_id}/vocab/{vocab_id}")
async def link_vocab_to_source(source_id: int, vocab_id: int, line_number: int = 0, context_ja: str | None = None):
    """Link a vocabulary word to a source."""
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO jp_source_vocab (source_id, vocab_id, line_number, context_ja)
               VALUES (?, ?, ?, ?)""",
            (source_id, vocab_id, line_number, context_ja),
        )
        await db.commit()
    except Exception:
        raise HTTPException(status_code=409, detail="Already linked")
    return {"status": "linked", "source_id": source_id, "vocab_id": vocab_id}


# ── Player Stats & Gamification ──────────────────────────


@router.get("/player", response_model=PlayerStatsResponse)
async def get_player_stats():
    """Get player stats, level, achievements."""
    db = await get_db()
    cursor = await db.execute("SELECT * FROM jp_player_stats WHERE id = 1")
    player = await cursor.fetchone()
    if not player:
        await db.execute("INSERT INTO jp_player_stats (id) VALUES (1)")
        await db.commit()
        cursor = await db.execute("SELECT * FROM jp_player_stats WHERE id = 1")
        player = await cursor.fetchone()

    player = dict(player)
    achievements_ids = json.loads(player["achievements"]) if isinstance(player["achievements"], str) else player["achievements"]

    xp_needed = xp_for_level(player["level"])
    xp_prev = total_xp_for_level(player["level"] - 1) if player["level"] > 1 else 0
    xp_in_level = player["total_xp"] - xp_prev

    accuracy = (player["total_correct"] / player["total_reviews"] * 100) if player["total_reviews"] > 0 else 0

    return {
        "total_xp": player["total_xp"],
        "level": player["level"],
        "xp_current_level": xp_in_level,
        "xp_next_level": xp_needed,
        "current_streak": player["current_streak"],
        "longest_streak": player["longest_streak"],
        "total_reviews": player["total_reviews"],
        "total_correct": player["total_correct"],
        "accuracy": round(accuracy, 1),
        "combo_best": player["combo_best"],
        "achievements": [{"id": a, **ACHIEVEMENTS.get(a, {"name": a, "desc": "", "xp_bonus": 0})} for a in achievements_ids],
        "title": _player_title(player["level"]),
    }


@router.get("/player/achievements")
async def get_all_achievements():
    """Get all possible achievements with unlock status."""
    db = await get_db()
    cursor = await db.execute("SELECT achievements FROM jp_player_stats WHERE id = 1")
    row = await cursor.fetchone()
    unlocked = json.loads(row["achievements"]) if row and isinstance(row["achievements"], str) else []

    result = []
    for aid, info in ACHIEVEMENTS.items():
        is_hidden = info.get("category") == "hidden"
        result.append({
            "id": aid,
            "name": info["name"] if (aid in unlocked or not is_hidden) else "???",
            "desc": info["desc"] if (aid in unlocked or not is_hidden) else "히든 업적 — 특정 조건을 달성하면 해금!",
            "xp_bonus": info["xp_bonus"],
            "category": info.get("category", "milestone"),
            "rarity": info.get("rarity", "common"),
            "unlocked": aid in unlocked,
        })
    return result


# ── Statistics ───────────────────────────────────────────


@router.get("/stats")
async def get_study_stats(days: int = Query(default=30, ge=1, le=365)):
    """Get study statistics over a period."""
    db = await get_db()

    # Daily review counts
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
    daily = [dict(r) for r in await cursor.fetchall()]

    # Mastered vocab (interval >= 21 days = well-learned)
    cursor = await db.execute(
        "SELECT COUNT(*) as cnt FROM jp_srs_cards WHERE interval_days >= 21"
    )
    mastered = (await cursor.fetchone())["cnt"]

    # Level distribution of mastered
    cursor = await db.execute(
        """SELECT v.jlpt_level, COUNT(*) as mastered
           FROM jp_srs_cards c
           JOIN jp_vocabulary v ON v.id = c.vocab_id
           WHERE c.interval_days >= 21
           GROUP BY v.jlpt_level"""
    )
    mastered_by_level = {r["jlpt_level"]: r["mastered"] for r in await cursor.fetchall()}

    # Quiz history
    cursor = await db.execute(
        """SELECT quiz_type, COUNT(*) as count,
                  AVG(correct * 100.0 / total_questions) as avg_accuracy,
                  SUM(xp_earned) as total_xp
           FROM jp_quiz_results
           WHERE created_at >= date('now', ?)
           GROUP BY quiz_type""",
        (f"-{days} days",),
    )
    quiz_stats = [dict(r) for r in await cursor.fetchall()]

    return {
        "period_days": days,
        "daily_reviews": daily,
        "total_reviews": sum(d["total_reviews"] for d in daily),
        "total_correct": sum(d["correct"] for d in daily),
        "total_xp_earned": sum(d["xp_earned"] for d in daily),
        "vocab_mastered": mastered,
        "mastered_by_level": mastered_by_level,
        "quiz_stats": quiz_stats,
        "study_days": len(daily),
    }


@router.get("/stats/heatmap")
async def get_study_heatmap(days: int = Query(default=90, ge=7, le=365)):
    """Get heatmap data for study activity."""
    db = await get_db()
    cursor = await db.execute(
        """SELECT date(created_at) as study_date, COUNT(*) as reviews
           FROM jp_review_logs
           WHERE created_at >= date('now', ?)
           GROUP BY date(created_at)""",
        (f"-{days} days",),
    )
    return [dict(r) for r in await cursor.fetchall()]


# ── Seed ─────────────────────────────────────────────────


@router.post("/seed")
async def seed_data():
    """Seed initial JLPT vocabulary and content sources."""
    from app.database.jp_seed import seed_japanese_data
    result = await seed_japanese_data()
    return result


# ── Daily Quests ────────────────────────────────────────


@router.get("/quests/daily")
async def get_daily_quests():
    """Get today's daily quests. Auto-generates if not yet created."""
    db = await get_db()
    today_str = date.today().isoformat()

    cursor = await db.execute(
        "SELECT * FROM jp_daily_quests WHERE date = ? ORDER BY slot",
        (today_str,),
    )
    quests = [dict(r) for r in await cursor.fetchall()]

    if not quests:
        # Generate new daily quests
        cursor = await db.execute("SELECT * FROM jp_player_stats WHERE id = 1")
        player = await cursor.fetchone()
        p_level = player["level"] if player else 1
        p_streak = player["current_streak"] if player else 0

        templates = generate_daily_quests(p_level, p_streak)
        for t in templates:
            await db.execute(
                """INSERT OR IGNORE INTO jp_daily_quests
                   (date, slot, quest_type, title, description, target, xp_reward, tier)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (today_str, t["slot"], t["quest_type"], t["title"],
                 t["desc"], t["target"], t["xp_reward"], t["tier"]),
            )
        await db.commit()

        cursor = await db.execute(
            "SELECT * FROM jp_daily_quests WHERE date = ? ORDER BY slot",
            (today_str,),
        )
        quests = [dict(r) for r in await cursor.fetchall()]

    return {"date": today_str, "quests": quests}


@router.post("/quests/daily/{quest_id}/progress")
async def update_quest_progress(quest_id: int, increment: int = 1):
    """Manually update a daily quest's progress (for quest types not auto-tracked)."""
    db = await get_db()
    cursor = await db.execute("SELECT * FROM jp_daily_quests WHERE id = ?", (quest_id,))
    quest = await cursor.fetchone()
    if not quest:
        raise HTTPException(status_code=404, detail="Quest not found")

    quest = dict(quest)
    if quest["is_completed"]:
        return {"status": "already_completed", "quest": quest}

    new_progress = min(quest["current_progress"] + increment, quest["target"])
    completed = 1 if new_progress >= quest["target"] else 0
    completed_at = _now() if completed else None

    await db.execute(
        """UPDATE jp_daily_quests SET current_progress = ?, is_completed = ?,
           completed_at = ? WHERE id = ?""",
        (new_progress, completed, completed_at, quest_id),
    )

    xp_earned = 0
    if completed and not quest["is_completed"]:
        xp_earned = quest["xp_reward"]
        await db.execute(
            """UPDATE jp_player_stats SET total_xp = total_xp + ?,
               daily_quests_completed = COALESCE(daily_quests_completed, 0) + 1,
               updated_at = ? WHERE id = 1""",
            (xp_earned, _now()),
        )

    await db.commit()
    return {
        "quest_id": quest_id,
        "progress": new_progress,
        "target": quest["target"],
        "completed": bool(completed),
        "xp_earned": xp_earned,
    }


# ── Weekly Challenge ────────────────────────────────────


@router.get("/challenge/weekly")
async def get_weekly_challenge_endpoint():
    """Get this week's challenge. Auto-generates if not yet created."""
    db = await get_db()
    # Monday of current week
    today = date.today()
    week_start = (today - timedelta(days=today.weekday())).isoformat()
    week_number = today.isocalendar()[1]

    cursor = await db.execute(
        "SELECT * FROM jp_weekly_challenges WHERE week_start = ?",
        (week_start,),
    )
    challenge = await cursor.fetchone()

    if not challenge:
        ch = get_weekly_challenge(week_number)
        await db.execute(
            """INSERT OR IGNORE INTO jp_weekly_challenges
               (week_start, challenge_type, title, description, target, xp_reward)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (week_start, ch["challenge_type"], ch["title"], ch["desc"],
             ch["target"], ch["xp_reward"]),
        )
        await db.commit()
        cursor = await db.execute(
            "SELECT * FROM jp_weekly_challenges WHERE week_start = ?",
            (week_start,),
        )
        challenge = await cursor.fetchone()

    challenge = dict(challenge)

    # Auto-calculate progress based on challenge type
    progress = challenge["current_progress"]
    if not challenge["is_completed"]:
        if challenge["challenge_type"] == "weekly_review_count":
            cursor = await db.execute(
                "SELECT COUNT(*) as cnt FROM jp_review_logs WHERE created_at >= ?",
                (week_start,),
            )
            progress = (await cursor.fetchone())["cnt"]
        elif challenge["challenge_type"] == "weekly_quiz_count":
            cursor = await db.execute(
                "SELECT COUNT(*) as cnt FROM jp_quiz_results WHERE created_at >= ?",
                (week_start,),
            )
            progress = (await cursor.fetchone())["cnt"]
        elif challenge["challenge_type"] == "weekly_xp":
            cursor = await db.execute(
                "SELECT SUM(xp_earned) as total FROM jp_review_logs WHERE created_at >= ?",
                (week_start,),
            )
            row = await cursor.fetchone()
            progress = row["total"] or 0
        elif challenge["challenge_type"] == "weekly_combo":
            cursor = await db.execute(
                "SELECT MAX(max_combo) as best FROM jp_quiz_results WHERE created_at >= ?",
                (week_start,),
            )
            row = await cursor.fetchone()
            progress = row["best"] or 0
        elif challenge["challenge_type"] == "weekly_streak":
            cursor = await db.execute(
                """SELECT COUNT(DISTINCT date(created_at)) as days
                   FROM jp_review_logs WHERE created_at >= ?""",
                (week_start,),
            )
            progress = (await cursor.fetchone())["days"]
        elif challenge["challenge_type"] == "weekly_accuracy":
            cursor = await db.execute(
                """SELECT SUM(CASE WHEN quality >= 3 THEN 1 ELSE 0 END) as correct,
                          COUNT(*) as total
                   FROM jp_review_logs WHERE created_at >= ?""",
                (week_start,),
            )
            row = await cursor.fetchone()
            if row["total"] and row["total"] > 0:
                progress = int(row["correct"] / row["total"] * 100)
            else:
                progress = 0

        # Check completion
        completed = progress >= challenge["target"]
        if completed and not challenge["is_completed"]:
            await db.execute(
                """UPDATE jp_weekly_challenges SET current_progress = ?,
                   is_completed = 1, completed_at = ? WHERE id = ?""",
                (progress, _now(), challenge["id"]),
            )
            await db.execute(
                """UPDATE jp_player_stats SET total_xp = total_xp + ?,
                   weekly_challenges_completed = COALESCE(weekly_challenges_completed, 0) + 1,
                   updated_at = ? WHERE id = 1""",
                (challenge["xp_reward"], _now()),
            )
            await db.commit()
            challenge["is_completed"] = 1
            challenge["xp_just_earned"] = challenge["xp_reward"]
        else:
            await db.execute(
                "UPDATE jp_weekly_challenges SET current_progress = ? WHERE id = ?",
                (progress, challenge["id"]),
            )
            await db.commit()

        challenge["current_progress"] = progress

    return {
        "week_start": week_start,
        "challenge": challenge,
        "days_remaining": 7 - today.weekday(),
    }


# ── Mastery Tiers ───────────────────────────────────────


@router.get("/mastery/summary")
async def get_mastery_summary():
    """Get vocabulary mastery tier distribution."""
    db = await get_db()
    cursor = await db.execute(
        """SELECT c.repetitions, c.interval_days, v.jlpt_level
           FROM jp_srs_cards c
           JOIN jp_vocabulary v ON v.id = c.vocab_id
           WHERE v.is_active = 1"""
    )
    rows = await cursor.fetchall()

    tier_counts = {t: 0 for t in MASTERY_TIERS}
    tier_by_level: dict[str, dict[str, int]] = {}

    for row in rows:
        tier = get_mastery_tier(row["repetitions"], row["interval_days"])
        tier_counts[tier] += 1
        jlpt = row["jlpt_level"]
        if jlpt not in tier_by_level:
            tier_by_level[jlpt] = {t: 0 for t in MASTERY_TIERS}
        tier_by_level[jlpt][tier] += 1

    total = sum(tier_counts.values())
    tier_details = []
    for key, info in MASTERY_TIERS.items():
        tier_details.append({
            "tier": key,
            "label": info["label"],
            "icon": info["icon"],
            "count": tier_counts[key],
            "percentage": round(tier_counts[key] / total * 100, 1) if total > 0 else 0,
        })

    return {
        "total_vocab": total,
        "tiers": tier_details,
        "by_jlpt_level": tier_by_level,
    }


@router.get("/mastery/vocab")
async def get_vocab_mastery(
    jlpt_level: str | None = None,
    tier: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
):
    """Get vocabulary with mastery tier info."""
    db = await get_db()
    q = """SELECT v.*, c.repetitions, c.interval_days, c.ease_factor, c.next_review
           FROM jp_srs_cards c
           JOIN jp_vocabulary v ON v.id = c.vocab_id
           WHERE v.is_active = 1"""
    params: list = []
    if jlpt_level:
        q += " AND v.jlpt_level = ?"
        params.append(jlpt_level)
    q += " ORDER BY c.interval_days DESC, c.repetitions DESC LIMIT ?"
    params.append(limit)

    cursor = await db.execute(q, params)
    rows = await cursor.fetchall()

    result = []
    for row in rows:
        row = dict(row)
        t = get_mastery_tier(row["repetitions"], row["interval_days"])
        if tier and t != tier:
            continue
        info = MASTERY_TIERS[t]
        row["mastery_tier"] = t
        row["mastery_label"] = info["label"]
        row["mastery_icon"] = info["icon"]
        result.append(row)

    return result


# ── Helpers ──────────────────────────────────────────────


def _shuffle(items: list) -> list:
    shuffled = items.copy()
    random.shuffle(shuffled)
    return shuffled


# ── Vocabulary Similarity & Grouping ──────────────────────


@router.get("/vocab/{vocab_id}/similar")
async def get_similar_vocab(vocab_id: int, top_n: int = Query(10, ge=1, le=30)):
    """Find words similar to the given vocabulary item (feature-based)."""
    from app.services.vocab_similarity import find_similar_words
    return await find_similar_words(vocab_id, top_n=top_n)


@router.get("/vocab/{vocab_id}/similar-semantic")
async def get_similar_vocab_semantic(vocab_id: int, top_n: int = Query(10, ge=1, le=30)):
    """Find semantically similar words using embeddings (requires sentence-transformers)."""
    from app.services.vocab_similarity import find_similar_words_embedding
    return await find_similar_words_embedding(vocab_id, top_n=top_n)


@router.get("/vocab/groups/thematic")
async def get_thematic_groups(
    jlpt_level: str | None = None,
    max_groups: int = Query(8, ge=1, le=20),
    group_size: int = Query(5, ge=2, le=15),
):
    """Group vocabulary into thematic clusters for study sessions."""
    from app.services.vocab_similarity import group_vocab_by_theme
    return await group_vocab_by_theme(
        jlpt_level=jlpt_level,
        max_groups=max_groups,
        group_size=group_size,
    )
