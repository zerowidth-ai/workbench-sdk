"""
NewsData.io Integration for the zv1 engine.

Provides access to news data through the NewsData.io API.
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


class NewsDataIntegration:
    """
    Integration with NewsData.io API.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://newsdata.io/api/1",
        timeout: float = 30.0,
    ) -> None:
        """
        Initialize the NewsData integration.

        Args:
            api_key: NewsData.io API key.
            base_url: Base URL for the API.
            timeout: Request timeout in seconds.
        """
        if not HAS_HTTPX:
            raise ImportError(
                "httpx package is required for NewsData integration. "
                "Install with: pip install httpx"
            )

        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout

        self.client = httpx.AsyncClient(timeout=timeout)

    async def request(
        self, endpoint: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Make a request to any NewsData.io endpoint.

        Args:
            endpoint: The endpoint path (e.g., 'latest', 'archive', 'crypto').
            params: Query parameters.

        Returns:
            API response.

        Raises:
            Exception: On API errors.
        """
        if params is None:
            params = {}

        # Clean params
        clean_params = self._clean_params(params)

        # Add API key
        clean_params["apikey"] = self.api_key

        url = f"{self.base_url}/{endpoint}"

        try:
            response = await self.client.get(url, params=clean_params)

            if response.status_code >= 400:
                try:
                    error_data = response.json()
                    error_msg = error_data.get("message", response.reason_phrase)
                except Exception:
                    error_msg = response.reason_phrase

                raise Exception(
                    f"NewsData API error: {response.status_code} - {error_msg}"
                )

            return response.json()

        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            status_text = e.response.reason_phrase
            try:
                response_data = e.response.json()
                error_detail = response_data.get("message", "")
            except Exception:
                error_detail = ""

            error_message = f"NewsData API Error ({status} {status_text})"
            if error_detail:
                error_message += f": {error_detail}"

            raise Exception(error_message) from e

        except httpx.RequestError as e:
            raise Exception(f"NewsData API Error: {e}") from e

    def _clean_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """Remove empty/null/false params and convert true to 1."""
        clean = {}
        for key, value in params.items():
            if value is None:
                continue
            if value == "":
                continue
            if value is False:
                continue
            if isinstance(value, list) and len(value) == 0:
                continue
            # Convert True to 1
            if value is True:
                clean[key] = 1
            else:
                clean[key] = value
        return clean

    async def get_latest(self, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """
        Get latest news from the last 48 hours.

        Args:
            params: Query parameters.

        Returns:
            Latest news response.
        """
        return await self.request("latest", params)

    async def get_archive(self, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """
        Get historical news from archive.

        Args:
            params: Query parameters.

        Returns:
            Archive news response.
        """
        return await self.request("archive", params)

    async def get_breaking(
        self, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Get breaking/real-time news.

        Args:
            params: Query parameters.

        Returns:
            Breaking news response.
        """
        return await self.request("news", params)

    async def get_crypto(self, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """
        Get crypto-specific news.

        Args:
            params: Query parameters.

        Returns:
            Crypto news response.
        """
        return await self.request("crypto", params)

    async def get_sources(self, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """
        Get list of source domains.

        Args:
            params: Query parameters.

        Returns:
            Sources response.
        """
        return await self.request("sources", params)

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

        # Parameter name mappings (snake_case to API names)
        param_mappings = {
            "categories": "category",
            "exclude_categories": "excludecategory",
            "countries": "country",
            "regions": "region",
            "languages": "language",
            "domains": "domain",
            "exclude_domains": "excludedomain",
            "exclude_fields": "excludefield",
            "coins": "coin",
        }

        # Apply parameter name mappings
        for input_key, api_key in param_mappings.items():
            if input_key in processed:
                processed[api_key] = processed.pop(input_key)

        # Fields that should be converted from comma-separated strings
        array_fields = [
            "country",
            "region",
            "category",
            "excludecategory",
            "language",
            "domain",
            "excludedomain",
            "excludefield",
            "coin",
        ]

        for field in array_fields:
            if field in processed:
                array_value = NewsDataIntegration.string_to_array(processed[field])
                if array_value:
                    processed[field] = ",".join(array_value)

        return processed

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()
