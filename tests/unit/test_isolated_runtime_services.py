"""Regression tests for test-owned runtime service construction."""

from pathlib import Path

import pytest

from tests.fixtures.helpers import create_isolated_runtime_services


@pytest.mark.asyncio
async def test_isolated_runtime_services_do_not_use_repository_data(tmp_path: Path):
    services = create_isolated_runtime_services(
        tmp_path, tmp_path / "data" / "db.sqlite"
    )

    try:
        assert Path(services.config.config_path).is_relative_to(tmp_path)
        assert Path(services.db.db_path).is_relative_to(tmp_path)
        assert Path(services.preferences.path).is_relative_to(tmp_path)
        assert services.config["platform"] == []
    finally:
        await services.preferences.terminate()
