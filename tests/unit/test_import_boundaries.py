import ast
import importlib
from pathlib import Path

ROOT = Path(__file__).parents[2]


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_import_boundaries_exclude_generated_files() -> None:
    for path in (ROOT / "astrbot").rglob("*.py"):
        if "generated" in path.parts:
            continue
        modules = _imports(path)
        relative = path.relative_to(ROOT).as_posix()
        if relative.startswith("astrbot/api/"):
            assert not any(module.startswith("astrbot.dashboard") for module in modules)
            assert not any(
                ".platform.sources." in module or ".provider.sources." in module
                for module in modules
            )
        if relative.startswith("astrbot/core/"):
            assert not any(
                module == "astrbot.api" or module.startswith("astrbot.api.")
                for module in modules
            )
        if (
            relative.startswith("astrbot/core/")
            and "/platform/sources/" not in relative
            and "/provider/sources/" not in relative
        ):
            assert not any(
                ".platform.sources." in module or ".provider.sources." in module
                for module in modules
            )
        if relative.startswith("astrbot/builtin_stars/"):
            assert not any(
                ".platform.sources." in module or ".provider.sources." in module
                for module in modules
            )


def test_builtin_stars_may_depend_on_the_plugin_sdk() -> None:
    imports = _imports(ROOT / "astrbot" / "builtin_stars" / "astrbot" / "main.py")
    assert "astrbot.api" in imports


def test_public_sdk_and_core_leaf_imports_remain_available() -> None:
    sdk = importlib.import_module("astrbot.api")
    leaf = importlib.import_module("astrbot.core.platform.astr_message_event")

    assert sdk.FunctionTool is not None
    assert leaf.AstrMessageEvent is not None
