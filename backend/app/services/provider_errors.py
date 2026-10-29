
import re
from dataclasses import dataclass
from enum import Enum

from groq import APIConnectionError, APIError, APITimeoutError, RateLimitError


class ProviderErrorKind(str, Enum):
    TEMPORARY_RATE_LIMIT = "temporary_rate_limit"
    DAILY_QUOTA_EXHAUSTED = "daily_quota_exhausted"
    TRANSIENT_ERROR = "transient_error"
    PERMANENT_ERROR = "permanent_error"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ProviderErrorDecision:
    kind: ProviderErrorKind
    retry_after_seconds: float | None = None
    message: str = ""


_DELAY_RE = re.compile(
    r"(?:try again|retry)\s+(?:in|after)\s+"
    r"(?:(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|h)(?![a-z]))?\s*"
    r"(?:(\d+(?:\.\d+)?)\s*(?:minutes?|mins?|m)(?![a-z]))?\s*"
    r"(?:(\d+(?:\.\d+)?)\s*(?:seconds?|secs?|s)(?![a-z]))?",
    re.IGNORECASE,
)

_DAILY_MARKERS = (
    "per day",
    "(tpd)",
    "(rpd)",
    "daily limit",
    "daily quota",
)

_MINUTE_MARKERS = (
    "per minute",
    "(tpm)",
    "(rpm)",
)


def _retry_after_seconds(message: str) -> float | None:
    match = _DELAY_RE.search(message)
    if not match:
        return None

    hours, minutes, seconds = match.groups()

    if hours is None and minutes is None and seconds is None:
        return None

    return (
        float(hours or 0) * 3600
        + float(minutes or 0) * 60
        + float(seconds or 0)
    )


def _is_rate_limit(error: Exception) -> bool:
    return (
        isinstance(error, RateLimitError)
        or getattr(error, "status_code", None) == 429
    )


def classify_provider_error(error: Exception) -> ProviderErrorDecision:
    """Classify provider failures conservatively.

    Daily quota delays are informational only, not guaranteed reset times.
   Only explicitly identified per-minute rate limits are eligible for retry.
    """
    message = str(error)
    lowered = message.lower()

    if _is_rate_limit(error):
        if any(marker in lowered for marker in _DAILY_MARKERS):
            return ProviderErrorDecision(
                ProviderErrorKind.DAILY_QUOTA_EXHAUSTED,
                _retry_after_seconds(message),
                message,
            )

        if any(marker in lowered for marker in _MINUTE_MARKERS):
            return ProviderErrorDecision(
                ProviderErrorKind.TEMPORARY_RATE_LIMIT,
                _retry_after_seconds(message),
                message,
            )

        return ProviderErrorDecision(
            ProviderErrorKind.UNKNOWN, None, message
        )

    if isinstance(error, (APIConnectionError, APITimeoutError)):
        return ProviderErrorDecision(
            ProviderErrorKind.TRANSIENT_ERROR, None, message
        )

    if isinstance(error, APIError):
        status = getattr(error, "status_code", None)

        if isinstance(status, int) and (
            status >= 500 or status in (408, 409, 425)
        ):
            return ProviderErrorDecision(
                ProviderErrorKind.TRANSIENT_ERROR, None, message
            )

        if isinstance(status, int) and 400 <= status < 500:
            return ProviderErrorDecision(
                ProviderErrorKind.PERMANENT_ERROR, None, message
            )

        return ProviderErrorDecision(
            ProviderErrorKind.UNKNOWN, None, message
        )

    # Ordinary application errors are not provider quota errors.
    return ProviderErrorDecision(
        ProviderErrorKind.PERMANENT_ERROR, None, message
    )
