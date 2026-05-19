from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from opencode_telegram.domain.entities import Session
from opencode_telegram.domain.value_objects import HealthStatus, RuntimeCapabilities, SessionId


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
