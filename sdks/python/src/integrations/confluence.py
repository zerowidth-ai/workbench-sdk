"""
Confluence Integration for the zv1 engine.

Provides page search and retrieval via the Confluence REST API.
"""

from __future__ import annotations

import base64
import time
from typing import Any

from src.utilities.sanitize_api_call import emit_api_call_event

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False


class ConfluenceIntegration:
    def __init__(self, config: dict[str, str] | str, timeout: float = 30.0) -> None:
        if not HAS_HTTPX:
            raise ImportError("httpx package is required for Confluence integration.")
        if isinstance(config, dict):
            self.email = config["email"]
            self.api_token = config["api_token"]
            self.domain = config["domain"]
        else:
            raise Exception("Confluence integration requires an object with email, api_token, and domain")

        auth = base64.b64encode(f"{self.email}:{self.api_token}".encode()).decode()
        self.base_url = f"https://{self.domain}/wiki/api/v2"
        self.client = httpx.AsyncClient(
            timeout=timeout,
            headers={
                "Authorization": f"Basic {auth}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )

    async def _request(self, method: str, url: str, params: dict | None = None,
                       json_data: dict | None = None) -> Any:
        start_time = int(time.time() * 1000)
        request_headers = dict(self.client.headers)
        try:
            response = await self.client.request(method, url, params=params, json=json_data)
            await emit_api_call_event(getattr(self, "_engine_config", None), {
                "timestamp": start_time, "integration": "confluence", "nodeId": None, "nodeType": None,
                "request": {"method": method, "url": url, "headers": request_headers, "body": json_data},
                "response": {"status": response.status_code, "statusText": response.reason_phrase or ""},
                "duration": int(time.time() * 1000) - start_time, "error": None,
            })
            if response.status_code >= 400:
                msg = response.json().get("message", response.reason_phrase) if response.content else response.reason_phrase
                raise Exception(f"Confluence API error ({response.status_code}): {msg}")
            return response.json() if response.content else None
        except Exception as e:
            if "Confluence API error" not in str(e):
                await emit_api_call_event(getattr(self, "_engine_config", None), {
                    "timestamp": start_time, "integration": "confluence", "nodeId": None, "nodeType": None,
                    "request": {"method": method, "url": url, "headers": request_headers, "body": json_data},
                    "response": {"status": 0, "statusText": "Error"},
                    "duration": int(time.time() * 1000) - start_time, "error": str(e),
                })
            raise

    async def search(self, cql: str, limit: int = 25, start: int = 0) -> dict[str, Any]:
        search_url = f"https://{self.domain}/wiki/rest/api/content/search"
        return await self._request("GET", search_url, params={"cql": cql, "limit": limit, "start": start})

    async def get_page(self, page_id: str, body_format: str | None = None) -> dict[str, Any]:
        params = {}
        if body_format:
            params["body-format"] = body_format
        return await self._request("GET", f"{self.base_url}/pages/{page_id}", params=params)

    async def close(self) -> None:
        await self.client.aclose()
