"""
Resend Integration for the zv1 engine.

Provides email sending via the Resend API.
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


class ResendIntegration:
    def __init__(self, api_key: str, base_url: str = "https://api.resend.com", timeout: float = 30.0) -> None:
        if not HAS_HTTPX:
            raise ImportError("httpx package is required for Resend integration.")
        self.api_key = api_key
        self.base_url = base_url
        self.client = httpx.AsyncClient(
            timeout=timeout,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        )

    async def _request(self, method: str, url: str, json_data: dict[str, Any] | None = None) -> dict[str, Any] | None:
        start_time = int(time.time() * 1000)
        request_headers = dict(self.client.headers)
        try:
            response = await self.client.request(method, url, json=json_data)
            await emit_api_call_event(getattr(self, "_engine_config", None), {
                "timestamp": start_time, "integration": "resend", "nodeId": None, "nodeType": None,
                "request": {"method": method, "url": url, "headers": request_headers, "body": json_data},
                "response": {"status": response.status_code, "statusText": response.reason_phrase or ""},
                "duration": int(time.time() * 1000) - start_time, "error": None,
            })
            if response.status_code >= 400:
                msg = response.json().get("message", response.reason_phrase) if response.content else response.reason_phrase
                raise Exception(f"Resend API error ({response.status_code}): {msg}")
            return response.json() if response.content else None
        except Exception as e:
            if "Resend API error" not in str(e):
                await emit_api_call_event(getattr(self, "_engine_config", None), {
                    "timestamp": start_time, "integration": "resend", "nodeId": None, "nodeType": None,
                    "request": {"method": method, "url": url, "headers": request_headers, "body": json_data},
                    "response": {"status": 0, "statusText": "Error"},
                    "duration": int(time.time() * 1000) - start_time, "error": str(e),
                })
            raise

    async def send_email(self, *, to: str | list[str], from_email: str, subject: str,
                         text: str | None = None, html: str | None = None,
                         reply_to: str | None = None, cc: str | list[str] | None = None,
                         bcc: str | list[str] | None = None) -> dict[str, Any] | None:
        if isinstance(to, str):
            to_list = [addr.strip() for addr in to.split(",")]
        else:
            to_list = to

        data: dict[str, Any] = {"from": from_email, "to": to_list, "subject": subject}
        if text:
            data["text"] = text
        if html:
            data["html"] = html
        if reply_to:
            data["reply_to"] = reply_to
        if cc:
            data["cc"] = [addr.strip() for addr in cc.split(",")] if isinstance(cc, str) else cc
        if bcc:
            data["bcc"] = [addr.strip() for addr in bcc.split(",")] if isinstance(bcc, str) else bcc
        if not text and not html:
            raise Exception("Either text or html content is required")

        return await self._request("POST", f"{self.base_url}/emails", json_data=data)

    async def close(self) -> None:
        await self.client.aclose()
