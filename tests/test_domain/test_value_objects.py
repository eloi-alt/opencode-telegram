from __future__ import annotations

from opencode_telegram.domain.value_objects import (
    ChatId,
    CommandName,
    MessageDirection,
    MessageStatus,
    RuntimeMode,
    SessionId,
    SessionStatus,
    UserId,
)


def test_session_id_generate() -> None:
    sid1 = SessionId.generate()
    sid2 = SessionId.generate()
    assert sid1 != sid2
    assert len(sid1.value) > 0


def test_user_id() -> None:
    uid = UserId(12345)
    assert uid.value == 12345
    assert str(uid) == "12345"


def test_chat_id() -> None:
    cid = ChatId(-1001234567890)
    assert cid.value == -1001234567890


def test_session_status_values() -> None:
    assert SessionStatus.pending.value == "pending"
    assert SessionStatus.ready.value == "ready"
    assert SessionStatus.busy.value == "busy"
    assert SessionStatus.failed.value == "failed"


def test_message_status_enum() -> None:
    assert MessageStatus.webhook_received.value == "webhook_received"
    assert MessageStatus.response_complete.value == "response_complete"
    assert MessageStatus.telegram_send_failed.value == "telegram_send_failed"


def test_runtime_mode() -> None:
    assert RuntimeMode.api.value == "api"
    assert RuntimeMode.cli.value == "cli"


def test_command_name() -> None:
    assert CommandName.start.value == "start"
    assert CommandName.health.value == "health"
    assert CommandName.help.value == "help"


def test_message_direction() -> None:
    assert MessageDirection.incoming.value == "incoming"
    assert MessageDirection.outgoing.value == "outgoing"
