"""Vocabulary Similarity & Grouping for Japanese learning.

Two modes:
1. Feature-based (default, no dependencies): Groups words by JLPT level,
   part of speech, tags, and character overlap.
2. Embedding-based (optional, requires sentence-transformers): Groups words
   by semantic similarity using multilingual embeddings.
"""

import json
import logging
import math
from collections import defaultdict
from typing import Any

from app.database.connection import get_db

logger = logging.getLogger("life-master.vocab_similarity")


# ---------------------------------------------------------------------------
# Feature-based similarity (always available)
# ---------------------------------------------------------------------------

def _jaccard(a: set, b: set) -> float:
    """Jaccard similarity between two sets."""
    if not a and not b:
        return 0.0
    return len(a & b) / len(a | b)


def _char_overlap(word_a: str, word_b: str) -> float:
    """Character-level overlap between two Japanese words."""
    chars_a = set(word_a)
    chars_b = set(word_b)
    return _jaccard(chars_a, chars_b)


def _feature_similarity(a: dict, b: dict) -> float:
    """Compute feature-based similarity between two vocabulary items."""
    score = 0.0

    # JLPT level match (0.3 weight)
    if a.get("jlpt_level") == b.get("jlpt_level"):
        score += 0.3

    # Part of speech match (0.25 weight)
    if a.get("part_of_speech") == b.get("part_of_speech"):
        score += 0.25

    # Tag overlap (0.25 weight)
    tags_a = set(json.loads(a.get("tags", "[]"))) if isinstance(a.get("tags"), str) else set(a.get("tags", []))
    tags_b = set(json.loads(b.get("tags", "[]"))) if isinstance(b.get("tags"), str) else set(b.get("tags", []))
    if tags_a or tags_b:
        score += 0.25 * _jaccard(tags_a, tags_b)

    # Character overlap in word (0.2 weight) — kanji sharing
    word_a = a.get("word", "")
    word_b = b.get("word", "")
    score += 0.2 * _char_overlap(word_a, word_b)

    return round(score, 4)


async def find_similar_words(
    vocab_id: int,
    top_n: int = 10,
) -> dict[str, Any]:
    """Find words similar to the given vocabulary item (feature-based)."""
    db = await get_db()

    # Get target word
    c = await db.execute(
        "SELECT * FROM jp_vocabulary WHERE id = ? AND is_active = 1",
        (vocab_id,),
    )
    target = await c.fetchone()
    if not target:
        return {"error": f"Vocabulary ID {vocab_id} not found"}
    target = dict(target)

    # Get all active words
    c = await db.execute(
        "SELECT * FROM jp_vocabulary WHERE is_active = 1 AND id != ?",
        (vocab_id,),
    )
    all_words = [dict(row) for row in await c.fetchall()]

    # Compute similarities
    results = []
    for w in all_words:
        sim = _feature_similarity(target, w)
        if sim > 0:
            results.append({
                "id": w["id"],
                "word": w["word"],
                "reading": w["reading"],
                "meaning": w["meaning"],
                "jlpt_level": w["jlpt_level"],
                "part_of_speech": w["part_of_speech"],
                "similarity": sim,
            })

    results.sort(key=lambda x: x["similarity"], reverse=True)

    return {
        "target": {
            "id": target["id"],
            "word": target["word"],
            "reading": target["reading"],
            "meaning": target["meaning"],
            "jlpt_level": target["jlpt_level"],
        },
        "similar": results[:top_n],
        "method": "feature-based",
    }


async def group_vocab_by_theme(
    jlpt_level: str | None = None,
    max_groups: int = 8,
    group_size: int = 5,
) -> dict[str, Any]:
    """Group vocabulary into thematic clusters for study sessions.

    Uses part of speech + tag overlap to create meaningful groups.
    """
    db = await get_db()

    query = "SELECT * FROM jp_vocabulary WHERE is_active = 1"
    params: list = []
    if jlpt_level:
        query += " AND jlpt_level = ?"
        params.append(jlpt_level)
    query += " ORDER BY RANDOM()"

    c = await db.execute(query, params)
    words = [dict(row) for row in await c.fetchall()]

    if not words:
        return {"groups": [], "total_words": 0}

    # Group by part_of_speech first, then by tags
    pos_groups: dict[str, list] = defaultdict(list)
    for w in words:
        pos_groups[w.get("part_of_speech", "other")].append(w)

    groups = []
    for pos, pos_words in pos_groups.items():
        if len(groups) >= max_groups:
            break

        # Sub-group by tags
        tag_groups: dict[str, list] = defaultdict(list)
        for w in pos_words:
            tags = json.loads(w.get("tags", "[]")) if isinstance(w.get("tags"), str) else w.get("tags", [])
            primary_tag = tags[0] if tags else "general"
            tag_groups[primary_tag].append(w)

        for tag, tag_words in tag_groups.items():
            if len(groups) >= max_groups:
                break
            group_words = tag_words[:group_size]
            if len(group_words) >= 2:
                groups.append({
                    "theme": f"{pos} — {tag}",
                    "words": [
                        {
                            "id": w["id"],
                            "word": w["word"],
                            "reading": w["reading"],
                            "meaning": w["meaning"],
                        }
                        for w in group_words
                    ],
                    "count": len(group_words),
                })

    return {
        "groups": groups[:max_groups],
        "total_words": len(words),
        "method": "feature-based",
        "jlpt_level": jlpt_level,
    }


# ---------------------------------------------------------------------------
# Embedding-based similarity (optional — requires sentence-transformers)
# ---------------------------------------------------------------------------

_embedding_model = None


def _get_embedding_model():
    """Lazy-load the sentence-transformers model (CPU only, ~120MB)."""
    global _embedding_model
    if _embedding_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _embedding_model = SentenceTransformer(
                "paraphrase-multilingual-MiniLM-L12-v2",
                device="cpu",
            )
            logger.info("Loaded embedding model: paraphrase-multilingual-MiniLM-L12-v2")
        except ImportError:
            logger.warning("sentence-transformers not installed. Using feature-based similarity.")
            return None
    return _embedding_model


async def find_similar_words_embedding(
    vocab_id: int,
    top_n: int = 10,
) -> dict[str, Any]:
    """Find semantically similar words using multilingual embeddings."""
    model = _get_embedding_model()
    if model is None:
        return await find_similar_words(vocab_id, top_n)

    db = await get_db()

    c = await db.execute(
        "SELECT * FROM jp_vocabulary WHERE id = ? AND is_active = 1",
        (vocab_id,),
    )
    target = await c.fetchone()
    if not target:
        return {"error": f"Vocabulary ID {vocab_id} not found"}
    target = dict(target)

    c = await db.execute(
        "SELECT * FROM jp_vocabulary WHERE is_active = 1 AND id != ?",
        (vocab_id,),
    )
    all_words = [dict(row) for row in await c.fetchall()]

    if not all_words:
        return {"target": target, "similar": [], "method": "embedding"}

    # Build text representations
    def _to_text(w: dict) -> str:
        parts = [w["word"], w["meaning"]]
        if w.get("example_ja"):
            parts.append(w["example_ja"])
        return " ".join(parts)

    target_text = _to_text(target)
    other_texts = [_to_text(w) for w in all_words]

    # Compute embeddings
    all_texts = [target_text] + other_texts
    embeddings = model.encode(all_texts, normalize_embeddings=True)
    target_emb = embeddings[0]

    # Compute cosine similarities (embeddings are already normalized)
    results = []
    for i, w in enumerate(all_words):
        sim = float(target_emb @ embeddings[i + 1])
        results.append({
            "id": w["id"],
            "word": w["word"],
            "reading": w["reading"],
            "meaning": w["meaning"],
            "jlpt_level": w["jlpt_level"],
            "similarity": round(sim, 4),
        })

    results.sort(key=lambda x: x["similarity"], reverse=True)

    return {
        "target": {
            "id": target["id"],
            "word": target["word"],
            "reading": target["reading"],
            "meaning": target["meaning"],
        },
        "similar": results[:top_n],
        "method": "embedding",
        "model": "paraphrase-multilingual-MiniLM-L12-v2",
    }
