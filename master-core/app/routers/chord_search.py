import json
import logging
import subprocess
import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger("ufs.chord_search")

router = APIRouter(prefix="/api/chord-search", tags=["chord-search"])

# Claude CLI path
CLAUDE_CLI = r"C:\Users\saos3\AppData\Roaming\Claude\claude-code\2.1.87\claude.exe"

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


PROMPT_TEMPLATE = """Return the chord progression for the song "{title}"{artist_hint}.
Provide the actual, accurate chord progression as widely known.
Include at least Verse and Chorus sections.
Use standard chord notation (e.g. Am, F#m7, Bbmaj7).
Set beats to the number of beats each chord is held.

Reply with ONLY a JSON object in this exact format, no other text:
{{
  "title": "Song Title",
  "artist": "Artist Name",
  "genre": "Genre",
  "key": "C",
  "bpm": 120,
  "timeSignature": [4, 4],
  "sections": [
    {{
      "name": "Verse",
      "chords": [
        {{"chord": "Am", "beats": 4}},
        {{"chord": "F", "beats": 4}}
      ]
    }}
  ]
}}

Section names must be one of: Intro, Verse, Pre-Chorus, Chorus, Bridge, Interlude, Solo, Outro, Other."""


@router.post("/", response_model=ChordSearchResponse)
async def search_chords(req: ChordSearchRequest):
    _check_rate_limit()

    artist_hint = f" by {req.artist}" if req.artist else ""
    prompt = PROMPT_TEMPLATE.format(title=req.title, artist_hint=artist_hint)

    try:
        result = subprocess.run(
            [CLAUDE_CLI, "-p", prompt, "--output-format", "text"],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except FileNotFoundError:
        logger.error("Claude CLI not found at %s", CLAUDE_CLI)
        raise HTTPException(status_code=503, detail="Claude CLI not found")
    except subprocess.TimeoutExpired:
        logger.error("Claude CLI timed out")
        raise HTTPException(status_code=504, detail="LLM 응답 시간 초과")

    if result.returncode != 0:
        logger.error("Claude CLI failed (code %d): %s", result.returncode, result.stderr[:500])
        raise HTTPException(status_code=502, detail="LLM 호출 실패")

    raw = result.stdout.strip()

    # Extract JSON from response (may have markdown fences)
    if "```" in raw:
        start = raw.find("```")
        end = raw.rfind("```")
        inner = raw[start:end + 3] if end > start else raw[start:]
        # Strip ```json and ```
        inner = inner.split("\n", 1)[-1] if "\n" in inner else inner
        if inner.endswith("```"):
            inner = inner[:-3]
        raw = inner.strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.error("Failed to parse CLI output as JSON: %s", raw[:300])
        raise HTTPException(status_code=500, detail="LLM 응답 파싱 실패")

    if "sections" not in data:
        raise HTTPException(status_code=500, detail="LLM 응답에 sections 누락")

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
            for s in data["sections"]
            if isinstance(s, dict)
        ]
    except (TypeError, KeyError) as e:
        logger.error("Failed to parse sections: %s", e)
        raise HTTPException(status_code=500, detail="LLM 응답 구조 파싱 실패")

    if not sections:
        raise HTTPException(status_code=500, detail="LLM returned empty sections")

    ts = data.get("timeSignature")
    if isinstance(ts, list) and len(ts) == 2:
        ts = [int(ts[0]), int(ts[1])]
    else:
        ts = None

    return ChordSearchResponse(
        id=f"llm-{uuid.uuid4().hex[:12]}",
        title=data.get("title", req.title),
        artist=data.get("artist", req.artist),
        genre=data.get("genre"),
        key=data.get("key"),
        bpm=data.get("bpm"),
        timeSignature=ts,
        sections=sections,
        source="llm",
        createdAt=now,
        updatedAt=now,
    )
