"""
Stripe Integration for the zv1 engine.

Provides customer management via the Stripe REST API.
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


class StripeIntegration:
    def __init__(self, api_key: str, base_url: str = "https://api.stripe.com/v1", timeout: float = 30.0) -> None:
        if not HAS_HTTPX:
            raise ImportError("httpx package is required for Stripe integration.")
        self.api_key = api_key
        self.base_url = base_url
        self.client = httpx.AsyncClient(
            timeout=timeout,
            headers={"Authorization": f"Bearer {api_key}"},
        )

    async def _request(self, method: str, url: str, params: dict | None = None, data: dict | None = None) -> dict[str, Any]:
        start_time = int(time.time() * 1000)
        request_headers = dict(self.client.headers)
        try:
            response = await self.client.request(method, url, params=params, data=data)
            await emit_api_call_event(getattr(self, "_engine_config", None), {
                "timestamp": start_time, "integration": "stripe", "nodeId": None, "nodeType": None,
                "request": {"method": method, "url": url, "headers": request_headers, "body": data},
                "response": {"status": response.status_code, "statusText": response.reason_phrase or ""},
                "duration": int(time.time() * 1000) - start_time, "error": None,
            })
            if response.status_code >= 400:
                error_data = response.json() if response.content else {}
                msg = error_data.get("error", {}).get("message", response.reason_phrase)
                raise Exception(f"Stripe API error ({response.status_code}): {msg}")
            return response.json()
        except Exception as e:
            if "Stripe API error" not in str(e):
                await emit_api_call_event(getattr(self, "_engine_config", None), {
                    "timestamp": start_time, "integration": "stripe", "nodeId": None, "nodeType": None,
                    "request": {"method": method, "url": url, "headers": request_headers, "body": data},
                    "response": {"status": 0, "statusText": "Error"},
                    "duration": int(time.time() * 1000) - start_time, "error": str(e),
                })
            raise

    async def list_customers(self, email: str | None = None, limit: int | None = None,
                             starting_after: str | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if email:
            params["email"] = email
        if limit:
            params["limit"] = limit
        if starting_after:
            params["starting_after"] = starting_after
        return await self._request("GET", f"{self.base_url}/customers", params=params)

    async def create_customer(self, email: str | None = None, name: str | None = None,
                              description: str | None = None, phone: str | None = None) -> dict[str, Any]:
        data: dict[str, str] = {}
        if email:
            data["email"] = email
        if name:
            data["name"] = name
        if description:
            data["description"] = description
        if phone:
            data["phone"] = phone
        return await self._request("POST", f"{self.base_url}/customers", data=data)

    async def close(self) -> None:
        await self.client.aclose()
