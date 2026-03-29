import json
import logging
import os
import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger("ufs.chord_search")

router = APIRouter(prefix="/api/chord-search", tags=["chord-search"])

# Simple daily rate limit (resets on server restart or date change)
_call_count = 0
_call_date = date.today().isoformat()
DAILY_LIMIT = 100


def _check_rate_limit() -> None:
    global _call_count, _call_date
    today = date.today().isoformat()
    if today != _call_date:
        _call_count = 0
        _call_date = today
    if _call_count >= DAILY_LIMIT:
        raise HTTPException(status_code=429, detail="Daily LLM call limit reached")
    _call_count += 1


# ── Request / Response schemas ──

class ChordSearchRequest(BaseModel):
    title: str
    artist: str | None = None


class SongChordEntry(BaseModel):
    chord: str
    beats: int
    annotation: str | None = None


class SongSectionEntry(BaseModel):
    name: str
    chords: list[SongChordEntry]


class ChordSearchResponse(BaseModel):
    id: str
    title: str
    artist: str | None = None
    genre: str | None = None
    key: str | None = None
    bpm: int | None = None
    timeSignature: list[int] | None = None
    sections: list[SongSectionEntry]
    source: str = "llm"
    createdAt: str
    updatedAt: str


# ── Tool schema for structured output ──

CHORD_TOOL = {
    "name": "return_chord_progression",
    "description": "Return the chord progression of a song in structured JSON format.",
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "artist": {"type": "string"},
            "genre": {"type": "string"},
            "key": {"type": "string", "description": "Musical key, e.g. C, Am, F#m"},
            "bpm": {"type": "integer"},
            "timeSignature": {
                "type": "array",
                "items": {"type": "integer"},
                "minItems": 2,
                "maxItems": 2,
            },
            "sections": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "enum": [
                                "Intro", "Verse", "Pre-Chorus", "Chorus",
                                "Bridge", "Interlude", "Solo", "Outro", "Other",
                            ],
                        },
                        "chords": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "chord": {"type": "string"},
                                    "beats": {"type": "integer"},
                                    "annotation": {"type": "string"},
                                },
                                "required": ["chord", "beats"],
                            },
                        },
                    },
                    "required": ["name", "chords"],
                },
            },
        },
        "required": ["title", "sections"],
    },
}


@router.post("/", response_model=ChordSearchResponse)
async def search_chords(req: ChordSearchRequest):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY not configured")

    _check_rate_limit()

    import anthropic

    artist_hint = f" by {req.artist}" if req.artist else ""
    prompt = (
        f'Return the chord progression for the song "{req.title}"{artist_hint}. '
        "Provide the actual, accurate chord progression as widely known. "
        "Include at least Verse and Chorus sections. "
        "Use standard chord notation (e.g. Am, F#m7, Bbmaj7). "
        "Set beats to the number of beats each chord is held."
    )

    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-haiku-4-5-20241022",
            max_tokens=2048,
            tools=[CHORD_TOOL],
            tool_choice={"type": "tool", "name": "return_chord_progression"},
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.APIConnectionError as e:
        logger.error("LLM connection failed: %s", e)
        raise HTTPException(status_code=502, detail="LLM 서버 연결 실패")
    except anthropic.RateLimitError as e:
        logger.warning("LLM rate limited: %s", e)
        raise HTTPException(status_code=429, detail="LLM API 요청 한도 초과")
    except anthropic.APIStatusError as e:
        logger.error("LLM API error (status %d): %s", e.status_code, e)
        raise HTTPException(status_code=502, detail=f"LLM API 오류 ({e.status_code})")

    # Extract tool_use block
    tool_input = None
    for block in message.content:
        if block.type == "tool_use":
            tool_input = block.input
            break

    if not tool_input or "sections" not in tool_input:
        raise HTTPException(status_code=500, detail="Failed to parse LLM response")

    now = datetime.now(timezone.utc).isoformat()

    try:
        sections = [
            SongSectionEntry(
                name=s.get("name", "Other"),
                chords=[
                    SongChordEntry(
                        chord=c.get("chord", "?"),
                        beats=c.get("beats", 4),
                        annotation=c.get("annotation"),
                    )
                    for c in s.get("chords", [])
                ],
            )
            for s in tool_input["sections"]
            if isinstance(s, dict)
        ]
    except (TypeError, KeyError) as e:
        logger.error("Failed to parse LLM tool output: %s", e)
        raise HTTPException(status_code=500, detail="Failed to parse LLM response structure")

    if not sections:
        raise HTTPException(status_code=500, detail="LLM returned empty sections")

    ts = tool_input.get("timeSignature")
    if isinstance(ts, list) and len(ts) == 2:
        ts = [int(ts[0]), int(ts[1])]
    else:
        ts = None

    return ChordSearchResponse(
        id=f"llm-{uuid.uuid4().hex[:12]}",
        title=tool_input.get("title", req.title),
        artist=tool_input.get("artist", req.artist),
        genre=tool_input.get("genre"),
        key=tool_input.get("key"),
        bpm=tool_input.get("bpm"),
        timeSignature=ts,
        sections=sections,
        source="llm",
        createdAt=now,
        updatedAt=now,
    )
