"""Shared API networking with explicit, user-controlled proxy behavior."""

from urllib.parse import urlparse

import httpx
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    OpenAI,
    PermissionDeniedError,
    RateLimitError,
)


DEFAULT_API_TIMEOUT_SECONDS = 600.0
DEFAULT_CONNECT_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_RETRIES = 2


class NetworkConfigurationError(ValueError):
    """Raised when a user-supplied network setting is invalid."""


def validate_api_proxy(proxy):
    """Return a normalized HTTP(S) proxy URL or an empty string for direct access."""
    normalized = str(proxy or "").strip()
    if not normalized:
        return ""

    parsed = urlparse(normalized)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        raise NetworkConfigurationError(
            "API proxy must be a complete http:// or https:// URL."
        )
    return normalized


def build_http_client(proxy="", timeout=DEFAULT_API_TIMEOUT_SECONDS):
    """Build an HTTP client that ignores inherited proxy environment variables."""
    normalized_proxy = validate_api_proxy(proxy)
    request_timeout = httpx.Timeout(
        float(timeout),
        connect=min(DEFAULT_CONNECT_TIMEOUT_SECONDS, float(timeout)),
    )
    return httpx.Client(
        trust_env=False,
        proxy=normalized_proxy or None,
        timeout=request_timeout,
        follow_redirects=True,
    )


def create_openai_client(
    api_key,
    *,
    base_url=None,
    proxy="",
    timeout=DEFAULT_API_TIMEOUT_SECONDS,
    max_retries=DEFAULT_MAX_RETRIES,
):
    """Create an OpenAI-compatible client with consistent retries and proxy handling."""
    options = {
        "api_key": api_key,
        "http_client": build_http_client(proxy=proxy, timeout=timeout),
        "max_retries": int(max_retries),
    }
    if base_url:
        options["base_url"] = base_url
    return OpenAI(**options)


def describe_api_error(provider_name, error):
    """Convert SDK exceptions into actionable messages without exposing secrets."""
    if isinstance(error, APITimeoutError):
        return f"{provider_name} request timed out. Check your network or API proxy setting."
    if isinstance(error, APIConnectionError):
        return f"{provider_name} connection failed. Check your network or API proxy setting."
    if isinstance(error, AuthenticationError):
        return f"{provider_name} authentication failed. Check the API key."
    if isinstance(error, PermissionDeniedError):
        return f"{provider_name} denied this request. Check account and model permissions."
    if isinstance(error, RateLimitError):
        return f"{provider_name} rate limit or quota was exceeded. Try again later."
    if isinstance(error, APIStatusError):
        return f"{provider_name} API returned HTTP {error.status_code}."
    return f"{provider_name} API request failed: {error}"
