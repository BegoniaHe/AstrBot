from dataclasses import dataclass


@dataclass(slots=True)
class PlatformSendResult:
    """Standardized send outcome for platform message delivery."""

    platform_id: str
    success: bool
    target: str
    message_count: int = 0
    error_message: str | None = None
