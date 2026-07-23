import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import astrbot.core.initial_loader as initial_loader


def _lifecycle(*, start) -> SimpleNamespace:
    return SimpleNamespace(
        initialize=AsyncMock(),
        start=start,
        stop=AsyncMock(),
        runtime=SimpleNamespace(dashboard_shutdown_event=asyncio.Event()),
    )


def _loader(monkeypatch, lifecycle, dashboard_run):
    monkeypatch.setattr(
        initial_loader,
        "AstrBotCoreLifecycle",
        lambda *_args: lifecycle,
    )

    class DashboardFactory:
        @classmethod
        async def create(cls, *_args, **_kwargs):
            return SimpleNamespace(run=dashboard_run)

    monkeypatch.setattr(initial_loader, "AstrBotDashboard", DashboardFactory)
    return initial_loader.InitialLoader(
        services=SimpleNamespace(db=MagicMock()),
        log_broker=MagicMock(),
    )


@pytest.mark.asyncio
async def test_initial_loader_propagates_initialize_failure_after_cleanup(monkeypatch):
    lifecycle = _lifecycle(start=AsyncMock())
    lifecycle.initialize.side_effect = RuntimeError("database failed")
    loader = _loader(monkeypatch, lifecycle, lambda: None)

    with pytest.raises(RuntimeError, match="database failed"):
        await loader.start()

    lifecycle.stop.assert_awaited_once()


@pytest.mark.asyncio
async def test_dashboard_failure_cancels_core_and_stops_lifecycle(monkeypatch):
    core_cancelled = asyncio.Event()

    async def core_start() -> None:
        try:
            await asyncio.Event().wait()
        finally:
            core_cancelled.set()

    async def dashboard_run() -> None:
        raise RuntimeError("dashboard failed")

    lifecycle = _lifecycle(start=core_start)
    loader = _loader(monkeypatch, lifecycle, dashboard_run)

    with pytest.raises(RuntimeError, match="dashboard failed"):
        await loader.start()

    assert core_cancelled.is_set()
    lifecycle.stop.assert_awaited_once()


@pytest.mark.asyncio
async def test_core_failure_cancels_dashboard_and_stops_lifecycle(monkeypatch):
    dashboard_cancelled = asyncio.Event()

    async def core_start() -> None:
        raise RuntimeError("core failed")

    async def dashboard_run() -> None:
        try:
            await asyncio.Event().wait()
        finally:
            dashboard_cancelled.set()

    lifecycle = _lifecycle(start=core_start)
    loader = _loader(monkeypatch, lifecycle, dashboard_run)

    with pytest.raises(RuntimeError, match="core failed"):
        await loader.start()

    assert dashboard_cancelled.is_set()
    lifecycle.stop.assert_awaited_once()


@pytest.mark.asyncio
async def test_normal_runtime_return_stops_lifecycle_once(monkeypatch):
    lifecycle = _lifecycle(start=AsyncMock())
    loader = _loader(monkeypatch, lifecycle, lambda: None)

    await loader.start()

    lifecycle.stop.assert_awaited_once()


@pytest.mark.asyncio
async def test_normal_core_return_cancels_dashboard_and_stops_lifecycle(monkeypatch):
    """A completed Core cannot leave the Dashboard serving on its own."""
    dashboard_cancelled = asyncio.Event()

    async def dashboard_run() -> None:
        try:
            await asyncio.Event().wait()
        finally:
            dashboard_cancelled.set()

    lifecycle = _lifecycle(start=AsyncMock())
    loader = _loader(monkeypatch, lifecycle, dashboard_run)

    await loader.start()

    assert dashboard_cancelled.is_set()
    lifecycle.stop.assert_awaited_once()


@pytest.mark.asyncio
async def test_runtime_cancellation_stops_lifecycle_once(monkeypatch):
    async def core_start() -> None:
        await asyncio.Event().wait()

    lifecycle = _lifecycle(start=core_start)
    loader = _loader(monkeypatch, lifecycle, lambda: None)
    task = asyncio.create_task(loader.start())
    await asyncio.sleep(0)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    lifecycle.stop.assert_awaited_once()


@pytest.mark.asyncio
async def test_core_self_cancellation_cancels_dashboard_and_stops_lifecycle(
    monkeypatch,
):
    """A cancelled Core task must not leave Dashboard supervision blocked."""
    dashboard_cancelled = asyncio.Event()

    async def core_start() -> None:
        raise asyncio.CancelledError

    async def dashboard_run() -> None:
        try:
            await asyncio.Event().wait()
        finally:
            dashboard_cancelled.set()

    lifecycle = _lifecycle(start=core_start)
    loader = _loader(monkeypatch, lifecycle, dashboard_run)

    with pytest.raises(asyncio.CancelledError):
        await loader.start()

    assert dashboard_cancelled.is_set()
    lifecycle.stop.assert_awaited_once()
