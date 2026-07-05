# 杂项

## 调用平台主动动作

```python
from astrbot.api.event import filter, AstrMessageEvent

@filter.command("test")
async def test_(self, event: AstrMessageEvent):
    if event.get_platform_name() != "napcat":
        return

    result = await self.context.invoke_event_platform_action(
        event,
        "delete_msg",
        message_id=event.message_obj.message_id,
    )
    logger.info(f"delete_msg: {result}")
```

插件不再暴露 `Platform` 实例或 `platform_manager`。常规平台 IO 请优先使用：

- `self.context.send_message(...)`
- `self.context.invoke_platform_action(...)`
- `self.context.invoke_event_platform_action(...)`
- `StarTools.send_message(...)`
- `StarTools.invoke_platform_action(...)`
- `StarTools.invoke_event_platform_action(...)`

只有在确实需要构造一条新的平台入站事件时，才使用 `StarTools.create_event(...)`。

## 调用 QQ 协议端 API

插件侧不要再直接依赖 `event.bot`、`event.client` 或平台 SDK client。

如果需要调用 AstrBot 已声明的平台主动动作，请优先通过 `invoke_event_platform_action(...)`
或 `invoke_platform_action(...)` 进入平台边界；只有平台事件类本身已经提供的高层方法
（例如某些事件类上的 `delete()`、`send_poke()` 等）才应直接调用。

关于 CQHTTP API，请参考如下文档：

Napcat API 文档：<https://napcat.apifox.cn/>

Lagrange API 文档：<https://lagrange-onebot.apifox.cn/>

## 获取载入的所有插件

```py
plugins = self.context.get_all_stars() # 返回 StarMetadata 包含了插件类实例、配置等等
```

## 获取加载的所有平台

插件侧不再提供“枚举所有平台实例”的接口。

如果插件需要对某个平台执行动作，应直接使用明确的平台 ID：

```py
result = await self.context.invoke_platform_action(
    "napcat-main",
    "get_status",
)
```
