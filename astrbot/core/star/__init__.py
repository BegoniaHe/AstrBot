from typing import TYPE_CHECKING

from astrbot.core.provider import Provider

from .base import Star
from .star import PluginRegistry, StarDeclaration, StarMetadata
from .star_handler import HandlerRegistry

if TYPE_CHECKING:
    from .plugin_context import PluginContext
    from .star_manager import PluginManager


def __getattr__(name: str):
    """Load heavyweight plugin runtime types only when a caller requests them."""
    if name == "PluginContext":
        from .plugin_context import PluginContext

        return PluginContext
    if name == "PluginManager":
        from .star_manager import PluginManager

        return PluginManager
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "PluginContext",
    "HandlerRegistry",
    "PluginManager",
    "PluginRegistry",
    "Provider",
    "Star",
    "StarDeclaration",
    "StarMetadata",
]
