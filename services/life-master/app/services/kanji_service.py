"""Kanji learning service — listing, search, quizzes."""

import logging
import random

from app.database.connection import get_db

logger = logging.getLogger("life-master.kanji")


# ── Listing & Detail ──────────────────────────────────────


async def get_kanji_list(
    jlpt_level: str | None = None,
    page: int = 1,
    per_page: int = 20,
) -> dict:
    """Filtered, paginated kanji listing."""
    db = await get_db()
    conditions: list[str] = ["k.is_active = 1"]
    params: list = []

    if jlpt_level:
        conditions.append("k.jlpt_level = ?")
        params.append(jlpt_level)

    where = " AND ".join(conditions)
    offset = (page - 1) * per_page

    count_row = await db.execute(
        f"SELECT COUNT(*) FROM jp_kanji k WHERE {where}", params
    )
    total = (await count_row.fetchone())[0]

    cursor = await db.execute(
        f"""SELECT k.id, k.character, k.meaning_ko, k.meaning_en,
                   k.onyomi, k.kunyomi, k.jlpt_level, k.grade,
                   k.stroke_count, k.radicals, k.order_index
            FROM jp_kanji k
            WHERE {where}
            ORDER BY k.jlpt_level, k.order_index
            LIMIT ? OFFSET ?""",
        [*params, per_page, offset],
    )
    rows = await cursor.fetchall()

    items = []
    for r in rows:
        items.append({
            "id": r[0],
            "character": r[1],
            "meaning_ko": r[2],
            "meaning_en": r[3],
            "onyomi": r[4],
            "kunyomi": r[5],
            "jlpt_level": r[6],
            "grade": r[7],
            "stroke_count": r[8],
            "radicals": r[9],
            "order_index": r[10],
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page,
    }


async def get_kanji_detail(kanji_id: int) -> dict | None:
    """Kanji detail with linked vocabulary via jp_kanji_vocab_link."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM jp_kanji WHERE id = ? AND is_active = 1",
        (kanji_id,),
    )
    row = await cursor.fetchone()
    if not row:
        return None

    kanji = {
        "id": row[0],
        "character": row[1],
        "meaning_ko": row[2],
        "meaning_en": row[3],
        "onyomi": row[4],
        "kunyomi": row[5],
        "jlpt_level": row[6],
        "grade": row[7],
        "stroke_count": row[8],
        "radicals": row[9],
        "order_index": row[10],
    }

    # Linked vocabulary
    vocab_cursor = await db.execute(
        """SELECT v.id, v.word, v.reading, v.meaning, v.jlpt_level, v.part_of_speech
           FROM jp_vocabulary v
           JOIN jp_kanji_vocab_link lnk ON lnk.vocab_id = v.id
           WHERE lnk.kanji_id = ?
           ORDER BY v.jlpt_level, v.id""",
        (kanji_id,),
    )
    vocab_rows = await vocab_cursor.fetchall()
    kanji["vocabulary"] = [
        {
            "id": v[0],
            "word": v[1],
            "reading": v[2],
            "meaning": v[3],
            "jlpt_level": v[4],
            "part_of_speech": v[5],
        }
        for v in vocab_rows
    ]

    return kanji


# ── Search ────────────────────────────────────────────────


async def search_kanji(query: str) -> list[dict]:
    """Search kanji by character, meaning, or readings (LIKE match)."""
    db = await get_db()
    like = f"%{query}%"
    cursor = await db.execute(
        """SELECT id, character, meaning_ko, meaning_en,
                  onyomi, kunyomi, jlpt_level, stroke_count
           FROM jp_kanji
           WHERE is_active = 1
             AND (character LIKE ?
               OR meaning_ko LIKE ?
               OR meaning_en LIKE ?
               OR onyomi LIKE ?
               OR kunyomi LIKE ?)
           ORDER BY jlpt_level, order_index
           LIMIT 50""",
        (like, like, like, like, like),
    )
    rows = await cursor.fetchall()
    return [
        {
            "id": r[0],
            "character": r[1],
            "meaning_ko": r[2],
            "meaning_en": r[3],
            "onyomi": r[4],
            "kunyomi": r[5],
            "jlpt_level": r[6],
            "stroke_count": r[7],
        }
        for r in rows
    ]


# ── Quiz: Reading ─────────────────────────────────────────


async def kanji_quiz_reading(
    jlpt_level: str | None = None,
    count: int = 5,
) -> list[dict]:
    """Multiple-choice quiz: show kanji, pick the correct reading."""
    db = await get_db()
    conditions = ["is_active = 1"]
    params: list = []

    if jlpt_level:
        conditions.append("jlpt_level = ?")
        params.append(jlpt_level)

    where = " AND ".join(conditions)

    # Fetch candidates that have at least one reading
    cursor = await db.execute(
        f"""SELECT id, character, meaning_ko, onyomi, kunyomi
            FROM jp_kanji
            WHERE {where} AND (onyomi IS NOT NULL OR kunyomi IS NOT NULL)
            ORDER BY RANDOM()
            LIMIT ?""",
        [*params, count * 3],
    )
    candidates = await cursor.fetchall()
    if not candidates:
        return []

    # Build all available readings for distractor pool
    all_readings: list[str] = []
    for c in candidates:
        for reading in _extract_readings(c[3], c[4]):
            if reading not in all_readings:
                all_readings.append(reading)

    questions = []
    for c in candidates:
        kid, char, meaning, onyomi, kunyomi = c
        readings = _extract_readings(onyomi, kunyomi)
        if not readings:
            continue

        answer = random.choice(readings)
        distractors = [r for r in all_readings if r not in readings]
        random.shuffle(distractors)
        choices = [answer] + distractors[:3]
        random.shuffle(choices)

        questions.append({
            "kanji_id": kid,
            "character": char,
            "meaning_ko": meaning,
            "answer": answer,
            "choices": choices,
        })

        if len(questions) >= count:
            break

    return questions


# ── Quiz: Meaning ─────────────────────────────────────────


async def kanji_quiz_meaning(
    jlpt_level: str | None = None,
    count: int = 5,
) -> list[dict]:
    """Multiple-choice quiz: show kanji, pick the correct meaning."""
    db = await get_db()
    conditions = ["is_active = 1"]
    params: list = []

    if jlpt_level:
        conditions.append("jlpt_level = ?")
        params.append(jlpt_level)

    where = " AND ".join(conditions)

    cursor = await db.execute(
        f"""SELECT id, character, meaning_ko, onyomi, kunyomi
            FROM jp_kanji
            WHERE {where}
            ORDER BY RANDOM()
            LIMIT ?""",
        [*params, count * 3],
    )
    candidates = await cursor.fetchall()
    if not candidates:
        return []

    # Collect all meanings for distractors
    all_meanings = list({c[2] for c in candidates})

    questions = []
    for c in candidates:
        kid, char, meaning, onyomi, kunyomi = c
        distractors = [m for m in all_meanings if m != meaning]
        random.shuffle(distractors)
        choices = [meaning] + distractors[:3]
        random.shuffle(choices)

        questions.append({
            "kanji_id": kid,
            "character": char,
            "onyomi": onyomi,
            "kunyomi": kunyomi,
            "answer": meaning,
            "choices": choices,
        })

        if len(questions) >= count:
            break

    return questions


# ── Helpers ───────────────────────────────────────────────


def _extract_readings(onyomi: str | None, kunyomi: str | None) -> list[str]:
    """Extract individual reading entries from comma/dot separated strings."""
    readings: list[str] = []
    for field in (onyomi, kunyomi):
        if not field:
            continue
        for part in field.replace("、", ",").replace("・", ",").split(","):
            stripped = part.strip()
            if stripped:
                readings.append(stripped)
    return readings
