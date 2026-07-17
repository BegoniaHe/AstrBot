"""Dashboard Extension Protocol v1 Page sessions and public bundles."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import html
import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import quote

from astrbot.core.star.dashboard_extension import (
    DashboardExtensionLifecycleEvent,
    DashboardExtensionRegistry,
    DashboardExtensionSnapshot,
    DashboardExtensionState,
    DashboardLifecycleEventKind,
    DashboardPageAsset,
    DashboardPageManifest,
)
from astrbot.dashboard.responses import ApiError
from astrbot.dashboard.services.auth_service import (
    DashboardSessionPrincipal,
    derive_dashboard_secret,
)

PAGE_SESSION_COOKIE_NAME = "astrbot_plugin_page"
PAGE_SESSION_IDLE_TTL = timedelta(hours=2)
PAGE_SESSION_ABSOLUTE_TTL = timedelta(hours=12)
PAGE_SESSION_MAX_PER_USER = 32
PAGE_SESSION_MAX_GLOBAL = 512
PAGE_SESSION_SECRET_PURPOSE = b"dashboard-plugin-page-session-secret-v1"


class RawPageError(Exception):
    """Minimal raw Page protocol failure."""

    def __init__(self, status_code: int) -> None:
        super().__init__("Page resource unavailable")
        self.status_code = status_code


@dataclass(frozen=True)
class CreatedPageSession:
    data: dict[str, object]
    cookie_secret: str
    cookie_path: str
    cookie_max_age: int


@dataclass(frozen=True)
class PageInstance:
    instance_id: str
    auth_session_id: str
    username: str
    extension_id: str
    page: DashboardPageManifest
    generation: str
    expires_at: datetime


@dataclass(frozen=True)
class BundleAsset:
    path: Path
    content_type: str
    size: int


@dataclass
class _PageSessionRecord:
    handle: str
    secret_hash: bytes
    instance_id: str
    auth_session_id: str
    username: str
    extension_id: str
    page_id: str
    generation: str
    created_at: datetime
    last_accessed_at: datetime
    expires_at: datetime


def build_page_bundle_id(page: DashboardPageManifest) -> str:
    """Build the protocol-defined content address for one Page manifest."""
    canonical = [
        {"path": asset.path, "sha256": asset.sha256, "size": asset.size}
        for asset in sorted(page.assets.values(), key=lambda item: item.path)
    ]
    encoded = json.dumps(
        canonical,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _hash_file(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        while chunk := handle.read(128 * 1024):
            size += len(chunk)
            digest.update(chunk)
    return size, digest.hexdigest()


class PluginPageSessionService:
    """Own short-lived authenticated Shell sessions and public Page bundles."""

    def __init__(
        self,
        registry: DashboardExtensionRegistry,
        jwt_secret: str,
    ) -> None:
        self.registry = registry
        self._secret_key = derive_dashboard_secret(
            jwt_secret,
            PAGE_SESSION_SECRET_PURPOSE,
        )
        self._sessions: dict[str, _PageSessionRecord] = {}
        self._handle_by_instance: dict[str, str] = {}
        self._lock = asyncio.Lock()
        self._unsubscribe = registry.subscribe(self._on_registry_event)
        self._sdk = (
            Path(__file__).resolve().parents[1] / "plugin_page_sdk.js"
        ).read_bytes()
        self.sdk_digest = hashlib.sha256(self._sdk).hexdigest()
        self.sdk_path = f"/api/plugin-pages/v1/sdk.{self.sdk_digest}.js"

    @property
    def sdk_bytes(self) -> bytes:
        return self._sdk

    def _digest_secret(self, secret: str) -> bytes:
        return hmac.new(self._secret_key, secret.encode(), hashlib.sha256).digest()

    @staticmethod
    def _page(
        snapshot: DashboardExtensionSnapshot, page_id: str
    ) -> DashboardPageManifest:
        for page in snapshot.pages:
            if page.id == page_id:
                return page
        raise ApiError("Not found", status_code=404)

    def _active_snapshot(self, extension_id: str) -> DashboardExtensionSnapshot:
        record = self.registry.get_record(extension_id)
        if record is None:
            raise ApiError("Not found", status_code=404)
        state, snapshot = record
        if state is DashboardExtensionState.DRAINING:
            raise ApiError("Plugin temporarily unavailable", status_code=503)
        if state is not DashboardExtensionState.ACTIVE:
            raise ApiError("Not found", status_code=404)
        return snapshot

    async def create_session(
        self,
        extension_id: str,
        page_id: str,
        expected_generation: str,
        principal: DashboardSessionPrincipal,
    ) -> CreatedPageSession:
        snapshot = self._active_snapshot(extension_id)
        if snapshot.generation != expected_generation:
            raise ApiError("Plugin generation changed", status_code=409)
        self._page(snapshot, page_id)
        now = datetime.now(UTC)
        handle = secrets.token_urlsafe(48)
        secret = secrets.token_urlsafe(48)
        instance_id = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32)
        expires_at = now + PAGE_SESSION_ABSOLUTE_TTL
        record = _PageSessionRecord(
            handle=handle,
            secret_hash=self._digest_secret(secret),
            instance_id=instance_id,
            auth_session_id=principal.sid,
            username=principal.username,
            extension_id=extension_id,
            page_id=page_id,
            generation=snapshot.generation,
            created_at=now,
            last_accessed_at=now,
            expires_at=expires_at,
        )
        async with self._lock:
            self._purge_expired_locked(now)
            owned = sorted(
                (
                    item
                    for item in self._sessions.values()
                    if item.username == principal.username
                ),
                key=lambda item: item.last_accessed_at,
            )
            while len(owned) >= PAGE_SESSION_MAX_PER_USER:
                self._remove_locked(owned.pop(0).handle)
            while len(self._sessions) >= PAGE_SESSION_MAX_GLOBAL:
                oldest = min(
                    self._sessions.values(),
                    key=lambda item: item.last_accessed_at,
                )
                self._remove_locked(oldest.handle)
            self._sessions[handle] = record
            self._handle_by_instance[instance_id] = handle
        path = f"/api/plugin-pages/v1/sessions/{handle}/"
        return CreatedPageSession(
            data={
                "protocol_version": 1,
                "instance_id": instance_id,
                "plugin_generation": snapshot.generation,
                "iframe_url": path,
                "handshake_nonce": nonce,
                "expires_at": expires_at.isoformat().replace("+00:00", "Z"),
            },
            cookie_secret=secret,
            cookie_path=path,
            cookie_max_age=int(PAGE_SESSION_ABSOLUTE_TTL.total_seconds()),
        )

    async def get_instance(
        self,
        instance_id: str,
        extension_id: str,
        expected_generation: str,
        principal: DashboardSessionPrincipal,
    ) -> PageInstance:
        snapshot = self._active_snapshot(extension_id)
        now = datetime.now(UTC)
        async with self._lock:
            self._purge_expired_locked(now)
            handle = self._handle_by_instance.get(instance_id)
            record = self._sessions.get(handle or "")
            if (
                record is None
                or record.auth_session_id != principal.sid
                or record.username != principal.username
                or record.extension_id != extension_id
            ):
                raise ApiError("Plugin instance mismatch", status_code=409)
            if (
                record.generation != expected_generation
                or snapshot.generation != expected_generation
            ):
                raise ApiError("Plugin generation changed", status_code=409)
            record.last_accessed_at = now
            page_id = record.page_id
            expires_at = record.expires_at
        return PageInstance(
            instance_id=instance_id,
            auth_session_id=principal.sid,
            username=principal.username,
            extension_id=extension_id,
            page=self._page(snapshot, page_id),
            generation=snapshot.generation,
            expires_at=expires_at,
        )

    async def render_shell(
        self,
        handle: str,
        cookie_secret: str | None,
        dashboard_origin: str,
    ) -> bytes:
        if not cookie_secret:
            raise RawPageError(401)
        now = datetime.now(UTC)
        async with self._lock:
            self._purge_expired_locked(now)
            record = self._sessions.get(handle)
            if record is None or not hmac.compare_digest(
                record.secret_hash,
                self._digest_secret(cookie_secret),
            ):
                raise RawPageError(404)
            snapshot = self.registry.get_snapshot(record.extension_id)
            if snapshot is None or snapshot.generation != record.generation:
                self._remove_locked(handle)
                raise RawPageError(404)
            record.last_accessed_at = now
            page = self._page(snapshot, record.page_id)
        bundle_id = build_page_bundle_id(page)
        bundle_prefix = f"/api/plugin-pages/v1/bundles/{bundle_id}/"
        styles = "\n".join(
            '    <link rel="stylesheet" '
            f'href="{html.escape(bundle_prefix + quote(style, safe="/"))}" '
            'crossorigin="anonymous" />'
            for style in page.styles
        )
        module_url = html.escape(bundle_prefix + quote(page.module, safe="/"))
        return (
            "<!doctype html>\n"
            '<html lang="en" data-theme="dark">\n'
            "  <head>\n"
            '    <meta charset="utf-8" />\n'
            '    <meta name="viewport" content="width=device-width, initial-scale=1" />\n'
            '    <meta name="color-scheme" content="dark" />\n'
            f"{styles}\n"
            "  </head>\n"
            "  <body>\n"
            '    <div id="astrbot-plugin-root"></div>\n'
            f'    <script src="{html.escape(self.sdk_path)}"></script>\n'
            f'    <script type="module" src="{module_url}" '
            'crossorigin="anonymous"></script>\n'
            "  </body>\n"
            "</html>\n"
        ).encode()

    def content_security_policy(self, dashboard_origin: str, bundle_id: str) -> str:
        sdk_source = f"{dashboard_origin}{self.sdk_path}"
        asset_source = f"{dashboard_origin}/api/plugin-pages/v1/bundles/{bundle_id}/"
        return "; ".join(
            (
                "sandbox allow-scripts",
                "default-src 'none'",
                f"script-src {sdk_source} {asset_source}",
                f"style-src {asset_source}",
                f"img-src {asset_source} data: blob:",
                f"font-src {asset_source} data:",
                f"media-src {asset_source} blob:",
                "connect-src 'none'",
                "object-src 'none'",
                "base-uri 'none'",
                "frame-src 'none'",
                "form-action 'none'",
                "navigate-to 'none'",
                "frame-ancestors 'self'",
                "worker-src 'none'",
            )
        )

    async def bundle_id_for_session(self, handle: str) -> str:
        async with self._lock:
            record = self._sessions.get(handle)
            if record is None:
                raise RawPageError(404)
            snapshot = self.registry.get_snapshot(record.extension_id)
            if snapshot is None or snapshot.generation != record.generation:
                raise RawPageError(404)
            page = self._page(snapshot, record.page_id)
        return build_page_bundle_id(page)

    async def resolve_bundle_asset(
        self, bundle_id: str, asset_path: str
    ) -> BundleAsset:
        if len(bundle_id) != 64 or any(
            ch not in "0123456789abcdef" for ch in bundle_id
        ):
            raise RawPageError(404)
        if (
            not asset_path
            or "\\" in asset_path
            or "\x00" in asset_path
            or any(part in {"", ".", ".."} for part in asset_path.split("/"))
        ):
            raise RawPageError(404)
        selected: tuple[DashboardExtensionSnapshot, DashboardPageAsset] | None = None
        for snapshot in self.registry.snapshots():
            for page in snapshot.pages:
                if build_page_bundle_id(page) != bundle_id:
                    continue
                asset = page.assets.get(asset_path)
                if asset is not None:
                    selected = snapshot, asset
                    break
            if selected is not None:
                break
        if selected is None:
            raise RawPageError(404)
        snapshot, asset = selected
        try:
            root = snapshot.plugin_root.resolve(strict=True)
            resolved = asset.resolved_path.resolve(strict=True)
            if not resolved.is_relative_to(root) or not resolved.is_file():
                raise OSError
            size, digest = await asyncio.to_thread(_hash_file, resolved)
        except OSError as exc:
            raise RawPageError(404) from exc
        if size != asset.size or digest != asset.sha256:
            raise RawPageError(404)
        return BundleAsset(path=resolved, content_type=asset.content_type, size=size)

    async def revoke_by_auth_session_id(self, auth_session_id: str) -> None:
        async with self._lock:
            for handle, record in tuple(self._sessions.items()):
                if record.auth_session_id == auth_session_id:
                    self._remove_locked(handle)

    async def revoke_generation(self, extension_id: str, generation: str) -> None:
        async with self._lock:
            for handle, record in tuple(self._sessions.items()):
                if (
                    record.extension_id == extension_id
                    and record.generation == generation
                ):
                    self._remove_locked(handle)

    async def _on_registry_event(
        self,
        event: DashboardExtensionLifecycleEvent,
    ) -> None:
        if event.kind in {
            DashboardLifecycleEventKind.DRAINING,
            DashboardLifecycleEventKind.INACTIVE,
        }:
            await self.revoke_generation(event.extension_id, event.generation)

    def _purge_expired_locked(self, now: datetime) -> None:
        for handle, record in tuple(self._sessions.items()):
            if (
                record.expires_at <= now
                or record.last_accessed_at + PAGE_SESSION_IDLE_TTL <= now
            ):
                self._remove_locked(handle)

    def _remove_locked(self, handle: str) -> None:
        record = self._sessions.pop(handle, None)
        if record is not None:
            self._handle_by_instance.pop(record.instance_id, None)

    async def shutdown(self) -> None:
        self._unsubscribe()
        async with self._lock:
            self._sessions.clear()
            self._handle_by_instance.clear()
