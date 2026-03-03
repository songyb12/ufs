from fastapi import APIRouter

from app.database import repositories as repo
from app.models.schemas import DashboardResponse

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("")
async def get_dashboard(market: str | None = None):
    """Get the latest dashboard snapshot."""
    snapshot = await repo.get_latest_dashboard(market=market)
    if not snapshot:
        return {
            "status": "not_generated",
            "message": "No dashboard snapshot available yet. Run the pipeline first.",
        }
    return {
        "snapshot_date": snapshot["snapshot_date"],
        "market": snapshot["market"],
        "run_id": snapshot["run_id"],
        "content": snapshot["content_json"],
        "discord_sent": bool(snapshot["discord_sent"]),
        "discord_sent_at": snapshot.get("discord_sent_at"),
    }
