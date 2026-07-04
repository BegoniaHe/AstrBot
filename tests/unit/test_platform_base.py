from asyncio import Queue
from types import SimpleNamespace

from astrbot.core.platform.astr_message_event import AstrMessageEvent
from astrbot.core.platform.platform import Platform
from astrbot.core.platform.platform_metadata import PlatformMetadata


class _DummyPlatform(Platform):
    async def run(self):
        return None

    def meta(self) -> PlatformMetadata:
        return PlatformMetadata(name="Dummy", description="Dummy", id="dummy")


def _make_event(origin: str) -> AstrMessageEvent:
    event = AstrMessageEvent(
        message_str="hello",
        message_obj=SimpleNamespace(type="FriendMessage"),
        platform_meta=PlatformMetadata(name="Dummy", description="Dummy", id="dummy"),
        session_id=origin,
    )
    event.unified_msg_origin = f"dummy:FriendMessage:{origin}"
    return event


def test_commit_event_returns_false_when_queue_is_full():
    queue: Queue[AstrMessageEvent] = Queue(maxsize=1)
    platform = _DummyPlatform({}, queue)
    queue.put_nowait(_make_event("dummy:first"))

    result = platform.commit_event(_make_event("dummy:second"))

    assert result is False
