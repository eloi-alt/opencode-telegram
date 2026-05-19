from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
import pytest_asyncio

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
from opencode_telegram.domain.ports import (
    AuditRepository,
    ChatRepository,
    MessageRepository,
    ServerProfileRepository,
    SessionBindingRepository,
    SessionRepository,
    TelegramClient,
    UserRepository,
    WorkspaceTargetRepository,
)
from opencode_telegram.domain.value_objects import (
    ChatId,
    HealthStatus,
    MessageId,
    MessageStatus,
    RuntimeCapabilities,
    SessionId,
    SessionStatus,
    UserId,
)
from opencode_telegram.infrastructure.opencode.base import OpenCodeRuntime
from opencode_telegram.infrastructure.security import SecurityService


class FakeUserRepository(UserRepository):
    def __init__(self) -> None:
        self._store: dict[int, User] = {}

    async def save(self, user: User) -> None:
        self._store[user.id.value] = user

    async def get(self, user_id: UserId) -> User | None:
        return self._store.get(user_id.value)

    async def list_all(self) -> list[User]:
        return list(self._store.values())


class FakeChatRepository(ChatRepository):
    def __init__(self) -> None:
        self._store: dict[int, Chat] = {}

    async def save(self, chat: Chat) -> None:
        self._store[chat.id.value] = chat

    async def get(self, chat_id: ChatId) -> Chat | None:
        return self._store.get(chat_id.value)


class FakeSessionRepository(SessionRepository):
    def __init__(self) -> None:
        self._store: dict[str, Session] = {}

    async def save(self, session: Session) -> None:
        self._store[str(session.id)] = session

    async def get(self, session_id: SessionId) -> Session | None:
        return self._store.get(str(session_id))

    async def list_active(self, limit: int = 10) -> list[Session]:
        active = [s for s in self._store.values() if s.status not in (SessionStatus.archived, SessionStatus.stopped)]
        return sorted(active, key=lambda s: s.last_activity, reverse=True)[:limit]

    async def list_by_status(self, status: SessionStatus) -> list[Session]:
        return [s for s in self._store.values() if s.status == status]

    async def update_status(self, session_id: SessionId, status: SessionStatus, error: str | None = None) -> None:
        s = self._store.get(str(session_id))
        if s:
            s.status = status
            if error:
                s.error_message = error

    async def touch_activity(self, session_id: SessionId) -> None:
        from datetime import datetime
        s = self._store.get(str(session_id))
        if s:
            s.last_activity = datetime.utcnow()

    async def archive_stale(self, timeout_seconds: int) -> int:
        from datetime import datetime, timedelta
        count = 0
        cutoff = datetime.utcnow() - timedelta(seconds=timeout_seconds)
        for s in self._store.values():
            if s.status not in (SessionStatus.archived, SessionStatus.stopped) and s.last_activity < cutoff:
                s.status = SessionStatus.archived
                count += 1
        return count


class FakeSessionBindingRepository(SessionBindingRepository):
    def __init__(self) -> None:
        self._store: dict[tuple[int, str], SessionBinding] = {}

    async def save(self, binding: SessionBinding) -> None:
        self._store[(binding.chat_id.value, str(binding.session_id))] = binding

    async def get_active(self, chat_id: ChatId) -> SessionBinding | None:
        for (cid, _), b in self._store.items():
            if cid == chat_id.value and b.is_active:
                return b
        return None

    async def list_all_active(self) -> list[SessionBinding]:
        return [b for b in self._store.values() if b.is_active]

    async def deactivate(self, chat_id: ChatId, session_id: SessionId) -> None:
        key = (chat_id.value, str(session_id))
        if key in self._store:
            self._store[key].is_active = False

    async def set_active(self, chat_id: ChatId, session_id: SessionId) -> None:
        for key in self._store:
            if key[0] == chat_id.value:
                self._store[key].is_active = False
        self._store[(chat_id.value, str(session_id))] = SessionBinding(
            chat_id=chat_id, session_id=session_id, is_active=True
        )


class FakeMessageRepository(MessageRepository):
    def __init__(self) -> None:
        self._store: dict[str, Message] = {}

    async def save(self, message: Message) -> None:
        self._store[str(message.id)] = message

    async def update_status(self, message_id: MessageId, status: MessageStatus, error: str | None = None) -> None:
        m = self._store.get(str(message_id))
        if m:
            m.status = status
            m.error = error

    async def get_by_session(self, session_id: SessionId, limit: int = 50) -> list[Message]:
        msgs = [m for m in self._store.values() if m.session_id == session_id]
        return sorted(msgs, key=lambda m: m.created_at, reverse=True)[:limit]

    async def get_recent_for_chat(self, chat_id: ChatId, limit: int = 20) -> list[Message]:
        msgs = [m for m in self._store.values() if m.chat_id == chat_id]
        return sorted(msgs, key=lambda m: m.created_at, reverse=True)[:limit]


class FakeAuditRepository(AuditRepository):
    def __init__(self) -> None:
        self._events: list[AuditEvent] = []

    async def log(self, event: AuditEvent) -> None:
        self._events.append(event)

    async def get_recent(self, limit: int = 50, since: Any = None) -> list[AuditEvent]:
        events = self._events
        if since:
            events = [e for e in events if e.timestamp >= since]
        return sorted(events, key=lambda e: e.timestamp, reverse=True)[:limit]


class FakeServerProfileRepository(ServerProfileRepository):
    async def save(self, profile: ServerProfile) -> None:
        pass

    async def get(self, name: str) -> ServerProfile | None:
        return None

    async def list_all(self) -> list[ServerProfile]:
        return []


class FakeWorkspaceTargetRepository(WorkspaceTargetRepository):
    async def save(self, target: WorkspaceTarget) -> None:
        pass

    async def list_by_server(self, server: str) -> list[WorkspaceTarget]:
        return []

    async def list_all(self) -> list[WorkspaceTarget]:
        return []


class FakeTelegramClient(TelegramClient):
    def __init__(self) -> None:
        self.sent_messages: list[dict] = []
        self.edited_messages: list[dict] = []

    async def send_message(self, chat_id: ChatId | int, text: str, parse_mode: str | None = None, reply_markup: dict | None = None) -> dict | None:
        self.sent_messages.append({"chat_id": chat_id, "text": text, "parse_mode": parse_mode, "reply_markup": reply_markup})
        return {"ok": True}

    async def edit_message(self, chat_id: ChatId | int, message_id: int, text: str, parse_mode: str | None = None) -> dict | None:
        self.edited_messages.append({"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": parse_mode})
        return {"ok": True}

    async def send_typing(self, chat_id: ChatId | int) -> None:
        pass

    async def set_reaction(self, chat_id: ChatId | int, message_id: int, emoji: str) -> None:
        pass

    async def answer_callback(self, callback_query_id: str, text: str | None = None) -> None:
        pass

    async def set_commands(self, commands: list[dict]) -> None:
        pass

    async def get_webhook_info(self) -> dict | None:
        return {"ok": True}


class FakeOpenCodeRuntime(OpenCodeRuntime):
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._responses: dict[str, str] = {}
        self._fail_on_prompt = False

    async def create_session(self, workspace: str | None = None, project: str | None = None) -> Session:
        from datetime import datetime
        s = Session(
            id=SessionId.generate(),
            status=SessionStatus.ready,
            workspace=workspace,
            project=project,
            server="test",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            last_activity=datetime.utcnow(),
        )
        self._sessions[str(s.id)] = s
        return s

    async def resume_session(self, session_id: str | SessionId) -> Session:
        s = self._sessions.get(str(session_id))
        if s:
            return s
        raise ValueError(f"Session not found: {session_id}")

    async def get_session(self, session_id: str | SessionId) -> Session | None:
        return self._sessions.get(str(session_id))

    async def list_sessions(self, limit: int = 10) -> list[Session]:
        return list(self._sessions.values())[:limit]

    async def send_prompt(self, session_id: str | SessionId, prompt: str, session_name: str | None = None) -> AsyncIterator[str]:
        if self._fail_on_prompt:
            from opencode_telegram.shared.errors import RuntimeUnavailableError
            raise RuntimeUnavailableError("Simulated runtime error")
        response = self._responses.get(str(session_id), f"Response to: {prompt}")
        yield response

    async def stop_session(self, session_id: str | SessionId) -> None:
        s = self._sessions.get(str(session_id))
        if s:
            s.status = SessionStatus.stopped

    async def clear_session(self, session_id: str | SessionId) -> None:
        pass

    async def get_health(self) -> HealthStatus:
        return HealthStatus(
            telegram_webhook=True,
            runtime_available=True,
            runtime_mode="test",
            latency_ms=5.0,
            storage_ok=True,
            active_sessions=len(self._sessions),
        )

    async def get_capabilities(self) -> RuntimeCapabilities:
        return RuntimeCapabilities(
            supports_streaming=False,
            supports_sessions=True,
            supports_stop=True,
            supports_projects=False,
            supports_workspaces=True,
            max_prompt_length=4096,
            available_commands=["start", "status", "sessions", "clear", "stop", "help"],
        )

    async def close(self) -> None:
        pass

    def set_fail_on_prompt(self, fail: bool = True) -> None:
        self._fail_on_prompt = fail

    def set_response(self, session_id: str, response: str) -> None:
        self._responses[session_id] = response


@pytest.fixture
def config() -> Any:
    from opencode_telegram.infrastructure.config import AppConfig
    import os
    os.environ["TELEGRAM_BOT_TOKEN"] = "test:token"
    os.environ["FAKE_RUNTIME"] = "true"
    return AppConfig()


@pytest.fixture
def telegram() -> FakeTelegramClient:
    return FakeTelegramClient()


@pytest.fixture
def runtime() -> FakeOpenCodeRuntime:
    return FakeOpenCodeRuntime()


@pytest.fixture
def security(config: Any) -> SecurityService:
    return SecurityService(config)


@pytest.fixture
def user_repo() -> FakeUserRepository:
    return FakeUserRepository()


@pytest.fixture
def chat_repo() -> FakeChatRepository:
    return FakeChatRepository()


@pytest.fixture
def session_repo() -> FakeSessionRepository:
    return FakeSessionRepository()


@pytest.fixture
def binding_repo() -> FakeSessionBindingRepository:
    return FakeSessionBindingRepository()


@pytest.fixture
def message_repo() -> FakeMessageRepository:
    return FakeMessageRepository()


@pytest.fixture
def audit_repo() -> FakeAuditRepository:
    return FakeAuditRepository()
