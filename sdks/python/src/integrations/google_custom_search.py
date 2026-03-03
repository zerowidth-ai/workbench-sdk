"""
Google Custom Search Integration for the zv1 engine.

Provides web search capabilities through Google's Custom Search API.
"""

from __future__ import annotations

import logging
import time
from typing import Any
from urllib.parse import urlencode

from src.utilities.sanitize_api_call import emit_api_call_event

try:
    import httpx

    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

logger = logging.getLogger(__name__)


class GoogleCustomSearchIntegration:
    """
    Integration with Google Custom Search API.
    """

    def __init__(
        self,
        api_key: dict[str, str] | str,
        base_url: str = "https://www.googleapis.com/customsearch/v1",
        timeout: float = 30.0,
    ) -> None:
        """
        Initialize the Google Custom Search integration.

        Args:
            api_key: API key dict with 'key' and 'cx', or just the key string.
            base_url: Base URL for the API.
            timeout: Request timeout in seconds.

        Raises:
            ValueError: If API key is missing.
        """
        if not HAS_HTTPX:
            raise ImportError(
                "httpx package is required for Google Custom Search integration. "
                "Install with: pip install httpx"
            )

        if isinstance(api_key, dict):
            self.api_key = api_key.get("key")
            self.cx = api_key.get("cx")
        else:
            self.api_key = api_key
            self.cx = None

        if not self.api_key:
            raise ValueError("Google Custom Search API key is required")

        self.base_url = base_url
        self.timeout = timeout

        self.client = httpx.AsyncClient(timeout=timeout)

    async def search(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        Perform a custom search using Google Custom Search API.

        Args:
            params: Search parameters (q, num, start, etc.).

        Returns:
            Search response.

        Raises:
            Exception: On API errors.
        """
        # Remove empty params
        clean_params = self._clean_params(params)

        # Add API key and cx
        clean_params["key"] = self.api_key
        if self.cx:
            clean_params["cx"] = self.cx

        start_time = int(time.time() * 1000)
        full_url = f"{self.base_url}?{urlencode(clean_params)}"

        try:
            response = await self.client.get(self.base_url, params=clean_params)

            await emit_api_call_event(getattr(self, "_engine_config", None), {
                "timestamp": start_time, "integration": "google_custom_search", "nodeId": None, "nodeType": None,
                "request": {"method": "GET", "url": full_url, "headers": {}, "body": None},
                "response": {"status": response.status_code, "statusText": response.reason_phrase or ""},
                "duration": int(time.time() * 1000) - start_time, "error": None,
            })

            if response.status_code >= 400:
                try:
                    error_data = response.json()
                    error_msg = error_data.get("error", {}).get(
                        "message", response.reason_phrase
                    )
                except Exception:
                    error_msg = response.reason_phrase

                raise Exception(
                    f"Google Custom Search API error: {response.status_code} - {error_msg}"
                )

            return response.json()

        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            status_text = e.response.reason_phrase
            try:
                response_data = e.response.json()
                error_detail = response_data.get("error", {}).get("message", "")
            except Exception:
                error_detail = ""

            error_message = f"Google Custom Search API Error ({status} {status_text})"
            if error_detail:
                error_message += f": {error_detail}"

            raise Exception(error_message) from e

        except httpx.RequestError as e:
            raise Exception(f"Google Custom Search API Error: {e}") from e

    def _clean_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """Remove empty/null params."""
        clean = {}
        for key, value in params.items():
            if value is None:
                continue
            if value == "":
                continue
            if isinstance(value, list) and len(value) == 0:
                continue
            clean[key] = value
        return clean

    @staticmethod
    def string_to_array(input_val: str | list[str]) -> list[str]:
        """
        Convert comma-separated string to array.

        Args:
            input_val: String or array input.

        Returns:
            Array of strings.
        """
        if isinstance(input_val, list):
            return input_val
        if isinstance(input_val, str):
            return [item.strip() for item in input_val.split(",") if item.strip()]
        return []

    @staticmethod
    def process_params(params: dict[str, Any]) -> dict[str, Any]:
        """
        Process parameters with array handling.

        Args:
            params: Raw parameters.

        Returns:
            Processed parameters.
        """
        processed = dict(params)

        # Fields that should be converted from comma-separated strings
        array_fields = ["excludeTerms", "fileType", "rights", "safe"]

        for field in array_fields:
            if field in processed:
                array_value = GoogleCustomSearchIntegration.string_to_array(
                    processed[field]
                )
                if array_value:
                    processed[field] = " ".join(array_value)

        # Special handling for searchType - only include if it's "image"
        if processed.get("searchType") and processed["searchType"] != "image":
            del processed["searchType"]

        return processed

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()
