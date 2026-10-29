import httpx
import pytest
from groq import APIError, RateLimitError

from app.services.provider_errors import (
    ProviderErrorKind,
    _retry_after_seconds,
    classify_provider_error,
)


# Retry-delay parsing tests — no API calls


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("try again in 1h2m3s.", 3723.0),
        ("try again in 3m55.44s.", 235.44),
        ("try again in 30s", 30.0),
        ("try again in 2 minutes", 120.0),
        ("nothing useful here", None),
    ],
)
def test_retry_after_seconds(message, expected):
    assert _retry_after_seconds(message) == expected


# Ordinary errors must not be mistaken for quota errors


def test_validation_error_mentioning_per_day_is_permanent():
    error = ValueError("recommended intake is 2000 calories per day")

    result = classify_provider_error(error)

    assert result.kind == ProviderErrorKind.PERMANENT_ERROR


def test_daily_quota_rate_limit_is_paused():
    error = RateLimitError(
        "tokens per day (TPD) quota exhausted; try again in 1h2m3s",
        response=httpx.Response(
            429,
            request=httpx.Request(
                "POST", "https://api.example.com"
            ),
        ),
        body=None,
    )

    result = classify_provider_error(error)

    assert result.kind == ProviderErrorKind.DAILY_QUOTA_EXHAUSTED
    assert result.retry_after_seconds == 3723.0

    result = classify_provider_error(error)

    assert result.kind == ProviderErrorKind.DAILY_QUOTA_EXHAUSTED
    assert result.retry_after_seconds == 3723.0


def test_named_per_minute_rate_limit_is_temporary():
    error = RateLimitError(
        "requests per minute (RPM); try again in 30s",
        response=httpx.Response(
            429,
            request=httpx.Request(
                "POST", "https://api.example.com"
            ),
        ),
        body=None,
    )

    result = classify_provider_error(error)

    assert result.kind == ProviderErrorKind.TEMPORARY_RATE_LIMIT
    assert result.retry_after_seconds == 30.0


def test_unrecognized_rate_limit_is_unknown():
    error = RateLimitError(
        "rate limit exceeded",
        response=httpx.Response(
            429,
            request=httpx.Request(
                "POST", "https://api.example.com"
            ),
        ),
        body=None,
    )

    result = classify_provider_error(error)

    assert result.kind == ProviderErrorKind.UNKNOWN

def test_http_429_is_rate_limit_even_if_not_rate_limit_exception():
    error = APIError(
        "rate limit exceeded",
        request=None,
        body=None,
    )
    error.status_code = 429

    result = classify_provider_error(error)

    assert result.kind == ProviderErrorKind.UNKNOWN


def test_validation_error_is_permanent():
    result = classify_provider_error(ValueError("invalid card format"))

    assert result.kind == ProviderErrorKind.PERMANENT_ERROR