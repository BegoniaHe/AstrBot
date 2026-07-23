# 插件存储

## 简单 KV 存储

`Star` 提供按插件隔离的异步 KV 存储，适合少量配置、状态或缓存数据：

```python
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Star


class Main(Star):
    @filter.command("hello")
    async def hello(self, event: AstrMessageEvent):
        await self.put_kv_data("greeted", True)
        greeted = await self.get_kv_data("greeted", False)
        await self.delete_kv_data("greeted")
        yield event.plain_result(f"greeted={greeted}")
```

每个插件有独立命名空间，不需要自行把插件名称拼进键名。

## 文件存储

持久化文件应写入 `data/plugin_data/{plugin_name}/`，不要写入插件源码目录。通过
`PluginContext.storage.data_directory()` 能力可以创建并返回当前插件的绝对数据目录
`Path`：

```python
from astrbot.api.star import Star


class Main(Star):
    async def initialize(self) -> None:
        plugin_data_path = self.context.storage.data_directory()
        cache_path = plugin_data_path / "cache.json"
```

建议从插件模块或插件类方法中调用无参数版本，以便 AstrBot 根据调用方识别插件。
如果代码位于无法自动识别的共享模块，可以显式传入插件名：

```python
plugin_data_path = self.context.storage.data_directory("astrbot_plugin_example")
```

插件更新或重装不会覆盖该目录。插件若创建数据库连接、打开文件或启动后台写入任务，
应在 `terminate()` 中显式关闭或停止相关资源。
