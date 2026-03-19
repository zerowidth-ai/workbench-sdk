"""
Supabase Integration for the zv1 engine.

Provides REST API access to Supabase tables.
"""

from __future__ import annotations

import time
from typing import Any
from urllib.parse import quote

from src.utilities.sanitize_api_call import emit_api_call_event

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False


class SupabaseIntegration:
    def __init__(self, config: dict[str, str] | str, timeout: float = 30.0) -> None:
        if not HAS_HTTPX:
            raise ImportError("httpx package is required for Supabase integration.")
        if isinstance(config, dict):
            self.url = config["url"]
            self.api_key = config.get("key") or config.get("api_key", "")
        else:
            raise Exception("Supabase integration requires an object with url and key")
        self.client = httpx.AsyncClient(
            timeout=timeout,
            headers={
                "apikey": self.api_key,
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Prefer": "return=representation",
            },
        )

    async def _request(self, method: str, url: str, params: dict | None = None, json_data: Any = None) -> Any:
        start_time = int(time.time() * 1000)
        request_headers = dict(self.client.headers)
        try:
            response = await self.client.request(method, url, params=params, json=json_data)
            await emit_api_call_event(getattr(self, "_engine_config", None), {
                "timestamp": start_time, "integration": "supabase", "nodeId": None, "nodeType": None,
                "request": {"method": method, "url": url, "headers": request_headers, "body": json_data},
                "response": {"status": response.status_code, "statusText": response.reason_phrase or ""},
                "duration": int(time.time() * 1000) - start_time, "error": None,
            })
            if response.status_code >= 400:
                msg = response.text or response.reason_phrase
                raise Exception(f"Supabase API error ({response.status_code}): {msg}")
            return response.json() if response.content else None
        except Exception as e:
            if "Supabase API error" not in str(e):
                await emit_api_call_event(getattr(self, "_engine_config", None), {
                    "timestamp": start_time, "integration": "supabase", "nodeId": None, "nodeType": None,
                    "request": {"method": method, "url": url, "headers": request_headers, "body": json_data},
                    "response": {"status": 0, "statusText": "Error"},
                    "duration": int(time.time() * 1000) - start_time, "error": str(e),
                })
            raise

    async def query(self, table: str, select: str | None = None, filters: list[dict] | None = None,
                    order: str | None = None, limit: int | None = None, offset: int | None = None) -> Any:
        url = f"{self.url}/rest/v1/{quote(table)}"
        params: dict[str, Any] = {}
        if select:
            params["select"] = select
        if filters:
            for f in filters:
                params[f["column"]] = f"{f['operator']}.{f['value']}"
        if order:
            params["order"] = order
        if limit:
            params["limit"] = limit
        if offset:
            params["offset"] = offset
        return await self._request("GET", url, params=params)

    async def insert(self, table: str, records: Any) -> Any:
        url = f"{self.url}/rest/v1/{quote(table)}"
        return await self._request("POST", url, json_data=records)

    async def update(self, table: str, updates: dict, filters: list[dict] | None = None) -> Any:
        url = f"{self.url}/rest/v1/{quote(table)}"
        params: dict[str, Any] = {}
        if filters:
            for f in filters:
                params[f["column"]] = f"{f['operator']}.{f['value']}"
        return await self._request("PATCH", url, params=params, json_data=updates)

    async def delete_rows(self, table: str, filters: list[dict] | None = None) -> Any:
        url = f"{self.url}/rest/v1/{quote(table)}"
        params: dict[str, Any] = {}
        if filters:
            for f in filters:
                params[f["column"]] = f"{f['operator']}.{f['value']}"
        return await self._request("DELETE", url, params=params)

    async def close(self) -> None:
        await self.client.aclose()
