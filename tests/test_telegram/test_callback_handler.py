from __future__ import annotations

import pytest

from opencode_telegram.domain.entities import SessionBinding
from opencode_telegram.domain.value_objects import ChatId, SessionStatus
from opencode_telegram.interfaces.telegram.handlers import TelegramUpdateHandler


@pytest.mark.asyncio
async def test_resume_callback(
    user_repo, chat_repo, session_repo, binding_repo, message_repo, audit_repo,
    runtime, telegram, security, config,
) -> None:
    from opencode_telegram.app.usecases import HandleCommandUseCase, HandleMessageUseCase

    capabilities = await runtime.get_capabilities()
    cmd_handler = HandleCommandUseCase(
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
    msg_handler = HandleMessageUseCase(
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

    session = await runtime.create_session("test")
    await session_repo.save(session)
    await binding_repo.save(SessionBinding(chat_id=ChatId(123), session_id=session.id))

    handler = TelegramUpdateHandler(
        message_handler=msg_handler,
        command_handler=cmd_handler,
        session_repo=session_repo,
        binding_repo=binding_repo,
        runtime=runtime,
        telegram=telegram,
        security=security,
    )

    callback_update = {
        "callback_query": {
            "id": "cb_1",
            "from": {"id": 456, "username": "testuser"},
            "message": {"chat": {"id": 123}, "message_id": 10},
            "data": f"resume:{session.id.value}",
        }
    }

    await handler.handle(callback_update)
    assert len(telegram.edited_messages) >= 1
    assert len(telegram.sent_messages) >= 1
