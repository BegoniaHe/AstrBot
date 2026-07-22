from dataclasses import dataclass
from typing import Any

INTERNAL_SERVER_ERROR_MESSAGE = "Internal server error"


@dataclass
class ApiError(Exception):
    message: str
    status_code: int = 400
    data: Any = None


class DashboardValidationError(ValueError):
    """A deliberate Dashboard validation failure that is safe to disclose."""


def ok(data: Any = None, message: str | None = None) -> dict[str, Any]:
    return {"status": "ok", "message": message, "data": {} if data is None else data}


def error(message: str, data: Any = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"status": "error", "message": message}
    if data is not None:
        payload["data"] = data
    return payload
