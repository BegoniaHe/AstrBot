"""Lifecycle tests for runtime-owned shared preferences."""

from unittest.mock import MagicMock

import pytest

from astrbot.core.utils.shared_preferences import SharedPreferences


@pytest.mark.asyncio
async def test_terminate_stops_scheduler_thread_once(tmp_path):
    """Terminate releases the scheduler thread and remains safe to repeat."""
    preferences = SharedPreferences(
        db_helper=MagicMock(),
        json_storage_path=str(tmp_path / "preferences.json"),
    )
    scheduler_thread = preferences._scheduler._thread  # noqa: SLF001

    try:
        assert scheduler_thread is not None
        assert scheduler_thread.is_alive()

        await preferences.terminate()
        await preferences.terminate()

        assert scheduler_thread.is_alive() is False
        assert preferences._scheduler.running is False  # noqa: SLF001
    finally:
        await preferences.terminate()
