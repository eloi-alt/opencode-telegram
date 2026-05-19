from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse

from opencode_telegram.app.di import Container
from opencode_telegram.infrastructure.config import AppConfig
from opencode_telegram.infrastructure.logging import get_logger, setup_logging
from opencode_telegram.infrastructure.telegram.formatting import format_as_html

log = get_logger("opencode_telegram.interfaces.http")


def create_app(config: AppConfig | None = None, container: Container | None = None) -> FastAPI:
    if config is None:
        config = AppConfig()
    setup_logging(config)

    own_container = container is None
    if container is None:
        container = Container(config)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> None:
        if own_container:
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
                {"command": "sync", "description": "Fetch session history from OpenCode"},
                {"command": "help", "description": "Show this help"},
            ]
            await container.telegram.set_commands(bot_commands)
        yield
        if own_container:
            await container.shutdown()

    app = FastAPI(
        title="OpenCode Telegram Bridge",
        version="0.2.0",
        lifespan=lifespan,
    )

    @app.get("/")
    async def root() -> PlainTextResponse:
        return PlainTextResponse("OpenCode Telegram Bridge")

    @app.get("/health")
    async def health() -> JSONResponse:
        health_data = await container.runtime.get_health()
        return JSONResponse({
            "status": "ok" if health_data.runtime_available else "degraded",
            "runtime": {
                "mode": health_data.runtime_mode,
                "available": health_data.runtime_available,
                "latency_ms": health_data.latency_ms,
            },
            "storage": health_data.storage_ok,
            "active_sessions": health_data.active_sessions,
            "errors": health_data.errors,
        })

    @app.get("/ready")
    async def ready() -> JSONResponse:
        return JSONResponse({"status": "ok"})

    @app.post("/webhook")
    async def telegram_webhook(request: Request) -> Response:
        body = await request.json()
        log.info("webhook_received", update_id=body.get("update_id"))

        if container.handle_message is None or container.handle_command is None:
            log.error("handlers_not_initialized")
            return Response("Service not ready", status_code=503)

        from opencode_telegram.interfaces.telegram.handlers import TelegramUpdateHandler

        handler = TelegramUpdateHandler(
            message_handler=container.handle_message,
            command_handler=container.handle_command,
            session_repo=container.session_repo,
            binding_repo=container.binding_repo,
            runtime=container.runtime,
            telegram=container.telegram,
            security=container.security,
        )
        await handler.handle(body)
        return Response("OK", status_code=200)

    @app.get("/metrics")
    async def metrics() -> PlainTextResponse:
        health_data = await container.runtime.get_health()
        lines = [
            f"# HELP opencode_telegram_runtime_available Runtime availability",
            f"# TYPE opencode_telegram_runtime_available gauge",
            f"opencode_telegram_runtime_available {1 if health_data.runtime_available else 0}",
            f"# HELP opencode_telegram_active_sessions Active sessions count",
            f"# TYPE opencode_telegram_active_sessions gauge",
            f"opencode_telegram_active_sessions {health_data.active_sessions}",
        ]
        return PlainTextResponse("\n".join(lines))

    return app
