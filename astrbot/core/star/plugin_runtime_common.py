"""Shared values for the instance-owned plugin runtime collaborators.

This module deliberately contains immutable value objects and pure helpers
only.  Mutable plugin state belongs to the catalog, loader, installer, or
lifecycle collaborator created for one :class:`PluginManager` instance.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import tempfile
from dataclasses import dataclass
from enum import Enum, auto

from astrbot import logger
from astrbot.core.utils.astrbot_path import get_astrbot_temp_path
from astrbot.core.utils.pip_installer import DependencyConflictError, PipInstaller
from astrbot.core.utils.requirements_utils import (
    MissingRequirementsPlan,
    plan_missing_requirements_install,
)


class PluginVersionUnsupportedError(Exception):
    """Raised when a plugin does not support the current AstrBot version."""


class PluginDependencyInstallError(Exception):
    """Raised when installing a plugin requirement set fails."""

    def __init__(
        self,
        *,
        plugin_label: str,
        requirements_path: str,
        error: Exception,
    ) -> None:
        super().__init__(f"插件 {plugin_label} 依赖安装失败: {error!s}")
        self.plugin_label = plugin_label
        self.requirements_path = requirements_path
        self.error = error


class ImportDependencyRecoveryMode(Enum):
    """How a plugin import may recover from missing requirements."""

    DISABLED = auto()
    PRELOAD_AND_RECOVER = auto()
    RECOVER_ON_FAILURE = auto()
    REINSTALL_ON_FAILURE = auto()


@dataclass(frozen=True, slots=True)
class ImportDependencyRecoveryState:
    """The requirement recovery decision for a single plugin import."""

    mode: ImportDependencyRecoveryMode
    install_plan: MissingRequirementsPlan | None = None


@contextlib.contextmanager
def temporary_filtered_requirements_file(*, install_lines: tuple[str, ...]):
    """Yield a temporary requirements file containing only missing packages."""
    filtered_requirements_path: str | None = None
    temp_dir = get_astrbot_temp_path()

    try:
        os.makedirs(temp_dir, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix="_plugin_requirements.txt",
            delete=False,
            dir=temp_dir,
            encoding="utf-8",
        ) as filtered_requirements_file:
            filtered_requirements_file.write("\n".join(install_lines) + "\n")
            filtered_requirements_path = filtered_requirements_file.name
        yield filtered_requirements_path
    finally:
        if filtered_requirements_path and os.path.exists(filtered_requirements_path):
            try:
                os.remove(filtered_requirements_path)
            except OSError as exc:
                logger.warning(
                    "删除临时插件依赖文件失败：%s（路径：%s）",
                    exc,
                    filtered_requirements_path,
                )


async def install_requirements_with_precheck(
    *,
    plugin_label: str,
    requirements_path: str,
    pip_installer: PipInstaller,
) -> None:
    """Install only unsatisfied plugin requirements when safely possible."""
    install_plan = plan_missing_requirements_install(requirements_path)

    if install_plan is None:
        logger.info(
            "正在安装插件 %s 的依赖库（缺失依赖预检查不可裁剪，回退到完整安装）: %s",
            plugin_label,
            requirements_path,
        )
        await pip_installer.install(requirements_path=requirements_path)
        return

    if not install_plan.missing_names:
        logger.info("插件 %s 的依赖已满足，跳过安装。", plugin_label)
        return

    if not install_plan.install_lines:
        fallback_reason = install_plan.fallback_reason or "unknown reason"
        logger.info(
            "检测到插件 %s 缺失依赖，但无法安全裁剪 requirements，回退到完整安装: %s (%s)",
            plugin_label,
            requirements_path,
            fallback_reason,
        )
        await pip_installer.install(
            requirements_path=requirements_path,
            allow_target_upgrade=bool(install_plan.version_mismatch_names),
        )
        return

    logger.info(
        "检测到插件 %s 缺失依赖，正在按 requirements.txt 安装: %s -> %s",
        plugin_label,
        requirements_path,
        sorted(install_plan.missing_names),
    )
    with temporary_filtered_requirements_file(
        install_lines=install_plan.install_lines,
    ) as filtered_requirements_path:
        await pip_installer.install(
            requirements_path=filtered_requirements_path,
            allow_target_upgrade=bool(install_plan.version_mismatch_names),
        )


async def ensure_plugin_requirements(
    *,
    plugin_dir_path: str,
    plugin_label: str,
    pip_installer: PipInstaller,
) -> None:
    """Install requirements for one plugin, preserving cancellation semantics."""
    requirements_path = os.path.join(plugin_dir_path, "requirements.txt")
    if not os.path.exists(requirements_path):
        return

    try:
        await install_requirements_with_precheck(
            plugin_label=plugin_label,
            requirements_path=requirements_path,
            pip_installer=pip_installer,
        )
    except asyncio.CancelledError:
        raise
    except DependencyConflictError:
        logger.exception("插件 %s 依赖冲突", plugin_label)
        raise
    except Exception as exc:
        dependency_error = PluginDependencyInstallError(
            plugin_label=plugin_label,
            requirements_path=requirements_path,
            error=exc,
        )
        logger.exception(str(dependency_error))
        raise dependency_error from exc
