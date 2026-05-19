from __future__ import annotations

from datetime import datetime

from opencode_telegram.domain.entities import (
    AuditEvent,
    Chat,
    Message,
    Session,
    SessionBinding,
    User,
)
from opencode_telegram.domain.value_objects import (
    ChatId,
    MessageDirection,
    MessageId,
    MessageStatus,
    SessionId,
    SessionStatus,
    UserId,
)


def test_user_creation() -> None:
    uid = UserId(123)
    user = User(id=uid, username="testuser", first_name="Test")
    assert user.id.value == 123
    assert user.username == "testuser"
    assert user.is_admin is False


def test_session_status_transitions() -> None:
    sid = SessionId.generate()
    session = Session(id=sid, status=SessionStatus.pending)
    assert session.status == SessionStatus.pending
    session.status = SessionStatus.ready
    assert session.status == SessionStatus.ready
    session.status = SessionStatus.busy
    assert session.status == SessionStatus.busy


def test_message_creation() -> None:
    mid = MessageId.generate()
    cid = ChatId(1)
    sid = SessionId.generate()
    msg = Message(
        id=mid,
        chat_id=cid,
        session_id=sid,
        direction=MessageDirection.incoming,
        content="hello",
        status=MessageStatus.webhook_received,
    )
    assert msg.direction == MessageDirection.incoming
    assert msg.status == MessageStatus.webhook_received


def test_session_binding() -> None:
    cid = ChatId(42)
    sid = SessionId.generate()
    binding = SessionBinding(chat_id=cid, session_id=sid)
    assert binding.is_active is True
    assert binding.chat_id.value == 42


def test_audit_event() -> None:
    event = AuditEvent(
        event_type="test_event",
        user_id=UserId(1),
        chat_id=ChatId(2),
        details="test details",
    )
    assert event.event_type == "test_event"
    assert isinstance(event.timestamp, datetime)


def test_chat_creation() -> None:
    chat = Chat(id=ChatId(1), type="private", title="Test Chat")
    assert chat.type == "private"
    assert chat.title == "Test Chat"


def test_session_defaults() -> None:
    sid = SessionId.generate()
    session = Session(id=sid)
    assert session.status == SessionStatus.pending
    assert session.workspace is None
    assert session.error_message is None
