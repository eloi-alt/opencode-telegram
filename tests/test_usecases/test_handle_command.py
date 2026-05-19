from __future__ import annotations

import pytest

from opencode_telegram.app.usecases import HandleCommandUseCase
from opencode_telegram.domain.value_objects import SessionStatus


@pytest.mark.asyncio
async def test_status_command(
    user_repo, chat_repo, session_repo, binding_repo, message_repo, audit_repo,
    runtime, telegram, security, config,
) -> None:
    capabilities = await runtime.get_capabilities()
    usecase = HandleCommandUseCase(
        user_repo=user_repo,
        chat_repo=chat_repo,
        session_repo=session_repo,
        binding_repo=binding_repo,
        message_repo=message_repo,
        audit_repo=audit_repo,
        runtime=runtime,
        telegram=telegram,
        security=security,
        default_workspace=config.OPENCODE_DEFAULT_WORKSPACE,
        default_server=config.OPENCODE_DEFAULT_SERVER,
        capabilities=capabilities,
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
    assert len(telegram.sent_messages) >= 1


@pytest.mark.asyncio
async def test_help_command(
    user_repo, chat_repo, session_repo, binding_repo, message_repo, audit_repo,
    runtime, telegram, security, config,
) -> None:
    capabilities = await runtime.get_capabilities()
    usecase = HandleCommandUseCase(
        user_repo=user_repo,
        chat_repo=chat_repo,
        session_repo=session_repo,
        binding_repo=binding_repo,
        message_repo=message_repo,
        audit_repo=audit_repo,
        runtime=runtime,
        telegram=telegram,
        security=security,
        default_workspace=config.OPENCODE_DEFAULT_WORKSPACE,
        default_server=config.OPENCODE_DEFAULT_SERVER,
        capabilities=capabilities,
    )

    update = {
        "message": {
            "text": "/help",
            "chat": {"id": 123, "type": "private"},
            "from": {"id": 456, "username": "testuser", "first_name": "Test"},
            "message_id": 1,
        }
    }

    await usecase.execute(update)
    assert len(telegram.sent_messages) >= 1
    assert any("help" in m["text"].lower() for m in telegram.sent_messages)


@pytest.mark.asyncio
async def test_stop_command(
    user_repo, chat_repo, session_repo, binding_repo, message_repo, audit_repo,
    runtime, telegram, security, config,
) -> None:
    session = await runtime.create_session("test")
    await session_repo.save(session)

    from opencode_telegram.domain.entities import SessionBinding
    from opencode_telegram.domain.value_objects import ChatId
    await binding_repo.save(SessionBinding(chat_id=ChatId(123), session_id=session.id))

    capabilities = await runtime.get_capabilities()
    usecase = HandleCommandUseCase(
        user_repo=user_repo,
        chat_repo=chat_repo,
        session_repo=session_repo,
        binding_repo=binding_repo,
        message_repo=message_repo,
        audit_repo=audit_repo,
        runtime=runtime,
        telegram=telegram,
        security=security,
        default_workspace=config.OPENCODE_DEFAULT_WORKSPACE,
        default_server=config.OPENCODE_DEFAULT_SERVER,
        capabilities=capabilities,
    )

    update = {
        "message": {
            "text": "/stop",
            "chat": {"id": 123, "type": "private"},
            "from": {"id": 456, "username": "testuser", "first_name": "Test"},
            "message_id": 1,
        }
    }

    await usecase.execute(update)
    stopped = await session_repo.get(session.id)
    assert stopped is not None
    assert stopped.status == SessionStatus.stopped


@pytest.mark.asyncio
async def test_clear_command(
    user_repo, chat_repo, session_repo, binding_repo, message_repo, audit_repo,
    runtime, telegram, security, config,
) -> None:
    session = await runtime.create_session("test")
    await session_repo.save(session)

    from opencode_telegram.domain.entities import SessionBinding
    from opencode_telegram.domain.value_objects import ChatId
    await binding_repo.save(SessionBinding(chat_id=ChatId(123), session_id=session.id))

    capabilities = await runtime.get_capabilities()
    usecase = HandleCommandUseCase(
        user_repo=user_repo,
        chat_repo=chat_repo,
        session_repo=session_repo,
        binding_repo=binding_repo,
        message_repo=message_repo,
        audit_repo=audit_repo,
        runtime=runtime,
        telegram=telegram,
        security=security,
        default_workspace=config.OPENCODE_DEFAULT_WORKSPACE,
        default_server=config.OPENCODE_DEFAULT_SERVER,
        capabilities=capabilities,
    )

    update = {
        "message": {
            "text": "/clear",
            "chat": {"id": 123, "type": "private"},
            "from": {"id": 456, "username": "testuser", "first_name": "Test"},
            "message_id": 1,
        }
    }

    await usecase.execute(update)
    assert len(telegram.sent_messages) >= 1
