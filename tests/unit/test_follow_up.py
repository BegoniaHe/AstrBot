import asyncio
from types import SimpleNamespace

import pytest

from astrbot.core.agent.runners.tool_loop_agent_runner import FollowUpTicket
from astrbot.core.pipeline.process_stage import follow_up


class FakeEvent:
    def __init__(
        self,
        *,
        unified_msg_origin: str = "umo-1",
        sender_id: str | None = "user-1",
        message_str: str = "",
        outline: str = "",
        extras: dict | None = None,
    ) -> None:
        self.unified_msg_origin = unified_msg_origin
        self._sender_id = sender_id
        self._message_str = message_str
        self._outline = outline
        self._extras = extras or {}

    def get_sender_id(self) -> str | None:
        return self._sender_id

    def get_message_str(self) -> str:
        return self._message_str

    def get_message_outline(self) -> str:
        return self._outline

    def get_extra(self, key: str):
        return self._extras.get(key)


@pytest.fixture(autouse=True)
def _clear_follow_up_state():
    follow_up._ACTIVE_AGENT_RUNNERS.clear()
    follow_up._FOLLOW_UP_ORDER_STATE.clear()
    yield
    follow_up._ACTIVE_AGENT_RUNNERS.clear()
    follow_up._FOLLOW_UP_ORDER_STATE.clear()


@pytest.mark.asyncio
async def test_try_capture_follow_up_requires_matching_sender_and_non_stopping_runner():
    runner_event = FakeEvent(sender_id="owner", extras={"agent_stop_requested": True})
    runner = SimpleNamespace(
        run_context=SimpleNamespace(context=SimpleNamespace(event=runner_event)),
        follow_up=lambda message_text: FollowUpTicket(seq=1, text=message_text),
    )
    follow_up.register_active_runner("umo-1", runner)

    assert follow_up.try_capture_follow_up(FakeEvent(sender_id=None)) is None
    assert follow_up.try_capture_follow_up(FakeEvent(sender_id="other")) is None
    assert follow_up.try_capture_follow_up(FakeEvent(sender_id="owner")) is None


@pytest.mark.asyncio
async def test_try_capture_follow_up_uses_outline_when_message_text_is_blank():
    captured_texts: list[str] = []
    runner_event = FakeEvent(sender_id="owner")

    def _follow_up(*, message_text: str):
        captured_texts.append(message_text)
        return FollowUpTicket(seq=7, text=message_text)

    runner = SimpleNamespace(
        run_context=SimpleNamespace(context=SimpleNamespace(event=runner_event)),
        follow_up=_follow_up,
    )
    follow_up.register_active_runner("umo-1", runner)
    event = FakeEvent(
        sender_id="owner",
        message_str="   ",
        outline="  fallback outline  ",
    )

    capture = follow_up.try_capture_follow_up(event)

    assert capture is not None
    assert capture.order_seq == 0
    assert captured_texts == ["fallback outline"]
    capture.ticket.resolved.set()
    await follow_up.finalize_follow_up_capture(
        capture,
        activated=False,
        consumed_marked=False,
    )


@pytest.mark.asyncio
async def test_prepare_follow_up_capture_marks_consumed_ticket_without_activation():
    ticket = FollowUpTicket(seq=1, text="consumed")
    ticket.consumed = True
    ticket.resolved.set()
    seq = follow_up._allocate_follow_up_order("umo-1")
    capture = follow_up.FollowUpCapture(
        umo="umo-1",
        ticket=ticket,
        order_seq=seq,
        monitor_task=asyncio.create_task(asyncio.sleep(30)),
    )

    consumed_marked, activated = await follow_up.prepare_follow_up_capture(capture)

    assert (consumed_marked, activated) == (True, False)
    assert "umo-1" not in follow_up._FOLLOW_UP_ORDER_STATE
    await follow_up.finalize_follow_up_capture(
        capture,
        activated=activated,
        consumed_marked=consumed_marked,
    )
    assert capture.monitor_task.cancelled()


@pytest.mark.asyncio
async def test_follow_up_activation_waits_for_previous_turn_to_finish():
    first_ticket = FollowUpTicket(seq=1, text="first")
    second_ticket = FollowUpTicket(seq=2, text="second")
    first_ticket.resolved.set()
    second_ticket.resolved.set()

    first_capture = follow_up.FollowUpCapture(
        umo="umo-1",
        ticket=first_ticket,
        order_seq=follow_up._allocate_follow_up_order("umo-1"),
        monitor_task=asyncio.create_task(asyncio.sleep(30)),
    )
    second_capture = follow_up.FollowUpCapture(
        umo="umo-1",
        ticket=second_ticket,
        order_seq=follow_up._allocate_follow_up_order("umo-1"),
        monitor_task=asyncio.create_task(asyncio.sleep(30)),
    )

    first_result = await follow_up.prepare_follow_up_capture(first_capture)
    second_task = asyncio.create_task(follow_up.prepare_follow_up_capture(second_capture))
    await asyncio.sleep(0)

    assert first_result == (False, True)
    assert not second_task.done()

    await follow_up.finalize_follow_up_capture(
        first_capture,
        activated=True,
        consumed_marked=False,
    )
    second_result = await second_task

    assert second_result == (False, True)
    state = follow_up._FOLLOW_UP_ORDER_STATE["umo-1"]
    assert state["next_turn"] == 1

    await follow_up.finalize_follow_up_capture(
        second_capture,
        activated=True,
        consumed_marked=False,
    )
    assert "umo-1" not in follow_up._FOLLOW_UP_ORDER_STATE
