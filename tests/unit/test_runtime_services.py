"""Tests for explicit runtime-service construction."""

from unittest.mock import MagicMock

import pytest

import astrbot.core.runtime_services as runtime_services


def test_factory_does_not_start_preferences_before_other_resources(monkeypatch, tmp_path):
    """A failed factory call must not leak SharedPreferences' scheduler."""

    config = MagicMock()
    config.get.return_value = ""
    preferences_factory = MagicMock()

    class BrokenToolImageCache:
        CACHE_DIR_NAME = "tool_images"

        def __init__(self, _cache_dir) -> None:
            raise OSError("cache directory is unavailable")

    monkeypatch.setattr(runtime_services, "AstrBotConfig", lambda: config)
    monkeypatch.setattr(runtime_services, "SQLiteDatabase", MagicMock())
    monkeypatch.setattr(
        runtime_services.LogManager,
        "configure_logger",
        MagicMock(),
    )
    monkeypatch.setattr(
        runtime_services.LogManager,
        "configure_trace_logger",
        MagicMock(),
    )
    monkeypatch.setattr(runtime_services, "ToolImageCache", BrokenToolImageCache)
    monkeypatch.setattr(runtime_services, "SharedPreferences", preferences_factory)
    monkeypatch.setattr(runtime_services, "get_astrbot_temp_path", lambda: str(tmp_path))

    with pytest.raises(OSError, match="cache directory is unavailable"):
        runtime_services.create_runtime_services()

    preferences_factory.assert_not_called()
