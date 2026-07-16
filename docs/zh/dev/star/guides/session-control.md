# 会话控制

会话控制适合需要连续多轮输入、但不需要把每一步都交给 LLM 的插件，例如问卷、游戏
或分步配置流程。

公开 SDK 从 `astrbot.api.util` 导出 `session_waiter` 和
`SessionController`：

```python
import astrbot.api.message_components as Comp
from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.util import SessionController, session_waiter
```

下面的示例在收到 `/成语接龙` 后等待同一会话中的后续消息：

```python
@filter.command("成语接龙")
async def idiom_chain(self, event: AstrMessageEvent):
    yield event.plain_result("请发送一个四字成语，发送“退出”结束。")

    @session_waiter(timeout=60, record_history_chains=False)
    async def waiter(
        controller: SessionController,
        next_event: AstrMessageEvent,
    ) -> None:
        idiom = next_event.message_str.strip()

        if idiom == "退出":
            await next_event.send(next_event.plain_result("已退出成语接龙。").chain)
            controller.stop()
            return

        if len(idiom) != 4:
            await next_event.send(
                next_event.plain_result("成语必须是四个字，请重新输入。").chain
            )
            controller.keep(timeout=60, reset_timeout=True)
            return

        result = next_event.make_result()
        result.chain = [Comp.Plain("先见之明")]
        await next_event.send(result.chain)

        # 继续等待下一条消息，并把超时时间重新设为 60 秒。
        controller.keep(timeout=60, reset_timeout=True)

    try:
        await waiter(event)
    except TimeoutError:
        yield event.plain_result("会话已超时。")
    except Exception:
        logger.exception("Idiom-chain session failed")
        yield event.plain_result("会话异常结束，请联系管理员。")
    finally:
        event.stop_event()
```

等待器内部已经在处理后续事件，不能在其中使用 `yield`；请调用
`await next_event.send(...)` 发送结果。`await waiter(event)` 会一直等待，直到
`controller.stop()`、超时或处理器抛出异常。

## 默认会话键

默认会话过滤器使用 `event.unified_msg_origin` 作为会话键，而不是只使用
`sender_id`。该字符串标识具体平台实例和对应会话；只有产生相同
`unified_msg_origin` 的后续事件才会进入当前等待器。

`SessionFilter` 等内部扩展类型没有从 `astrbot.api.util` 公开导出。插件不要为了
自定义会话键而导入 `astrbot.core.utils.session_waiter`；内部接口可能随核心实现
调整。

## SessionController

- `keep(timeout, reset_timeout=True)`：继续等待，并从现在开始重置为指定超时。
- `keep(timeout, reset_timeout=False)`：在当前剩余时间上增减 `timeout`；结果小于
  等于零时结束会话。
- `stop()`：立即结束会话。
- `get_history_chains()`：返回已记录的历史消息链。仅当装饰器设置
  `record_history_chains=True` 时才会记录后续输入。

等待超时后，`await waiter(event)` 会抛出 `TimeoutError`。始终在外层处理超时和
异常，并在插件 `terminate()` 中停止插件自行创建的其他长期任务。
