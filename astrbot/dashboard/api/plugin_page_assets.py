"""Raw Dashboard Extension Protocol v1 Shell, SDK, and bundle routes."""

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, Response

from astrbot.dashboard.services.plugin_page_session_service import (
    PAGE_SESSION_COOKIE_NAME,
    PluginPageSessionService,
    RawPageError,
)

from .auth import request_external_origin

router = APIRouter(include_in_schema=False)


def _service(request: Request) -> PluginPageSessionService:
    return request.app.state.services.plugin_page_sessions


def _raw_error(status_code: int) -> Response:
    message = b"Unauthorized" if status_code == 401 else b"Not found"
    return Response(
        message,
        status_code=status_code,
        media_type="text/plain",
        headers={"Cache-Control": "no-store"},
    )


def _has_forbidden_credentials(request: Request) -> bool:
    return bool(
        request.headers.get("authorization")
        or request.headers.get("x-api-key")
        or request.query_params
    )


@router.get("/api/plugin-pages/v1/sdk.{content_hash}.js")
async def get_plugin_page_sdk(content_hash: str, request: Request):
    service = _service(request)
    if content_hash != service.sdk_digest:
        return _raw_error(404)
    return Response(
        service.sdk_bytes,
        media_type="application/javascript",
        headers={
            "Cache-Control": "public, max-age=31536000, immutable",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/api/plugin-pages/v1/sessions/{session_handle}/")
async def get_plugin_page_shell(session_handle: str, request: Request):
    if _has_forbidden_credentials(request):
        return _raw_error(401)
    origin = request_external_origin(request)
    if origin is None:
        return _raw_error(404)
    service = _service(request)
    try:
        body = await service.render_shell(
            session_handle,
            request.cookies.get(PAGE_SESSION_COOKIE_NAME),
            origin,
        )
        bundle_id = await service.bundle_id_for_session(session_handle)
    except RawPageError as exc:
        return _raw_error(exc.status_code)
    return Response(
        body,
        media_type="text/html",
        headers={
            "Content-Security-Policy": service.content_security_policy(
                origin,
                bundle_id,
            ),
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
            "Permissions-Policy": (
                "camera=(), microphone=(), geolocation=(), payment=(), "
                "usb=(), serial=(), bluetooth=()"
            ),
            "Cache-Control": "private, no-store",
        },
    )


@router.get("/api/plugin-pages/v1/bundles/{bundle_id}/{asset_path:path}")
async def get_plugin_page_bundle_asset(
    bundle_id: str,
    asset_path: str,
    request: Request,
):
    if request.headers.get("cookie") or _has_forbidden_credentials(request):
        return _raw_error(403)
    dashboard_origin = request_external_origin(request)
    if dashboard_origin is None:
        return _raw_error(404)
    origin = request.headers.get("origin")
    if origin not in {None, "null", dashboard_origin}:
        return _raw_error(403)
    try:
        asset = await _service(request).resolve_bundle_asset(bundle_id, asset_path)
    except RawPageError as exc:
        return _raw_error(exc.status_code)
    return FileResponse(
        asset.path,
        media_type=asset.content_type,
        headers={
            "Access-Control-Allow-Origin": origin or "null",
            "Vary": "Origin",
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "public, max-age=31536000, immutable",
        },
    )
