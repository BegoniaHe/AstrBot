import logging
import re
from functools import lru_cache
from pathlib import Path

from markdown_it import MarkdownIt
from mdit_py_plugins.dollarmath import dollarmath_plugin

try:
    from latex2mathml.converter import convert as latex_to_mathml
except ImportError:  # pragma: no cover - fallback depends on runtime setup
    latex_to_mathml = None

try:
    from pykatex import OUTPUT_MATHML
    from pykatex import renderToString as katex_render_to_string
except ImportError:  # pragma: no cover - fallback depends on runtime setup
    OUTPUT_MATHML = None
    katex_render_to_string = None

SHIKI_RUNTIME_SCRIPT_ID = "astrbot-t2i-shiki-runtime"
SHIKI_RUNTIME_TEMPLATE_PATTERN = re.compile(r"\{\{\s*shiki_runtime\s*\|\s*safe\s*\}\}")
JINJA_SYNTAX_PATTERN = re.compile(r"\{[{%#]")
JINJA_RAW_OPEN_PATTERN = re.compile(r"{%-?\s*raw\s*-?%}")
JINJA_RAW_CLOSE_PATTERN = re.compile(r"{%-?\s*endraw\s*-?%}")

logger = logging.getLogger("astrbot")


@lru_cache(maxsize=1)
def get_markdown_renderer() -> MarkdownIt:
    markdown_it = (
        MarkdownIt(
            "commonmark",
            {
                "html": False,
                "breaks": False,
            },
        )
        .enable("table")
        .enable("strikethrough")
        .use(dollarmath_plugin)
    )

    def render_math_inline(self, tokens, idx, options, env) -> str:
        _ = self, options, env
        return _render_math(tokens[idx].content, display_mode=False)

    def render_math_block(self, tokens, idx, options, env) -> str:
        _ = self, options, env
        return _render_math(tokens[idx].content, display_mode=True)

    markdown_it.add_render_rule("math_inline", render_math_inline)
    markdown_it.add_render_rule("math_block", render_math_block)
    return markdown_it


def render_markdown(text: str) -> str:
    return get_markdown_renderer().render(text)


def _render_math(expression: str, *, display_mode: bool) -> str:
    expression = expression.strip()
    if not expression:
        return ""

    if katex_render_to_string is not None and OUTPUT_MATHML is not None:
        try:
            return katex_render_to_string(
                expression,
                displayMode=display_mode,
                output=OUTPUT_MATHML,
                throwOnError=False,
            )
        except Exception as exc:
            logger.debug("Failed to render math with pykatex: %s", exc)

    if latex_to_mathml is not None:
        try:
            mathml = latex_to_mathml(
                expression,
                display="block" if display_mode else "inline",
            )
            return f'<span class="katex katex--fallback">{mathml}</span>'
        except Exception as exc:
            logger.debug("Failed to render math with latex2mathml: %s", exc)

    escaped_expression = (
        expression.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )
    if display_mode:
        return f'<pre class="math-fallback">{escaped_expression}</pre>'
    return f"<code>{escaped_expression}</code>"


@lru_cache(maxsize=1)
def get_shiki_runtime() -> str:
    runtime_path = (
        Path(__file__).resolve().parent / "template" / "shiki_runtime.iife.js"
    )
    if not runtime_path.exists():
        logger.error(
            "T2I Shiki runtime not found at %s. Run `cd dashboard && pnpm run build:t2i-shiki-runtime` to regenerate it. Continuing without code highlighting.",
            runtime_path,
        )
        return ""

    try:
        runtime = runtime_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as err:
        logger.warning(
            "Failed to load T2I Shiki runtime from %s: %s. Continuing without code highlighting.",
            runtime_path,
            err,
        )
        return ""

    return re.sub(r"</(script)", r"<\/\1", runtime, flags=re.IGNORECASE)


def _is_inside_jinja_raw_block(tmpl_str: str, index: int) -> bool:
    raw_open_index = -1
    for match in JINJA_RAW_OPEN_PATTERN.finditer(tmpl_str, 0, index):
        raw_open_index = match.start()

    raw_close_index = -1
    for match in JINJA_RAW_CLOSE_PATTERN.finditer(tmpl_str, 0, index):
        raw_close_index = match.start()

    return raw_open_index > raw_close_index


def _wrap_runtime_for_jinja(tmpl_str: str, script: str, index: int) -> str:
    if not JINJA_SYNTAX_PATTERN.search(script) or _is_inside_jinja_raw_block(
        tmpl_str,
        index,
    ):
        return script

    return f"{{% raw %}}{script}{{% endraw %}}"


def inject_shiki_runtime(tmpl_str: str) -> str:
    if SHIKI_RUNTIME_SCRIPT_ID in tmpl_str or SHIKI_RUNTIME_TEMPLATE_PATTERN.search(
        tmpl_str,
    ):
        return tmpl_str

    runtime = get_shiki_runtime()
    if not runtime:
        return tmpl_str

    script = f'<script id="{SHIKI_RUNTIME_SCRIPT_ID}">{runtime}</script>'
    head_close = re.search(r"</head\s*>", tmpl_str, flags=re.IGNORECASE)
    if head_close:
        script = _wrap_runtime_for_jinja(tmpl_str, script, head_close.start())
        return f"{tmpl_str[: head_close.start()]}  {script}\n{tmpl_str[head_close.start() :]}"

    script = _wrap_runtime_for_jinja(tmpl_str, script, 0)
    return f"{script}\n{tmpl_str}"
