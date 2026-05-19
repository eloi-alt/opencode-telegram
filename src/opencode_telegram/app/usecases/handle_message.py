from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime

from opencode_telegram.domain.entities import (
    AuditEvent,
    Chat,
    Message,
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
    MessageDirection,
    MessageId,
    MessageStatus,
    SessionId,
    SessionStatus,
    UserId,
)
from opencode_telegram.infrastructure.logging import get_logger
from opencode_telegram.infrastructure.opencode.base import OpenCodeRuntime
from opencode_telegram.infrastructure.telegram.formatting import (
    format_as_html,
    split_long_message,
)
from opencode_telegram.shared.errors import (
    RuntimeUnavailableError,
    SessionBusyError,
    TelegramSendError,
)

log = get_logger("opencode_telegram.app.usecases.handle_message")


class HandleMessageUseCase:
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
        default_workspace: str,
        default_server: str,
        max_message_length: int,
    ) -> None:
        self._user_repo = user_repo
        self._chat_repo = chat_repo
        self._session_repo = session_repo
        self._binding_repo = binding_repo
        self._message_repo = message_repo
        self._audit_repo = audit_repo
        self._runtime = runtime
        self._telegram = telegram
        self._default_workspace = default_workspace
        self._default_server = default_server
        self._max_message_length = max_message_length

    async def execute(self, update: dict) -> None:
        message = update.get("message", {})
        text = (message.get("text") or "").strip()
        chat_id = ChatId(message.get("chat", {}).get("id", 0))
        user_data = message.get("from", {})
        user_id = UserId(user_data.get("id", 0))
        msg_id = message.get("message_id")

        if not text or not chat_id.value:
            return

        await self._ensure_user(user_id, user_data)
        await self._ensure_chat(chat_id, message.get("chat", {}))

        if text.startswith("/"):
            return

        await self._telegram.set_reaction(chat_id, msg_id, "✅")
        await self._telegram.send_typing(chat_id)

        session = await self._resolve_session(chat_id)
        if session is None:
            session = await self._create_session(chat_id)

        if session.status == SessionStatus.busy:
            raise SessionBusyError(str(session.id))

        msg = Message(
            id=MessageId.generate(),
            chat_id=chat_id,
            session_id=session.id,
            telegram_message_id=msg_id,
            direction=MessageDirection.incoming,
            content=text,
            status=MessageStatus.validated,
        )
        await self._message_repo.save(msg)
        await self._message_repo.update_status(msg.id, MessageStatus.dispatched)
        await self._session_repo.update_status(session.id, SessionStatus.busy)

        try:
            response_parts: list[str] = []
            async for chunk in self._runtime.send_prompt(session.id, text):
                response_parts.append(chunk)

            full_response = "".join(response_parts).strip()
            if not full_response:
                full_response = "[No response]"

            await self._message_repo.update_status(msg.id, MessageStatus.response_complete)
            await self._session_repo.update_status(session.id, SessionStatus.ready)

            await self._send_response(chat_id.value, full_response)

            await self._audit_repo.log(AuditEvent(
                event_type="message_handled",
                user_id=user_id,
                chat_id=chat_id,
                details=f"session={session.id.value} prompt_len={len(text)} response_len={len(full_response)}",
            ))

        except RuntimeUnavailableError as e:
            await self._message_repo.update_status(msg.id, MessageStatus.response_error, str(e))
            await self._session_repo.update_status(session.id, SessionStatus.failed, str(e))
            await self._telegram.send_message(
                chat_id.value,
                f"⚠️ OpenCode runtime error: {e.detail}",
            )

        except Exception as e:
            await self._message_repo.update_status(msg.id, MessageStatus.response_error, str(e))
            await self._session_repo.update_status(session.id, SessionStatus.failed, str(e))
            await self._telegram.send_message(
                chat_id.value,
                f"⚠️ Unexpected error: {e}",
            )

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

    async def _resolve_session(self, chat_id: ChatId) -> Session | None:
        binding = await self._binding_repo.get_active(chat_id)
        if binding is None:
            return None
        return await self._session_repo.get(binding.session_id)

    async def _create_session(self, chat_id: ChatId) -> Session:
        session = await self._runtime.create_session(
            workspace=self._default_workspace,
        )
        session.server = self._default_server
        await self._session_repo.save(session)
        binding = SessionBinding(chat_id=chat_id, session_id=session.id, is_active=True)
        await self._binding_repo.save(binding)
        return session

    async def _send_response(self, chat_id: int, text: str) -> None:
        formatted = format_as_html(text)
        parts = split_long_message(formatted, self._max_message_length)
        for part in parts:
            ok = await self._telegram.send_message(chat_id, part, parse_mode="HTML")
            if ok is None:
                ok = await self._telegram.send_message(chat_id, part)
            if ok is None:
                log.error("telegram_send_failed", chat_id=chat_id)
                raise TelegramSendError(f"Failed to send message to {chat_id}")
