from types import SimpleNamespace

import pytest

from astrbot.core.platform.send_result import PlatformSendResult
from astrbot.dashboard.services.open_api_service import (
    OpenApiService,
    OpenApiServiceError,
    OpenApiWebSocketChatBridge,
)


def _service() -> OpenApiService:
    core_lifecycle = SimpleNamespace(
        platform_manager=SimpleNamespace(
            send_to_session=None,
        ),
        platform_message_history_manager=None,
    )
    return OpenApiService(
        SimpleNamespace(
            get_attachment_by_id=lambda _attachment_id: None,
        ),
        core_lifecycle,
    )


def _bridge() -> OpenApiWebSocketChatBridge:
    async def build_user_message_parts(_message):
        return []

    async def create_attachment_from_file(_filename, _attach_type):
        return None

    async def insert_user_message(_session_id, _effective_username, _message_parts):
        pass

    async def save_bot_message(_session_id, _message_parts, _agent_stats, _refs):
        return None

    return OpenApiWebSocketChatBridge(
        build_user_message_parts=build_user_message_parts,
        create_attachment_from_file=create_attachment_from_file,
        extract_web_search_refs=lambda _text, _parts: {},
        insert_user_message=insert_user_message,
        save_bot_message=save_bot_message,
    )


@pytest.mark.asyncio
async def test_run_chat_websocket_closes_when_api_key_is_invalid(monkeypatch):
    service = _service()
    sent: list[dict] = []
    closed: list[tuple[int, str]] = []

    async def authenticate_api_key(_raw_key):
        return False, "Invalid API key"

    monkeypatch.setattr(service, "authenticate_api_key", authenticate_api_key)

    async def receive_json():
        raise AssertionError("receive_json should not be called")

    async def send_json(payload: dict) -> None:
        sent.append(payload)

    async def close(code: int, reason: str) -> None:
        closed.append((code, reason))

    await service.run_chat_websocket(
        raw_api_key="bad",
        receive_json=receive_json,
        send_json=send_json,
        close=close,
        conf_list=[],
        chat_bridge=_bridge(),
    )

    assert sent == [
        {"type": "error", "code": "UNAUTHORIZED", "data": "Invalid API key"}
    ]
    assert closed == [(1008, "Invalid API key")]


@pytest.mark.asyncio
async def test_run_chat_websocket_handles_control_messages(monkeypatch):
    service = _service()
    messages = iter(
        [
            ["not", "an", "object"],
            {"t": "ping"},
            {"t": "unknown"},
            {"t": "send", "message": "hello"},
        ]
    )
    sent: list[dict] = []
    handled: list[dict] = []

    async def authenticate_api_key(_raw_key):
        return True, None

    async def handle_chat_ws_send(**kwargs):
        handled.append(kwargs["post_data"])

    monkeypatch.setattr(service, "authenticate_api_key", authenticate_api_key)
    monkeypatch.setattr(service, "handle_chat_ws_send", handle_chat_ws_send)

    async def receive_json():
        try:
            return next(messages)
        except StopIteration as exc:
            raise RuntimeError("disconnect") from exc

    async def send_json(payload: dict) -> None:
        sent.append(payload)

    async def close(_code: int, _reason: str) -> None:
        raise AssertionError("close should not be called")

    await service.run_chat_websocket(
        raw_api_key="good",
        receive_json=receive_json,
        send_json=send_json,
        close=close,
        conf_list=[],
        chat_bridge=_bridge(),
    )

    assert sent == [
        {
            "type": "error",
            "code": "INVALID_MESSAGE",
            "data": "message must be an object",
        },
        {"type": "pong"},
        {
            "type": "error",
            "code": "INVALID_MESSAGE",
            "data": "Unsupported message type: unknown",
        },
    ]
    assert handled == [{"t": "send", "message": "hello"}]


@pytest.mark.asyncio
async def test_open_api_send_message_delegates_to_platform_manager():
    service = _service()
    calls: list[tuple[object, object]] = []

    async def _send_to_session(session, message_chain):
        calls.append((session, message_chain))
        return PlatformSendResult(
            platform_id="webchat-main",
            success=True,
            target="test-session",
            message_count=1,
        )

    service.platform_manager.send_to_session = _send_to_session

    await service.send_message(
        {
            "umo": "webchat-main:FriendMessage:test-session",
            "message": "hello",
        }
    )

    assert len(calls) == 1
    session, message_chain = calls[0]
    assert str(session) == "webchat-main:FriendMessage:test-session"
    assert message_chain.chain[0].text == "hello"


@pytest.mark.asyncio
async def test_open_api_send_message_raises_when_platform_missing():
    service = _service()

    async def _send_to_session(session, message_chain):
        return PlatformSendResult(
            platform_id=session.platform_id,
            success=False,
            target=session.session_id,
            message_count=len(message_chain.chain),
            error_message="platform adapter not found",
        )

    service.platform_manager.send_to_session = _send_to_session

    with pytest.raises(
        OpenApiServiceError,
        match="Bot not found or not running for platform: platform-not-running",
    ):
        await service.send_message(
            {
                "umo": "platform-not-running:FriendMessage:test-session",
                "message": "hello",
            }
        )


@pytest.mark.asyncio
async def test_open_api_send_message_raises_with_adapter_error_message():
    service = _service()

    async def _send_to_session(session, message_chain):
        return PlatformSendResult(
            platform_id=session.platform_id,
            success=False,
            target=session.session_id,
            message_count=len(message_chain.chain),
            error_message="adapter rejected payload",
        )

    service.platform_manager.send_to_session = _send_to_session

    with pytest.raises(
        OpenApiServiceError,
        match="Failed to send message: adapter rejected payload",
    ):
        await service.send_message(
            {
                "umo": "telegram:FriendMessage:test-session",
                "message": "hello",
            }
        )
