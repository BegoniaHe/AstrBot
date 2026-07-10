import subprocess
import sys

import click


@click.command("install-browser")
def install_browser() -> None:
    """Install Chromium required by local HTML text-to-image rendering."""
    try:
        import playwright  # noqa: F401
    except ImportError as exc:
        raise click.ClickException(
            "Playwright is not installed. Reinstall AstrBot before installing Chromium."
        ) from exc

    result = subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        check=False,
    )
    if result.returncode:
        raise click.ClickException("Failed to install Chromium for Playwright.")

    click.echo("Chromium for local HTML rendering has been installed.")
