"""
OAuth 2.0 Token Refresh Utility.

Handles OAuth token refresh with:
- Expiry pre-checking (epoch or ISO timestamps)
- Refresh coalescing (multiple nodes waiting for same provider refresh)
- Retry logic with max retries
- Automatic in-memory key updates
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable, Awaitable

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def is_oauth_key(key: Any) -> bool:
    """
    Check if a key is an OAuth key (has access_token and on_refresh).

    Args:
        key: The key value to check.

    Returns:
        True if this is an OAuth key.
    """
    if not isinstance(key, dict):
        return False

    has_token = isinstance(key.get("access_token"), str) or isinstance(
        key.get("accessToken"), str
    )
    has_refresh = callable(key.get("on_refresh")) or callable(key.get("onRefresh"))

    return has_token and has_refresh


def parse_expires_at(expires_at: int | str | None) -> int | None:
    """
    Parse expiresAt value (supports epoch milliseconds or ISO string).

    Args:
        expires_at: Expiry timestamp.

    Returns:
        Milliseconds since epoch, or None if invalid/undefined.
    """
    if expires_at is None:
        return None

    if isinstance(expires_at, int):
        return expires_at

    if isinstance(expires_at, float):
        return int(expires_at)

    if isinstance(expires_at, str):
        # Try ISO string
        try:
            dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            return int(dt.timestamp() * 1000)
        except ValueError:
            pass

        # Try epoch string
        try:
            return int(expires_at)
        except ValueError:
            pass

    return None


def is_token_expired(oauth_key: dict[str, Any], expiry_skew_ms: int = 0) -> bool:
    """
    Check if token is expired or will expire soon.

    Args:
        oauth_key: OAuth key object.
        expiry_skew_ms: Milliseconds before actual expiry to consider expired.

    Returns:
        True if token needs refresh.
    """
    expires_at = parse_expires_at(
        oauth_key.get("expires_at") or oauth_key.get("expiresAt")
    )
    if expires_at is None:
        # No expiry info - assume not expired (can't determine)
        return False

    import time

    now = int(time.time() * 1000)
    expiry_threshold = expires_at - expiry_skew_ms
    return now >= expiry_threshold


@dataclass
class OAuthRefreshConfig:
    """Configuration for OAuth refresh manager."""

    expiry_skew_ms: int = 60000  # 1 minute
    max_refresh_retries: int = 3
    refresh_timeout_ms: int = 20000  # 20 seconds
    on_node_update: Callable[[dict[str, Any]], Any] | None = None
    keys: dict[str, Any] | None = None


class OAuthRefreshManager:
    """
    OAuth Refresh Manager.

    Handles token refresh with coalescing for concurrent requests.
    """

    def __init__(self, config: OAuthRefreshConfig | dict[str, Any] | None = None) -> None:
        """
        Initialize the OAuth refresh manager.

        Args:
            config: Configuration options.
        """
        if config is None:
            config = OAuthRefreshConfig()
        elif isinstance(config, dict):
            config = OAuthRefreshConfig(
                expiry_skew_ms=config.get("oauth_expiry_skew_ms", 60000),
                max_refresh_retries=config.get("oauth_max_refresh_retries", 3),
                refresh_timeout_ms=config.get("oauth_refresh_timeout_ms", 20000),
                on_node_update=config.get("on_node_update"),
                keys=config.get("keys"),
            )

        self.expiry_skew_ms = config.expiry_skew_ms
        self.max_refresh_retries = config.max_refresh_retries
        self.refresh_timeout_ms = config.refresh_timeout_ms
        self.on_node_update = config.on_node_update
        self.keys = config.keys

        # Map of provider -> refresh task (for coalescing)
        self._refresh_tasks: dict[str, asyncio.Task[dict[str, Any]]] = {}

    async def ensure_valid_token(
        self, provider: str, oauth_key: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Ensure token is valid, refresh if needed.

        Args:
            provider: Provider name (e.g., 'hubspot').
            oauth_key: OAuth key object.

        Returns:
            Updated OAuth key object with valid token.

        Raises:
            Exception: If refresh fails after max retries.
        """
        if not is_token_expired(oauth_key, self.expiry_skew_ms):
            return oauth_key

        return await self.refresh_token(provider, oauth_key)

    async def refresh_token(
        self, provider: str, oauth_key: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Refresh OAuth token with coalescing support.

        Args:
            provider: Provider name.
            oauth_key: OAuth key object.

        Returns:
            Updated OAuth key object.

        Raises:
            Exception: If refresh fails after max retries.
        """
        # Check if refresh is already in progress for this provider
        existing_task = self._refresh_tasks.get(provider)
        if existing_task and not existing_task.done():
            try:
                return await existing_task
            except Exception:
                # If existing refresh failed, retry our own
                pass

        # Start new refresh
        refresh_task = asyncio.create_task(self._perform_refresh(provider, oauth_key))
        self._refresh_tasks[provider] = refresh_task

        try:
            return await refresh_task
        finally:
            # Clean up task after completion
            if self._refresh_tasks.get(provider) is refresh_task:
                del self._refresh_tasks[provider]

    async def _perform_refresh(
        self, provider: str, oauth_key: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Perform the actual token refresh.

        Args:
            provider: Provider name.
            oauth_key: OAuth key object.

        Returns:
            Updated OAuth key object.
        """
        import time

        last_error: Exception | None = None
        retries = 0

        # Emit refresh started event
        if self.on_node_update:
            await self._call_callback(
                {
                    "type": "oauth_refresh_start",
                    "provider": provider,
                    "timestamp": int(time.time() * 1000),
                    "data": {
                        "status": "started",
                        "retry_attempt": retries,
                    },
                }
            )

        while retries <= self.max_refresh_retries:
            try:
                # Get the on_refresh callback
                on_refresh = oauth_key.get("on_refresh") or oauth_key.get("onRefresh")
                if not callable(on_refresh):
                    raise ValueError("OAuth key must have on_refresh callback")

                # Prepare refresh context
                refresh_context = {
                    "provider": provider,
                    "current_token": oauth_key.get("access_token")
                    or oauth_key.get("accessToken"),
                    "refresh_token": oauth_key.get("refresh_token")
                    or oauth_key.get("refreshToken"),
                    "expires_at": oauth_key.get("expires_at")
                    or oauth_key.get("expiresAt"),
                }

                # Call onRefresh with timeout
                refresh_coro = on_refresh(refresh_context)
                if asyncio.iscoroutine(refresh_coro):
                    updated_key = await asyncio.wait_for(
                        refresh_coro, timeout=self.refresh_timeout_ms / 1000
                    )
                else:
                    updated_key = refresh_coro

                # Validate the returned key object
                if not isinstance(updated_key, dict):
                    raise ValueError("on_refresh callback must return an OAuth key dict")

                access_token = updated_key.get("access_token") or updated_key.get(
                    "accessToken"
                )
                if not isinstance(access_token, str):
                    raise ValueError(
                        "on_refresh callback must return a dict with access_token string"
                    )

                # Update in-memory keys object
                if self.keys and provider in self.keys:
                    self.keys[provider] = {**self.keys[provider], **updated_key}

                # Emit refresh success event
                if self.on_node_update:
                    await self._call_callback(
                        {
                            "type": "oauth_refresh_complete",
                            "provider": provider,
                            "timestamp": int(time.time() * 1000),
                            "data": {
                                "status": "success",
                                "retry_attempt": retries,
                            },
                        }
                    )

                return updated_key

            except asyncio.TimeoutError:
                last_error = Exception(
                    f"OAuth refresh timeout after {self.refresh_timeout_ms}ms"
                )
                retries += 1
            except Exception as e:
                last_error = e
                retries += 1

            # Emit refresh failure event (if not final attempt)
            if retries <= self.max_refresh_retries and self.on_node_update:
                await self._call_callback(
                    {
                        "type": "oauth_refresh_failed",
                        "provider": provider,
                        "timestamp": int(time.time() * 1000),
                        "data": {
                            "status": "failed",
                            "retry_attempt": retries,
                            "error": str(last_error),
                        },
                    }
                )

            if retries > self.max_refresh_retries:
                break

            # Wait before retry (exponential backoff: 100ms, 200ms, 400ms)
            backoff_ms = min(100 * (2 ** (retries - 1)), 1000)
            await asyncio.sleep(backoff_ms / 1000)

        # Emit final failure event
        if self.on_node_update:
            await self._call_callback(
                {
                    "type": "oauth_refresh_complete",
                    "provider": provider,
                    "timestamp": int(time.time() * 1000),
                    "data": {
                        "status": "failed",
                        "retry_attempt": retries - 1,
                        "error": str(last_error) if last_error else "Unknown error",
                    },
                }
            )

        # All retries exhausted
        error_msg = str(last_error) if last_error else "Unknown error"
        raise Exception(
            f"OAuth refresh failed for provider '{provider}' after "
            f"{self.max_refresh_retries} retries: {error_msg}"
        )

    async def _call_callback(self, event: dict[str, Any]) -> None:
        """Call the on_node_update callback."""
        if not self.on_node_update:
            return

        try:
            result = self.on_node_update(event)
            if asyncio.iscoroutine(result):
                await result
        except Exception as e:
            logger.warning(f"Error in on_node_update callback: {e}")

    @staticmethod
    def needs_refresh(
        response: Any,
        provider_specific_check: Callable[[Any], bool] | None = None,
    ) -> bool:
        """
        Check if a response indicates token refresh is needed.

        Args:
            response: HTTP response object.
            provider_specific_check: Optional provider-specific check function.

        Returns:
            True if refresh is needed.
        """
        # Check HTTP status codes
        status = getattr(response, "status", None) or getattr(
            response, "status_code", None
        )
        if status in (401, 403):
            return True

        # Run provider-specific check if provided
        if provider_specific_check:
            return provider_specific_check(response)

        return False
