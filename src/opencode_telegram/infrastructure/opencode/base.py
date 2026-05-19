from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass

from opencode_telegram.domain.entities import Session
from opencode_telegram.domain.value_objects import HealthStatus, RuntimeCapabilities, SessionId


@dataclass
class HistoryEntry:
    role: str  # "user" | "assistant"
    text: str
    timestamp: float


class OpenCodeRuntime(ABC):
    @abstractmethod
    async def create_session(
        self, workspace: str | None = None, project: str | None = None
    ) -> Session:
        ...

    @abstractmethod
    async def resume_session(self, session_id: str | SessionId) -> Session:
        ...

    @abstractmethod
    async def get_session(self, session_id: str | SessionId) -> Session | None:
        ...

    @abstractmethod
    async def list_sessions(self, limit: int = 10) -> list[Session]:
        ...

    @abstractmethod
    async def send_prompt(
        self, session_id: str | SessionId, prompt: str, session_name: str | None = None
    ) -> AsyncIterator[str]:
        ...

    def get_runtime_session_id(self) -> str | None:
        return None

    def get_opencode_db_path(self) -> str | None:
        return None

    async def get_session_history(self, runtime_session_id: str) -> list[HistoryEntry]:
        return []

    @abstractmethod
    async def stop_session(self, session_id: str | SessionId) -> None:
        ...

    @abstractmethod
    async def clear_session(self, session_id: str | SessionId) -> None:
        ...

    @abstractmethod
    async def get_health(self) -> HealthStatus:
        ...

    @abstractmethod
    async def get_capabilities(self) -> RuntimeCapabilities:
        ...

    @abstractmethod
    async def close(self) -> None:
        ...
