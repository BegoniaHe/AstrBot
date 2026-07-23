import copy

from astrbot import logger

from .catalog import PROVIDER_ADAPTER_DESCRIPTOR_ATTR, ProviderAdapterDescriptor
from .entities import ProviderType


def register_provider_adapter(
    provider_type_name: str,
    desc: str,
    provider_type: ProviderType = ProviderType.CHAT_COMPLETION,
    default_config_tmpl: dict | None = None,
    provider_display_name: str | None = None,
):
    """Declare immutable metadata on a provider adapter class.

    Runtime-owned ``ProviderCatalog`` instances discover this declaration after
    the adapter module has been imported. The decorator deliberately performs
    no process-wide registration.
    """

    template = copy.deepcopy(default_config_tmpl) if default_config_tmpl else None
    if template is not None:
        template.setdefault("type", provider_type_name)
        template.setdefault("enable", False)
        template.setdefault("id", provider_type_name)
    descriptor = ProviderAdapterDescriptor.create(
        type=provider_type_name,
        desc=desc,
        provider_type=provider_type,
        default_config_tmpl=template,
        provider_display_name=provider_display_name,
    )

    def decorator(cls):
        existing = cls.__dict__.get(PROVIDER_ADAPTER_DESCRIPTOR_ATTR)
        if existing is not None and existing != descriptor:
            raise ValueError(
                f"Provider adapter {cls.__qualname__} already declares metadata.",
            )
        setattr(cls, PROVIDER_ADAPTER_DESCRIPTOR_ATTR, descriptor)
        logger.debug("Model provider declared: %s", provider_type_name)
        return cls

    return decorator
