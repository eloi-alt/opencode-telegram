from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4


class SessionStatus(str, enum.Enum):
    pending = "pending"
    starting = "starting"
    ready = "ready"
    busy = "busy"
    streaming = "streaming"
    idle = "idle"
    failed = "failed"
    stopped = "stopped"
    archived = "archived"


class MessageStatus(str, enum.Enum):
    webhook_received = "webhook_received"
    validated = "validated"
    queued = "queued"
    dispatched = "dispatched"
    running = "running"
    response_partial = "response_partial"
    response_complete = "response_complete"
    response_error = "response_error"
    telegram_send_failed = "telegram_send_failed"


class MessageDirection(str, enum.Enum):
    incoming = "incoming"
    outgoing = "outgoing"


class RuntimeMode(str, enum.Enum):
    api = "api"
    cli = "cli"


class CommandName(str, enum.Enum):
    start = "start"
    status = "status"
    sessions = "sessions"
    resume = "resume"
    clear = "clear"
    stop = "stop"
    bind = "bind"
    health = "health"
    logs = "logs"
    help = "help"
    new = "new"


@dataclass
class UserId:
    value: int

    def __str__(self) -> str:
        return str(self.value)


@dataclass
class ChatId:
    value: int

    def __str__(self) -> str:
        return str(self.value)


@dataclass
class SessionId:
    value: str

    def __str__(self) -> str:
        return self.value

    @classmethod
    def generate(cls) -> SessionId:
        return cls(value=str(uuid4()))


@dataclass
class MessageId:
    value: str

    @classmethod
    def generate(cls) -> MessageId:
        return cls(value=str(uuid4()))

    def __str__(self) -> str:
        return self.value


@dataclass
class HealthStatus:
    telegram_webhook: bool
    runtime_available: bool
    runtime_mode: str
    latency_ms: float | None
    storage_ok: bool
    active_sessions: int
    errors: list[str] = field(default_factory=list)


@dataclass
class RuntimeCapabilities:
    supports_streaming: bool
    supports_sessions: bool
    supports_stop: bool
    supports_projects: bool
    supports_workspaces: bool
    max_prompt_length: int
    available_commands: list[str]
