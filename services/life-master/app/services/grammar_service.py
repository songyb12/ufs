"""Grammar learning service — SRS, quizzes, listing."""

import json
import logging
import random
import re
from datetime import date, datetime, timezone

from app.database.connection import get_db
from app.services.japanese import sm2_update

logger = logging.getLogger("life-master.grammar")


# ── Listing & Detail ──────────────────────────────────────


async def get_grammar_list(
    jlpt_level: str | None = None,
    category: str | None = None,
    page: int = 1,
    per_page: int = 20,
) -> dict:
    """Filtered, paginated grammar point listing."""
    db = await get_db()
    conditions: list[str] = ["g.is_active = 1"]
    params: list[str] = []

    if jlpt_level:
        conditions.append("g.jlpt_level = ?")
        params.append(jlpt_level)
    if category:
        conditions.append("g.category = ?")
        params.append(category)

    where = " AND ".join(conditions)
    offset = (page - 1) * per_page

    count_row = await db.execute(
        f"SELECT COUNT(*) FROM jp_grammar g WHERE {where}", params
    )
    total = (await count_row.fetchone())[0]

    cursor = await db.execute(
        f"""SELECT g.*, (SELECT COUNT(*) FROM jp_grammar_example e WHERE e.grammar_id = g.id) as example_count
            FROM jp_grammar g
            WHERE {where}
            ORDER BY g.jlpt_level, g.order_index
            LIMIT ? OFFSET ?""",
        [*params, per_page, offset],
    )
    rows = await cursor.fetchall()

    items = []
    for r in rows:
        items.append({
            "id": r[0],
            "grammar_point": r[1],
            "meaning_ko": r[2],
            "meaning_en": r[3],
            "jlpt_level": r[4],
            "category": r[5],
            "formation": r[6],
            "notes": r[7],
            "order_index": r[8],
            "example_count": r[-1],
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page,
    }


async def get_grammar_detail(grammar_id: int) -> dict | None:
    """Grammar point with all examples."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM jp_grammar WHERE id = ? AND is_active = 1",
        (grammar_id,),
    )
    row = await cursor.fetchone()
    if not row:
        return None

    grammar = {
        "id": row[0],
        "grammar_point": row[1],
        "meaning_ko": row[2],
        "meaning_en": row[3],
        "jlpt_level": row[4],
        "category": row[5],
        "formation": row[6],
        "notes": row[7],
        "order_index": row[8],
    }

    ex_cursor = await db.execute(
        "SELECT id, sentence_jp, sentence_ko, sentence_en, audio_url FROM jp_grammar_example WHERE grammar_id = ? ORDER BY id",
        (grammar_id,),
    )
    examples = []
    for e in await ex_cursor.fetchall():
        examples.append({
            "id": e[0],
            "sentence_jp": e[1],
            "sentence_ko": e[2],
            "sentence_en": e[3],
            "audio_url": e[4],
        })
    grammar["examples"] = examples

    # SRS state if exists
    srs_cursor = await db.execute(
        "SELECT ease_factor, interval_days, repetitions, next_review, last_reviewed FROM jp_grammar_srs WHERE grammar_id = ?",
        (grammar_id,),
    )
    srs = await srs_cursor.fetchone()
    if srs:
        grammar["srs"] = {
            "ease_factor": srs[0],
            "interval_days": srs[1],
            "repetitions": srs[2],
            "next_review": srs[3],
            "last_reviewed": srs[4],
        }

    return grammar


# ── SRS Review ────────────────────────────────────────────


async def get_grammar_for_review(limit: int = 20) -> list[dict]:
    """Get grammar cards due for review today."""
    db = await get_db()
    today_str = date.today().isoformat()
    cursor = await db.execute(
        """SELECT g.id, g.grammar_point, g.meaning_ko, g.meaning_en,
                  g.jlpt_level, g.category, g.formation,
                  s.ease_factor, s.interval_days, s.repetitions, s.next_review
           FROM jp_grammar g
           JOIN jp_grammar_srs s ON s.grammar_id = g.id
           WHERE s.next_review <= ? AND g.is_active = 1
           ORDER BY s.next_review ASC
           LIMIT ?""",
        (today_str, limit),
    )
    rows = await cursor.fetchall()
    items = []
    for r in rows:
        items.append({
            "id": r[0],
            "grammar_point": r[1],
            "meaning_ko": r[2],
            "meaning_en": r[3],
            "jlpt_level": r[4],
            "category": r[5],
            "formation": r[6],
            "srs": {
                "ease_factor": r[7],
                "interval_days": r[8],
                "repetitions": r[9],
                "next_review": r[10],
            },
        })
    return items


async def submit_grammar_review(grammar_id: int, quality: int) -> dict:
    """Submit a grammar review and update SRS card."""
    if quality < 0 or quality > 5:
        raise ValueError("quality must be 0-5")

    db = await get_db()

    # Get or create SRS card
    cursor = await db.execute(
        "SELECT ease_factor, interval_days, repetitions, quality_history FROM jp_grammar_srs WHERE grammar_id = ?",
        (grammar_id,),
    )
    card = await cursor.fetchone()

    if card:
        ef, interval, reps, history_json = card[0], card[1], card[2], card[3]
        history = json.loads(history_json) if history_json else []
    else:
        ef, interval, reps = 2.5, 0, 0
        history = []
        await db.execute(
            "INSERT INTO jp_grammar_srs (grammar_id) VALUES (?)",
            (grammar_id,),
        )

    # Apply SM-2
    updated = sm2_update(quality, reps, ef, interval)
    history.append(quality)

    now = datetime.now(timezone.utc).isoformat()
    await db.execute(
        """UPDATE jp_grammar_srs
           SET ease_factor = ?, interval_days = ?, repetitions = ?,
               next_review = ?, last_reviewed = ?, quality_history = ?
           WHERE grammar_id = ?""",
        (
            updated["ease_factor"],
            updated["interval_days"],
            updated["repetitions"],
            updated["next_review"],
            now,
            json.dumps(history),
            grammar_id,
        ),
    )
    await db.commit()

    return {
        "grammar_id": grammar_id,
        "quality": quality,
        **updated,
        "quality_history": history,
    }


# ── Quiz: Fill-in-the-blank ──────────────────────────────


async def grammar_quiz_fill_blank(
    jlpt_level: str = "N5",
    count: int = 5,
) -> list[dict]:
    """Generate fill-in-the-blank quiz from grammar examples."""
    db = await get_db()
    cursor = await db.execute(
        """SELECT g.id, g.grammar_point, g.meaning_ko, g.category,
                  e.sentence_jp, e.sentence_ko
           FROM jp_grammar g
           JOIN jp_grammar_example e ON e.grammar_id = g.id
           WHERE g.jlpt_level = ? AND g.is_active = 1
           ORDER BY RANDOM()
           LIMIT ?""",
        (jlpt_level, count * 3),  # fetch extra for filtering
    )
    rows = await cursor.fetchall()
    if not rows:
        return []

    # Build questions
    questions = []
    seen_grammar_ids: set[int] = set()

    for r in rows:
        gid, point, meaning, category, sentence_jp, sentence_ko = r
        if gid in seen_grammar_ids:
            continue

        # Create blank by removing grammar point from sentence
        blank_sentence = _make_blank(sentence_jp, point)
        if blank_sentence == sentence_jp:
            continue  # couldn't create blank, skip

        # Generate distractors from other grammar points
        distractor_cursor = await db.execute(
            """SELECT grammar_point FROM jp_grammar
               WHERE jlpt_level = ? AND id != ? AND category = ?
               ORDER BY RANDOM() LIMIT 3""",
            (jlpt_level, gid, category),
        )
        distractors = [d[0] for d in await distractor_cursor.fetchall()]

        # Pad distractors if not enough from same category
        if len(distractors) < 3:
            extra_cursor = await db.execute(
                """SELECT grammar_point FROM jp_grammar
                   WHERE jlpt_level = ? AND id != ?
                   ORDER BY RANDOM() LIMIT ?""",
                (jlpt_level, gid, 3 - len(distractors)),
            )
            distractors.extend([d[0] for d in await extra_cursor.fetchall()])

        choices = [point] + distractors[:3]
        random.shuffle(choices)

        questions.append({
            "grammar_id": gid,
            "question": blank_sentence,
            "sentence_ko": sentence_ko,
            "answer": point,
            "choices": choices,
            "meaning_ko": meaning,
        })
        seen_grammar_ids.add(gid)

        if len(questions) >= count:
            break

    return questions


def _make_blank(sentence: str, grammar_point: str) -> str:
    """Replace grammar point in sentence with ＿＿＿."""
    # Try exact match first
    clean_point = grammar_point.lstrip("~～")
    if clean_point in sentence:
        return sentence.replace(clean_point, "＿＿＿", 1)
    # Try without tilde prefix variations
    for variant in [grammar_point, clean_point]:
        if variant in sentence:
            return sentence.replace(variant, "＿＿＿", 1)
    return sentence  # couldn't find match


# ── Quiz: Sentence ordering ──────────────────────────────


async def grammar_quiz_sentence_order(
    jlpt_level: str = "N5",
    count: int = 5,
) -> list[dict]:
    """Generate sentence-ordering quiz from grammar examples."""
    db = await get_db()
    cursor = await db.execute(
        """SELECT g.id, g.grammar_point, g.meaning_ko,
                  e.sentence_jp, e.sentence_ko
           FROM jp_grammar g
           JOIN jp_grammar_example e ON e.grammar_id = g.id
           WHERE g.jlpt_level = ? AND g.is_active = 1
           ORDER BY RANDOM()
           LIMIT ?""",
        (jlpt_level, count * 2),
    )
    rows = await cursor.fetchall()

    questions = []
    seen: set[int] = set()

    for r in rows:
        gid, point, meaning, sentence_jp, sentence_ko = r
        if gid in seen:
            continue

        # Tokenize sentence into chunks (simple approach: split by particles + morphemes)
        tokens = _tokenize_simple(sentence_jp)
        if len(tokens) < 3:
            continue  # too short to shuffle meaningfully

        shuffled = tokens[:]
        # Shuffle until different from original
        for _ in range(10):
            random.shuffle(shuffled)
            if shuffled != tokens:
                break

        questions.append({
            "grammar_id": gid,
            "grammar_point": point,
            "scrambled": shuffled,
            "answer": tokens,
            "sentence_ko": sentence_ko,
            "meaning_ko": meaning,
        })
        seen.add(gid)

        if len(questions) >= count:
            break

    return questions


def _tokenize_simple(sentence: str) -> list[str]:
    """Simple Japanese tokenization by splitting on particles and punctuation."""
    # Remove trailing punctuation
    sentence = sentence.rstrip("。、！？")
    # Split on common particle boundaries
    # This is a rough heuristic; perfect tokenization requires MeCab
    tokens = re.split(r'(は|が|を|に|で|へ|と|も|の|から|まで|より|って|けど|ので|たら|ても|ば|なら)', sentence)
    # Recombine: attach particle to preceding word
    result = []
    i = 0
    while i < len(tokens):
        chunk = tokens[i].strip()
        if chunk:
            # If next token is a particle, attach it
            if i + 1 < len(tokens) and tokens[i + 1].strip():
                chunk += tokens[i + 1].strip()
                i += 1
            result.append(chunk)
        i += 1
    # If we got too few tokens, fall back to character-level chunking
    if len(result) < 3:
        result = [sentence[j:j+3] for j in range(0, len(sentence), 3)]
    return result
