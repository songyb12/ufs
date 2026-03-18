"""Writing practice service — translation, sentence ordering, grammar usage."""

import json
import logging
import random
import re
import unicodedata

from app.database.connection import get_db

logger = logging.getLogger("life-master.writing")


# ── Translation Exercise ──────────────────────────────────


async def get_translation_exercise(jlpt_level: str = "N5") -> dict | None:
    """Random translation exercise: Korean prompt → write in Japanese."""
    db = await get_db()
    cursor = await db.execute(
        """SELECT id, prompt_ko, prompt_jp, answer_jp, hint, grammar_point, difficulty
           FROM jp_writing_exercise
           WHERE exercise_type = 'translation' AND jlpt_level = ?
           ORDER BY RANDOM() LIMIT 1""",
        (jlpt_level,),
    )
    row = await cursor.fetchone()
    if not row:
        return None

    return {
        "exercise_id": row[0],
        "exercise_type": "translation",
        "jlpt_level": jlpt_level,
        "prompt_ko": row[1],
        "prompt_jp": row[2],
        "hint": row[4],
        "grammar_point": row[5],
        "difficulty": row[6],
    }


# ── Sentence Order Exercise ───────────────────────────────


async def get_sentence_order_exercise(jlpt_level: str = "N5") -> dict | None:
    """Random sentence ordering: shuffled words → arrange correctly."""
    db = await get_db()
    cursor = await db.execute(
        """SELECT id, prompt_ko, answer_jp, hint, grammar_point, difficulty
           FROM jp_writing_exercise
           WHERE exercise_type = 'sentence_order' AND jlpt_level = ?
           ORDER BY RANDOM() LIMIT 1""",
        (jlpt_level,),
    )
    row = await cursor.fetchone()
    if not row:
        return None

    answer = row[2]
    # Split into words by spaces or particles
    words = _split_japanese(answer)

    # Shuffle until different
    shuffled = words[:]
    for _ in range(20):
        random.shuffle(shuffled)
        if shuffled != words:
            break

    return {
        "exercise_id": row[0],
        "exercise_type": "sentence_order",
        "jlpt_level": jlpt_level,
        "prompt_ko": row[1],
        "scrambled_words": shuffled,
        "word_count": len(words),
        "hint": row[3],
        "grammar_point": row[4],
        "difficulty": row[5],
    }


def _split_japanese(sentence: str) -> list[str]:
    """Split Japanese sentence into word-like chunks for ordering exercise."""
    # Remove trailing punctuation
    sentence = sentence.rstrip("。、！？")
    # Split by common particles as boundaries
    # Attach particle to preceding word
    parts = re.split(r'(は|が|を|に|で|へ|と|も|の|から|まで|より|って|けど|ので)', sentence)
    result = []
    i = 0
    while i < len(parts):
        chunk = parts[i].strip()
        if chunk:
            # If next is a particle, attach
            if i + 1 < len(parts) and parts[i + 1].strip():
                chunk += parts[i + 1].strip()
                i += 1
            result.append(chunk)
        i += 1
    if len(result) < 2:
        # Fallback: split by spaces if present
        if " " in sentence:
            result = sentence.split()
        else:
            # Split into roughly equal chunks
            n = max(2, len(sentence) // 4)
            result = [sentence[j:j + n] for j in range(0, len(sentence), n)]
    return result


# ── Grammar Usage Exercise ────────────────────────────────


async def get_grammar_usage_exercise(jlpt_level: str = "N5") -> dict | None:
    """Random grammar usage exercise: use specific grammar point in a sentence."""
    db = await get_db()
    cursor = await db.execute(
        """SELECT id, prompt_ko, prompt_jp, answer_jp, grammar_point, hint, difficulty
           FROM jp_writing_exercise
           WHERE exercise_type = 'grammar_usage' AND jlpt_level = ?
           ORDER BY RANDOM() LIMIT 1""",
        (jlpt_level,),
    )
    row = await cursor.fetchone()
    if not row:
        return None

    return {
        "exercise_id": row[0],
        "exercise_type": "grammar_usage",
        "jlpt_level": jlpt_level,
        "prompt_ko": row[1],
        "prompt_jp": row[2],
        "grammar_point": row[4],
        "hint": row[5],
        "difficulty": row[6],
    }


# ── Answer Checking ───────────────────────────────────────


async def check_writing_answer(exercise_id: int, user_answer: str) -> dict:
    """Check user's writing answer against correct answer and alternatives."""
    db = await get_db()
    cursor = await db.execute(
        """SELECT id, exercise_type, prompt_ko, answer_jp, alt_answers, grammar_point
           FROM jp_writing_exercise WHERE id = ?""",
        (exercise_id,),
    )
    row = await cursor.fetchone()
    if not row:
        return {"error": "Exercise not found"}

    answer_jp = row[3]
    alt_answers_json = row[4]
    alt_answers: list[str] = json.loads(alt_answers_json) if alt_answers_json else []

    # Normalize for comparison
    user_norm = _normalize(user_answer)
    correct_norm = _normalize(answer_jp)
    alt_norms = [_normalize(a) for a in alt_answers]

    is_correct = user_norm == correct_norm or user_norm in alt_norms

    return {
        "exercise_id": exercise_id,
        "exercise_type": row[1],
        "is_correct": is_correct,
        "user_answer": user_answer,
        "correct_answer": answer_jp,
        "alt_answers": alt_answers,
        "prompt_ko": row[2],
        "grammar_point": row[5],
    }


def _normalize(text: str) -> str:
    """Normalize Japanese text for comparison: strip whitespace, punctuation, normalize unicode."""
    text = unicodedata.normalize("NFKC", text)
    # Remove common punctuation and whitespace
    text = re.sub(r'[\s。、！？!?,.\-~～・「」『』（）()]+', '', text)
    # Convert fullwidth alphanumerics to halfwidth
    text = text.strip()
    return text
