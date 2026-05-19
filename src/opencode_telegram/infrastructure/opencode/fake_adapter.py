from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import datetime

from opencode_telegram.domain.entities import Session
from opencode_telegram.domain.value_objects import (
    HealthStatus,
    RuntimeCapabilities,
    SessionId,
    SessionStatus,
)
from opencode_telegram.infrastructure.logging import get_logger
from opencode_telegram.infrastructure.opencode.base import OpenCodeRuntime

log = get_logger("opencode_telegram.infrastructure.opencode.fake")


class FakeOpenCodeAdapter(OpenCodeRuntime):
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    async def create_session(
        self, workspace: str | None = None, project: str | None = None
    ) -> Session:
        now = datetime.utcnow()
        session = Session(
            id=SessionId.generate(),
            status=SessionStatus.ready,
            workspace=workspace,
            project=project,
            server="fake",
            created_at=now,
            updated_at=now,
            last_activity=now,
        )
        self._sessions[str(session.id)] = session
        log.info("fake_session_created", session_id=str(session.id))
        return session

    async def resume_session(self, session_id: str | SessionId) -> Session:
        sid = str(session_id)
        session = self._sessions.get(sid)
        if not session:
            now = datetime.utcnow()
            session = Session(
                id=SessionId(sid) if isinstance(session_id, str) else session_id,
                status=SessionStatus.ready,
                server="fake",
                created_at=now,
                updated_at=now,
                last_activity=now,
            )
            self._sessions[sid] = session
        return session

    async def get_session(self, session_id: str | SessionId) -> Session | None:
        return self._sessions.get(str(session_id))

    async def list_sessions(self, limit: int = 10) -> list[Session]:
        return list(self._sessions.values())[:limit]

    async def send_prompt(self, session_id: str | SessionId, prompt: str, session_name: str | None = None) -> AsyncIterator[str]:
        words = prompt.split()
        for w in words:
            yield w + " "
            await asyncio.sleep(0.05)
        yield f"\n\n[Fake response to your {len(words)}-word prompt]"
        log.info("fake_prompt_handled", session_id=str(session_id), words=len(words))

    async def stop_session(self, session_id: str | SessionId) -> None:
        session = self._sessions.get(str(session_id))
        if session:
            session.status = SessionStatus.stopped
        log.info("fake_session_stopped", session_id=str(session_id))

    async def clear_session(self, session_id: str | SessionId) -> None:
        log.info("fake_session_cleared", session_id=str(session_id))

    async def get_health(self) -> HealthStatus:
        return HealthStatus(
            telegram_webhook=True,
            runtime_available=True,
            runtime_mode="fake",
            latency_ms=0.0,
            storage_ok=True,
            active_sessions=len(self._sessions),
        )

    async def get_capabilities(self) -> RuntimeCapabilities:
        return RuntimeCapabilities(
            supports_streaming=True,
            supports_sessions=True,
            supports_stop=True,
            supports_projects=True,
            supports_workspaces=True,
            max_prompt_length=100000,
            available_commands=["start", "status", "sessions", "resume", "clear", "stop", "bind", "health", "logs", "help"],
        )

    async def close(self) -> None:
        self._sessions.clear()
        log.info("fake_adapter_closed")
