from __future__ import annotations

import asyncio
from datetime import datetime

from opencode_telegram.domain.ports import SessionBindingRepository, SessionRepository, TelegramClient
from opencode_telegram.domain.value_objects import SessionId, SessionStatus
from opencode_telegram.infrastructure.logging import get_logger
from opencode_telegram.infrastructure.opencode.base import OpenCodeRuntime

log = get_logger("opencode_telegram.app.services.session_sync")


class SessionSyncService:
    def __init__(
        self,
        binding_repo: SessionBindingRepository,
        session_repo: SessionRepository,
        runtime: OpenCodeRuntime,
        telegram: TelegramClient,
        interval: float = 15.0,
    ) -> None:
        self._binding_repo = binding_repo
        self._session_repo = session_repo
        self._runtime = runtime
        self._telegram = telegram
        self._interval = interval
        self._last_seen: dict[str, int] = {}
        self._running = False

    async def start(self) -> None:
        self._running = True
        log.info("sync_service_started", interval=self._interval)
        while self._running:
            try:
                await self._sync_active_sessions()
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error("sync_service_error", error=str(e))
            await asyncio.sleep(self._interval)

    async def stop(self) -> None:
        self._running = False
        log.info("sync_service_stopped")

    async def _sync_active_sessions(self) -> None:
        bindings = await self._binding_repo.list_all_active()
        for binding in bindings:
            session = await self._session_repo.get(binding.session_id)
            if not session or not session.runtime_session_id:
                continue
            if session.status == SessionStatus.busy:
                continue

            rid = session.runtime_session_id
            history = await self._runtime.get_session_history(rid)
            if not history:
                continue

            last_ts = self._last_seen.get(rid, 0)
            new_entries = [e for e in history if e.timestamp > last_ts and e.timestamp > 0]

            if not new_entries:
                continue

            for entry in new_entries:
                if entry.role == "assistant":
                    from opencode_telegram.infrastructure.telegram.formatting import format_as_html
                    text = format_as_html(entry.text)
                    await self._telegram.send_message(binding.chat_id.value, text, parse_mode="HTML")

            self._last_seen[rid] = max(e.timestamp for e in new_entries)

            if new_entries:
                await self._session_repo.touch_activity(session.id)
