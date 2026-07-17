import re
from pathlib import Path


class StaticFileService:
    PLUGIN_UI_PROTOCOL_VERSION = 1
    PLUGIN_UI_PROTOCOL_RELATIVE_PATH = Path("assets/plugin-ui-protocol")
    INDEX_ROUTES = (
        "/",
        "/auth/login",
        "/config",
        "/logs",
        "/extension",
        "/dashboard/default",
        "/console",
        "/chat",
        "/settings",
        "/platforms",
        "/providers",
        "/about",
        "/extension-marketplace",
        "/conversation",
        "/tool-use",
    )
    DYNAMIC_INDEX_ROUTES = (
        "/extension/{extension_id}/pages/{page_id}",
        "/extension/{plugin_name}",
    )
    _DYNAMIC_INDEX_PATTERNS = (
        re.compile(
            r"^/extension/[a-z0-9](?:[a-z0-9.-]{1,126}[a-z0-9])/pages/"
            r"[a-z][a-z0-9-]{0,47}$"
        ),
        re.compile(r"^/extension/[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$"),
    )
    NOT_FOUND_MESSAGE = (
        "404 Not found。如果你初次使用打开面板发现 404, 请参考文档: "
        "https://docs.astrbot.app/faq.html。如果你正在测试回调地址可达性，"
        "显示这段文字说明测试成功了。"
    )

    def list_index_routes(self) -> tuple[str, ...]:
        return self.INDEX_ROUTES

    def list_dynamic_index_routes(self) -> tuple[str, ...]:
        return self.DYNAMIC_INDEX_ROUTES

    def matches_dynamic_index_route(self, path: str) -> bool:
        return any(pattern.fullmatch(path) for pattern in self._DYNAMIC_INDEX_PATTERNS)

    def get_not_found_message(self) -> str:
        return self.NOT_FOUND_MESSAGE

    def resolve_index_file(self, static_folder: str | Path | None) -> Path | None:
        if not static_folder:
            return None
        index_file = Path(static_folder) / "index.html"
        if index_file.is_file():
            return index_file
        return None

    def get_plugin_ui_protocol_version(
        self,
        static_folder: str | Path | None,
    ) -> int | None:
        if not static_folder:
            return None
        protocol_file = Path(static_folder) / self.PLUGIN_UI_PROTOCOL_RELATIVE_PATH
        try:
            value = protocol_file.read_text(encoding="utf-8").strip()
            return int(value) if value.isascii() and value.isdecimal() else None
        except OSError:
            return None

    def is_plugin_ui_protocol_compatible(
        self,
        static_folder: str | Path | None,
    ) -> bool:
        return (
            self.get_plugin_ui_protocol_version(static_folder)
            == self.PLUGIN_UI_PROTOCOL_VERSION
        )

    def resolve_static_file(
        self,
        static_folder: str | Path | None,
        requested_path: str,
    ) -> Path | None:
        if not static_folder or not requested_path:
            return None
        if requested_path.startswith("api/"):
            return None
        path_parts = requested_path.replace("\\", "/").split("/")
        if requested_path.startswith(("/", "\\")) or ".." in path_parts:
            return None

        static_root = Path(static_folder).resolve()
        target_file = (static_root / requested_path).resolve()
        try:
            target_file.relative_to(static_root)
        except ValueError:
            return None

        if target_file.is_file():
            return target_file
        return None
