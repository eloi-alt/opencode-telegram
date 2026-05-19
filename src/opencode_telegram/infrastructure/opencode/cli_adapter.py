from __future__ import annotations

import asyncio
import json
import shlex
from collections.abc import AsyncIterator
from datetime import datetime
from pathlib import Path

from opencode_telegram.domain.entities import Session
from opencode_telegram.domain.value_objects import (
    HealthStatus,
    RuntimeCapabilities,
    SessionId,
    SessionStatus,
)
from opencode_telegram.infrastructure.logging import get_logger
from opencode_telegram.infrastructure.opencode.base import OpenCodeRuntime
from opencode_telegram.shared.errors import RuntimeUnavailableError

log = get_logger("opencode_telegram.infrastructure.opencode.cli")


class OpenCodeCliAdapter(OpenCodeRuntime):
    def __init__(
        self,
        cli_path: str = "opencode",
        workspace_root: str = "",
        default_workspace: str = "default",
    ) -> None:
        self._cli_path = cli_path
        self._workspace_root = Path(workspace_root).resolve() if workspace_root else Path.cwd()
        self._default_workspace = default_workspace
        self._session_id: str | None = None
        self._has_sent: bool = False

    def _workspace_dir(self, workspace: str | None = None) -> Path:
        ws = workspace or self._default_workspace
        path = self._workspace_root / ws
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _build_cmd(self, prompt: str, workspace: str | None, continue_session: bool = False) -> list[str]:
        ws_dir = self._workspace_dir(workspace)
        cmd = [
            self._cli_path,
            "run",
            prompt,
            "--dangerously-skip-permissions",
            "--format", "json",
            "--dir", str(ws_dir),
        ]
        if continue_session:
            cmd.append("--continue")
        return cmd

    async def _run_opencode(self, prompt: str, workspace: str | None, continue_session: bool = False) -> str:
        cmd = self._build_cmd(prompt, workspace, continue_session)
        log.info("cli_running_cmd", prompt_len=len(prompt), workspace=workspace, continue_session=continue_session)
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300.0)
        except asyncio.TimeoutError:
            raise RuntimeUnavailableError("OpenCode CLI timed out (300s)")
        except FileNotFoundError:
            raise RuntimeUnavailableError(f"OpenCode CLI not found at '{self._cli_path}'")

        if proc.returncode != 0:
            err = stderr.decode("utf-8", errors="replace")[:500]
            log.warning("cli_nonzero_exit", returncode=proc.returncode, stderr=err)
            raise RuntimeUnavailableError(f"OpenCode CLI exited with code {proc.returncode}: {err}")

        output = stdout.decode("utf-8", errors="replace")
        self._has_sent = True
        self._extract_session_id(output)
        return self._extract_response(output)

    def _extract_session_id(self, raw_output: str) -> None:
        for line in raw_output.strip().split("\n"):
            line = line.strip()
            if not line or not line.startswith("{"):
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("type") == "step_start":
                sid = event.get("sessionID")
                if sid:
                    self._session_id = sid
                    log.info("cli_session_detected", session_id=sid)

    def _extract_response(self, raw_output: str) -> str:
        texts: list[str] = []
        for line in raw_output.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            if not line.startswith("{"):
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            msg_type = event.get("type", "")
            if msg_type == "text":
                part = event.get("part", {})
                if isinstance(part, dict) and part.get("type") == "text":
                    text = part.get("text", "")
                    if text:
                        texts.append(text)
            elif msg_type in ("assistant_message",):
                content = event.get("content", "")
                if content:
                    texts.append(content)
            elif msg_type == "error":
                raise RuntimeUnavailableError(event.get("content", "Unknown OpenCode error"))

        result = "\n".join(texts).strip()
        return result if result else "(no response)"

    async def create_session(
        self, workspace: str | None = None, project: str | None = None
    ) -> Session:
        sid = f"oc-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        self._session_id = sid
        self._has_sent = False
        now = datetime.utcnow()
        log.info("cli_session_created", session_id=sid, workspace=workspace or self._default_workspace)
        return Session(
            id=SessionId(sid),
            status=SessionStatus.ready,
            workspace=workspace or self._default_workspace,
            project=project,
            server="cli",
            created_at=now,
            updated_at=now,
            last_activity=now,
        )

    async def resume_session(self, session_id: str | SessionId) -> Session:
        self._session_id = str(session_id)
        self._has_sent = True
        now = datetime.utcnow()
        return Session(
            id=SessionId(str(session_id)),
            status=SessionStatus.ready,
            server="cli",
            created_at=now,
            updated_at=now,
            last_activity=now,
        )

    async def get_session(self, session_id: str | SessionId) -> Session | None:
        sid = str(session_id)
        if self._session_id and self._session_id != sid:
            return None
        now = datetime.utcnow()
        return Session(
            id=SessionId(sid),
            status=SessionStatus.ready,
            server="cli",
            created_at=now,
            updated_at=now,
            last_activity=now,
        )

    async def list_sessions(self, limit: int = 10) -> list[Session]:
        if self._session_id:
            now = datetime.utcnow()
            return [Session(
                id=SessionId(self._session_id),
                status=SessionStatus.ready,
                server="cli",
                created_at=now,
                updated_at=now,
                last_activity=now,
            )]
        return []

    async def send_prompt(self, session_id: str | SessionId, prompt: str) -> AsyncIterator[str]:
        try:
            response = await self._run_opencode(
                prompt=prompt,
                workspace=self._default_workspace,
                continue_session=self._has_sent,
            )
            yield response
        except RuntimeUnavailableError:
            raise
        except Exception as e:
            raise RuntimeUnavailableError(f"CLI prompt failed: {e}") from e

    async def stop_session(self, session_id: str | SessionId) -> None:
        log.info("cli_session_stopped", session_id=str(session_id))

    async def clear_session(self, session_id: str | SessionId) -> None:
        self._has_sent = False
        log.info("cli_session_cleared", session_id=str(session_id))

    async def get_health(self) -> HealthStatus:
        try:
            cmd = shlex.split(self._cli_path) + ["--version"]
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.communicate(), timeout=5.0)
            available = proc.returncode == 0
        except Exception:
            available = False

        return HealthStatus(
            telegram_webhook=True,
            runtime_available=available,
            runtime_mode="cli",
            latency_ms=None,
            storage_ok=True,
            active_sessions=1 if self._session_id else 0,
            errors=[] if available else [f"OpenCode CLI not found at '{self._cli_path}'"],
        )

    async def get_capabilities(self) -> RuntimeCapabilities:
        return RuntimeCapabilities(
            supports_streaming=False,
            supports_sessions=True,
            supports_stop=False,
            supports_projects=True,
            supports_workspaces=True,
            max_prompt_length=100000,
            available_commands=["start", "status", "sessions", "resume", "clear", "stop", "help"],
        )

    async def close(self) -> None:
        self._session_id = None
        self._has_sent = False
        log.info("cli_adapter_closed")
