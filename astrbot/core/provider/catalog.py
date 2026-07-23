"""Runtime-owned catalog for provider adapter declarations."""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from types import ModuleType
from typing import Any

from astrbot.core.catalog_values import freeze_catalog_value, thaw_catalog_value

from .entities import ProviderMetaData, ProviderType

PROVIDER_ADAPTER_DESCRIPTOR_ATTR = "__astrbot_provider_adapter_descriptor__"


@dataclass(frozen=True, slots=True)
class ProviderAdapterDescriptor:
    """Immutable declaration attached to a provider adapter class."""

    type: str
    desc: str
    provider_type: ProviderType
    default_config_tmpl: object | None
    provider_display_name: str | None

    @classmethod
    def create(
        cls,
        *,
        type: str,
        desc: str,
        provider_type: ProviderType,
        default_config_tmpl: dict | None,
        provider_display_name: str | None,
    ) -> ProviderAdapterDescriptor:
        """Create a descriptor with an immutable configuration template."""

        return cls(
            type=type,
            desc=desc,
            provider_type=provider_type,
            default_config_tmpl=(
                freeze_catalog_value(default_config_tmpl)
                if default_config_tmpl is not None
                else None
            ),
            provider_display_name=provider_display_name,
        )

    def config_template(self) -> dict | None:
        """Return an isolated mutable configuration template."""

        if self.default_config_tmpl is None:
            return None
        return thaw_catalog_value(self.default_config_tmpl)


@dataclass(frozen=True, slots=True)
class ProviderAdapterRegistration:
    """A provider descriptor bound to one concrete adapter class."""

    descriptor: ProviderAdapterDescriptor
    cls_type: type[Any]
    module_path: str

    def metadata(self) -> ProviderMetaData:
        """Build a compatibility-neutral value for existing metadata consumers."""

        return ProviderMetaData(
            id="default",
            model=None,
            type=self.descriptor.type,
            desc=self.descriptor.desc,
            provider_type=self.descriptor.provider_type,
            cls_type=self.cls_type,
            default_config_tmpl=self.descriptor.config_template(),
            provider_display_name=self.descriptor.provider_display_name,
        )


class ProviderCatalog:
    """Provider adapter registrations owned by one runtime."""

    def __init__(self) -> None:
        self._by_type: dict[str, ProviderAdapterRegistration] = {}
        self._types_by_module: dict[str, set[str]] = {}

    def register_class(self, adapter_class: type[Any]) -> ProviderAdapterRegistration:
        """Register an adapter class carrying an own provider descriptor.

        Imported classes are deliberately ignored. Only a descriptor declared
        directly on the class proves that the module owns the declaration.
        """

        descriptor = adapter_class.__dict__.get(PROVIDER_ADAPTER_DESCRIPTOR_ATTR)
        if not isinstance(descriptor, ProviderAdapterDescriptor):
            raise ValueError(
                f"Provider adapter {adapter_class!r} does not declare a descriptor"
            )
        return self.register(
            descriptor,
            adapter_class,
            module_path=adapter_class.__module__,
        )

    def register(
        self,
        descriptor: ProviderAdapterDescriptor,
        adapter_class: type[Any],
        *,
        module_path: str | None = None,
    ) -> ProviderAdapterRegistration:
        """Register one descriptor and reject type collisions."""

        source_module = module_path or adapter_class.__module__
        registration = ProviderAdapterRegistration(
            descriptor=descriptor,
            cls_type=adapter_class,
            module_path=source_module,
        )
        existing = self._by_type.get(descriptor.type)
        if existing is not None:
            if existing == registration:
                return existing
            raise ValueError(
                "Provider adapter type collision for "
                f"{descriptor.type!r}: {existing.module_path} and {source_module}"
            )

        self._by_type[descriptor.type] = registration
        self._types_by_module.setdefault(source_module, set()).add(descriptor.type)
        return registration

    def register_module(
        self, module: ModuleType
    ) -> tuple[ProviderAdapterRegistration, ...]:
        """Discover and register every adapter declared directly in ``module``."""

        registrations: list[ProviderAdapterRegistration] = []
        for candidate in vars(module).values():
            if not inspect.isclass(candidate):
                continue
            if candidate.__module__ != module.__name__:
                continue
            if PROVIDER_ADAPTER_DESCRIPTOR_ATTR not in candidate.__dict__:
                continue
            registrations.append(self.register_class(candidate))
        return tuple(registrations)

    def get(self, provider_type: str) -> ProviderAdapterRegistration | None:
        """Return the registration for one provider adapter type."""

        return self._by_type.get(provider_type)

    def registrations(self) -> tuple[ProviderAdapterRegistration, ...]:
        """Return registrations in declaration order."""

        return tuple(self._by_type.values())

    def metadata(self) -> tuple[ProviderMetaData, ...]:
        """Return isolated metadata values for display and config consumers."""

        return tuple(registration.metadata() for registration in self._by_type.values())

    def module_paths(self, module_prefix: str | None = None) -> tuple[str, ...]:
        """Return exact source module paths, optionally scoped to a prefix."""

        if module_prefix is None:
            return tuple(self._types_by_module)
        return tuple(
            module_path
            for module_path in self._types_by_module
            if module_path == module_prefix
            or module_path.startswith(f"{module_prefix}.")
        )

    def unregister_module(self, module_path: str) -> tuple[str, ...]:
        """Unregister declarations that originated from one exact module."""

        types = tuple(self._types_by_module.pop(module_path, ()))
        for provider_type in types:
            registration = self._by_type.get(provider_type)
            if registration is not None and registration.module_path == module_path:
                self._by_type.pop(provider_type, None)
        return types
