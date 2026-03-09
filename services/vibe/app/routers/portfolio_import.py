"""Portfolio import via image (LLM Vision) or text paste."""

import base64
import json
import logging
import re

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from app.database import repositories as repo

logger = logging.getLogger("vibe.routers.portfolio_import")

router = APIRouter(prefix="/portfolio/import", tags=["portfolio-import"])


class TextImportRequest(BaseModel):
    text: str = Field(max_length=100_000)
    market: str = "KR"


class ConfirmImportRequest(BaseModel):
    positions: list[dict]
    portfolio_id: int = 1


def _extract_json_from_text(text: str) -> list[dict]:
    """Extract JSON array from LLM response (handles markdown code blocks)."""
    # Try to find JSON in code block
    match = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
    if match:
        return json.loads(match.group(1))
    # Try each '[' position as a potential JSON array start
    for i, ch in enumerate(text):
        if ch == '[':
            try:
                return json.loads(text[i:])
            except json.JSONDecodeError:
                # Try to find matching ']' backwards from end
                for j in range(len(text) - 1, i, -1):
                    if text[j] == ']':
                        try:
                            return json.loads(text[i:j + 1])
                        except json.JSONDecodeError:
                            continue
    raise ValueError("No JSON array found in response")


@router.post("/image")
async def import_from_image(
    file: UploadFile = File(...),
    portfolio_id: int = Query(1),
):
    """Extract portfolio positions from a screenshot using LLM Vision."""
    from app.config import settings

    if not settings.LLM_API_KEY:
        raise HTTPException(400, "LLM API key not configured. Set LLM_API_KEY in .env")

    # Read with size limit to avoid OOM on large uploads
    max_size = 10 * 1024 * 1024  # 10MB
    contents = await file.read(max_size + 1)
    if len(contents) > max_size:
        raise HTTPException(413, "Image too large (max 10MB)")

    b64 = base64.b64encode(contents).decode()
    content_type = file.content_type or "image/png"

    prompt = (
        "이 이미지는 증권사 앱의 보유 종목 화면입니다. "
        "각 종목의 정보를 추출하여 JSON 배열로 반환해주세요.\n\n"
        "반환 형식:\n"
        '```json\n'
        '[{"symbol": "005930", "market": "KR", "name": "삼성전자", '
        '"position_size": 5000000, "entry_price": 56000, "quantity": 100}]\n'
        '```\n\n'
        "규칙:\n"
        "- symbol: 한국 종목은 6자리 코드, 미국 종목은 티커\n"
        "- market: 한국='KR', 미국='US'\n"
        "- position_size: 매입 총액 (원 또는 달러)\n"
        "- entry_price: 매입 단가\n"
        "- quantity: 보유 수량\n"
        "- 읽을 수 없는 필드는 null로\n"
        "- JSON만 반환, 설명 불필요"
    )

    try:
        provider = settings.LLM_PROVIDER.lower()
        if provider == "anthropic":
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=settings.LLM_API_KEY)
            response = await client.messages.create(
                model=settings.LLM_MODEL or "claude-3-5-haiku-20241022",
                max_tokens=2000,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": content_type, "data": b64}},
                        {"type": "text", "text": prompt},
                    ],
                }],
            )
            raw_text = response.content[0].text
        elif provider == "openai":
            import openai
            client = openai.AsyncOpenAI(api_key=settings.LLM_API_KEY)
            response = await client.chat.completions.create(
                model=settings.LLM_MODEL or "gpt-4o-mini",
                max_tokens=2000,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:{content_type};base64,{b64}"}},
                        {"type": "text", "text": prompt},
                    ],
                }],
            )
            raw_text = response.choices[0].message.content
        else:
            raise HTTPException(400, f"Unsupported LLM provider: {provider}")

        positions = _extract_json_from_text(raw_text)
        # Normalize and validate
        validated = []
        for p in positions:
            if not p.get("symbol"):
                continue
            entry = {
                "symbol": str(p["symbol"]).strip().upper(),
                "market": (p.get("market") or "KR").upper(),
                "name": p.get("name", ""),
                "position_size": p.get("position_size"),
                "entry_price": p.get("entry_price"),
                "quantity": p.get("quantity"),
            }
            # Calculate position_size from quantity * entry_price if missing
            if not entry["position_size"] and entry["quantity"] and entry["entry_price"]:
                try:
                    entry["position_size"] = float(entry["quantity"]) * float(entry["entry_price"])
                except (ValueError, TypeError):
                    pass
            validated.append(entry)

        return {"status": "preview", "positions": validated, "raw_text": raw_text, "source": "image"}

    except json.JSONDecodeError as e:
        logger.error("Failed to parse LLM response: %s", e, exc_info=True)
        raise HTTPException(422, "LLM returned invalid JSON. Check server logs for details.")
    except Exception as e:
        logger.exception("Image import failed: %s", e)
        raise HTTPException(500, "Image processing failed. Check server logs for details.")


@router.post("/text")
async def import_from_text(req: TextImportRequest):
    """Parse pasted text (tab/comma/space separated) into positions."""
    lines = req.text.strip().split("\n")
    positions = []
    for line in lines:
        parts = re.split(r"[\t,;|]+", line.strip())
        if len(parts) < 1 or not parts[0].strip():
            continue
        entry = {
            "symbol": parts[0].strip().upper(),
            "market": req.market,
            "name": parts[1].strip() if len(parts) > 1 else "",
            "quantity": _safe_float(parts[2]) if len(parts) > 2 else None,
            "entry_price": _safe_float(parts[3]) if len(parts) > 3 else None,
            "position_size": _safe_float(parts[4]) if len(parts) > 4 else None,
        }
        if not entry["position_size"] and entry["quantity"] and entry["entry_price"]:
            entry["position_size"] = entry["quantity"] * entry["entry_price"]
        positions.append(entry)
    return {"status": "preview", "positions": positions, "source": "text"}


@router.post("/confirm")
async def confirm_import(req: ConfirmImportRequest):
    """Confirm and insert previewed positions into portfolio."""
    imported = 0
    for p in req.positions:
        symbol = p.get("symbol")
        market = p.get("market", "KR")
        if not symbol:
            continue
        data = {
            "position_size": p.get("position_size") if p.get("position_size") is not None else 0,
            "entry_price": p.get("entry_price"),
            "entry_date": p.get("entry_date"),
            "sector": p.get("sector"),
        }
        await repo.upsert_portfolio_position(
            symbol=symbol, market=market,
            data=data, portfolio_id=req.portfolio_id,
        )
        imported += 1
    return {"status": "ok", "imported": imported}


def _safe_float(v) -> float | None:
    """Safely parse a string to float, removing commas and whitespace."""
    if v is None:
        return None
    try:
        return float(str(v).replace(",", "").replace(" ", ""))
    except (ValueError, TypeError):
        return None
