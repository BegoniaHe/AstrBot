import copy

from astrbot import logger

from .catalog import PLATFORM_ADAPTER_DESCRIPTOR_ATTR, PlatformAdapterDescriptor
from .provisioning import PlatformProvisioner


def register_platform_adapter(
    adapter_name: str,
    desc: str,
    default_config_tmpl: dict | None = None,
    adapter_display_name: str | None = None,
    logo_path: str | None = None,
    support_streaming_message: bool = True,
    i18n_resources: dict[str, dict] | None = None,
    config_metadata: dict | None = None,
    provisioner: PlatformProvisioner | None = None,
):
    """Declare immutable metadata on a platform adapter class.

    Runtime-owned ``PlatformCatalog`` instances discover the declaration after
    import. This decorator intentionally does not mutate a module-level
    registry.
    """

    template = copy.deepcopy(default_config_tmpl) if default_config_tmpl else None
    if template is not None:
        template.setdefault("type", adapter_name)
        template.setdefault("enable", False)
        template.setdefault("id", adapter_name)
    descriptor = PlatformAdapterDescriptor.create(
        name=adapter_name,
        description=desc,
        default_config_tmpl=template,
        adapter_display_name=adapter_display_name,
        logo_path=logo_path,
        support_streaming_message=support_streaming_message,
        i18n_resources=i18n_resources,
        config_metadata=config_metadata,
        provisioner=provisioner,
    )

    def decorator(cls):
        existing = cls.__dict__.get(PLATFORM_ADAPTER_DESCRIPTOR_ATTR)
        if existing is not None and existing != descriptor:
            raise ValueError(
                f"Platform adapter {cls.__qualname__} already declares metadata.",
            )
        setattr(cls, PLATFORM_ADAPTER_DESCRIPTOR_ATTR, descriptor)
        logger.debug("Platform adapter declared: %s", adapter_name)
        return cls

    return decorator
