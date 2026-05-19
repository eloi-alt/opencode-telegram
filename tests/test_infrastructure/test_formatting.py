from __future__ import annotations

from opencode_telegram.infrastructure.telegram.formatting import (
    escape_html,
    format_as_html,
    render_help_text,
    render_status_card,
    split_long_message,
)


def test_escape_html() -> None:
    assert escape_html("<b>bold</b>") == "&lt;b&gt;bold&lt;/b&gt;"
    assert escape_html("a & b") == "a &amp; b"
    assert escape_html("plain text") == "plain text"


def test_format_as_html_bold() -> None:
    result = format_as_html("**bold text**")
    assert "<b>bold text</b>" in result


def test_format_as_html_italic() -> None:
    result = format_as_html("*italic*")
    assert "<i>italic</i>" in result


def test_format_as_html_code_block() -> None:
    result = format_as_html("```python\nprint('hello')\n```")
    assert "<pre><code class='language-python'>print('hello')</code></pre>" in result or "<pre>" in result


def test_format_as_html_inline_code() -> None:
    result = format_as_html("Use `code` here")
    assert "<code>code</code>" in result


def test_split_long_message_short() -> None:
    parts = split_long_message("short text", max_length=100)
    assert parts == ["short text"]


def test_split_long_message_long() -> None:
    text = "word " * 1000
    parts = split_long_message(text, max_length=100)
    assert len(parts) > 1
    assert all(len(p) <= 100 for p in parts)


def test_render_status_card_with_session() -> None:
    from opencode_telegram.domain.entities import Session
    from opencode_telegram.domain.value_objects import SessionId, SessionStatus
    session = Session(id=SessionId.generate(), status=SessionStatus.ready)
    card = render_status_card(session=session, server="local", workspace="default", uptime="5m ago", error=None)
    assert "System Status" in card
    assert "ready" in card
    assert "local" in card
    assert "default" in card


def test_render_status_card_without_session() -> None:
    card = render_status_card(session=None, server=None, workspace=None, uptime=None, error="Something broke")
    assert "none" in card
    assert "Something broke" in card


def test_render_help_text() -> None:
    text = render_help_text(has_admin=True)
    assert "OpenCode" in text
    assert "/status" in text
    assert "Admin" in text

    text_no_admin = render_help_text(has_admin=False)
    assert "Admin" not in text_no_admin


def test_escape_in_format_as_html() -> None:
    result = format_as_html("**a < b**")
    assert "&lt;" in result
    assert "<b>" in result
