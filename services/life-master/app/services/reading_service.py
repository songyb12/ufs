"""Reading practice service — passages, comprehension quizzes, vocab highlights."""

import logging

from app.database.connection import get_db

logger = logging.getLogger("life-master.reading")


# ── Listing ───────────────────────────────────────────────


async def get_passages(
    jlpt_level: str | None = None,
    category: str | None = None,
    page: int = 1,
    per_page: int = 10,
) -> dict:
    """Filtered, paginated passage listing."""
    db = await get_db()
    conditions: list[str] = []
    params: list = []

    if jlpt_level:
        conditions.append("p.jlpt_level = ?")
        params.append(jlpt_level)
    if category:
        conditions.append("p.category = ?")
        params.append(category)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    offset = (page - 1) * per_page

    count_row = await db.execute(
        f"SELECT COUNT(*) FROM jp_reading_passage p {where}", params
    )
    total = (await count_row.fetchone())[0]

    cursor = await db.execute(
        f"""SELECT p.id, p.title, p.jlpt_level, p.category, p.word_count,
                   (SELECT COUNT(*) FROM jp_reading_question q WHERE q.passage_id = p.id) as question_count
            FROM jp_reading_passage p
            {where}
            ORDER BY p.jlpt_level, p.id
            LIMIT ? OFFSET ?""",
        [*params, per_page, offset],
    )
    rows = await cursor.fetchall()

    items = []
    for r in rows:
        items.append({
            "id": r[0],
            "title": r[1],
            "jlpt_level": r[2],
            "category": r[3],
            "word_count": r[4],
            "question_count": r[5],
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page,
    }


# ── Detail ────────────────────────────────────────────────


async def get_passage_detail(passage_id: int) -> dict | None:
    """Passage content with all questions."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM jp_reading_passage WHERE id = ?",
        (passage_id,),
    )
    row = await cursor.fetchone()
    if not row:
        return None

    passage = {
        "id": row[0],
        "title": row[1],
        "content_jp": row[2],
        "content_ko": row[3],
        "jlpt_level": row[4],
        "category": row[5],
        "word_count": row[6],
    }

    q_cursor = await db.execute(
        """SELECT id, question_jp, question_ko, option_a, option_b, option_c, option_d
           FROM jp_reading_question
           WHERE passage_id = ?
           ORDER BY id""",
        (passage_id,),
    )
    questions = []
    for q in await q_cursor.fetchall():
        questions.append({
            "id": q[0],
            "question_jp": q[1],
            "question_ko": q[2],
            "options": {
                "a": q[3],
                "b": q[4],
                "c": q[5],
                "d": q[6],
            },
        })
    passage["questions"] = questions

    return passage


# ── Submit Answers ────────────────────────────────────────


async def submit_reading_answers(passage_id: int, answers: dict[str, str]) -> dict:
    """Grade reading comprehension answers.

    answers: {question_id: "a"|"b"|"c"|"d"}
    """
    db = await get_db()

    # Verify passage exists
    p_cursor = await db.execute(
        "SELECT id FROM jp_reading_passage WHERE id = ?", (passage_id,)
    )
    if not await p_cursor.fetchone():
        return {"error": "Passage not found"}

    # Fetch all questions for this passage
    q_cursor = await db.execute(
        """SELECT id, question_jp, question_ko, option_a, option_b, option_c, option_d,
                  correct_answer, explanation
           FROM jp_reading_question
           WHERE passage_id = ?
           ORDER BY id""",
        (passage_id,),
    )
    rows = await q_cursor.fetchall()
    if not rows:
        return {"error": "No questions for this passage"}

    total = 0
    correct = 0
    details = []

    for q in rows:
        qid = q[0]
        qid_str = str(qid)
        correct_ans = q[7].strip().lower()
        explanation = q[8]

        user_ans = answers.get(qid_str, "").strip().lower()
        is_correct = user_ans == correct_ans
        if is_correct:
            correct += 1
        total += 1

        options = {"a": q[3], "b": q[4], "c": q[5], "d": q[6]}

        details.append({
            "question_id": qid,
            "question_jp": q[1],
            "question_ko": q[2],
            "user_answer": user_ans or None,
            "correct_answer": correct_ans,
            "correct_answer_text": options.get(correct_ans, ""),
            "is_correct": is_correct,
            "explanation": explanation,
        })

    score_percent = round((correct / total) * 100) if total > 0 else 0

    return {
        "passage_id": passage_id,
        "total": total,
        "correct": correct,
        "score_percent": score_percent,
        "details": details,
    }


# ── Vocab Highlights ──────────────────────────────────────


async def get_passage_vocab_highlights(passage_id: int) -> dict | None:
    """Find jp_vocabulary words that appear in the passage content."""
    db = await get_db()

    # Get passage content
    p_cursor = await db.execute(
        "SELECT id, title, content_jp FROM jp_reading_passage WHERE id = ?",
        (passage_id,),
    )
    row = await p_cursor.fetchone()
    if not row:
        return None

    content = row[2]

    # Fetch all active vocab words and check if they appear in the content
    # Use words of length >= 2 to avoid single-kana false positives
    v_cursor = await db.execute(
        "SELECT id, word, reading, meaning, jlpt_level, part_of_speech FROM jp_vocabulary WHERE is_active = 1 AND LENGTH(word) >= 2"
    )
    vocab_rows = await v_cursor.fetchall()

    highlights = []
    for v in vocab_rows:
        word = v[1]
        if word in content:
            highlights.append({
                "vocab_id": v[0],
                "word": word,
                "reading": v[2],
                "meaning": v[3],
                "jlpt_level": v[4],
                "part_of_speech": v[5],
            })

    # Sort by position in text for natural reading order
    highlights.sort(key=lambda h: content.index(h["word"]))

    return {
        "passage_id": passage_id,
        "title": row[1],
        "highlight_count": len(highlights),
        "vocabulary": highlights,
    }
