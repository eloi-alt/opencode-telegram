from __future__ import annotations

import httpx

from opencode_telegram.domain.ports import TelegramClient as TelegramClientPort
from opencode_telegram.domain.value_objects import ChatId
from opencode_telegram.infrastructure.logging import get_logger

log = get_logger("opencode_telegram.infrastructure.telegram.client")


class HttpxTelegramClient(TelegramClientPort):
    def __init__(self, bot_token: str, base_url: str = "https://api.telegram.org") -> None:
        self.token = bot_token
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(15.0))
        self._api_base = f"{base_url}/bot{bot_token}"

    async def _call(self, method: str, data: dict | None = None) -> dict | None:
        url = f"{self._api_base}/{method}"
        try:
            resp = await self._client.post(url, json=data or {})
            resp.raise_for_status()
            result = resp.json()
            if not result.get("ok"):
                log.warning("telegram_api_not_ok", method=method, description=result.get("description"))
                return None
            return result.get("result")
        except httpx.HTTPError as e:
            log.error("telegram_api_error", method=method, error=str(e))
            return None

    async def send_message(
        self,
        chat_id: ChatId | int,
        text: str,
        parse_mode: str | None = None,
        reply_markup: dict | None = None,
    ) -> dict | None:
        cid = chat_id.value if isinstance(chat_id, ChatId) else chat_id
        data: dict = {"chat_id": cid, "text": text}
        if parse_mode:
            data["parse_mode"] = parse_mode
        if reply_markup:
            data["reply_markup"] = reply_markup
        return await self._call("sendMessage", data)

    async def edit_message(
        self,
        chat_id: ChatId | int,
        message_id: int,
        text: str,
        parse_mode: str | None = None,
    ) -> dict | None:
        cid = chat_id.value if isinstance(chat_id, ChatId) else chat_id
        data: dict = {"chat_id": cid, "message_id": message_id, "text": text}
        if parse_mode:
            data["parse_mode"] = parse_mode
        return await self._call("editMessageText", data)

    async def send_typing(self, chat_id: ChatId | int) -> None:
        cid = chat_id.value if isinstance(chat_id, ChatId) else chat_id
        await self._call("sendChatAction", {"chat_id": cid, "action": "typing"})

    async def set_reaction(self, chat_id: ChatId | int, message_id: int, emoji: str) -> None:
        cid = chat_id.value if isinstance(chat_id, ChatId) else chat_id
        await self._call("setMessageReaction", {
            "chat_id": cid,
            "message_id": message_id,
            "reaction": [{"type": "emoji", "emoji": emoji}],
        })

    async def answer_callback(self, callback_query_id: str, text: str | None = None) -> None:
        data: dict = {"callback_query_id": callback_query_id}
        if text:
            data["text"] = text
        await self._call("answerCallbackQuery", data)

    async def set_commands(self, commands: list[dict]) -> None:
        await self._call("setMyCommands", {"commands": commands})

    async def get_webhook_info(self) -> dict | None:
        return await self._call("getWebhookInfo")

    async def close(self) -> None:
        await self._client.aclose()
