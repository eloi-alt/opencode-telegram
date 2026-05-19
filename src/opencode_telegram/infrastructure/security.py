from __future__ import annotations

import time
from collections.abc import Callable
from functools import wraps
from typing import Any

from opencode_telegram.domain.value_objects import ChatId, UserId
from opencode_telegram.infrastructure.config import AppConfig
from opencode_telegram.shared.errors import CommandNotAllowedError, UnauthorizedError


class SecurityService:
    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._rate_limit_store: dict[str, list[float]] = {}

    def check_user_allowed(self, user_id: UserId | int) -> None:
        uid = user_id.value if isinstance(user_id, UserId) else user_id
        allowed = self._config.allowed_users
        if allowed and uid not in allowed:
            raise UnauthorizedError(f"User {uid} is not allowed")

    def check_chat_allowed(self, chat_id: ChatId | int) -> None:
        cid = chat_id.value if isinstance(chat_id, ChatId) else chat_id
        allowed = self._config.allowed_chats
        if allowed and cid not in allowed:
            raise UnauthorizedError(f"Chat {cid} is not allowed")

    def check_admin(self, user_id: UserId | int) -> None:
        if not self._config.ENABLE_ADMIN_COMMANDS:
            raise CommandNotAllowedError("admin commands")
        uid = user_id.value if isinstance(user_id, UserId) else user_id
        allowed = self._config.allowed_users
        if allowed and uid not in allowed:
            raise UnauthorizedError(f"User {uid} is not admin")

    def check_command_allowed(self, command: str) -> None:
        dangerous = {"exec", "shell", "bash", "sh", "run", "sudo"}
        if not self._config.ENABLE_DANGEROUS_COMMANDS and command.lower() in dangerous:
            raise CommandNotAllowedError(command)

    def rate_limit(self, key: str, max_calls: int = 10, window: float = 60.0) -> None:
        now = time.time()
        self._rate_limit_store.setdefault(key, [])
        self._rate_limit_store[key] = [t for t in self._rate_limit_store[key] if now - t < window]
        if len(self._rate_limit_store[key]) >= max_calls:
            raise UnauthorizedError(f"Rate limit exceeded for {key}")
        self._rate_limit_store[key].append(now)


def require_auth(security: SecurityService) -> Callable:
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(update: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
            user = update.get("message", {}).get("from", {})
            chat = update.get("message", {}).get("chat", {})
            user_id = user.get("id")
            chat_id = chat.get("id")
            if user_id:
                security.check_user_allowed(user_id)
            if chat_id:
                security.check_chat_allowed(chat_id)
            return await func(update, *args, **kwargs)
        return wrapper
    return decorator
