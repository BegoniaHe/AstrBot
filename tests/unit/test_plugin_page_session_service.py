import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict

import astrbot.dashboard.services.plugin_page_session_service as session_module
from astrbot.core.star.dashboard_extension import (
    DashboardExtensionRegistry,
    DashboardJsonAction,
    validate_dashboard_manifest,
)
from astrbot.core.star.star import StarMetadata
from astrbot.dashboard.responses import ApiError
from astrbot.dashboard.services.auth_service import DashboardSessionPrincipal
from astrbot.dashboard.services.plugin_page_session_service import (
    PluginPageSessionService,
    RawPageError,
    build_page_bundle_id,
)


class EmptyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Result(BaseModel):
    ok: bool


async def _handler(_payload, _context):
    return Result(ok=True)


def _write(root: Path, relative: str, content: bytes) -> dict:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return {
        "path": relative,
        "sha256": hashlib.sha256(content).hexdigest(),
        "size": len(content),
    }


async def _registry(tmp_path: Path):
    files = [
        _write(tmp_path, "pages/settings/app.js", b"export default 1;\n"),
        _write(tmp_path, "pages/settings/style.css", b"body { color: red; }\n"),
        _write(tmp_path, "pages/settings/pixel.png", b"\x89PNG\r\n\x1a\nfixture"),
    ]
    manifest_path = tmp_path / "pages/settings/assets.v1.json"
    manifest_path.write_text(json.dumps({"version": 1, "files": files}))
    manifest = validate_dashboard_manifest(
        {
            "name": "astrbot_plugin_palette",
            "requires": {"dashboard_extension": 1},
            "dashboard": {
                "extension_id": "io.github.example.palette",
                "pages": [
                    {
                        "id": "settings",
                        "title": "Settings",
                        "module": "pages/settings/app.js",
                        "assets_manifest": "pages/settings/assets.v1.json",
                        "styles": ["pages/settings/style.css"],
                        "actions": ["config.read"],
                    }
                ],
            },
        },
        tmp_path,
    )
    owner = object()
    metadata = StarMetadata(
        name="astrbot_plugin_palette",
        root_dir_name="astrbot_plugin_palette",
        star_cls=owner,  # type: ignore[arg-type]
        dashboard=manifest,
        dashboard_root=tmp_path.resolve(),
    )
    registry = DashboardExtensionRegistry()
    registry.begin_registration(metadata, owner)  # type: ignore[arg-type]
    registry.registrar_for(owner).register_json(  # type: ignore[arg-type]
        DashboardJsonAction(
            name="config.read",
            input_model=EmptyRequest,
            output_model=Result,
        ),
        _handler,
    )
    snapshot = await registry.commit_registration(owner)  # type: ignore[arg-type]
    assert snapshot is not None
    return registry, metadata, snapshot


def _principal(sid: str = "sid-one") -> DashboardSessionPrincipal:
    return DashboardSessionPrincipal(username="astrbot", sid=sid, jti=f"jti-{sid}")


@pytest.mark.asyncio
async def test_page_session_requires_handle_and_exact_cookie(tmp_path: Path):
    registry, _metadata, snapshot = await _registry(tmp_path)
    service = PluginPageSessionService(registry, "page-session-test-secret")
    created = await service.create_session(
        snapshot.extension_id,
        "settings",
        snapshot.generation,
        _principal(),
    )
    handle = str(created.data["iframe_url"]).split("/")[-2]

    with pytest.raises(RawPageError) as missing:
        await service.render_shell(handle, None, "https://dashboard.example")
    assert missing.value.status_code == 401
    with pytest.raises(RawPageError) as mismatch:
        await service.render_shell(handle, "wrong", "https://dashboard.example")
    assert mismatch.value.status_code == 404

    shell = await service.render_shell(
        handle,
        created.cookie_secret,
        "https://dashboard.example",
    )
    text = shell.decode()
    assert 'crossorigin="anonymous"' in text
    assert "/api/plugin-pages/v1/bundles/" in text
    assert created.cookie_secret not in text
    assert handle not in text
    record = service._sessions[handle]
    assert record.secret_hash != created.cookie_secret.encode()
    await service.shutdown()


@pytest.mark.asyncio
async def test_page_instance_is_bound_to_sid_extension_and_generation(tmp_path: Path):
    registry, _metadata, snapshot = await _registry(tmp_path)
    service = PluginPageSessionService(registry, "page-session-test-secret")
    created = await service.create_session(
        snapshot.extension_id,
        "settings",
        snapshot.generation,
        _principal(),
    )
    instance_id = str(created.data["instance_id"])

    instance = await service.get_instance(
        instance_id,
        snapshot.extension_id,
        snapshot.generation,
        _principal(),
    )
    assert instance.page.id == "settings"

    with pytest.raises(ApiError) as cross_sid:
        await service.get_instance(
            instance_id,
            snapshot.extension_id,
            snapshot.generation,
            _principal("sid-two"),
        )
    assert cross_sid.value.status_code == 409
    with pytest.raises(ApiError) as stale_generation:
        await service.get_instance(
            instance_id,
            snapshot.extension_id,
            "old-generation",
            _principal(),
        )
    assert stale_generation.value.status_code == 409
    await service.shutdown()


@pytest.mark.asyncio
async def test_bundle_id_is_canonical_and_asset_is_revalidated(tmp_path: Path):
    registry, _metadata, snapshot = await _registry(tmp_path)
    service = PluginPageSessionService(registry, "page-session-test-secret")
    page = snapshot.pages[0]
    bundle_id = build_page_bundle_id(page)
    assert len(bundle_id) == 64
    assert bundle_id == build_page_bundle_id(page)

    asset = await service.resolve_bundle_asset(
        bundle_id,
        "pages/settings/app.js",
    )
    assert asset.content_type in {"text/javascript", "application/javascript"}
    asset.path.write_text("tampered", encoding="utf-8")
    with pytest.raises(RawPageError) as tampered:
        await service.resolve_bundle_asset(bundle_id, "pages/settings/app.js")
    assert tampered.value.status_code == 404
    with pytest.raises(RawPageError):
        await service.resolve_bundle_asset(bundle_id, "../app.js")
    await service.shutdown()


@pytest.mark.asyncio
async def test_session_idle_expiry_and_logout_revocation(tmp_path: Path):
    registry, _metadata, snapshot = await _registry(tmp_path)
    service = PluginPageSessionService(registry, "page-session-test-secret")
    first = await service.create_session(
        snapshot.extension_id,
        "settings",
        snapshot.generation,
        _principal(),
    )
    first_handle = str(first.data["iframe_url"]).split("/")[-2]
    service._sessions[first_handle].last_accessed_at = datetime.now(UTC) - timedelta(
        hours=3
    )
    second = await service.create_session(
        snapshot.extension_id,
        "settings",
        snapshot.generation,
        _principal(),
    )
    assert first_handle not in service._sessions
    await service.revoke_by_auth_session_id("sid-one")
    assert not service._sessions
    assert str(second.data["instance_id"]) not in service._handle_by_instance
    await service.shutdown()


@pytest.mark.asyncio
async def test_registry_draining_revokes_page_sessions(tmp_path: Path):
    registry, metadata, snapshot = await _registry(tmp_path)
    service = PluginPageSessionService(registry, "page-session-test-secret")
    created = await service.create_session(
        snapshot.extension_id,
        "settings",
        snapshot.generation,
        _principal(),
    )
    await registry.deactivate(metadata, reason="reload")
    assert not service._sessions
    with pytest.raises(RawPageError):
        await service.render_shell(
            str(created.data["iframe_url"]).split("/")[-2],
            created.cookie_secret,
            "https://dashboard.example",
        )
    await service.shutdown()


@pytest.mark.asyncio
async def test_session_caps_evict_least_recently_used(tmp_path: Path, monkeypatch):
    registry, _metadata, snapshot = await _registry(tmp_path)
    monkeypatch.setattr(session_module, "PAGE_SESSION_MAX_PER_USER", 2)
    service = PluginPageSessionService(registry, "page-session-test-secret")
    created = []
    for _index in range(3):
        created.append(
            await service.create_session(
                snapshot.extension_id,
                "settings",
                snapshot.generation,
                _principal(),
            )
        )
    first_handle = str(created[0].data["iframe_url"]).split("/")[-2]
    assert first_handle not in service._sessions
    assert len(service._sessions) == 2
    await service.shutdown()
