"""Runtime-owned catalog for platform adapter declarations."""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from types import ModuleType
from typing import Any

from astrbot.core.catalog_values import freeze_catalog_value, thaw_catalog_value

from .platform_metadata import PlatformMetadata
from .provisioning import PlatformProvisioner

PLATFORM_ADAPTER_DESCRIPTOR_ATTR = "__astrbot_platform_adapter_descriptor__"


@dataclass(frozen=True, slots=True)
class PlatformAdapterDescriptor:
    """Immutable declaration attached to a platform adapter class."""

    name: str
    description: str
    default_config_tmpl: object | None
    adapter_display_name: str | None
    logo_path: str | None
    support_streaming_message: bool
    i18n_resources: object | None
    config_metadata: object | None
    provisioner: PlatformProvisioner | None = None

    @classmethod
    def create(
        cls,
        *,
        name: str,
        description: str,
        default_config_tmpl: dict | None,
        adapter_display_name: str | None,
        logo_path: str | None,
        support_streaming_message: bool,
        i18n_resources: dict[str, dict] | None,
        config_metadata: dict | None,
        provisioner: PlatformProvisioner | None = None,
    ) -> PlatformAdapterDescriptor:
        """Create a descriptor with immutable declaration data."""

        return cls(
            name=name,
            description=description,
            default_config_tmpl=(
                freeze_catalog_value(default_config_tmpl)
                if default_config_tmpl is not None
                else None
            ),
            adapter_display_name=adapter_display_name,
            logo_path=logo_path,
            support_streaming_message=support_streaming_message,
            i18n_resources=(
                freeze_catalog_value(i18n_resources)
                if i18n_resources is not None
                else None
            ),
            config_metadata=(
                freeze_catalog_value(config_metadata)
                if config_metadata is not None
                else None
            ),
            provisioner=provisioner,
        )

    def config_template(self) -> dict | None:
        """Return an isolated mutable default configuration."""

        if self.default_config_tmpl is None:
            return None
        return thaw_catalog_value(self.default_config_tmpl)

    def i18n(self) -> dict[str, dict] | None:
        """Return an isolated mutable i18n declaration."""

        if self.i18n_resources is None:
            return None
        return thaw_catalog_value(self.i18n_resources)

    def schema(self) -> dict | None:
        """Return an isolated mutable configuration schema."""

        if self.config_metadata is None:
            return None
        return thaw_catalog_value(self.config_metadata)


@dataclass(frozen=True, slots=True)
class PlatformAdapterRegistration:
    """A platform descriptor bound to one concrete adapter class."""

    descriptor: PlatformAdapterDescriptor
    cls_type: type[Any]
    module_path: str

    def metadata(self) -> PlatformMetadata:
        """Build an isolated value for existing metadata consumers."""

        return PlatformMetadata(
            name=self.descriptor.name,
            description=self.descriptor.description,
            id=self.descriptor.name,
            default_config_tmpl=self.descriptor.config_template(),
            adapter_display_name=self.descriptor.adapter_display_name,
            logo_path=self.descriptor.logo_path,
            support_streaming_message=self.descriptor.support_streaming_message,
            module_path=self.module_path,
            i18n_resources=self.descriptor.i18n(),
            config_metadata=self.descriptor.schema(),
        )


class PlatformCatalog:
    """Platform adapter registrations owned by one runtime."""

    def __init__(self) -> None:
        self._by_name: dict[str, PlatformAdapterRegistration] = {}
        self._names_by_module: dict[str, set[str]] = {}

    def register_class(self, adapter_class: type[Any]) -> PlatformAdapterRegistration:
        """Register an adapter class carrying an own platform descriptor."""

        descriptor = adapter_class.__dict__.get(PLATFORM_ADAPTER_DESCRIPTOR_ATTR)
        if not isinstance(descriptor, PlatformAdapterDescriptor):
            raise ValueError(
                f"Platform adapter {adapter_class!r} does not declare a descriptor"
            )
        return self.register(
            descriptor,
            adapter_class,
            module_path=adapter_class.__module__,
        )

    def register(
        self,
        descriptor: PlatformAdapterDescriptor,
        adapter_class: type[Any],
        *,
        module_path: str | None = None,
    ) -> PlatformAdapterRegistration:
        """Register one descriptor and reject adapter name collisions."""

        source_module = module_path or adapter_class.__module__
        registration = PlatformAdapterRegistration(
            descriptor=descriptor,
            cls_type=adapter_class,
            module_path=source_module,
        )
        existing = self._by_name.get(descriptor.name)
        if existing is not None:
            if existing == registration:
                return existing
            raise ValueError(
                "Platform adapter name collision for "
                f"{descriptor.name!r}: {existing.module_path} and {source_module}"
            )

        self._by_name[descriptor.name] = registration
        self._names_by_module.setdefault(source_module, set()).add(descriptor.name)
        return registration

    def register_module(
        self, module: ModuleType
    ) -> tuple[PlatformAdapterRegistration, ...]:
        """Discover and register every adapter declared directly in ``module``."""

        registrations: list[PlatformAdapterRegistration] = []
        for candidate in vars(module).values():
            if not inspect.isclass(candidate):
                continue
            if candidate.__module__ != module.__name__:
                continue
            if PLATFORM_ADAPTER_DESCRIPTOR_ATTR not in candidate.__dict__:
                continue
            registrations.append(self.register_class(candidate))
        return tuple(registrations)

    def get(self, adapter_name: str) -> PlatformAdapterRegistration | None:
        """Return the registration for one platform adapter name."""

        return self._by_name.get(adapter_name)

    def registrations(self) -> tuple[PlatformAdapterRegistration, ...]:
        """Return registrations in declaration order."""

        return tuple(self._by_name.values())

    def metadata(self) -> tuple[PlatformMetadata, ...]:
        """Return isolated metadata values for display and config consumers."""

        return tuple(registration.metadata() for registration in self._by_name.values())

    def module_paths(self, module_prefix: str | None = None) -> tuple[str, ...]:
        """Return exact source module paths, optionally scoped to a prefix."""

        if module_prefix is None:
            return tuple(self._names_by_module)
        return tuple(
            module_path
            for module_path in self._names_by_module
            if module_path == module_prefix
            or module_path.startswith(f"{module_prefix}.")
        )

    def unregister_module(self, module_path: str) -> tuple[str, ...]:
        """Unregister declarations that originated from one exact module."""

        names = tuple(self._names_by_module.pop(module_path, ()))
        for adapter_name in names:
            registration = self._by_name.get(adapter_name)
            if registration is not None and registration.module_path == module_path:
                self._by_name.pop(adapter_name, None)
        return names
