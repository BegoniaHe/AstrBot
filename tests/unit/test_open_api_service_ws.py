import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import astrbot.dashboard.services.open_api_service as open_api_service_module
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
async def test_handle_chat_ws_send_reduces_queue_results_and_persists_native_refs(
    monkeypatch,
):
    service = _service()
    back_queue = asyncio.Queue()
    chat_queue = MagicMock()
    chat_queue.put = AsyncMock()
    service.prepare_chat_send = AsyncMock(return_value=("alice", "session-1", None))
    service.update_session_config_route = AsyncMock(return_value=None)
    monkeypatch.setattr(
        open_api_service_module.webchat_queue_mgr,
        "get_or_create_back_queue",
        lambda *_args: back_queue,
    )
    monkeypatch.setattr(
        open_api_service_module.webchat_queue_mgr,
        "get_or_create_queue",
        lambda *_args: chat_queue,
    )
    monkeypatch.setattr(
        open_api_service_module.webchat_queue_mgr, "remove_back_queue", MagicMock()
    )

    saved = []

    async def build_user_message_parts(_message):
        return [{"type": "plain", "text": "question"}]

    async def create_attachment(filename, attach_type, display_name=None):
        assert (filename, attach_type, display_name) == (
            "stored.pdf",
            "file",
            "report.pdf",
        )
        return {"type": "file", "attachment_id": "attachment-1"}

    async def insert_user_message(*_args):
        return None

    async def save_bot_message(*args):
        saved.append(args)
        return SimpleNamespace(id=99, created_at=datetime.now(UTC))

    bridge = OpenApiWebSocketChatBridge(
        build_user_message_parts=build_user_message_parts,
        create_attachment_from_file=create_attachment,
        extract_web_search_refs=lambda *_args: {
            "used": [{"url": "https://example.com", "title": "Tool source"}]
        },
        insert_user_message=insert_user_message,
        save_bot_message=save_bot_message,
    )
    await back_queue.put({"message_id": "wrong", "type": "plain", "data": "ignored"})
    await back_queue.put(
        {
            "message_id": "message-1",
            "type": "plain",
            "data": '{"id":"tool-1","name":"search"}',
            "streaming": True,
            "chain_type": "tool_call",
        }
    )
    await back_queue.put(
        {
            "message_id": "message-1",
            "type": "agent_stats",
            "data": '{"latency": 3}',
            "chain_type": "agent_stats",
        }
    )
    await back_queue.put(
        {
            "message_id": "message-1",
            "type": "refs",
            "data": {"used": [{"url": "https://example.com", "snippet": "Native"}]},
        }
    )
    await back_queue.put(
        {
            "message_id": "message-1",
            "type": "plain",
            "data": "answer",
            "streaming": True,
        }
    )
    await back_queue.put(
        {
            "message_id": "message-1",
            "type": "file",
            "data": "[FILE]stored.pdf|report.pdf",
            "streaming": False,
        }
    )
    await back_queue.put({"message_id": "message-1", "type": "end", "data": ""})

    sent = []

    async def send_json(payload):
        sent.append(payload)

    async def send_error(*_args):
        raise AssertionError("send_error should not be called")

    await service.handle_chat_ws_send(
        post_data={"message": "question", "message_id": "message-1"},
        conf_list=[],
        chat_bridge=bridge,
        send_json=send_json,
        send_error=send_error,
    )

    assert len(saved) == 1
    _, parts, agent_stats, refs = saved[0]
    assert parts == [
        {"type": "plain", "text": "answer"},
        {"type": "file", "attachment_id": "attachment-1"},
        {"type": "tool_call", "tool_calls": [{"id": "tool-1", "name": "search"}]},
    ]
    assert agent_stats == {"latency": 3}
    assert refs == {"used": [{"url": "https://example.com", "title": "Tool source"}]}
    assert not any(item.get("data") == "ignored" for item in sent)
    assert any(item.get("type") == "refs" for item in sent)


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
