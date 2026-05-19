from __future__ import annotations

import os

import pytest

from opencode_telegram.shared.errors import CommandNotAllowedError, UnauthorizedError


def test_security_rate_limit() -> None:
    os.environ["TELEGRAM_BOT_TOKEN"] = "test:token"
    from opencode_telegram.infrastructure.config import AppConfig
    from opencode_telegram.infrastructure.security import SecurityService
    config = AppConfig()
    security = SecurityService(config)

    key = "test_key"
    for _ in range(10):
        security.rate_limit(key, max_calls=10, window=60.0)

    with pytest.raises(UnauthorizedError):
        security.rate_limit(key, max_calls=10, window=60.0)


def test_security_allowed_users() -> None:
    os.environ["TELEGRAM_BOT_TOKEN"] = "test:token"
    os.environ["TELEGRAM_ALLOWED_USERS"] = "123,456"
    from opencode_telegram.infrastructure.config import AppConfig
    from opencode_telegram.infrastructure.security import SecurityService
    config = AppConfig()
    security = SecurityService(config)

    security.check_user_allowed(123)
    security.check_user_allowed(456)

    with pytest.raises(UnauthorizedError):
        security.check_user_allowed(789)


def test_security_allowed_chats() -> None:
    os.environ["TELEGRAM_BOT_TOKEN"] = "test:token"
    os.environ["TELEGRAM_ALLOWED_CHATS"] = "-100123"
    from opencode_telegram.infrastructure.config import AppConfig
    from opencode_telegram.infrastructure.security import SecurityService
    config = AppConfig()
    security = SecurityService(config)

    security.check_chat_allowed(-100123)

    with pytest.raises(UnauthorizedError):
        security.check_chat_allowed(999)


def test_dangerous_commands_blocked() -> None:
    os.environ["TELEGRAM_BOT_TOKEN"] = "test:token"
    os.environ["ENABLE_DANGEROUS_COMMANDS"] = "false"
    from opencode_telegram.infrastructure.config import AppConfig
    from opencode_telegram.infrastructure.security import SecurityService
    config = AppConfig()
    security = SecurityService(config)

    with pytest.raises(CommandNotAllowedError):
        security.check_command_allowed("exec")

    with pytest.raises(CommandNotAllowedError):
        security.check_command_allowed("shell")

    security.check_command_allowed("status")
