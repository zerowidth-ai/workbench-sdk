"""
SendGrid Integration for the zv1 engine.

Provides email sending via the SendGrid Mail Send API.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from src.utilities.sanitize_api_call import emit_api_call_event

try:
    import httpx

    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

logger = logging.getLogger(__name__)


class SendgridIntegration:
    """
    Integration with SendGrid's Mail Send API.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.sendgrid.com/v3",
        timeout: float = 30.0,
    ) -> None:
        if not HAS_HTTPX:
            raise ImportError(
                "httpx package is required for SendGrid integration. "
                "Install with: pip install httpx"
            )

        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout

        self.client = httpx.AsyncClient(
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )

    async def _request(
        self,
        method: str,
        url: str,
        json_data: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Central request method with API call event emission."""
        start_time = int(time.time() * 1000)
        request_headers = dict(self.client.headers)

        try:
            response = await self.client.request(method, url, json=json_data)

            await emit_api_call_event(getattr(self, "_engine_config", None), {
                "timestamp": start_time, "integration": "sendgrid", "nodeId": None, "nodeType": None,
                "request": {"method": method, "url": url, "headers": request_headers, "body": json_data},
                "response": {"status": response.status_code, "statusText": response.reason_phrase or ""},
                "duration": int(time.time() * 1000) - start_time, "error": None,
            })

            self._check_response(response)
            # SendGrid mail/send returns 202 with empty body on success
            if response.status_code == 202:
                return {"status_code": 202, "message": "Email accepted for delivery"}
            return response.json() if response.content else None

        except Exception as e:
            if "SendGrid API error" not in str(e):
                await emit_api_call_event(getattr(self, "_engine_config", None), {
                    "timestamp": start_time, "integration": "sendgrid", "nodeId": None, "nodeType": None,
                    "request": {"method": method, "url": url, "headers": request_headers, "body": json_data},
                    "response": {"status": 0, "statusText": "Error"},
                    "duration": int(time.time() * 1000) - start_time, "error": str(e),
                })
            raise

    async def send_email(
        self,
        *,
        to: str | list[str],
        from_email: str,
        subject: str,
        from_name: str | None = None,
        text: str | None = None,
        html: str | None = None,
        reply_to: str | None = None,
        cc: str | list[str] | None = None,
        bcc: str | list[str] | None = None,
    ) -> dict[str, Any] | None:
        """
        Send an email using the SendGrid Mail Send API.

        Args:
            to: Recipient email address(es).
            from_email: Sender email address.
            subject: Email subject line.
            from_name: Sender display name.
            text: Plain text body.
            html: HTML body.
            reply_to: Reply-to email address.
            cc: CC email addresses.
            bcc: BCC email addresses.

        Returns:
            Response dict with status info.
        """
        # Build to addresses
        if isinstance(to, str):
            to_list = [{"email": addr.strip()} for addr in to.split(",")]
        else:
            to_list = [{"email": addr.strip()} for addr in to]

        personalization: dict[str, Any] = {"to": to_list}

        if cc:
            cc_list = cc.split(",") if isinstance(cc, str) else cc
            personalization["cc"] = [{"email": addr.strip()} for addr in cc_list]
        if bcc:
            bcc_list = bcc.split(",") if isinstance(bcc, str) else bcc
            personalization["bcc"] = [{"email": addr.strip()} for addr in bcc_list]

        # Build content
        content = []
        if text:
            content.append({"type": "text/plain", "value": text})
        if html:
            content.append({"type": "text/html", "value": html})
        if not content:
            raise Exception("Either text or html content is required")

        # Build request body
        from_obj: dict[str, str] = {"email": from_email}
        if from_name:
            from_obj["name"] = from_name

        data: dict[str, Any] = {
            "personalizations": [personalization],
            "from": from_obj,
            "subject": subject,
            "content": content,
        }

        if reply_to:
            data["reply_to"] = {"email": reply_to}

        return await self._request("POST", f"{self.base_url}/mail/send", json_data=data)

    def _check_response(self, response: httpx.Response) -> None:
        """Check response for errors and raise if needed."""
        if response.status_code >= 400:
            try:
                error_data = response.json()
                errors = error_data.get("errors", [])
                if errors:
                    error_message = "; ".join(e.get("message", "") for e in errors)
                else:
                    error_message = response.reason_phrase or "Unknown error"
                raise Exception(
                    f"SendGrid API error ({response.status_code}): {error_message}"
                )
            except Exception as e:
                if "SendGrid API error" in str(e):
                    raise
                raise Exception(
                    f"SendGrid API error ({response.status_code}): {response.reason_phrase}"
                )

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()
