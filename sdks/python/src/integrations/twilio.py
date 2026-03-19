"""
Twilio Integration for the zv1 engine.

Provides SMS sending via the Twilio REST API.
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


class TwilioIntegration:
    def __init__(self, config: dict[str, str] | str, timeout: float = 30.0) -> None:
        if not HAS_HTTPX:
            raise ImportError("httpx package is required for Twilio integration.")
        if isinstance(config, dict):
            self.account_sid = config["account_sid"]
            self.auth_token = config["auth_token"]
        else:
            raise Exception("Twilio integration requires an object with account_sid and auth_token")
        self.base_url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}"
        self.client = httpx.AsyncClient(
            timeout=timeout,
            auth=(self.account_sid, self.auth_token),
        )

    async def _request(self, method: str, url: str, data: dict[str, str] | None = None) -> dict[str, Any]:
        start_time = int(time.time() * 1000)
        try:
            response = await self.client.request(method, url, data=data)
            await emit_api_call_event(getattr(self, "_engine_config", None), {
                "timestamp": start_time, "integration": "twilio", "nodeId": None, "nodeType": None,
                "request": {"method": method, "url": url, "headers": {}, "body": data},
                "response": {"status": response.status_code, "statusText": response.reason_phrase or ""},
                "duration": int(time.time() * 1000) - start_time, "error": None,
            })
            if response.status_code >= 400:
                msg = response.json().get("message", response.reason_phrase) if response.content else response.reason_phrase
                raise Exception(f"Twilio API error ({response.status_code}): {msg}")
            return response.json()
        except Exception as e:
            if "Twilio API error" not in str(e):
                await emit_api_call_event(getattr(self, "_engine_config", None), {
                    "timestamp": start_time, "integration": "twilio", "nodeId": None, "nodeType": None,
                    "request": {"method": method, "url": url, "headers": {}, "body": data},
                    "response": {"status": 0, "statusText": "Error"},
                    "duration": int(time.time() * 1000) - start_time, "error": str(e),
                })
            raise

    async def send_sms(self, to: str, from_number: str, body: str) -> dict[str, Any]:
        return await self._request("POST", f"{self.base_url}/Messages.json", data={"To": to, "From": from_number, "Body": body})

    async def close(self) -> None:
        await self.client.aclose()
