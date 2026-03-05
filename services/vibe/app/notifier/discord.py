"""Discord webhook sender."""

import asyncio
import logging
from typing import Any

import httpx

from app.config import Settings
from app.database import repositories as repo
from app.notifier.formatter import build_dashboard_payloads

logger = logging.getLogger("vibe.notifier")


class DiscordNotifier:
    def __init__(self, config: Settings):
        self.config = config
        self.webhook_url = config.DISCORD_WEBHOOK_URL

    async def send_dashboard(self, context: dict[str, Any]) -> bool:
        """Build and send dashboard to Discord. Returns True on success."""
        payloads = build_dashboard_payloads(context)

        # Always save snapshot to DB (merge all embeds for storage)
        all_embeds = []
        for p in payloads:
            all_embeds.extend(p.get("embeds", []))
        snapshot_content = {"username": "VIBE", "embeds": all_embeds}

        snapshot_id = await repo.save_dashboard_snapshot(
            run_id=context["run_id"],
            snapshot_date=context["date"],
            market=context["market"],
            content=snapshot_content,
        )

        if not self.webhook_url:
            logger.warning("Discord webhook URL not configured, snapshot saved but not sent")
            return False

        # Send each payload as a separate message
        all_success = True
        for i, payload in enumerate(payloads):
            success = await self._send_payload(payload)
            if not success:
                all_success = False
                logger.error("Discord payload %d/%d failed", i + 1, len(payloads))
            elif len(payloads) > 1 and i < len(payloads) - 1:
                # Rate limit: wait between messages
                await asyncio.sleep(1.0)

        if all_success:
            logger.info(
                "Dashboard sent to Discord: %d message(s)", len(payloads),
            )
            await repo.mark_dashboard_sent(snapshot_id)

        return all_success

    async def _send_payload(self, payload: dict) -> bool:
        """Send a single payload to Discord webhook."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    self.webhook_url,
                    json=payload,
                    timeout=15.0,
                )

                if resp.status_code == 204:
                    return True
                elif resp.status_code == 429:
                    # Rate limited — wait and retry once
                    try:
                        retry_after = resp.json().get("retry_after", 5)
                    except Exception:
                        retry_after = 5
                    logger.warning("Discord rate limited, retrying in %.1fs", retry_after)
                    await asyncio.sleep(retry_after)
                    resp2 = await client.post(
                        self.webhook_url, json=payload, timeout=15.0,
                    )
                    return resp2.status_code == 204
                else:
                    logger.error(
                        "Discord send failed: status=%d body=%s",
                        resp.status_code, resp.text[:300],
                    )
                    return False

        except httpx.TimeoutException:
            logger.error("Discord webhook timed out")
            return False
        except Exception as e:
            logger.error("Discord send error: %s", e)
            return False
