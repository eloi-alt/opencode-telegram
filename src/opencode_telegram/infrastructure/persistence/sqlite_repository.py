from __future__ import annotations

from datetime import datetime

import aiosqlite

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
    UserRepository,
    WorkspaceTargetRepository,
)
from opencode_telegram.domain.value_objects import (
    ChatId,
    MessageId,
    MessageStatus,
    SessionId,
    SessionStatus,
    UserId,
)
from opencode_telegram.infrastructure.logging import get_logger
from opencode_telegram.shared.errors import PersistenceError

log = get_logger("opencode_telegram.infrastructure.persistence.sqlite")


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    is_admin INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chats (
    id INTEGER PRIMARY KEY,
    type TEXT NOT NULL,
    title TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'pending',
    name TEXT,
    workspace TEXT,
    project TEXT,
    server TEXT,
    runtime_session_id TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_activity TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS session_bindings (
    chat_id INTEGER NOT NULL,
    session_id TEXT NOT NULL,
    is_active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    PRIMARY KEY (chat_id, session_id)
);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    chat_id INTEGER NOT NULL,
    session_id TEXT NOT NULL,
    telegram_message_id INTEGER,
    direction TEXT NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'webhook_received',
    error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    user_id INTEGER,
    chat_id INTEGER,
    details TEXT NOT NULL,
    timestamp TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS server_profiles (
    name TEXT PRIMARY KEY,
    mode TEXT NOT NULL,
    base_url TEXT,
    api_key TEXT,
    cli_path TEXT,
    workspace_root TEXT
);

CREATE TABLE IF NOT EXISTS workspace_targets (
    name TEXT PRIMARY KEY,
    path TEXT NOT NULL,
    server TEXT NOT NULL DEFAULT 'local'
);

CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);
CREATE INDEX IF NOT EXISTS idx_sessions_activity ON sessions(last_activity);
CREATE INDEX IF NOT EXISTS idx_bindings_chat ON session_bindings(chat_id);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
CREATE INDEX IF NOT EXISTS idx_messages_chat ON messages(chat_id);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);
"""


class SqliteSessionRepository(SessionRepository):
    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def save(self, session: Session) -> None:
        await self._db.execute(
            """INSERT OR REPLACE INTO sessions
               (id, status, name, workspace, project, server, runtime_session_id, error_message, created_at, updated_at, last_activity)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(session.id),
                session.status.value,
                session.name,
                session.workspace,
                session.project,
                session.server,
                session.runtime_session_id,
                session.error_message,
                session.created_at.isoformat(),
                session.updated_at.isoformat(),
                session.last_activity.isoformat(),
            ),
        )
        await self._db.commit()

    async def get(self, session_id: SessionId) -> Session | None:
        cursor = await self._db.execute(
            "SELECT * FROM sessions WHERE id = ?", (str(session_id),)
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return self._row_to_session(row)

    async def list_active(self, limit: int = 10) -> list[Session]:
        cursor = await self._db.execute(
            "SELECT * FROM sessions WHERE status NOT IN ('archived', 'stopped') ORDER BY last_activity DESC LIMIT ?",
            (limit,),
        )
        rows = await cursor.fetchall()
        return [self._row_to_session(r) for r in rows]

    async def list_by_status(self, status: SessionStatus) -> list[Session]:
        cursor = await self._db.execute(
            "SELECT * FROM sessions WHERE status = ? ORDER BY last_activity DESC", (status.value,)
        )
        rows = await cursor.fetchall()
        return [self._row_to_session(r) for r in rows]

    async def update_status(self, session_id: SessionId, status: SessionStatus, error: str | None = None) -> None:
        now = datetime.utcnow().isoformat()
        if error:
            await self._db.execute(
                "UPDATE sessions SET status = ?, error_message = ?, updated_at = ?, last_activity = ? WHERE id = ?",
                (status.value, error, now, now, str(session_id)),
            )
        else:
            await self._db.execute(
                "UPDATE sessions SET status = ?, updated_at = ?, last_activity = ? WHERE id = ?",
                (status.value, now, now, str(session_id)),
            )
        await self._db.commit()

    async def touch_activity(self, session_id: SessionId) -> None:
        now = datetime.utcnow().isoformat()
        await self._db.execute(
            "UPDATE sessions SET last_activity = ? WHERE id = ?", (now, str(session_id))
        )
        await self._db.commit()

    async def archive_stale(self, timeout_seconds: int) -> int:
        cursor = await self._db.execute(
            """UPDATE sessions SET status = 'archived', updated_at = ?
               WHERE status NOT IN ('archived', 'stopped')
               AND (strftime('%s', 'now') - strftime('%s', last_activity)) > ?""",
            (datetime.utcnow().isoformat(), timeout_seconds),
        )
        await self._db.commit()
        return cursor.rowcount

    @staticmethod
    def _row_to_session(row: aiosqlite.Row) -> Session:
        return Session(
            id=SessionId(str(row[0])),
            status=SessionStatus(row[1]),
            name=row[2],
            workspace=row[3],
            project=row[4],
            server=row[5],
            runtime_session_id=row[6],
            error_message=row[7],
            created_at=datetime.fromisoformat(row[8]),
            updated_at=datetime.fromisoformat(row[9]),
            last_activity=datetime.fromisoformat(row[10]),
        )


class SqliteUserRepository(UserRepository):
    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def save(self, user: User) -> None:
        await self._db.execute(
            """INSERT OR REPLACE INTO users
               (id, username, first_name, is_admin, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                user.id.value,
                user.username,
                user.first_name,
                int(user.is_admin),
                user.created_at.isoformat(),
                user.updated_at.isoformat(),
            ),
        )
        await self._db.commit()

    async def get(self, user_id: UserId) -> User | None:
        cursor = await self._db.execute("SELECT * FROM users WHERE id = ?", (user_id.value,))
        row = await cursor.fetchone()
        if not row:
            return None
        return User(
            id=UserId(row[0]),
            username=row[1],
            first_name=row[2],
            is_admin=bool(row[3]),
            created_at=datetime.fromisoformat(row[4]),
            updated_at=datetime.fromisoformat(row[5]),
        )

    async def list_all(self) -> list[User]:
        cursor = await self._db.execute("SELECT * FROM users")
        rows = await cursor.fetchall()
        return [
            User(
                id=UserId(r[0]),
                username=r[1],
                first_name=r[2],
                is_admin=bool(r[3]),
                created_at=datetime.fromisoformat(r[4]),
                updated_at=datetime.fromisoformat(r[5]),
            )
            for r in rows
        ]


class SqliteChatRepository(ChatRepository):
    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def save(self, chat: Chat) -> None:
        await self._db.execute(
            "INSERT OR REPLACE INTO chats (id, type, title, created_at) VALUES (?, ?, ?, ?)",
            (chat.id.value, chat.type, chat.title, chat.created_at.isoformat()),
        )
        await self._db.commit()

    async def get(self, chat_id: ChatId) -> Chat | None:
        cursor = await self._db.execute("SELECT * FROM chats WHERE id = ?", (chat_id.value,))
        row = await cursor.fetchone()
        if not row:
            return None
        return Chat(id=ChatId(row[0]), type=row[1], title=row[2], created_at=datetime.fromisoformat(row[3]))


class SqliteSessionBindingRepository(SessionBindingRepository):
    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def save(self, binding: SessionBinding) -> None:
        await self._db.execute(
            "INSERT OR REPLACE INTO session_bindings (chat_id, session_id, is_active, created_at) VALUES (?, ?, ?, ?)",
            (binding.chat_id.value, str(binding.session_id), int(binding.is_active), binding.created_at.isoformat()),
        )
        await self._db.commit()

    async def get_active(self, chat_id: ChatId) -> SessionBinding | None:
        cursor = await self._db.execute(
            "SELECT * FROM session_bindings WHERE chat_id = ? AND is_active = 1 ORDER BY created_at DESC LIMIT 1",
            (chat_id.value,),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return SessionBinding(
            chat_id=ChatId(row[0]),
            session_id=SessionId(row[1]),
            is_active=bool(row[2]),
            created_at=datetime.fromisoformat(row[3]),
        )

    async def deactivate(self, chat_id: ChatId, session_id: SessionId) -> None:
        await self._db.execute(
            "UPDATE session_bindings SET is_active = 0 WHERE chat_id = ? AND session_id = ?",
            (chat_id.value, str(session_id)),
        )
        await self._db.commit()

    async def set_active(self, chat_id: ChatId, session_id: SessionId) -> None:
        await self._db.execute(
            "UPDATE session_bindings SET is_active = 0 WHERE chat_id = ?",
            (chat_id.value,),
        )
        await self._db.execute(
            "INSERT OR REPLACE INTO session_bindings (chat_id, session_id, is_active, created_at) VALUES (?, ?, 1, ?)",
            (chat_id.value, str(session_id), datetime.utcnow().isoformat()),
        )
        await self._db.commit()


class SqliteMessageRepository(MessageRepository):
    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def save(self, message: Message) -> None:
        await self._db.execute(
            """INSERT OR REPLACE INTO messages
               (id, chat_id, session_id, telegram_message_id, direction, content, status, error, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(message.id),
                message.chat_id.value,
                str(message.session_id),
                message.telegram_message_id,
                message.direction.value,
                message.content,
                message.status.value,
                message.error,
                message.created_at.isoformat(),
                message.updated_at.isoformat(),
            ),
        )
        await self._db.commit()

    async def update_status(self, message_id: MessageId, status: MessageStatus, error: str | None = None) -> None:
        now = datetime.utcnow().isoformat()
        if error:
            await self._db.execute(
                "UPDATE messages SET status = ?, error = ?, updated_at = ? WHERE id = ?",
                (status.value, error, now, str(message_id)),
            )
        else:
            await self._db.execute(
                "UPDATE messages SET status = ?, updated_at = ? WHERE id = ?",
                (status.value, now, str(message_id)),
            )
        await self._db.commit()

    async def get_by_session(self, session_id: SessionId, limit: int = 50) -> list[Message]:
        cursor = await self._db.execute(
            "SELECT * FROM messages WHERE session_id = ? ORDER BY created_at DESC LIMIT ?",
            (str(session_id), limit),
        )
        return [self._row_to_message(r) for r in await cursor.fetchall()]

    async def get_recent_for_chat(self, chat_id: ChatId, limit: int = 20) -> list[Message]:
        cursor = await self._db.execute(
            "SELECT * FROM messages WHERE chat_id = ? ORDER BY created_at DESC LIMIT ?",
            (chat_id.value, limit),
        )
        return [self._row_to_message(r) for r in await cursor.fetchall()]

    @staticmethod
    def _row_to_message(row: aiosqlite.Row) -> Message:
        from opencode_telegram.domain.value_objects import MessageDirection
        return Message(
            id=MessageId(str(row[0])),
            chat_id=ChatId(row[1]),
            session_id=SessionId(row[2]),
            telegram_message_id=row[3],
            direction=MessageDirection(row[4]),
            content=row[5],
            status=MessageStatus(row[6]),
            error=row[7],
            created_at=datetime.fromisoformat(row[8]),
            updated_at=datetime.fromisoformat(row[9]),
        )


class SqliteAuditRepository(AuditRepository):
    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def log(self, event: AuditEvent) -> None:
        await self._db.execute(
            "INSERT INTO audit_log (event_type, user_id, chat_id, details, timestamp) VALUES (?, ?, ?, ?, ?)",
            (
                event.event_type,
                event.user_id.value if event.user_id else None,
                event.chat_id.value if event.chat_id else None,
                event.details,
                event.timestamp.isoformat(),
            ),
        )
        await self._db.commit()

    async def get_recent(self, limit: int = 50, since: datetime | None = None) -> list[AuditEvent]:
        if since:
            cursor = await self._db.execute(
                "SELECT * FROM audit_log WHERE timestamp >= ? ORDER BY timestamp DESC LIMIT ?",
                (since.isoformat(), limit),
            )
        else:
            cursor = await self._db.execute(
                "SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT ?", (limit,)
            )
        return [
            AuditEvent(
                event_type=r[1],
                user_id=UserId(r[2]) if r[2] else None,
                chat_id=ChatId(r[3]) if r[3] else None,
                details=r[4],
                timestamp=datetime.fromisoformat(r[5]),
            )
            for r in await cursor.fetchall()
        ]


class SqliteServerProfileRepository(ServerProfileRepository):
    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def save(self, profile: ServerProfile) -> None:
        await self._db.execute(
            "INSERT OR REPLACE INTO server_profiles (name, mode, base_url, api_key, cli_path, workspace_root) VALUES (?, ?, ?, ?, ?, ?)",
            (
                profile.name,
                profile.mode.value,
                profile.base_url,
                profile.api_key,
                profile.cli_path,
                profile.workspace_root,
            ),
        )
        await self._db.commit()

    async def get(self, name: str) -> ServerProfile | None:
        cursor = await self._db.execute("SELECT * FROM server_profiles WHERE name = ?", (name,))
        row = await cursor.fetchone()
        if not row:
            return None
        return self._row_to_profile(row)

    async def list_all(self) -> list[ServerProfile]:
        cursor = await self._db.execute("SELECT * FROM server_profiles")
        return [self._row_to_profile(r) for r in await cursor.fetchall()]

    @staticmethod
    def _row_to_profile(row: aiosqlite.Row) -> ServerProfile:
        from opencode_telegram.domain.value_objects import RuntimeMode
        return ServerProfile(
            name=row[0],
            mode=RuntimeMode(row[1]),
            base_url=row[2],
            api_key=row[3],
            cli_path=row[4],
            workspace_root=row[5],
        )


class SqliteWorkspaceTargetRepository(WorkspaceTargetRepository):
    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def save(self, target: WorkspaceTarget) -> None:
        await self._db.execute(
            "INSERT OR REPLACE INTO workspace_targets (name, path, server) VALUES (?, ?, ?)",
            (target.name, target.path, target.server),
        )
        await self._db.commit()

    async def list_by_server(self, server: str) -> list[WorkspaceTarget]:
        cursor = await self._db.execute(
            "SELECT * FROM workspace_targets WHERE server = ?", (server,)
        )
        return [self._row_to_target(r) for r in await cursor.fetchall()]

    async def list_all(self) -> list[WorkspaceTarget]:
        cursor = await self._db.execute("SELECT * FROM workspace_targets")
        return [self._row_to_target(r) for r in await cursor.fetchall()]

    @staticmethod
    def _row_to_target(row: aiosqlite.Row) -> WorkspaceTarget:
        return WorkspaceTarget(name=row[0], path=row[1], server=row[2])
