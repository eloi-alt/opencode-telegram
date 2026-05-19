from __future__ import annotations

import argparse
import asyncio
import signal
import sys

import uvicorn

from opencode_telegram.infrastructure.config import AppConfig
from opencode_telegram.infrastructure.logging import get_logger

log = get_logger("opencode_telegram.__main__")


def run() -> None:
    parser = argparse.ArgumentParser(description="OpenCode Telegram Bridge")
    parser.add_argument(
        "--poll",
        action="store_true",
        help="Use polling (getUpdates) instead of webhook. No public URL needed.",
    )
    args = parser.parse_args()

    config = AppConfig()

    if args.poll:
        _run_polling(config)
    else:
        _run_webhook(config)


def _run_webhook(config: AppConfig) -> None:
    from opencode_telegram.interfaces.http import create_app
    app = create_app(config)
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=config.PORT,
        log_level=config.LOG_LEVEL.lower(),
    )


def _run_polling(config: AppConfig) -> None:
    from opencode_telegram.app.di import Container
    from opencode_telegram.infrastructure.telegram.poller import TelegramPoller
    from opencode_telegram.interfaces.http import create_app
    from opencode_telegram.interfaces.telegram.handlers import TelegramUpdateHandler

    async def main() -> None:
        container = Container(config)
        await container.init()

        bot_commands = [
            {"command": "start", "description": "Start and show system status"},
            {"command": "status", "description": "Show session status"},
            {"command": "new", "description": "Create a new session (e.g. /new my-project)"},
            {"command": "sessions", "description": "List active sessions"},
            {"command": "resume", "description": "Pick session to resume"},
            {"command": "clear", "description": "Clear current session"},
            {"command": "stop", "description": "Interrupt execution"},
            {"command": "health", "description": "Detailed diagnostics"},
            {"command": "logs", "description": "Recent events"},
            {"command": "help", "description": "Show this help"},
        ]
        await container.telegram.set_commands(bot_commands)

        if container.handle_message is None or container.handle_command is None:
            log.error("handlers_not_initialized")
            sys.exit(1)

        handler = TelegramUpdateHandler(
            message_handler=container.handle_message,
            command_handler=container.handle_command,
            session_repo=container.session_repo,
            binding_repo=container.binding_repo,
            runtime=container.runtime,
            telegram=container.telegram,
            security=container.security,
        )

        poller = TelegramPoller(container.telegram, handler, poll_interval=1.0)

        app = create_app(config, container=container)

        stop_event = asyncio.Event()

        def _signal_handler() -> None:
            log.info("shutdown_signal_received")
            stop_event.set()

        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, _signal_handler)
            except NotImplementedError:
                pass

        log.info("polling_mode_enabled")
        poll_task = asyncio.create_task(poller.start())

        http_config = uvicorn.Config(
            app,
            host="0.0.0.0",
            port=config.PORT,
            log_level=config.LOG_LEVEL.lower(),
        )
        http_server = uvicorn.Server(http_config)
        http_task = asyncio.create_task(http_server.serve())

        done, pending = await asyncio.wait(
            [poll_task, http_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in pending:
            task.cancel()

        await poller.stop()
        await container.shutdown()
        log.info("shutdown_complete")

    asyncio.run(main())


if __name__ == "__main__":
    run()
