from __future__ import annotations

import re

from opencode_telegram.domain.entities import Session
from opencode_telegram.domain.value_objects import SessionStatus


def escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def format_as_html(text: str) -> str:
    text = escape_html(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", text)
    text = re.sub(
        r"```(\w*)\n?(.*?)```",
        lambda m: f"<pre><code class='language-{m.group(1)}'>{escape_html(m.group(2).strip())}</code></pre>"
        if m.group(1)
        else f"<pre>{escape_html(m.group(2).strip())}</pre>",
        text,
        flags=re.DOTALL,
    )
    text = re.sub(r"`([^`\n]+)`", lambda m: f"<code>{escape_html(m.group(1))}</code>", text)
    return text


def split_long_message(text: str, max_length: int = 4096) -> list[str]:
    if len(text) <= max_length:
        return [text]
    parts: list[str] = []
    while len(text) > max_length:
        split_at = text.rfind("\n", 0, max_length)
        if split_at == -1:
            split_at = text.rfind(" ", 0, max_length)
        if split_at == -1:
            split_at = max_length
        parts.append(text[:split_at])
        text = text[split_at:].lstrip()
    if text:
        parts.append(text)
    return parts


def render_status_card(
    session: Session | None,
    server: str | None,
    workspace: str | None,
    uptime: str | None,
    error: str | None,
) -> str:
    lines = ["<b>System Status</b>\n"]
    if session:
        status_emoji = {
            SessionStatus.ready: "✅",
            SessionStatus.busy: "⚡",
            SessionStatus.streaming: "📡",
            SessionStatus.idle: "💤",
            SessionStatus.failed: "❌",
            SessionStatus.stopped: "⏹️",
            SessionStatus.pending: "⏳",
            SessionStatus.starting: "🚀",
            SessionStatus.archived: "📦",
        }.get(session.status, "❓")
        label = f"<b>{session.name}</b>" if session.name else f"<code>{session.id.value[:12]}...</code>"
        lines.append(f"Session: {status_emoji} {label} ({session.status.value})")
        lines.append(f"Session ID: <code>{session.id.value[:12]}...</code>")
    else:
        lines.append("Session: ⚪ <b>none</b>")
    if server:
        lines.append(f"Server: <b>{server}</b>")
    if workspace:
        lines.append(f"Workspace: <b>{workspace}</b>")
    if uptime:
        lines.append(f"Last activity: {uptime}")
    if error:
        lines.append(f"\n⚠️ <b>Error:</b> {escape_html(error)}")
    return "\n".join(lines)


def render_help_text(has_admin: bool) -> str:
    lines = [
        "<b>OpenCode Telegram Bridge</b>\n",
        "Send any message to chat with OpenCode.",
        "Commands:",
        "  /status — show session status",
        "  /new <name> — create a new session with an optional name",
        "  /sync — fetch session history from OpenCode",
        "  /sessions — list active sessions",
        "  /resume — pick a session to resume",
        "  /clear — clear current session context",
        "  /stop — interrupt running execution",
        "  /help — this message",
    ]
    if has_admin:
        lines.extend([
            "",
            "<b>Admin commands:</b>",
            "  /health — detailed diagnostics",
            "  /logs — recent events",
            "  /bind — bind a workspace",
        ])
    lines.extend([
        "",
        "<i>Responses are formatted with HTML.</i>",
    ])
    return "\n".join(lines)
