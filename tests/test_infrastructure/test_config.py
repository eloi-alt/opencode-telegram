from __future__ import annotations

import os

import pytest


def test_config_requires_bot_token() -> None:
    from opencode_telegram.infrastructure.config import AppConfig
    if "TELEGRAM_BOT_TOKEN" in os.environ:
        del os.environ["TELEGRAM_BOT_TOKEN"]
    with pytest.raises(ValueError):
        AppConfig()


def test_config_parses_allowed_users() -> None:
    os.environ["TELEGRAM_BOT_TOKEN"] = "test:token"
    os.environ["TELEGRAM_ALLOWED_USERS"] = "123,456,789"
    from opencode_telegram.infrastructure.config import AppConfig
    config = AppConfig()
    assert config.allowed_users == [123, 456, 789]


def test_config_parses_empty_allowed_users() -> None:
    os.environ["TELEGRAM_BOT_TOKEN"] = "test:token"
    os.environ["TELEGRAM_ALLOWED_USERS"] = ""
    from opencode_telegram.infrastructure.config import AppConfig
    config = AppConfig()
    assert config.allowed_users == []


def test_config_parses_allowed_chats() -> None:
    os.environ["TELEGRAM_BOT_TOKEN"] = "test:token"
    os.environ["TELEGRAM_ALLOWED_CHATS"] = "-100123,-456"
    from opencode_telegram.infrastructure.config import AppConfig
    config = AppConfig()
    assert config.allowed_chats == [-100123, -456]


def test_config_defaults() -> None:
    os.environ["TELEGRAM_BOT_TOKEN"] = "test:token"
    from opencode_telegram.infrastructure.config import AppConfig
    config = AppConfig()
    assert config.PORT == 8080
    assert config.OPENCODE_MODE == "cli"
    assert config.LOG_LEVEL == "INFO"
    assert config.ENABLE_ADMIN_COMMANDS is True
    assert config.ENABLE_DANGEROUS_COMMANDS is False


def test_config_database_path_resolution() -> None:
    os.environ["TELEGRAM_BOT_TOKEN"] = "test:token"
    from opencode_telegram.infrastructure.config import AppConfig
    config = AppConfig()
    path = config.database_path
    assert path.startswith("sqlite+aiosqlite:///")
