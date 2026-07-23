---
outline: deep
---

# 开发平台适配器

平台适配器把外部消息平台转换成 AstrBot 的 `AstrBotMessage` / `AstrMessageEvent`，并负责把 `MessageChain` 发送回正确的会话。适配器可以由 Star 插件注册，但文档代码只能使用 `astrbot.api` 公共 SDK；如果所需类型尚未导出，应先补 SDK，而不是从 `astrbot.core` 导入。

## 核心契约

一个适配器至少需要：

1. 用 `@register_platform_adapter` 注册类型和默认配置；
2. 继承 `Platform`，实现 `meta()`、`run()` 和实际的发送逻辑；
3. 把收到的平台消息转换为 `AstrBotMessage`；
4. 创建事件并通过 `commit_event()` 放入共享队列；
5. 在 `terminate()` 中关闭长连接、HTTP client、轮询任务和临时资源；
6. 返回父类生成的 `PlatformSendResult`，让指标和调用方知道发送结果。

`run()` 是长生命周期协程。捕获宽泛异常时必须重新抛出 `asyncio.CancelledError`，并保证部分初始化也能安全调用 `terminate()`。

## 最小示例

假设插件自带一个 `FakeClient`，它提供 `listen(callback)`、`send_chain(target, chain)` 和 `close()`。下面的示例只展示 AstrBot 边界；平台认证、重连、限流和 SDK 错误映射仍需由适配器实现。

### 事件类型

```python
from astrbot.api.event import AstrMessageEvent, MessageChain


class FakePlatformEvent(AstrMessageEvent):
    def __init__(self, *args, client, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.client = client

    async def send(self, message: MessageChain):
        target = self.get_sender_id() if self.is_private_chat() else self.get_group_id()
        await self.client.send_chain(target, message)
        return await super().send(message)
```

平台 SDK 完成实际发送后，再调用并返回 `super().send()`。父类负责统一指标和逻辑发送结果；只调用父类不会替你向平台 SDK 发消息。

### 适配器类型

```python
import asyncio

from astrbot import logger
from astrbot.api.event import MessageChain
from astrbot.api.message_components import Plain
from astrbot.api.platform import (
    AstrBotMessage,
    MessageMember,
    MessageType,
    Platform,
    PlatformMetadata,
    register_platform_adapter,
)

from .client import FakeClient
from .fake_platform_event import FakePlatformEvent


@register_platform_adapter(
    "fake",
    "Fake platform adapter",
    default_config_tmpl={
        "id": "fake",
        "enable": False,
        "token": "",
    },
)
class FakePlatformAdapter(Platform):
    def __init__(
        self,
        platform_config: dict,
        platform_settings: dict,
        event_queue: asyncio.Queue,
    ) -> None:
        super().__init__(platform_config, event_queue)
        self.settings = platform_settings
        self.client = FakeClient(token=str(platform_config.get("token", "")))
        self.metadata = PlatformMetadata(
            name="fake",
            description="Fake platform adapter",
            id=str(platform_config.get("id", "fake")),
            adapter_display_name="Fake Platform",
            support_streaming_message=False,
            support_proactive_message=True,
        )

    def meta(self) -> PlatformMetadata:
        return self.metadata

    async def run(self) -> None:
        async def on_message(data: dict) -> None:
            try:
                message = self.convert_message(data)
                event = FakePlatformEvent(
                    message_str=message.message_str,
                    message_obj=message,
                    platform_meta=self.meta(),
                    session_id=message.session_id,
                    client=self.client,
                )
                if not self.commit_event(event):
                    logger.warning("Fake platform event queue is full")
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Failed to convert Fake platform message")

        await self.client.listen(on_message)

    async def terminate(self) -> None:
        await self.client.close()

    def convert_message(self, data: dict) -> AstrBotMessage:
        sender_id = str(data["user_id"])
        group_id = str(data.get("group_id") or "")
        is_group = bool(group_id)

        message = AstrBotMessage()
        message.type = (
            MessageType.GROUP_MESSAGE if is_group else MessageType.FRIEND_MESSAGE
        )
        message.session_id = group_id if is_group else sender_id
        message.group_id = group_id
        message.message_id = str(data["message_id"])
        message.self_id = str(data["bot_id"])
        message.sender = MessageMember(
            user_id=sender_id,
            nickname=str(data.get("nickname") or sender_id),
        )
        message.message_str = str(data.get("content") or "")
        message.message = [Plain(message.message_str)]
        message.raw_message = data
        return message

    async def send_by_session(self, session, message_chain: MessageChain):
        await self.client.send_chain(session.session_id, message_chain)
        return await super().send_by_session(session, message_chain)
```

### 会话路由不能使用发送者 ID 代替群 ID

`session_id` 是回复和主动消息的目标：

- 私聊使用发送者/私聊会话 ID；
- 群聊使用群、频道或 thread ID，而不是群成员的 sender ID。

事件的 `send()` 也必须使用相同路由。否则入站消息看似正常，回复却会被发成私聊或发给错误对象。如果平台需要更多不可变路由信息，应在平台事件/客户端内部保存并在发送时校验，不要依赖易变化的展示名称。

`send_by_session()` 用于没有原始 event 的主动发送。实际调用 SDK 成功后必须 `return await super().send_by_session(...)`；如果失败，适配器应记录平台错误并返回/抛出可诊断的失败，而不是让父类记录一次虚假的成功。

## 消息组件与媒体

使用公共消息组件构造标准消息链：

```python
from astrbot.api.message_components import Image, Plain, Record, Video

message.message = [
    Plain("文本"),
    Image.fromFileSystem("/tmp/image.png"),
    Record(file="https://example.com/audio.ogg"),
    Video(file="base64://..."),
]
```

组件可保存本地路径、`file:` URI、HTTP(S) URL、`base64://` 或 Data URI。发送端需要本地文件时使用组件的 `convert_to_file_path()`，不要手写各种 URI 前缀解析。

AstrBot 预处理会尽量下载和标准化图片、语音及引用消息媒体。适配器自行创建的临时文件应登记到事件：

```python
event.track_temporary_local_file(temp_path)
```

媒体格式最终仍受平台 SDK 限制。把 AstrBot 组件转换为平台消息时，应明确不支持的组件、大小限制、URL 下载策略和失败结果。

## 能力元数据

`PlatformMetadata` 的 `name`、`description` 和 `id` 都是必填项。`id` 通常来自平台实例配置，必须在多实例之间唯一。

- 未实现原生流式协议时设置 `support_streaming_message=False`；普通分段回复不等于原生流式。
- 只有真正实现 `send_by_session()` 时才声明 `support_proactive_message=True`。
- 平台动作（禁言、踢人、戳一戳等）应覆写对应 `Platform` 方法；`supported_actions` 可由覆写自动推导。
- `adapter_display_name`、`logo_path`、i18n 和配置元数据可改善 WebUI 展示，但不能代替运行时校验。

## 在 Star 中加载

注册装饰器只有在模块被导入后才会执行。插件入口中显式导入适配器：

```python
from astrbot.api.star import PluginContext, Star

from .fake_platform_adapter import FakePlatformAdapter  # noqa: F401


class Main(Star):
    def __init__(self, context: PluginContext) -> None:
        super().__init__(context)
```

所有 Star 和第三方适配器示例都应保持在 `astrbot.api` 边界内。

## NapCat 生成模型

内置 NapCat 的 `generated/ob11_events.py` 来自 schema，不要手改。更新类型定义后执行：

```bash
make napcat-codegen
make napcat-test
make napcat-check
```

`make napcat-check` 会重新生成模型并运行定向测试。手写的连接、事件和出站协议代码仍需普通单元测试覆盖。

## 验证清单

- 私聊、群聊和 thread 的 `session_id` 都能正确回复；
- `send()` 与 `send_by_session()` 都进行真实 SDK 调用并返回逻辑发送结果；
- 队列满、连接断开、限流、取消和关闭不会泄漏任务/client；
- 同一适配器多实例使用不同 metadata ID；
- 图片、音频、文件、引用和不支持组件有明确行为；
- 声明的流式、主动消息和平台动作能力都有端到端测试；
- 插件停用/热重载后没有重复回调或旧连接残留。
