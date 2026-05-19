from __future__ import annotations

import pytest

from opencode_telegram.app.usecases import HandleMessageUseCase
from opencode_telegram.domain.value_objects import SessionStatus


@pytest.mark.asyncio
async def test_handle_message_creates_session(
    user_repo, chat_repo, session_repo, binding_repo, message_repo, audit_repo,
    runtime, telegram, config,
) -> None:
    usecase = HandleMessageUseCase(
        user_repo=user_repo,
        chat_repo=chat_repo,
        session_repo=session_repo,
        binding_repo=binding_repo,
        message_repo=message_repo,
        audit_repo=audit_repo,
        runtime=runtime,
        telegram=telegram,
        default_workspace=config.OPENCODE_DEFAULT_WORKSPACE,
        default_server=config.OPENCODE_DEFAULT_SERVER,
        max_message_length=config.MESSAGE_MAX_LENGTH,
    )

    update = {
        "message": {
            "text": "Hello OpenCode",
            "chat": {"id": 123, "type": "private"},
            "from": {"id": 456, "username": "testuser", "first_name": "Test"},
            "message_id": 1,
        }
    }

    await usecase.execute(update)

    sessions = await session_repo.list_active()
    assert len(sessions) == 1
    assert sessions[0].status in (SessionStatus.ready, SessionStatus.busy)

    assert len(telegram.sent_messages) >= 1


@pytest.mark.asyncio
async def test_handle_message_reuses_session(
    user_repo, chat_repo, session_repo, binding_repo, message_repo, audit_repo,
    runtime, telegram, config,
) -> None:
    usecase = HandleMessageUseCase(
        user_repo=user_repo,
        chat_repo=chat_repo,
        session_repo=session_repo,
        binding_repo=binding_repo,
        message_repo=message_repo,
        audit_repo=audit_repo,
        runtime=runtime,
        telegram=telegram,
        default_workspace=config.OPENCODE_DEFAULT_WORKSPACE,
        default_server=config.OPENCODE_DEFAULT_SERVER,
        max_message_length=config.MESSAGE_MAX_LENGTH,
    )

    update1 = {
        "message": {
            "text": "First message",
            "chat": {"id": 123, "type": "private"},
            "from": {"id": 456, "username": "testuser", "first_name": "Test"},
            "message_id": 1,
        }
    }
    await usecase.execute(update1)

    update2 = {
        "message": {
            "text": "Second message",
            "chat": {"id": 123, "type": "private"},
            "from": {"id": 456, "username": "testuser", "first_name": "Test"},
            "message_id": 2,
        }
    }
    await usecase.execute(update2)

    sessions = await session_repo.list_active()
    assert len(sessions) >= 1
    assert len(telegram.sent_messages) >= 2


@pytest.mark.asyncio
async def test_handle_message_with_runtime_error(
    user_repo, chat_repo, session_repo, binding_repo, message_repo, audit_repo,
    runtime, telegram, config,
) -> None:
    runtime.set_fail_on_prompt(True)

    usecase = HandleMessageUseCase(
        user_repo=user_repo,
        chat_repo=chat_repo,
        session_repo=session_repo,
        binding_repo=binding_repo,
        message_repo=message_repo,
        audit_repo=audit_repo,
        runtime=runtime,
        telegram=telegram,
        default_workspace=config.OPENCODE_DEFAULT_WORKSPACE,
        default_server=config.OPENCODE_DEFAULT_SERVER,
        max_message_length=config.MESSAGE_MAX_LENGTH,
    )

    update = {
        "message": {
            "text": "Trigger error",
            "chat": {"id": 123, "type": "private"},
            "from": {"id": 456, "username": "testuser", "first_name": "Test"},
            "message_id": 1,
        }
    }

    await usecase.execute(update)

    error_msgs = [m for m in telegram.sent_messages if "error" in m["text"].lower()]
    assert len(error_msgs) >= 1


@pytest.mark.asyncio
async def test_ignores_command_messages(
    user_repo, chat_repo, session_repo, binding_repo, message_repo, audit_repo,
    runtime, telegram, config,
) -> None:
    usecase = HandleMessageUseCase(
        user_repo=user_repo,
        chat_repo=chat_repo,
        session_repo=session_repo,
        binding_repo=binding_repo,
        message_repo=message_repo,
        audit_repo=audit_repo,
        runtime=runtime,
        telegram=telegram,
        default_workspace=config.OPENCODE_DEFAULT_WORKSPACE,
        default_server=config.OPENCODE_DEFAULT_SERVER,
        max_message_length=config.MESSAGE_MAX_LENGTH,
    )

    update = {
        "message": {
            "text": "/status",
            "chat": {"id": 123, "type": "private"},
            "from": {"id": 456, "username": "testuser", "first_name": "Test"},
            "message_id": 1,
        }
    }

    await usecase.execute(update)
    assert len(telegram.sent_messages) == 0
