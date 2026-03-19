"""
Slack Integration for the zv1 engine.

Provides messaging via the Slack Web API.
"""

from __future__ import annotations

import time
from typing import Any

from src.utilities.sanitize_api_call import emit_api_call_event

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False


class SlackIntegration:
    def __init__(self, api_key: str, base_url: str = "https://slack.com/api", timeout: float = 30.0) -> None:
        if not HAS_HTTPX:
            raise ImportError("httpx package is required for Slack integration.")
        self.api_key = api_key
        self.base_url = base_url
        self.client = httpx.AsyncClient(
            timeout=timeout,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        )

    async def _request(self, method: str, url: str, json_data: dict[str, Any] | None = None) -> dict[str, Any]:
        start_time = int(time.time() * 1000)
        request_headers = dict(self.client.headers)
        try:
            response = await self.client.request(method, url, json=json_data)
            await emit_api_call_event(getattr(self, "_engine_config", None), {
                "timestamp": start_time, "integration": "slack", "nodeId": None, "nodeType": None,
                "request": {"method": method, "url": url, "headers": request_headers, "body": json_data},
                "response": {"status": response.status_code, "statusText": response.reason_phrase or ""},
                "duration": int(time.time() * 1000) - start_time, "error": None,
            })
            data = response.json()
            if data.get("ok") is False:
                raise Exception(f"Slack API error: {data.get('error')}")
            return data
        except Exception as e:
            if "Slack API error" not in str(e):
                await emit_api_call_event(getattr(self, "_engine_config", None), {
                    "timestamp": start_time, "integration": "slack", "nodeId": None, "nodeType": None,
                    "request": {"method": method, "url": url, "headers": request_headers, "body": json_data},
                    "response": {"status": 0, "statusText": "Error"},
                    "duration": int(time.time() * 1000) - start_time, "error": str(e),
                })
            raise

    async def post_message(self, channel: str, text: str, thread_ts: str | None = None, blocks: list | None = None) -> dict[str, Any]:
        data: dict[str, Any] = {"channel": channel, "text": text}
        if thread_ts:
            data["thread_ts"] = thread_ts
        if blocks:
            data["blocks"] = blocks
        return await self._request("POST", f"{self.base_url}/chat.postMessage", json_data=data)

    async def close(self) -> None:
        await self.client.aclose()
