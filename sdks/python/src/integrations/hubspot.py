"""
HubSpot Integration for the zv1 engine.

Provides access to HubSpot's CRM API with OAuth token refresh support.
"""

from __future__ import annotations

import logging
from typing import Any

try:
    import httpx

    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

from src.utilities.oauth import is_oauth_key, OAuthRefreshManager

logger = logging.getLogger(__name__)


class HubSpotIntegration:
    """
    Integration with HubSpot's CRM API.

    Uses OAuth authentication with automatic token refresh.
    """

    def __init__(
        self,
        oauth_key: dict[str, Any],
        base_url: str = "https://api.hubapi.com",
        timeout: float = 30.0,
    ) -> None:
        """
        Initialize the HubSpot integration.

        Args:
            oauth_key: OAuth key object with access_token and on_refresh.
            base_url: Base URL for the API.
            timeout: Request timeout in seconds.

        Raises:
            ValueError: If oauth_key is not a valid OAuth key.
        """
        if not HAS_HTTPX:
            raise ImportError(
                "httpx package is required for HubSpot integration. "
                "Install with: pip install httpx"
            )

        if not is_oauth_key(oauth_key):
            raise ValueError(
                "HubSpot integration requires an OAuth key with access_token and on_refresh"
            )

        self.oauth_key = oauth_key
        self.base_url = base_url
        self.timeout = timeout

        # OAuth refresh manager (set during integration loading)
        self.refresh_manager: OAuthRefreshManager | None = None

        self.client = httpx.AsyncClient(timeout=timeout)

    def set_refresh_manager(self, refresh_manager: OAuthRefreshManager) -> None:
        """
        Set the OAuth refresh manager (called during integration loading).

        Args:
            refresh_manager: The refresh manager instance.
        """
        self.refresh_manager = refresh_manager

    def update_oauth_key(self, updated_key: dict[str, Any]) -> None:
        """
        Update OAuth key (called after refresh).

        Args:
            updated_key: Updated OAuth key object.
        """
        self.oauth_key = {**self.oauth_key, **updated_key}

    async def request(
        self,
        method: str,
        url: str,
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """
        Make an API request to HubSpot with automatic OAuth token refresh.

        Args:
            method: HTTP method (GET, POST, etc.).
            url: API endpoint (relative to base_url).
            data: Request body data.
            params: Query parameters.
            headers: Additional headers.
            timeout: Request timeout override.

        Returns:
            API response data.

        Raises:
            Exception: On API errors or if refresh manager not set.
        """
        if not self.refresh_manager:
            raise Exception(
                "OAuth refresh manager not initialized. "
                "This integration requires engine config context."
            )

        # Ensure absolute URL
        full_url = url if url.startswith("http") else f"{self.base_url}{url}"

        # Ensure token is valid before making request
        self.oauth_key = await self.refresh_manager.ensure_valid_token(
            "hubspot", self.oauth_key
        )

        # Make request with retry logic for expired tokens
        max_retries = 2
        retries = 0

        while retries <= max_retries:
            try:
                access_token = self.oauth_key.get("access_token") or self.oauth_key.get(
                    "accessToken"
                )

                request_headers = {
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                }
                if headers:
                    request_headers.update(headers)

                response = await self.client.request(
                    method=method,
                    url=full_url,
                    json=data,
                    params=params,
                    headers=request_headers,
                    timeout=timeout or self.timeout,
                )

                # Check if response indicates token refresh is needed
                if OAuthRefreshManager.needs_refresh(
                    response, self._check_hubspot_error
                ):
                    if retries < max_retries:
                        self.oauth_key = await self.refresh_manager.refresh_token(
                            "hubspot", self.oauth_key
                        )
                        retries += 1
                        continue
                    else:
                        raise Exception(
                            f"HubSpot API error: {response.status_code} - Token refresh failed"
                        )

                # Check for other HTTP errors
                if response.status_code >= 400:
                    error_message = self._extract_error_message(response)
                    raise Exception(
                        f"HubSpot API error: {response.status_code} - {error_message}"
                    )

                return response.json()

            except Exception as e:
                # If it's an OAuth refresh error, throw immediately
                if "OAuth refresh failed" in str(e):
                    raise

                # For other errors, try refresh if we haven't exhausted retries
                if retries < max_retries:
                    try:
                        self.oauth_key = await self.refresh_manager.refresh_token(
                            "hubspot", self.oauth_key
                        )
                        retries += 1
                        continue
                    except Exception:
                        raise e

                raise

        raise Exception("HubSpot API request failed")

    def _check_hubspot_error(self, response: Any) -> bool:
        """
        Check if HubSpot response indicates OAuth refresh is needed.

        Args:
            response: HTTP response object.

        Returns:
            True if refresh is needed.
        """
        if not response or not hasattr(response, "content"):
            return False

        try:
            data = response.json()
        except Exception:
            return False

        # Check for HubSpot-specific error codes
        status = (data.get("status") or "").lower()
        if status == "error":
            message = (data.get("message") or "").lower()
            category = data.get("category", "")

            # HubSpot error codes that indicate token refresh needed
            refresh_error_codes = [
                "INVALID_AUTHENTICATION",
                "EXPIRED_AUTHENTICATION",
                "TOKEN_EXPIRED",
                "REFRESH_TOKEN_EXPIRED",
                "INVALID_REFRESH_TOKEN",
            ]

            if category in refresh_error_codes:
                return True

            if any(
                keyword in message
                for keyword in ["token", "authentication", "unauthorized", "expired"]
            ):
                return True

        # Check for JSON error objects
        if "error" in data:
            error_code = data["error"].get("code") or data["error"].get("message") or ""
            if isinstance(error_code, str):
                lower_error = error_code.lower()
                if any(
                    keyword in lower_error
                    for keyword in ["token", "auth", "unauthorized", "expired"]
                ):
                    return True

        return False

    def _extract_error_message(self, response: Any) -> str:
        """
        Extract error message from HubSpot API response.

        Args:
            response: HTTP response object.

        Returns:
            Error message.
        """
        try:
            data = response.json()
        except Exception:
            return getattr(response, "reason_phrase", "Unknown error")

        # HubSpot error format
        status = (data.get("status") or "").lower()
        if status == "error" and data.get("message"):
            return data["message"]

        # Standard error object
        if "error" in data:
            if isinstance(data["error"], str):
                return data["error"]
            if data["error"].get("message"):
                return data["error"]["message"]

        return str(data)

    async def get(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        GET request.

        Args:
            url: API endpoint.
            params: Query parameters.
            **kwargs: Additional request options.
        """
        return await self.request("GET", url, params=params, **kwargs)

    async def post(
        self,
        url: str,
        data: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        POST request.

        Args:
            url: API endpoint.
            data: Request body.
            **kwargs: Additional request options.
        """
        return await self.request("POST", url, data=data, **kwargs)

    async def patch(
        self,
        url: str,
        data: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        PATCH request.

        Args:
            url: API endpoint.
            data: Request body.
            **kwargs: Additional request options.
        """
        return await self.request("PATCH", url, data=data, **kwargs)

    async def put(
        self,
        url: str,
        data: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        PUT request.

        Args:
            url: API endpoint.
            data: Request body.
            **kwargs: Additional request options.
        """
        return await self.request("PUT", url, data=data, **kwargs)

    async def delete(self, url: str, **kwargs: Any) -> dict[str, Any]:
        """
        DELETE request.

        Args:
            url: API endpoint.
            **kwargs: Additional request options.
        """
        return await self.request("DELETE", url, **kwargs)

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()
