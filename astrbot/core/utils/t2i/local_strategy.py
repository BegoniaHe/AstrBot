import asyncio
import logging
import re
import uuid
from pathlib import Path
from typing import Any, Literal

from jinja2.sandbox import SandboxedEnvironment
from pydantic import BaseModel
from typing_extensions import TypedDict

from astrbot.core.config import VERSION
from astrbot.core.utils.astrbot_path import get_astrbot_temp_path

from . import RenderStrategy
from .template_manager import TemplateManager
from .template_runtime import (
    SHIKI_RUNTIME_TEMPLATE_PATTERN,
    get_shiki_runtime,
    inject_shiki_runtime,
    render_markdown,
)

try:
    from playwright._impl._errors import TargetClosedError
    from playwright.async_api import async_playwright
except ImportError:  # pragma: no cover - exercised indirectly in runtime setups
    TargetClosedError = RuntimeError
    async_playwright = None

logger = logging.getLogger("astrbot")


class FloatRect(TypedDict):
    x: float
    y: float
    width: float
    height: float


class ScreenshotOptions(BaseModel):
    timeout: float | None = None
    type: Literal["jpeg", "png", None] = None
    quality: int | None = None
    omit_background: bool | None = None
    full_page: bool | None = True
    clip: FloatRect | None = None
    animations: Literal["allow", "disabled", None] = None
    caret: Literal["hide", "initial", None] = None
    scale: Literal["css", "device", None] = None
    viewport_width: int | None = None
    viewport_height: int | None = None
    device_scale_factor_level: Literal["normal", "high", "ultra", None] = None


class LocalRenderStrategy(RenderStrategy):
    SCALE_FACTOR_MAP = {
        "normal": 1.0,
        "high": 1.3,
        "ultra": 1.8,
    }

    def __init__(self) -> None:
        self.template_manager = TemplateManager()
        self.playwright: Any | None = None
        self.browser: Any | None = None
        self.contexts: dict[str, Any] = {}
        self._browser_lock = asyncio.Lock()
        self.temp_dir = Path(get_astrbot_temp_path()) / "t2i_local"
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    async def initialize(self) -> None:
        return None

    async def terminate(self) -> None:
        async with self._browser_lock:
            for context in self.contexts.values():
                try:
                    await context.close()
                except Exception as exc:
                    logger.debug("Failed to close local T2I browser context: %s", exc)
            self.contexts.clear()

            if self.browser is not None:
                try:
                    await self.browser.close()
                except Exception as exc:
                    logger.debug("Failed to close local T2I browser: %s", exc)
                self.browser = None

            if self.playwright is not None:
                try:
                    await self.playwright.stop()
                except Exception as exc:
                    logger.debug("Failed to stop local T2I Playwright: %s", exc)
                self.playwright = None

    async def _ensure_context(self, level: str = "normal"):
        if async_playwright is None:
            raise RuntimeError(
                "Playwright is not installed. Install the `playwright` package and run `playwright install chromium`.",
            )
        async with self._browser_lock:
            playwright = self.playwright
            if playwright is None:
                playwright = await async_playwright().start()
                self.playwright = playwright

            browser = self.browser
            if browser is None or not browser.is_connected():
                if browser is not None:
                    try:
                        await browser.close()
                    except Exception as exc:
                        logger.debug("Failed to close stale local T2I browser: %s", exc)
                browser = await playwright.chromium.launch(headless=True)
                self.browser = browser

            context = self.contexts.get(level)
            if context is None:
                scale_factor = self.SCALE_FACTOR_MAP.get(level, 1.0)
                context = await browser.new_context(device_scale_factor=scale_factor)
                self.contexts[level] = context

            return context

    @staticmethod
    def _prepare_template_sync(tmpl_str: str, tmpl_data: dict) -> tuple[str, dict]:
        if SHIKI_RUNTIME_TEMPLATE_PATTERN.search(tmpl_str):
            tmpl_data = {"shiki_runtime": get_shiki_runtime()} | tmpl_data
        if "text" in tmpl_data and "rendered_html" not in tmpl_data:
            tmpl_data = {
                "rendered_html": render_markdown(str(tmpl_data["text"])),
            } | tmpl_data
        tmpl_str = inject_shiki_runtime(tmpl_str)
        return tmpl_str, tmpl_data

    def _create_temp_path(self, suffix: str) -> Path:
        return self.temp_dir / f"t2i_{uuid.uuid4().hex}.{suffix}"

    def _resolve_viewport_size(
        self,
        html_file_path: Path,
        screenshot_options: ScreenshotOptions,
    ) -> tuple[int | None, int | None]:
        viewport_width = screenshot_options.viewport_width
        viewport_height = screenshot_options.viewport_height

        if viewport_width is not None and viewport_height is not None:
            return viewport_width, viewport_height

        try:
            head_snippet = html_file_path.read_text(encoding="utf-8")[:4096]
            if viewport_width is None:
                pattern = (
                    r'<meta\s+[^>]*name=["\']viewport["\'][^>]*'
                    r'content=["\'][^"\']*width\s*=\s*(\d+)[^"\']*["\'][^>]*>'
                )
                if match := re.search(pattern, head_snippet, re.IGNORECASE):
                    viewport_width = int(match[1])

            if viewport_height is None:
                pattern = (
                    r'<meta\s+[^>]*name=["\']viewport["\'][^>]*'
                    r'content=["\'][^"\']*height\s*=\s*(\d+)[^"\']*["\'][^>]*>'
                )
                if match := re.search(pattern, head_snippet, re.IGNORECASE):
                    viewport_height = int(match[1])
        except (OSError, UnicodeDecodeError, ValueError, re.error) as exc:
            logger.debug("Failed to resolve local T2I viewport size: %s", exc)

        return viewport_width, viewport_height

    async def _render_html_to_image(
        self,
        html: str,
        screenshot_options: ScreenshotOptions,
    ) -> str:
        level = screenshot_options.device_scale_factor_level or "normal"
        context = await self._ensure_context(level)

        html_path = self._create_temp_path("html")
        html_path.write_text(html, encoding="utf-8")
        image_path = self._create_temp_path(screenshot_options.type or "png")
        page = None
        rendered = False
        try:
            try:
                page = await context.new_page()
            except TargetClosedError:
                try:
                    await context.close()
                except Exception:
                    pass
                self.contexts.pop(level, None)
                context = await self._ensure_context(level)
                page = await context.new_page()

            async def block_remote_requests(route) -> None:
                if route.request.url.startswith(("http://", "https://")):
                    await route.abort()
                    return
                await route.continue_()

            await page.route("**/*", block_remote_requests)
            viewport_width, viewport_height = self._resolve_viewport_size(
                html_path,
                screenshot_options,
            )
            if viewport_width is not None or viewport_height is not None:
                await page.set_viewport_size(
                    {
                        "width": viewport_width or 800,
                        "height": viewport_height or 720,
                    },
                )

            await page.goto(html_path.as_uri(), timeout=screenshot_options.timeout)
            screenshot_kwargs = screenshot_options.model_dump(exclude_none=True)
            screenshot_kwargs.pop("viewport_width", None)
            screenshot_kwargs.pop("viewport_height", None)
            screenshot_kwargs.pop("device_scale_factor_level", None)
            if screenshot_options.type == "png":
                screenshot_kwargs.pop("quality", None)
            screenshot_kwargs["path"] = str(image_path)
            await page.screenshot(**screenshot_kwargs)
            rendered = True
            return str(image_path)
        finally:
            if page is not None:
                try:
                    await page.close()
                except Exception as exc:
                    logger.debug("Failed to close local T2I page: %s", exc)
            html_path.unlink(missing_ok=True)
            if not rendered:
                image_path.unlink(missing_ok=True)

    async def render_custom_template(
        self,
        tmpl_str: str,
        tmpl_data: dict,
        options: dict | None = None,
    ) -> str:
        default_options = {
            "full_page": True,
            "type": "png",
            "device_scale_factor_level": "ultra",
            "viewport_width": 1280,
        }
        if options:
            default_options |= options

        loop = asyncio.get_running_loop()
        tmpl_str, tmpl_data = await loop.run_in_executor(
            None,
            self._prepare_template_sync,
            tmpl_str,
            tmpl_data,
        )
        html = SandboxedEnvironment().from_string(tmpl_str).render(tmpl_data)
        return await self._render_html_to_image(
            html,
            ScreenshotOptions(**default_options),
        )

    async def render(
        self,
        text: str,
        template_name: str | None = "base",
    ) -> str:
        if not template_name:
            template_name = "base"
        tmpl_str = self.template_manager.get_template(template_name)
        return await self.render_custom_template(
            tmpl_str,
            {
                "text": text,
                "version": f"v{VERSION}",
            },
        )
