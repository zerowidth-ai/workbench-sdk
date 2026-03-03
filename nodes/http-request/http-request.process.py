"""
HTTP Request Node - Make HTTP requests.
"""

import json
import time
from typing import Any
from urllib.parse import urlencode

try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False


async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    """
    Process function for the HTTP Request node.
    """
    if not HAS_AIOHTTP:
        raise Exception("aiohttp library is required for HTTP requests. Install with: pip install aiohttp")

    url = inputs.get("url")
    method = (inputs.get("method") or "GET").upper()
    headers = inputs.get("headers") or {}
    query = inputs.get("query") or {}
    body = inputs.get("body")
    timeout = settings.get("timeout", 10000) / 1000  # Convert to seconds
    follow_redirects = settings.get("follow_redirects", True)

    # Build full URL with query params
    full_url = url
    if query:
        params = urlencode(query)
        full_url += ("&" if "?" in url else "?") + params

    start_time = int(time.time() * 1000)
    emit_api_call = config.get("_emit_api_call")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method=method,
                url=full_url,
                headers=headers,
                json=body if isinstance(body, (dict, list)) else None,
                data=body if isinstance(body, str) else None,
                timeout=aiohttp.ClientTimeout(total=timeout),
                allow_redirects=follow_redirects,
            ) as response:
                status = response.status
                response_headers = dict(response.headers)

                if emit_api_call:
                    await emit_api_call({
                        "timestamp": start_time,
                        "integration": "http-request",
                        "nodeId": node_config.get("id") if node_config else None,
                        "nodeType": node_config.get("type", "http-request") if node_config else "http-request",
                        "request": {"method": method, "url": full_url, "headers": headers, "body": body},
                        "response": {"status": status, "statusText": response.reason or ""},
                        "duration": int(time.time() * 1000) - start_time,
                        "error": None,
                    })

                # Try to parse response body
                content_type = response_headers.get("Content-Type", "")
                try:
                    if "application/json" in content_type:
                        parsed_body = await response.json()
                    else:
                        parsed_body = await response.text()
                except Exception:
                    parsed_body = await response.text()

                result = {
                    "status": status,
                    "headers": response_headers,
                    "body": parsed_body,
                }

                if status >= 400:
                    result["error"] = f"HTTP error: {status}"

                return result

    except Exception as err:
        if emit_api_call:
            await emit_api_call({
                "timestamp": start_time,
                "integration": "http-request",
                "nodeId": node_config.get("id") if node_config else None,
                "nodeType": node_config.get("type", "http-request") if node_config else "http-request",
                "request": {"method": method, "url": full_url, "headers": headers, "body": body},
                "response": {"status": 0, "statusText": "Error"},
                "duration": int(time.time() * 1000) - start_time,
                "error": str(err),
            })

        return {
            "status": None,
            "headers": {},
            "body": None,
            "error": str(err),
        }
