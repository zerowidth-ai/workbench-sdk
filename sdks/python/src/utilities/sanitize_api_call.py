"""
API call event sanitization for the zv1 engine.
Strips auth credentials from headers and URLs before emitting events.
"""
from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

logger = logging.getLogger(__name__)

AUTH_HEADER_PATTERN = re.compile(
    r"^(authorization|x-api-key|api-key|apikey|cookie)$",
    re.IGNORECASE,
)

SENSITIVE_PARAM_PATTERN = re.compile(
    r"^(key|apikey|api_key|token|secret|password|access_token)$",
    re.IGNORECASE,
)


def sanitize_api_call_event(event: dict[str, Any]) -> dict[str, Any]:
    """Sanitize an API call event by stripping auth credentials."""
    sanitized = {**event}

    if "request" in sanitized and sanitized["request"]:
        sanitized["request"] = {**sanitized["request"]}

        # Sanitize headers
        headers = sanitized["request"].get("headers")
        if headers:
            clean_headers = {}
            for key, value in headers.items():
                clean_headers[key] = "[REDACTED]" if AUTH_HEADER_PATTERN.match(key) else value
            sanitized["request"]["headers"] = clean_headers

        # Sanitize URL query params
        url = sanitized["request"].get("url")
        if url:
            try:
                parsed = urlparse(url)
                if parsed.query:
                    params = parse_qs(parsed.query, keep_blank_values=True)
                    redacted_params = {}
                    for key, values in params.items():
                        if SENSITIVE_PARAM_PATTERN.match(key):
                            redacted_params[key] = ["[REDACTED]"]
                        else:
                            redacted_params[key] = values
                    new_query = urlencode(redacted_params, doseq=True)
                    sanitized["request"]["url"] = urlunparse(parsed._replace(query=new_query))
            except Exception:
                pass

    return sanitized


async def emit_api_call_event(
    engine_config: dict[str, Any] | None,
    raw_event: dict[str, Any],
) -> None:
    """Emit an on_api_call event if the callback is configured."""
    if not engine_config or not engine_config.get("on_api_call"):
        return

    event = sanitize_api_call_event(raw_event)

    try:
        callback = engine_config["on_api_call"]
        if callable(callback):
            result = callback(event)
            if hasattr(result, "__await__"):
                await result
    except Exception as e:
        logger.warning(f"Error in on_api_call callback: {e}")
