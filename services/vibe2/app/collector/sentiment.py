"""Sentiment data collector — CNN Fear & Greed Index via httpx."""

import logging
from datetime import datetime

import httpx

from app.db import get_sync_db

logger = logging.getLogger("vibe2.collector.sentiment")

# CNN Fear & Greed API endpoint
FEAR_GREED_URL = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
FEAR_GREED_TIMEOUT = 15.0


def fetch_fear_greed() -> dict | None:
    """Fetch CNN Fear & Greed Index.

    Returns dict with keys: fear_greed_index, fear_greed_label, or None on failure.
    """
    try:
        with httpx.Client(timeout=FEAR_GREED_TIMEOUT) as client:
            resp = client.get(
                FEAR_GREED_URL,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; VIBE2/1.0)",
                    "Accept": "application/json",
                },
            )
            resp.raise_for_status()
            data = resp.json()

            # CNN API returns {"fear_and_greed": {"score": 42, "rating": "Fear", ...}}
            fng = data.get("fear_and_greed", {})
            score = fng.get("score")
            if score is None:
                logger.warning("No score in Fear & Greed response")
                return None

            return {
                "fear_greed_index": int(round(score)),
                "fear_greed_label": fng.get("rating", "Unknown"),
            }
    except httpx.HTTPStatusError as e:
        logger.warning("Fear & Greed HTTP error %d: %s", e.response.status_code, e)
        return None
    except Exception as e:
        logger.warning("Fear & Greed fetch failed: %s", e)
        return None


def save_sentiment(fear_greed: dict | None) -> bool:
    """Save sentiment data to sentiment_data table. Returns True on success."""
    if not fear_greed:
        return False

    indicator_date = datetime.now().strftime("%Y-%m-%d")
    conn = get_sync_db()
    try:
        conn.execute(
            """INSERT OR REPLACE INTO sentiment_data
               (indicator_date, fear_greed_index, put_call_ratio, vix_term_structure)
               VALUES (?, ?, ?, ?)""",
            (
                indicator_date,
                fear_greed.get("fear_greed_index"),
                None,  # put_call_ratio — TODO Phase 3
                None,  # vix_term_structure — TODO Phase 3
            ),
        )
        conn.commit()
        logger.info(
            "Saved sentiment: F&G=%s (%s)",
            fear_greed.get("fear_greed_index"),
            fear_greed.get("fear_greed_label"),
        )
        return True
    except Exception as e:
        logger.error("Failed to save sentiment: %s", e)
        return False
    finally:
        conn.close()


def collect_sentiment() -> bool:
    """Collect and save sentiment data. Returns True on success."""
    fg = fetch_fear_greed()
    return save_sentiment(fg)
