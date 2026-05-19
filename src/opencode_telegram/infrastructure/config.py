from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Telegram
    TELEGRAM_BOT_TOKEN: str = Field(default="", validation_alias="TELEGRAM_BOT_TOKEN")
    TELEGRAM_WEBHOOK_SECRET: str = Field(default="")
    TELEGRAM_ALLOWED_USERS: str = Field(default="")
    TELEGRAM_ALLOWED_CHATS: str = Field(default="")

    # OpenCode Runtime
    OPENCODE_MODE: Literal["api", "cli"] = Field(default="cli")
    OPENCODE_BASE_URL: str = Field(default="")
    OPENCODE_API_KEY: str = Field(default="")
    OPENCODE_CLI_PATH: str = Field(default="opencode")
    OPENCODE_WORKSPACE_ROOT: str = Field(default=str(Path.home() / "opencode" / "workspaces"))
    OPENCODE_DEFAULT_WORKSPACE: str = Field(default="default")
    OPENCODE_DEFAULT_SERVER: str = Field(default="local")

    # Server
    PORT: int = Field(default=8080, ge=1, le=65535)
    APP_BASE_URL: str = Field(default="")

    # Logging
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(default="INFO")

    # Persistence
    DATABASE_URL: str = Field(default="sqlite+aiosqlite:///data/opencode-telegram.db")
    STORAGE_PATH: str = Field(default="./data")

    # Session
    SESSION_TIMEOUT_SEC: int = Field(default=1800, ge=60)
    MESSAGE_MAX_LENGTH: int = Field(default=4096, ge=256, le=65536)

    # Feature flags
    ENABLE_ADMIN_COMMANDS: bool = Field(default=True)
    ENABLE_DANGEROUS_COMMANDS: bool = Field(default=False)

    # Health
    HEALTHCHECK_INTERVAL_SEC: int = Field(default=60, ge=5)

    @field_validator("TELEGRAM_BOT_TOKEN")
    @classmethod
    def bot_token_required(cls, v: str) -> str:
        if not v:
            raise ValueError("TELEGRAM_BOT_TOKEN is required")
        return v

    @field_validator("STORAGE_PATH")
    @classmethod
    def resolve_storage_path(cls, v: str) -> str:
        p = Path(v)
        if not p.is_absolute():
            p = Path.cwd() / v
        p.mkdir(parents=True, exist_ok=True)
        return str(p.resolve())

    @property
    def allowed_users(self) -> list[int]:
        if not self.TELEGRAM_ALLOWED_USERS:
            return []
        return [int(u.strip()) for u in self.TELEGRAM_ALLOWED_USERS.split(",") if u.strip()]

    @property
    def allowed_chats(self) -> list[int]:
        if not self.TELEGRAM_ALLOWED_CHATS:
            return []
        return [int(c.strip()) for c in self.TELEGRAM_ALLOWED_CHATS.split(",") if c.strip()]

    @property
    def database_path(self) -> str:
        if self.DATABASE_URL.startswith("sqlite+aiosqlite:///"):
            path_part = self.DATABASE_URL[len("sqlite+aiosqlite:///"):]
            p = Path(path_part)
            if not p.is_absolute():
                p = Path(self.STORAGE_PATH) / path_part
            p.parent.mkdir(parents=True, exist_ok=True)
            return f"sqlite+aiosqlite:///{p.resolve()}"
        return self.DATABASE_URL
