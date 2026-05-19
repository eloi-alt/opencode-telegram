from __future__ import annotations

from opencode_telegram.app.usecases import HandleCommandUseCase, HandleMessageUseCase
from opencode_telegram.domain.ports import (
    SessionBindingRepository,
    SessionRepository,
    TelegramClient,
)
from opencode_telegram.domain.value_objects import ChatId, SessionId, SessionStatus
from opencode_telegram.infrastructure.logging import get_logger
from opencode_telegram.infrastructure.opencode.base import OpenCodeRuntime
from opencode_telegram.infrastructure.security import SecurityService
from opencode_telegram.infrastructure.telegram.formatting import format_as_html

log = get_logger("opencode_telegram.interfaces.telegram.handlers")


class TelegramUpdateHandler:
    def __init__(
        self,
        message_handler: HandleMessageUseCase,
        command_handler: HandleCommandUseCase,
        session_repo: SessionRepository,
        binding_repo: SessionBindingRepository,
        runtime: OpenCodeRuntime,
        telegram: TelegramClient,
        security: SecurityService,
    ) -> None:
        self._message_handler = message_handler
        self._command_handler = command_handler
        self._session_repo = session_repo
        self._binding_repo = binding_repo
        self._runtime = runtime
        self._telegram = telegram
        self._security = security

    async def handle(self, update: dict) -> None:
        try:
            if "callback_query" in update:
                await self._handle_callback(update["callback_query"])
            elif "message" in update:
                await self._handle_message(update)
        except Exception as e:
            log.error("unhandled_update_error", error=str(e))

    async def _handle_message(self, update: dict) -> None:
        text = update.get("message", {}).get("text", "")
        if text.startswith("/"):
            await self._command_handler.execute(update)
        else:
            await self._message_handler.execute(update)

    async def _handle_callback(self, callback: dict) -> None:
        data = callback.get("data", "")
        chat_id = ChatId(callback.get("message", {}).get("chat", {}).get("id", 0))
        cb_id = callback.get("id", "")
        msg_id = callback.get("message", {}).get("message_id")
        user_id_data = callback.get("from", {})

        await self._telegram.answer_callback(cb_id)

        if data.startswith("resume:"):
            session_id = SessionId(data.split(":", 1)[1])
            session = await self._session_repo.get(session_id)
            if session is None:
                await self._telegram.send_message(chat_id.value, "Session not found.")
                return

            await self._binding_repo.set_active(chat_id, session_id)
            await self._session_repo.update_status(session_id, SessionStatus.ready)
            await self._telegram.edit_message(
                chat_id.value,
                msg_id,
                f"Resumed: <code>{session_id.value[:12]}...</code>",
                parse_mode="HTML",
            )

            lines = [
                "<b>Session Resumed</b>\n",
                f"Session: <code>{session_id.value[:12]}...</code>",
                f"Workspace: <b>{session.workspace or '-'}</b>",
                f"Server: <b>{session.server or '-'}</b>",
                "\nSend a message to continue.",
            ]
            await self._telegram.send_message(chat_id.value, "\n".join(lines), parse_mode="HTML")
