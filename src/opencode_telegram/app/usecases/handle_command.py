from __future__ import annotations

import shlex
from datetime import datetime

from opencode_telegram.domain.entities import (
    AuditEvent,
    Chat,
    Session,
    SessionBinding,
    User,
)
from opencode_telegram.domain.ports import (
    AuditRepository,
    ChatRepository,
    MessageRepository,
    SessionBindingRepository,
    SessionRepository,
    TelegramClient,
    UserRepository,
)
from opencode_telegram.domain.value_objects import (
    ChatId,
    CommandName,
    RuntimeCapabilities,
    SessionId,
    SessionStatus,
    UserId,
)
from opencode_telegram.infrastructure.logging import get_logger
from opencode_telegram.infrastructure.opencode.base import OpenCodeRuntime
from opencode_telegram.infrastructure.security import SecurityService
from opencode_telegram.infrastructure.telegram.formatting import (
    render_help_text,
    render_status_card,
    split_long_message,
)
from opencode_telegram.shared.errors import CommandNotAllowedError, SessionNotFoundError

log = get_logger("opencode_telegram.app.usecases.handle_command")


class HandleCommandUseCase:
    _pending_new_names: dict[int, bool] = {}

    def __init__(
        self,
        user_repo: UserRepository,
        chat_repo: ChatRepository,
        session_repo: SessionRepository,
        binding_repo: SessionBindingRepository,
        message_repo: MessageRepository,
        audit_repo: AuditRepository,
        runtime: OpenCodeRuntime,
        telegram: TelegramClient,
        security: SecurityService,
        default_workspace: str,
        default_server: str,
        capabilities: RuntimeCapabilities,
        max_message_length: int = 4096,
    ) -> None:
        self._user_repo = user_repo
        self._chat_repo = chat_repo
        self._session_repo = session_repo
        self._binding_repo = binding_repo
        self._message_repo = message_repo
        self._audit_repo = audit_repo
        self._runtime = runtime
        self._telegram = telegram
        self._security = security
        self._default_workspace = default_workspace
        self._default_server = default_server
        self._capabilities = capabilities
        self._max_msg_length = max_message_length

    def has_pending_name(self, chat_id: ChatId) -> bool:
        return self._pending_new_names.get(chat_id.value, False)

    async def handle_name_response(self, chat_id: ChatId, user_id: UserId, name: str) -> None:
        if not self._pending_new_names.pop(chat_id.value, False):
            return
        binding = await self._binding_repo.get_active(chat_id)
        if binding:
            await self._binding_repo.deactivate(chat_id, binding.session_id)
            await self._session_repo.update_status(binding.session_id, SessionStatus.archived)
        session = await self._runtime.create_session(workspace=self._default_workspace)
        session.name = name
        session.server = self._default_server
        await self._session_repo.save(session)
        binding = SessionBinding(chat_id=chat_id, session_id=session.id, is_active=True)
        await self._binding_repo.save(binding)
        await self._telegram.send_message(
            chat_id.value,
            f"🆕 New session <b>{name}</b> created and bound.",
            parse_mode="HTML",
        )

    async def execute(self, update: dict) -> None:
        message = update.get("message", {})
        text = (message.get("text") or "").strip()
        chat_id = ChatId(message.get("chat", {}).get("id", 0))
        user_data = message.get("from", {})
        user_id = UserId(user_data.get("id", 0))

        if not text or not chat_id.value:
            return

        parts = shlex.split(text)
        command = parts[0].lower().lstrip("/")
        args = parts[1:]

        await self._ensure_user(user_id, user_data)
        await self._ensure_chat(chat_id, message.get("chat", {}))

        try:
            cmd = CommandName(command)
        except ValueError:
            await self._telegram.send_message(
                chat_id.value,
                f"Unknown command: /{command}. Try /help",
            )
            return

        self._security.check_command_allowed(command)

        handler_map = {
            CommandName.start: self._handle_start,
            CommandName.status: self._handle_status,
            CommandName.sessions: self._handle_sessions,
            CommandName.resume: self._handle_resume,
            CommandName.new: self._handle_new,
            CommandName.sync: self._handle_sync,
            CommandName.clear: self._handle_clear,
            CommandName.stop: self._handle_stop,
            CommandName.bind: self._handle_bind,
            CommandName.health: self._handle_health,
            CommandName.logs: self._handle_logs,
            CommandName.help: self._handle_help,
        }

        handler = handler_map.get(cmd)
        if handler is None:
            await self._telegram.send_message(chat_id.value, f"Unknown command: /{command}")
            return

        if cmd in (CommandName.health, CommandName.logs):
            self._security.check_admin(user_id)

        await handler(chat_id, user_id, args)

        await self._audit_repo.log(AuditEvent(
            event_type=f"command_{command}",
            user_id=user_id,
            chat_id=chat_id,
            details=f"args={' '.join(args)}",
        ))

    async def _ensure_user(self, user_id: UserId, user_data: dict) -> None:
        existing = await self._user_repo.get(user_id)
        if existing:
            return
        user = User(
            id=user_id,
            username=user_data.get("username"),
            first_name=user_data.get("first_name"),
        )
        await self._user_repo.save(user)

    async def _ensure_chat(self, chat_id: ChatId, chat_data: dict) -> None:
        existing = await self._chat_repo.get(chat_id)
        if existing:
            return
        chat = Chat(
            id=chat_id,
            type=chat_data.get("type", "private"),
            title=chat_data.get("title"),
        )
        await self._chat_repo.save(chat)

    async def _handle_start(self, chat_id: ChatId, user_id: UserId, args: list[str]) -> None:
        session = await self._resolve_or_create_session(chat_id)
        status = render_status_card(
            session=session,
            server=session.server,
            workspace=session.workspace,
            uptime="just now",
            error=None,
        )
        lines = [
            "👋 <b>OpenCode Telegram Bridge</b>\n",
            "Send any message to chat with OpenCode.",
            "Use /help to see available commands.\n",
            status,
        ]
        await self._telegram.send_message(chat_id.value, "\n".join(lines), parse_mode="HTML")

    async def _handle_status(self, chat_id: ChatId, user_id: UserId, args: list[str]) -> None:
        binding = await self._binding_repo.get_active(chat_id)
        session: Session | None = None
        error: str | None = None
        if binding:
            session = await self._session_repo.get(binding.session_id)
        if session is None:
            session = await self._resolve_or_create_session(chat_id)

        uptime: str | None = None
        if session:
            delta = datetime.utcnow() - session.last_activity
            minutes = int(delta.total_seconds() // 60)
            if minutes < 1:
                uptime = "just now"
            elif minutes < 60:
                uptime = f"{minutes}m ago"
            else:
                uptime = f"{minutes // 60}h {minutes % 60}m ago"
            if session.error_message:
                error = session.error_message

        card = render_status_card(
            session=session,
            server=session.server if session else self._default_server,
            workspace=session.workspace if session else self._default_workspace,
            uptime=uptime,
            error=error,
        )
        await self._telegram.send_message(chat_id.value, card, parse_mode="HTML")

    async def _handle_sessions(self, chat_id: ChatId, user_id: UserId, args: list[str]) -> None:
        sessions = await self._session_repo.list_active(limit=10)
        if not sessions:
            await self._telegram.send_message(chat_id.value, "No active sessions.")
            return
        lines = ["<b>Active Sessions</b>\n"]
        for s in sessions:
            status_emoji = "✅" if s.status == SessionStatus.ready else "⚡" if s.status == SessionStatus.busy else "❌"
            label = f"<b>{s.name}</b>" if s.name else f"<code>{s.id.value[:12]}...</code>"
            lines.append(f"{status_emoji} {label} {s.status.value} | ws:{s.workspace or '-'}")
        await self._telegram.send_message(chat_id.value, "\n".join(lines), parse_mode="HTML")

    async def _handle_resume(self, chat_id: ChatId, user_id: UserId, args: list[str]) -> None:
        sessions = await self._session_repo.list_active(limit=5)
        if not sessions:
            await self._telegram.send_message(
                chat_id.value, "No sessions to resume. Send a message to start one."
            )
            return
        kb = []
        for s in sessions:
            name_part = s.name or s.id.value[:12]
            label = f"{name_part} ({s.workspace or '-'})"
            kb.append([{"text": label, "callback_data": f"resume:{s.id.value}"}])
        await self._telegram.send_message(
            chat_id.value,
            "Select a session to resume:",
            reply_markup={"inline_keyboard": kb},
        )

    async def _handle_new(self, chat_id: ChatId, user_id: UserId, args: list[str]) -> None:
        if args:
            name = args[0]
            binding = await self._binding_repo.get_active(chat_id)
            if binding:
                await self._binding_repo.deactivate(chat_id, binding.session_id)
                await self._session_repo.update_status(binding.session_id, SessionStatus.archived)
            session = await self._runtime.create_session(workspace=self._default_workspace)
            session.name = name
            session.server = self._default_server
            await self._session_repo.save(session)
            binding = SessionBinding(chat_id=chat_id, session_id=session.id, is_active=True)
            await self._binding_repo.save(binding)
            await self._telegram.send_message(
                chat_id.value,
                f"🆕 New session <b>{name}</b> created and bound.",
                parse_mode="HTML",
            )
        else:
            self._pending_new_names[chat_id.value] = True
            await self._telegram.send_message(
                chat_id.value,
                "What name for the new session?",
            )

    async def _handle_sync(self, chat_id: ChatId, user_id: UserId, args: list[str]) -> None:
        binding = await self._binding_repo.get_active(chat_id)
        if binding is None:
            await self._telegram.send_message(
                chat_id.value, "No active session. Send a message first."
            )
            return
        session = await self._session_repo.get(binding.session_id)
        if not session or not session.runtime_session_id:
            await self._telegram.send_message(
                chat_id.value, "No runtime session yet. Send a message to this session first."
            )
            return
        await self._telegram.send_message(chat_id.value, "📡 Fetching session history...")
        history = await self._runtime.get_session_history(session.runtime_session_id)
        if not history:
            await self._telegram.send_message(
                chat_id.value, "No history found in OpenCode for this session."
            )
            return
        lines: list[str] = [f"<b>Session History: {session.name or session.id.value[:12]}</b>\n"]
        for entry in history[-30:]:
            icon = "👤" if entry.role == "user" else "🤖"
            text = entry.text[:200]
            lines.append(f"{icon} {text}")
        text = "\n\n".join(lines)
        parts = split_long_message(text, self._max_msg_length)
        for part in parts:
            await self._telegram.send_message(chat_id.value, part, parse_mode="HTML")

    async def _handle_clear(self, chat_id: ChatId, user_id: UserId, args: list[str]) -> None:
        binding = await self._binding_repo.get_active(chat_id)
        if binding is None:
            await self._telegram.send_message(
                chat_id.value, "No active session to clear."
            )
            return
        try:
            await self._runtime.clear_session(binding.session_id)
            await self._session_repo.update_status(binding.session_id, SessionStatus.ready)
            await self._telegram.send_message(chat_id.value, "Session context cleared.")
        except Exception as e:
            await self._telegram.send_message(chat_id.value, f"Failed to clear session: {e}")

    async def _handle_stop(self, chat_id: ChatId, user_id: UserId, args: list[str]) -> None:
        binding = await self._binding_repo.get_active(chat_id)
        if binding is None:
            await self._telegram.send_message(chat_id.value, "No active session to stop.")
            return
        try:
            await self._runtime.stop_session(binding.session_id)
            await self._session_repo.update_status(binding.session_id, SessionStatus.stopped)
            await self._telegram.send_message(chat_id.value, "Execution stopped.")
        except Exception as e:
            await self._telegram.send_message(chat_id.value, f"Failed to stop session: {e}")

    async def _handle_bind(self, chat_id: ChatId, user_id: UserId, args: list[str]) -> None:
        await self._telegram.send_message(
            chat_id.value,
            "Binding is configured via environment or server profiles.\n"
            "Current: workspace=<b>{}</b>, server=<b>{}</b>".format(
                self._default_workspace, self._default_server
            ),
            parse_mode="HTML",
        )

    async def _handle_health(self, chat_id: ChatId, user_id: UserId, args: list[str]) -> None:
        health = await self._runtime.get_health()
        lines = [
            "<b>Health Diagnostics</b>\n",
            f"Runtime: {'✅' if health.runtime_available else '❌'} <b>{health.runtime_mode}</b>",
            f"Telegram: {'✅' if health.telegram_webhook else '❌'}",
            f"Storage: {'✅' if health.storage_ok else '❌'}",
            f"Active sessions: <b>{health.active_sessions}</b>",
        ]
        if health.latency_ms is not None:
            lines.append(f"Latency: <b>{health.latency_ms:.0f}ms</b>")
        if health.errors:
            lines.append(f"\nErrors: {', '.join(health.errors)}")
        await self._telegram.send_message(chat_id.value, "\n".join(lines), parse_mode="HTML")

    async def _handle_logs(self, chat_id: ChatId, user_id: UserId, args: list[str]) -> None:
        events = await self._audit_repo.get_recent(limit=20)
        if not events:
            await self._telegram.send_message(chat_id.value, "No recent events.")
            return
        lines = ["<b>Recent Events</b>\n"]
        for e in events:
            ts = e.timestamp.strftime("%H:%M:%S")
            uid = str(e.user_id.value) if e.user_id else "-"
            lines.append(f"<code>{ts}</code> {e.event_type} | u:{uid} | {e.details[:60]}")
        await self._telegram.send_message(chat_id.value, "\n".join(lines), parse_mode="HTML")

    async def _handle_help(self, chat_id: ChatId, user_id: UserId, args: list[str]) -> None:
        is_admin = self._capabilities.available_commands is not None
        text = render_help_text(has_admin=is_admin)
        await self._telegram.send_message(chat_id.value, text, parse_mode="HTML")

    async def _resolve_or_create_session(self, chat_id: ChatId) -> Session:
        binding = await self._binding_repo.get_active(chat_id)
        if binding:
            session = await self._session_repo.get(binding.session_id)
            if session:
                return session
        session = await self._runtime.create_session(workspace=self._default_workspace)
        session.server = self._default_server
        await self._session_repo.save(session)
        binding = SessionBinding(chat_id=chat_id, session_id=session.id, is_active=True)
        await self._binding_repo.save(binding)
        return session
