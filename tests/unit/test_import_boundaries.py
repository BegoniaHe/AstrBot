"""Architecture boundary checks for production Python modules."""

import ast
from pathlib import Path

ROOT = Path(__file__).parents[2]
ASTRBOT = ROOT / "astrbot"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    return imported


def _python_files(directory: Path):
    return (path for path in directory.rglob("*.py") if "generated" not in path.parts)


def test_builtin_stars_use_the_plugin_sdk() -> None:
    assert any(
        module == "astrbot.api" or module.startswith("astrbot.api.")
        for path in _python_files(ASTRBOT / "builtin_stars")
        for module in _imports(path)
    )


def test_api_does_not_depend_on_runtime_implementations() -> None:
    forbidden = (
        "astrbot.dashboard",
        "astrbot.core.platform.sources",
        "astrbot.core.provider.sources",
    )
    violations = [
        f"{path.relative_to(ROOT)}: {module}"
        for path in _python_files(ASTRBOT / "api")
        for module in _imports(path)
        if module.startswith(forbidden)
    ]
    assert not violations, "\n".join(violations)


def test_core_generic_modules_do_not_depend_on_source_implementations() -> None:
    forbidden = ("astrbot.core.platform.sources", "astrbot.core.provider.sources")
    excluded = (ASTRBOT / "core" / "platform", ASTRBOT / "core" / "provider")
    violations = [
        f"{path.relative_to(ROOT)}: {module}"
        for path in _python_files(ASTRBOT / "core")
        if not any(path.is_relative_to(directory) for directory in excluded)
        for module in _imports(path)
        if module.startswith(forbidden)
    ]
    assert not violations, "\n".join(violations)
