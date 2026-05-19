from __future__ import annotations

import os

from opencode_telegram.app.usecases import HandleCommandUseCase, HandleMessageUseCase
from opencode_telegram.domain.ports import TelegramClient
from opencode_telegram.infrastructure.config import AppConfig
from opencode_telegram.infrastructure.logging import get_logger
from opencode_telegram.infrastructure.opencode import (
    FakeOpenCodeAdapter,
    OpenCodeApiAdapter,
    OpenCodeCliAdapter,
    OpenCodeRuntime,
)
from opencode_telegram.infrastructure.persistence.database import Database
from opencode_telegram.infrastructure.persistence.sqlite_repository import (
    SqliteAuditRepository,
    SqliteChatRepository,
    SqliteMessageRepository,
    SqliteServerProfileRepository,
    SqliteSessionBindingRepository,
    SqliteSessionRepository,
    SqliteUserRepository,
    SqliteWorkspaceTargetRepository,
)
from opencode_telegram.infrastructure.security import SecurityService
from opencode_telegram.infrastructure.telegram.client import HttpxTelegramClient

log = get_logger("opencode_telegram.app.di")


class Container:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.db = Database(config.database_path)

        self.telegram: TelegramClient = HttpxTelegramClient(config.TELEGRAM_BOT_TOKEN)
        self.security = SecurityService(config)
        self.runtime: OpenCodeRuntime = self._create_runtime()

        self.user_repo = SqliteUserRepository.__new__(SqliteUserRepository)
        self.chat_repo = SqliteChatRepository.__new__(SqliteChatRepository)
        self.session_repo = SqliteSessionRepository.__new__(SqliteSessionRepository)
        self.binding_repo = SqliteSessionBindingRepository.__new__(SqliteSessionBindingRepository)
        self.message_repo = SqliteMessageRepository.__new__(SqliteMessageRepository)
        self.audit_repo = SqliteAuditRepository.__new__(SqliteAuditRepository)
        self.server_profile_repo = SqliteServerProfileRepository.__new__(SqliteServerProfileRepository)
        self.workspace_repo = SqliteWorkspaceTargetRepository.__new__(SqliteWorkspaceTargetRepository)

        self.handle_message: HandleMessageUseCase | None = None
        self.handle_command: HandleCommandUseCase | None = None

    def _create_runtime(self) -> OpenCodeRuntime:
        if os.environ.get("FAKE_RUNTIME", "").lower() in ("1", "true", "yes"):
            log.info("using_fake_runtime")
            return FakeOpenCodeAdapter()

        mode = self.config.OPENCODE_MODE
        if mode == "api":
            if not self.config.OPENCODE_BASE_URL:
                log.warning("OPENCODE_MODE=api but OPENCODE_BASE_URL not set, falling back to CLI")
                return self._create_cli_runtime()
            return OpenCodeApiAdapter(
                base_url=self.config.OPENCODE_BASE_URL,
                api_key=self.config.OPENCODE_API_KEY or None,
            )
        return self._create_cli_runtime()

    def _create_cli_runtime(self) -> OpenCodeRuntime:
        return OpenCodeCliAdapter(
            cli_path=self.config.OPENCODE_CLI_PATH,
            workspace_root=self.config.OPENCODE_WORKSPACE_ROOT,
            default_workspace=self.config.OPENCODE_DEFAULT_WORKSPACE,
        )

    async def init(self) -> None:
        conn = await self.db.connect()
        self.user_repo = SqliteUserRepository(conn)
        self.chat_repo = SqliteChatRepository(conn)
        self.session_repo = SqliteSessionRepository(conn)
        self.binding_repo = SqliteSessionBindingRepository(conn)
        self.message_repo = SqliteMessageRepository(conn)
        self.audit_repo = SqliteAuditRepository(conn)
        self.server_profile_repo = SqliteServerProfileRepository(conn)
        self.workspace_repo = SqliteWorkspaceTargetRepository(conn)

        cap = await self.runtime.get_capabilities()

        self.handle_message = HandleMessageUseCase(
            user_repo=self.user_repo,
            chat_repo=self.chat_repo,
            session_repo=self.session_repo,
            binding_repo=self.binding_repo,
            message_repo=self.message_repo,
            audit_repo=self.audit_repo,
            runtime=self.runtime,
            telegram=self.telegram,
            default_workspace=self.config.OPENCODE_DEFAULT_WORKSPACE,
            default_server=self.config.OPENCODE_DEFAULT_SERVER,
            max_message_length=self.config.MESSAGE_MAX_LENGTH,
        )
        self.handle_command = HandleCommandUseCase(
            user_repo=self.user_repo,
            chat_repo=self.chat_repo,
            session_repo=self.session_repo,
            binding_repo=self.binding_repo,
            message_repo=self.message_repo,
            audit_repo=self.audit_repo,
            runtime=self.runtime,
            telegram=self.telegram,
            security=self.security,
            default_workspace=self.config.OPENCODE_DEFAULT_WORKSPACE,
            default_server=self.config.OPENCODE_DEFAULT_SERVER,
            capabilities=cap,
            max_message_length=self.config.MESSAGE_MAX_LENGTH,
        )

        log.info("container_initialized")

    async def shutdown(self) -> None:
        await self.runtime.close()
        await self.db.close()
        if hasattr(self.telegram, "close"):
            await self.telegram.close()
        log.info("container_shutdown")
