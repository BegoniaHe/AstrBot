import pytest

from astrbot.core.platform.astrbot_message import AstrBotMessage, MessageMember
from astrbot.core.platform.message_type import MessageType
from astrbot.core.platform.platform_metadata import PlatformMetadata
from astrbot.core.platform.sources.webchat.webchat_event import WebChatMessageEvent
from astrbot.core.platform.sources.webchat.webchat_queue_mgr import webchat_queue_mgr


def _event(message_id: str) -> WebChatMessageEvent:
    message = AstrBotMessage()
    message.type = MessageType.FRIEND_MESSAGE
    message.self_id = "webchat"
    message.session_id = "session-1"
    message.message_id = message_id
    message.sender = MessageMember("alice", "Alice")
    message.message = []
    message.message_str = "hello"
    return WebChatMessageEvent(
        "hello",
        message,
        PlatformMetadata(name="webchat", description="webchat", id="webchat"),
        "webchat!alice!session-1",
    )


@pytest.mark.asyncio
async def test_webchat_emits_run_started_before_response():
    event = _event("request-1")
    queue = webchat_queue_mgr.get_or_create_back_queue("request-1")

    try:
        await event.send_typing()
        await event.send(None)

        assert await queue.get() == {
            "type": "run_started",
            "data": {"run_id": "request-1"},
            "streaming": False,
            "message_id": "request-1",
        }
        assert (await queue.get())["type"] == "end"
    finally:
        webchat_queue_mgr.remove_back_queue("request-1")


@pytest.mark.asyncio
async def test_webchat_emits_follow_up_capture_status():
    event = _event("follow-up-request")
    queue = webchat_queue_mgr.get_or_create_back_queue("follow-up-request")

    try:
        event.set_extra("_follow_up_captured", {"target_run_id": "original-run"})
        await event.send(None)

        assert await queue.get() == {
            "type": "follow_up_captured",
            "data": {"target_run_id": "original-run"},
            "streaming": False,
            "message_id": "follow-up-request",
        }
        assert (await queue.get())["type"] == "end"
    finally:
        webchat_queue_mgr.remove_back_queue("follow-up-request")
