from typing import Any

from fastapi.responses import JSONResponse

from astrbot.core.utils.error_redaction import safe_error
from astrbot.dashboard.responses import INTERNAL_SERVER_ERROR_MESSAGE, error


def internal_error_response(
    logger: Any,
    context: str,
    exc: Exception,
) -> JSONResponse:
    """Log an unexpected API failure safely and return a stable envelope."""
    logger.error("%s: %s", context, safe_error("", exc))
    return JSONResponse(
        error(INTERNAL_SERVER_ERROR_MESSAGE),
        status_code=500,
    )
