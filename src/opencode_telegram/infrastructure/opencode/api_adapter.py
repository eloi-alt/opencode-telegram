from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime

import httpx

from opencode_telegram.domain.entities import Session
from opencode_telegram.domain.value_objects import (
    HealthStatus,
    RuntimeCapabilities,
    RuntimeMode,
    SessionId,
    SessionStatus,
)
from opencode_telegram.infrastructure.logging import get_logger
from opencode_telegram.infrastructure.opencode.base import OpenCodeRuntime
from opencode_telegram.shared.errors import RuntimeUnavailableError

log = get_logger("opencode_telegram.infrastructure.opencode.api")


class OpenCodeApiAdapter(OpenCodeRuntime):
    def __init__(self, base_url: str, api_key: str | None = None) -> None:
        self._base_url = base_url.rstrip("/")
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers=headers,
            timeout=httpx.Timeout(60.0, read=300.0),
        )

    async def create_session(
        self, workspace: str | None = None, project: str | None = None
    ) -> Session:
        body: dict = {}
        if workspace:
            body["workspace"] = workspace
        if project:
            body["project"] = project
        try:
            resp = await self._client.post("/api/sessions", json=body)
            resp.raise_for_status()
            data = resp.json()
            now = datetime.utcnow()
            return Session(
                id=SessionId(data["id"]),
                status=SessionStatus(data.get("status", "ready")),
                workspace=data.get("workspace", workspace),
                project=data.get("project", project),
                server="api",
                runtime_session_id=data.get("runtime_session_id"),
                created_at=now,
                updated_at=now,
                last_activity=now,
            )
        except httpx.HTTPError as e:
            raise RuntimeUnavailableError(f"API create_session failed: {e}") from e

    async def resume_session(self, session_id: str | SessionId) -> Session:
        sid = str(session_id)
        try:
            resp = await self._client.post(f"/api/sessions/{sid}/resume")
            resp.raise_for_status()
            data = resp.json()
            now = datetime.utcnow()
            return Session(
                id=SessionId(data["id"]),
                status=SessionStatus(data.get("status", "ready")),
                workspace=data.get("workspace"),
                project=data.get("project"),
                server="api",
                runtime_session_id=data.get("runtime_session_id"),
                created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else now,
                updated_at=now,
                last_activity=now,
            )
        except httpx.HTTPError as e:
            raise RuntimeUnavailableError(f"API resume_session failed: {e}") from e

    async def get_session(self, session_id: str | SessionId) -> Session | None:
        sid = str(session_id)
        try:
            resp = await self._client.get(f"/api/sessions/{sid}")
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            data = resp.json()
            return Session(
                id=SessionId(data["id"]),
                status=SessionStatus(data.get("status", "idle")),
                workspace=data.get("workspace"),
                project=data.get("project"),
                server="api",
                runtime_session_id=data.get("runtime_session_id"),
                error_message=data.get("error_message"),
                created_at=datetime.fromisoformat(data["created_at"]),
                updated_at=datetime.fromisoformat(data["updated_at"]),
                last_activity=datetime.fromisoformat(data.get("last_activity", data["updated_at"])),
            )
        except httpx.HTTPError as e:
            raise RuntimeUnavailableError(f"API get_session failed: {e}") from e

    async def list_sessions(self, limit: int = 10) -> list[Session]:
        try:
            resp = await self._client.get("/api/sessions", params={"limit": limit})
            resp.raise_for_status()
            data = resp.json()
            sessions = data if isinstance(data, list) else data.get("sessions", [])
            return [
                Session(
                    id=SessionId(s["id"]),
                    status=SessionStatus(s.get("status", "idle")),
                    workspace=s.get("workspace"),
                    project=s.get("project"),
                    server="api",
                    runtime_session_id=s.get("runtime_session_id"),
                    error_message=s.get("error_message"),
                    created_at=datetime.fromisoformat(s["created_at"]),
                    updated_at=datetime.fromisoformat(s["updated_at"]),
                    last_activity=datetime.fromisoformat(s.get("last_activity", s["updated_at"])),
                )
                for s in sessions
            ]
        except httpx.HTTPError as e:
            raise RuntimeUnavailableError(f"API list_sessions failed: {e}") from e

    async def send_prompt(self, session_id: str | SessionId, prompt: str, session_name: str | None = None) -> AsyncIterator[str]:
        sid = str(session_id)
        try:
            async with self._client.stream(
                "POST",
                f"/api/sessions/{sid}/prompt",
                json={"prompt": prompt},
            ) as resp:
                resp.raise_for_status()
                async for chunk in resp.aiter_text():
                    yield chunk
        except httpx.HTTPError as e:
            raise RuntimeUnavailableError(f"API send_prompt failed: {e}") from e

    async def stop_session(self, session_id: str | SessionId) -> None:
        sid = str(session_id)
        try:
            resp = await self._client.post(f"/api/sessions/{sid}/stop")
            resp.raise_for_status()
        except httpx.HTTPError as e:
            raise RuntimeUnavailableError(f"API stop_session failed: {e}") from e

    async def clear_session(self, session_id: str | SessionId) -> None:
        sid = str(session_id)
        try:
            resp = await self._client.post(f"/api/sessions/{sid}/clear")
            resp.raise_for_status()
        except httpx.HTTPError as e:
            raise RuntimeUnavailableError(f"API clear_session failed: {e}") from e

    async def get_health(self) -> HealthStatus:
        try:
            start = datetime.utcnow()
            resp = await self._client.get("/health")
            latency = (datetime.utcnow() - start).total_seconds() * 1000
            resp.raise_for_status()
            data = resp.json()
            return HealthStatus(
                telegram_webhook=True,
                runtime_available=True,
                runtime_mode="api",
                latency_ms=latency,
                storage_ok=data.get("storage_ok", True),
                active_sessions=data.get("active_sessions", 0),
            )
        except httpx.HTTPError as e:
            return HealthStatus(
                telegram_webhook=True,
                runtime_available=False,
                runtime_mode="api",
                latency_ms=None,
                storage_ok=False,
                active_sessions=0,
                errors=[str(e)],
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
        await self._client.aclose()
