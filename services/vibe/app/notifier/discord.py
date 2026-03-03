"""Discord webhook sender."""

import logging
from typing import Any

import httpx

from app.config import Settings
from app.database import repositories as repo
from app.notifier.formatter import build_dashboard_payload

logger = logging.getLogger("vibe.notifier")


class DiscordNotifier:
    def __init__(self, config: Settings):
        self.config = config
        self.webhook_url = config.DISCORD_WEBHOOK_URL

    async def send_dashboard(self, context: dict[str, Any]) -> bool:
        """Build and send dashboard to Discord. Returns True on success."""
        payload = build_dashboard_payload(context)

        # Always save snapshot to DB (regardless of Discord config)
        snapshot_id = await repo.save_dashboard_snapshot(
            run_id=context["run_id"],
            snapshot_date=context["date"],
            market=context["market"],
            content=payload,
        )

        if not self.webhook_url:
            logger.warning("Discord webhook URL not configured, snapshot saved but not sent")
            return False

        # Send to Discord
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    self.webhook_url,
                    json=payload,
                    timeout=15.0,
                )

                if resp.status_code == 204:
                    logger.info("Dashboard sent to Discord successfully")
                    await repo.mark_dashboard_sent(snapshot_id)
                    return True
                elif resp.status_code == 429:
                    logger.warning("Discord rate limited: %s", resp.text)
                    return False
                else:
                    logger.error(
                        "Discord send failed: status=%d body=%s",
                        resp.status_code, resp.text[:200],
                    )
                    return False

        except httpx.TimeoutException:
            logger.error("Discord webhook timed out")
            return False
        except Exception as e:
            logger.error("Discord send error: %s", e)
            return False
