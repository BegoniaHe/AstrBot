from astrbot import logger
from astrbot.api import star
from astrbot.api.event import AstrMessageEvent, MessageEventResult


class PluginCommands:
    def __init__(self, context: star.PluginContext) -> None:
        self.context = context

    async def list_plugins(self, event: AstrMessageEvent) -> None:
        """List loaded plugins."""
        parts = ["Loaded plugins:\n"]
        for plugin in self.context.runtime_info.plugins():
            line = f"- `{plugin.name}` by {plugin.author}: {plugin.description}"
            if not plugin.active:
                line += " (disabled)"
            parts.append(line + "\n")

        if len(parts) == 1:
            plugin_list_info = "No plugins are currently loaded."
        else:
            plugin_list_info = "".join(parts)

        plugin_list_info += (
            "\nUse /plugin show <plugin> to inspect commands.\n"
            "Use /plugin enable <plugin> or /plugin disable <plugin> to change its state."
        )
        event.set_result(
            MessageEventResult().message(plugin_list_info).use_t2i(False),
        )

    async def disable(self, event: AstrMessageEvent, plugin_name: str) -> None:
        """Disable a plugin."""
        if self.context.runtime_info.demo_mode:
            event.set_result(
                MessageEventResult().message("Cannot disable plugins in demo mode."),
            )
            return
        try:
            await self.context.runtime_info.disable_plugin(plugin_name)
        except RuntimeError:
            event.set_result(
                MessageEventResult().message("Plugin manager is not available."),
            )
            return
        event.set_result(
            MessageEventResult().message(f"✅ Plugin `{plugin_name}` disabled."),
        )

    async def enable(self, event: AstrMessageEvent, plugin_name: str) -> None:
        """Enable a plugin."""
        if self.context.runtime_info.demo_mode:
            event.set_result(
                MessageEventResult().message("Cannot enable plugins in demo mode."),
            )
            return
        try:
            await self.context.runtime_info.enable_plugin(plugin_name)
        except RuntimeError:
            event.set_result(
                MessageEventResult().message("Plugin manager is not available."),
            )
            return
        event.set_result(
            MessageEventResult().message(f"✅ Plugin `{plugin_name}` enabled."),
        )

    async def install(self, event: AstrMessageEvent, plugin_repo: str) -> None:
        """Install a plugin from a repo URL."""
        if self.context.runtime_info.demo_mode:
            event.set_result(
                MessageEventResult().message("Cannot install plugins in demo mode."),
            )
            return
        logger.info("Preparing to install plugin from %s", plugin_repo)
        try:
            await self.context.runtime_info.install_plugin(plugin_repo)
        except RuntimeError:
            event.set_result(
                MessageEventResult().message("Plugin manager is not available."),
            )
            return
        except Exception as exc:
            logger.error("Plugin installation failed: %s", exc)
            event.set_result(
                MessageEventResult().message(f"❌ Failed to install plugin: {exc}"),
            )
            return

        event.set_result(
            MessageEventResult().message("✅ Plugin installed successfully."),
        )

    async def show(
        self,
        event: AstrMessageEvent,
        plugin_name: str,
    ) -> None:
        """Show plugin metadata and commands."""
        plugin = self.context.runtime_info.plugin(plugin_name)
        if plugin is None:
            event.set_result(MessageEventResult().message("Plugin not found."))
            return

        help_msg = f"\n\nAuthor: {plugin.author}\nVersion: {plugin.version}"
        command_entries = self.context.runtime_info.commands_for_plugin(plugin_name)

        if command_entries:
            parts = ["\n\nCommands:\n"]
            for command in command_entries:
                line = f"- /{command.invocation}"
                if command.description:
                    line += f": {command.description}"
                parts.append(line + "\n")
            parts.append(
                "\nTip: commands are triggered through the configured wake prefix, usually `/`."
            )
            help_msg += "".join(parts)

        event.set_result(
            MessageEventResult()
            .message(
                f"Plugin `{plugin_name}` help:\n{help_msg}\nMore details may be available in the plugin README.",
            )
            .use_t2i(False),
        )
