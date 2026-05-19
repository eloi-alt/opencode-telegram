from __future__ import annotations

import asyncio
from typing import Any

import httpx

from opencode_telegram.infrastructure.logging import get_logger
from opencode_telegram.infrastructure.telegram.client import HttpxTelegramClient

log = get_logger("opencode_telegram.infrastructure.telegram.poller")


class TelegramPoller:
    def __init__(
        self,
        client: HttpxTelegramClient,
        handler: Any,
        poll_interval: float = 1.0,
    ) -> None:
        self._token = client.token
        self._handler = handler
        self._poll_interval = poll_interval
        self._offset: int = 0
        self._running = False
        self._conflict_backoff = 0

    async def start(self) -> None:
        self._running = True
        log.info("poller_started", interval=self._poll_interval)
        while self._running:
            try:
                await self._poll()
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error("poller_error", error=str(e))
            await asyncio.sleep(self._poll_interval)

    async def stop(self) -> None:
        self._running = False
        log.info("poller_stopped")

    async def _poll(self) -> None:
        if self._conflict_backoff > 0:
            log.info("poll_backoff", seconds=self._conflict_backoff)
            await asyncio.sleep(self._conflict_backoff)
            self._conflict_backoff = max(0, self._conflict_backoff - 1)

        url = f"https://api.telegram.org/bot{self._token}/getUpdates"
        payload: dict[str, Any] = {
            "offset": self._offset,
            "timeout": 5,
            "allowed_updates": ["message", "callback_query"],
        }
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as http:
                resp = await http.post(url, json=payload)
                if resp.status_code == 409:
                    self._conflict_backoff = min(self._conflict_backoff + 2, 30)
                    log.warning("poll_conflict", status=409, backoff=self._conflict_backoff)
                    return
                self._conflict_backoff = 0
                resp.raise_for_status()
                data: dict = resp.json()
        except httpx.TimeoutException:
            return
        except Exception as e:
            log.warning("poll_request_failed", error=str(e))
            return

        if not data.get("ok"):
            return

        for update in data.get("result", []):
            self._offset = update.get("update_id", 0) + 1
            try:
                await self._handler.handle(update)
            except Exception as e:
                log.error("poll_handler_error", update_id=update.get("update_id"), error=str(e))
