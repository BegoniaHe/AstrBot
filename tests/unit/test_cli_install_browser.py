import sys
from types import SimpleNamespace

from click.testing import CliRunner

from astrbot.cli.commands.cmd_install_browser import install_browser


def test_install_browser_runs_playwright_in_current_environment(monkeypatch):
    calls = []

    def fake_run(command, *, check):
        calls.append((command, check))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(
        "astrbot.cli.commands.cmd_install_browser.subprocess.run",
        fake_run,
    )

    result = CliRunner().invoke(install_browser)

    assert result.exit_code == 0
    assert calls == [
        (
            [
                sys.executable,
                "-m",
                "playwright",
                "install",
                "chromium",
            ],
            False,
        )
    ]
