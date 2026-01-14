"""
Firecrawl Integration for the zv1 engine.

Provides web scraping capabilities through the Firecrawl API.
"""

from __future__ import annotations

import logging
from typing import Any

try:
    import httpx

    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

logger = logging.getLogger(__name__)


class FirecrawlIntegration:
    """
    Integration with Firecrawl's web scraping API.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.firecrawl.dev/v2",
        timeout: float = 60.0,
    ) -> None:
        """
        Initialize the Firecrawl integration.

        Args:
            api_key: Firecrawl API key.
            base_url: Base URL for the API.
            timeout: Request timeout in seconds (default 60s for scraping).
        """
        if not HAS_HTTPX:
            raise ImportError(
                "httpx package is required for Firecrawl integration. "
                "Install with: pip install httpx"
            )

        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout

        self.client = httpx.AsyncClient(
            base_url=base_url,
            timeout=timeout,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
        )

    async def scrape(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        Scrape a single URL with various options.

        Args:
            params: Scraping parameters (url, formats, etc.).

        Returns:
            Scraping response.

        Raises:
            Exception: On API errors.
        """
        # Remove empty params
        clean_params = self._clean_params(params)

        try:
            response = await self.client.post("/scrape", json=clean_params)

            if response.status_code >= 400:
                error_data = response.json() if response.content else {}
                error_msg = error_data.get("error", response.reason_phrase)
                raise Exception(f"Firecrawl API error: {response.status_code} - {error_msg}")

            return response.json()

        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            status_text = e.response.reason_phrase
            try:
                response_data = e.response.json()
                error_detail = response_data.get("error", "")
            except Exception:
                error_detail = ""

            error_message = f"Firecrawl API Error ({status} {status_text})"
            if error_detail:
                error_message += f": {error_detail}"

            raise Exception(error_message) from e

        except httpx.RequestError as e:
            raise Exception(f"Firecrawl API Error: {e}") from e

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
        Process parameters with array handling and name mappings.

        Args:
            params: Raw parameters.

        Returns:
            Processed parameters.
        """
        processed = dict(params)

        # Parameter name mappings (snake_case to camelCase)
        param_mappings = {
            "include_tags": "includeTags",
            "exclude_tags": "excludeTags",
            "only_main_content": "onlyMainContent",
            "max_age": "maxAge",
            "wait_for": "waitFor",
            "mobile_device": "mobile",
            "skip_tls_verification": "skipTlsVerification",
            "remove_base64_images": "removeBase64Images",
            "block_ads": "blockAds",
            "store_in_cache": "storeInCache",
            "zero_data_retention": "zeroDataRetention",
        }

        # Apply parameter name mappings
        for input_key, api_key in param_mappings.items():
            if input_key in processed:
                processed[api_key] = processed.pop(input_key)

        # Fields that should be converted from comma-separated strings to arrays
        array_fields = ["includeTags", "excludeTags", "formats"]

        for field in array_fields:
            if field in processed:
                array_value = FirecrawlIntegration.string_to_array(processed[field])
                if array_value:
                    processed[field] = array_value

        # Handle formats - convert string to array of objects if needed
        if "formats" in processed and isinstance(processed["formats"], list):
            processed["formats"] = [
                {"type": fmt} if isinstance(fmt, str) else fmt
                for fmt in processed["formats"]
            ]

        return processed

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()
