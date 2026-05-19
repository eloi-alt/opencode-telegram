from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from opencode_telegram.domain.value_objects import (
    ChatId,
    MessageDirection,
    MessageId,
    MessageStatus,
    RuntimeMode,
    SessionId,
    SessionStatus,
    UserId,
)


@dataclass
class User:
    id: UserId
    username: str | None
    first_name: str | None
    is_admin: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Chat:
    id: ChatId
    type: str  # private, group, supergroup, channel
    title: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Session:
    id: SessionId
    status: SessionStatus = SessionStatus.pending
    name: str | None = None
    workspace: str | None = None
    project: str | None = None
    server: str | None = None
    runtime_session_id: str | None = None
    error_message: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    last_activity: datetime = field(default_factory=datetime.utcnow)


@dataclass
class SessionBinding:
    chat_id: ChatId
    session_id: SessionId
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Message:
    id: MessageId
    chat_id: ChatId
    session_id: SessionId
    telegram_message_id: int | None = None
    direction: MessageDirection = MessageDirection.incoming
    content: str = ""
    status: MessageStatus = MessageStatus.webhook_received
    error: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ServerProfile:
    name: str
    mode: RuntimeMode
    base_url: str | None = None
    api_key: str | None = None
    cli_path: str | None = None
    workspace_root: str | None = None


@dataclass
class WorkspaceTarget:
    name: str
    path: str
    server: str = "local"


@dataclass
class CommandInvocation:
    command: str
    args: list[str]
    user_id: UserId
    chat_id: ChatId
    session_id: SessionId | None = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ExecutionTrace:
    message_id: MessageId
    session_id: SessionId
    status: str
    duration_ms: float | None = None
    error: str | None = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class AuditEvent:
    event_type: str
    user_id: UserId | None
    chat_id: ChatId | None
    details: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
