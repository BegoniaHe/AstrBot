"""Lazy discovery of built-in platform adapters.

The platform manager owns adapter lifecycles; this module alone knows where
built-in adapter implementations live.
"""

from __future__ import annotations

import importlib

from astrbot.core.platform.catalog import PlatformCatalog

BUILTIN_PLATFORM_MODULES = {
    "aiocqhttp": "astrbot.core.platform.sources.aiocqhttp.aiocqhttp_platform_adapter",
    "qq_official": "astrbot.core.platform.sources.qqofficial.qqofficial_platform_adapter",
    "qq_official_webhook": "astrbot.core.platform.sources.qqofficial_webhook.qo_webhook_adapter",
    "lark": "astrbot.core.platform.sources.lark.lark_adapter",
    "dingtalk": "astrbot.core.platform.sources.dingtalk.dingtalk_adapter",
    "telegram": "astrbot.core.platform.sources.telegram.tg_adapter",
    "wecom": "astrbot.core.platform.sources.wecom.wecom_adapter",
    "wecom_ai_bot": "astrbot.core.platform.sources.wecom_ai_bot.wecomai_adapter",
    "weixin_official_account": "astrbot.core.platform.sources.weixin_official_account.weixin_offacc_adapter",
    "discord": "astrbot.core.platform.sources.discord.discord_platform_adapter",
    "misskey": "astrbot.core.platform.sources.misskey.misskey_adapter",
    "weixin_oc": "astrbot.core.platform.sources.weixin_oc.weixin_oc_adapter",
    "slack": "astrbot.core.platform.sources.slack.slack_adapter",
    "satori": "astrbot.core.platform.sources.satori.satori_adapter",
    "line": "astrbot.core.platform.sources.line.line_adapter",
    "kook": "astrbot.core.platform.sources.kook.kook_adapter",
    "mattermost": "astrbot.core.platform.sources.mattermost.mattermost_adapter",
    "napcat": "astrbot.core.platform.sources.napcat.napcat_platform_adapter",
    "webchat": "astrbot.core.platform.sources.webchat.webchat_adapter",
}


def discover_platform_adapter(
    adapter_type: str,
    catalog: PlatformCatalog,
) -> type | None:
    """Load a built-in adapter on demand and return its cataloged class.

    ImportError is intentionally allowed to propagate so callers retain the
    existing optional-dependency diagnostic.
    """
    registration = catalog.get(adapter_type)
    if registration is None:
        module_name = BUILTIN_PLATFORM_MODULES.get(adapter_type)
        if module_name is None:
            return None
        module = importlib.import_module(module_name)
        catalog.register_module(module)
        registration = catalog.get(adapter_type)
    return registration.cls_type if registration is not None else None
