"""Atomic Dashboard-extension lifecycle for one plugin runtime."""

from __future__ import annotations

from astrbot.core.star.dashboard_extension import DashboardExtensionRegistry
from astrbot.core.star.star import StarMetadata


class PluginExtensionCoordinator:
    """Coordinate extension publication with plugin initialization and teardown.

    The registry remains the protocol implementation.  This coordinator owns
    when a plugin generation may enter or leave it, so a failed plugin never
    exposes a partially registered Dashboard extension.
    """

    __slots__ = ("_registry",)

    def __init__(self, registry: DashboardExtensionRegistry) -> None:
        self._registry = registry

    @property
    def registry(self) -> DashboardExtensionRegistry:
        """Return the protocol registry for dedicated Dashboard composition."""
        return self._registry

    async def initialize(self, metadata: StarMetadata) -> None:
        """Initialize a plugin and atomically commit its extension generation."""
        if metadata.star_cls and metadata.activated:
            self._registry.begin_registration(metadata, metadata.star_cls)
            try:
                if hasattr(metadata.star_cls, "initialize"):
                    await metadata.star_cls.initialize()
                await self._registry.commit_registration(metadata.star_cls)
            except BaseException:
                self._registry.rollback_registration(metadata.star_cls)
                raise

    async def deactivate(
        self,
        metadata: StarMetadata,
        *,
        reason: str,
        release: bool = False,
    ) -> None:
        """Drain and deactivate one plugin Dashboard extension generation."""
        await self._registry.deactivate(metadata, reason=reason, release=release)

    async def promote_staged_generation(
        self,
        staging: PluginExtensionCoordinator,
        current: StarMetadata,
        replacement: StarMetadata,
        *,
        reason: str,
    ) -> None:
        """Promote a fully initialized isolated extension generation."""
        await self._registry.promote_staged_generation(
            staging.registry,
            current,
            replacement,
            reason=reason,
        )

    def validate_staged_generation(
        self,
        staging: PluginExtensionCoordinator,
        current: StarMetadata,
        replacement: StarMetadata,
    ) -> None:
        """Verify a staged extension can be promoted without draining live state."""
        self._registry.validate_staged_generation(
            staging.registry,
            current,
            replacement,
        )

    def rollback_metadata(self, metadata: StarMetadata) -> None:
        """Discard staging state belonging to a failed plugin load."""
        self._registry.rollback_metadata(metadata)
