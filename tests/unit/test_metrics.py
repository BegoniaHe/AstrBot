import pytest

from astrbot.core.utils.metrics import Metric


@pytest.mark.asyncio
async def test_metric_shutdown_cancels_pending_flush_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The lifecycle stops the periodic metric task rather than leaving it alive."""
    await Metric.shutdown()
    monkeypatch.setenv("ASTRBOT_TEST_MODE", "false")
    monkeypatch.delenv("ASTRBOT_DISABLE_METRICS", raising=False)
    monkeypatch.setattr(Metric, "_upload_interval_seconds", 3600)
    Metric.configure({"disable_metrics": False}, None)
    Metric._has_uploaded_once = True

    try:
        await Metric.upload(msg_event_tick=1, adapter_name="test")
        flush_task = Metric._flush_task
        assert flush_task is not None
        assert not flush_task.done()

        await Metric.shutdown()

        assert flush_task.cancelled()
        assert Metric._flush_task is None
        assert Metric._pending_metrics == {}
    finally:
        await Metric.shutdown()


def test_metrics_are_disabled_in_test_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ASTRBOT_TEST_MODE", "true")
    monkeypatch.delenv("ASTRBOT_DISABLE_METRICS", raising=False)
    monkeypatch.setattr(Metric, "_config", {"disable_metrics": False})

    assert Metric._is_disabled()
