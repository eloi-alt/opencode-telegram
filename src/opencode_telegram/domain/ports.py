from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from datetime import datetime

from opencode_telegram.domain.entities import (
    AuditEvent,
    Chat,
    Message,
    ServerProfile,
    Session,
    SessionBinding,
    User,
    WorkspaceTarget,
)
from opencode_telegram.domain.value_objects import (
    ChatId,
    HealthStatus,
    MessageStatus,
    RuntimeCapabilities,
    SessionId,
    SessionStatus,
    UserId,
)


class AgentRuntime(ABC):
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
        self, session_id: str | SessionId, prompt: str
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


class SessionRepository(ABC):
    @abstractmethod
    async def save(self, session: Session) -> None:
        ...

    @abstractmethod
    async def get(self, session_id: SessionId) -> Session | None:
        ...

    @abstractmethod
    async def list_active(self, limit: int = 10) -> list[Session]:
        ...

    @abstractmethod
    async def list_by_status(self, status: SessionStatus) -> list[Session]:
        ...

    @abstractmethod
    async def update_status(
        self, session_id: SessionId, status: SessionStatus, error: str | None = None
    ) -> None:
        ...

    @abstractmethod
    async def touch_activity(self, session_id: SessionId) -> None:
        ...

    @abstractmethod
    async def archive_stale(self, timeout_seconds: int) -> int:
        ...


class UserRepository(ABC):
    @abstractmethod
    async def save(self, user: User) -> None:
        ...

    @abstractmethod
    async def get(self, user_id: UserId) -> User | None:
        ...

    @abstractmethod
    async def list_all(self) -> list[User]:
        ...


class ChatRepository(ABC):
    @abstractmethod
    async def save(self, chat: Chat) -> None:
        ...

    @abstractmethod
    async def get(self, chat_id: ChatId) -> Chat | None:
        ...


class SessionBindingRepository(ABC):
    @abstractmethod
    async def save(self, binding: SessionBinding) -> None:
        ...

    @abstractmethod
    async def get_active(self, chat_id: ChatId) -> SessionBinding | None:
        ...

    @abstractmethod
    async def list_all_active(self) -> list[SessionBinding]:
        ...

    @abstractmethod
    async def deactivate(self, chat_id: ChatId, session_id: SessionId) -> None:
        ...

    @abstractmethod
    async def set_active(
        self, chat_id: ChatId, session_id: SessionId
    ) -> None:
        ...


class MessageRepository(ABC):
    @abstractmethod
    async def save(self, message: Message) -> None:
        ...

    @abstractmethod
    async def update_status(
        self,
        message_id: MessageId,
        status: MessageStatus,
        error: str | None = None,
    ) -> None:
        ...

    @abstractmethod
    async def get_by_session(
        self, session_id: SessionId, limit: int = 50
    ) -> list[Message]:
        ...

    @abstractmethod
    async def get_recent_for_chat(
        self, chat_id: ChatId, limit: int = 20
    ) -> list[Message]:
        ...


class AuditRepository(ABC):
    @abstractmethod
    async def log(self, event: AuditEvent) -> None:
        ...

    @abstractmethod
    async def get_recent(
        self, limit: int = 50, since: datetime | None = None
    ) -> list[AuditEvent]:
        ...


class ServerProfileRepository(ABC):
    @abstractmethod
    async def save(self, profile: ServerProfile) -> None:
        ...

    @abstractmethod
    async def get(self, name: str) -> ServerProfile | None:
        ...

    @abstractmethod
    async def list_all(self) -> list[ServerProfile]:
        ...


class WorkspaceTargetRepository(ABC):
    @abstractmethod
    async def save(self, target: WorkspaceTarget) -> None:
        ...

    @abstractmethod
    async def list_by_server(self, server: str) -> list[WorkspaceTarget]:
        ...

    @abstractmethod
    async def list_all(self) -> list[WorkspaceTarget]:
        ...


class TelegramClient(ABC):
    @abstractmethod
    async def send_message(
        self,
        chat_id: ChatId | int,
        text: str,
        parse_mode: str | None = None,
        reply_markup: dict | None = None,
    ) -> dict | None:
        ...

    @abstractmethod
    async def edit_message(
        self,
        chat_id: ChatId | int,
        message_id: int,
        text: str,
        parse_mode: str | None = None,
    ) -> dict | None:
        ...

    @abstractmethod
    async def send_typing(self, chat_id: ChatId | int) -> None:
        ...

    @abstractmethod
    async def set_reaction(
        self, chat_id: ChatId | int, message_id: int, emoji: str
    ) -> None:
        ...

    @abstractmethod
    async def answer_callback(
        self, callback_query_id: str, text: str | None = None
    ) -> None:
        ...

    @abstractmethod
    async def set_commands(self, commands: list[dict]) -> None:
        ...

    @abstractmethod
    async def get_webhook_info(self) -> dict | None:
        ...
