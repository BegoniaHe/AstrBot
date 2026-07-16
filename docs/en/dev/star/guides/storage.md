# Plugin Storage

## Simple KV Storage

`Star` provides an asynchronous key-value store isolated per plugin. It is
suited to small configuration values, state, or cached data:

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

Each plugin has its own namespace, so the plugin name does not need to be
embedded in every key.

## File Storage

Persistent files belong under `data/plugin_data/{plugin_name}/`, not in the
plugin source directory. The public `StarTools.get_data_dir()` API creates and
returns the current plugin's absolute data-directory `Path`:

```python
from astrbot.api.star import StarTools

plugin_data_path = StarTools.get_data_dir()
cache_path = plugin_data_path / "cache.json"
```

Call the no-argument form from a plugin module or plugin class method so AstrBot
can identify the calling plugin. Code in a shared module that cannot be
identified automatically may pass the plugin name explicitly:

```python
plugin_data_path = StarTools.get_data_dir("astrbot_plugin_example")
```

Plugin updates and reinstalls do not overwrite this directory. If a plugin
opens database connections or files, or starts background writers, close or
stop those resources explicitly in `terminate()`.
