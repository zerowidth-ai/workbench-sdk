"""
Notion Integration for the zv1 engine.

Provides database, page, block, and search operations for Notion workspaces.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional
from urllib.parse import quote

from src.utilities.sanitize_api_call import emit_api_call_event

try:
    import httpx

    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

logger = logging.getLogger(__name__)

# Current Notion API version
NOTION_VERSION = "2022-06-28"


class NotionIntegration:
    """
    Integration with Notion's REST API.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.notion.com/v1",
        timeout: float = 30.0,
    ) -> None:
        """
        Initialize the Notion integration.

        Args:
            api_key: Notion Internal Integration Token.
            base_url: Base URL for the API.
            timeout: Request timeout in seconds.
        """
        if not HAS_HTTPX:
            raise ImportError(
                "httpx package is required for Notion integration. "
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
                "Notion-Version": NOTION_VERSION,
            },
        )

    async def _request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Make an API request with error handling.

        Args:
            method: HTTP method.
            endpoint: API endpoint (without base URL).
            json_data: Optional JSON body.

        Returns:
            Response data as dict.
        """
        url = f"{self.base_url}{endpoint}"
        start_time = int(time.time() * 1000)
        request_headers = dict(self.client.headers)

        try:
            response = await self.client.request(
                method=method,
                url=url,
                json=json_data,
            )

            await emit_api_call_event(getattr(self, "_engine_config", None), {
                "timestamp": start_time, "integration": "notion", "nodeId": None, "nodeType": None,
                "request": {"method": method, "url": url, "headers": request_headers, "body": json_data},
                "response": {"status": response.status_code, "statusText": response.reason_phrase or ""},
                "duration": int(time.time() * 1000) - start_time, "error": None,
            })

            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            error_body = e.response.text
            raise Exception(
                f"Notion API error ({e.response.status_code}): {error_body}"
            ) from e
        except httpx.RequestError as e:
            await emit_api_call_event(getattr(self, "_engine_config", None), {
                "timestamp": start_time, "integration": "notion", "nodeId": None, "nodeType": None,
                "request": {"method": method, "url": url, "headers": request_headers, "body": json_data},
                "response": {"status": 0, "statusText": "Error"},
                "duration": int(time.time() * 1000) - start_time, "error": str(e),
            })
            raise Exception(f"Notion request error: {str(e)}") from e

    async def query_database(
        self,
        database_id: str,
        filter: Optional[dict[str, Any]] = None,
        sorts: Optional[list[dict[str, Any]]] = None,
        start_cursor: Optional[str] = None,
        page_size: Optional[int] = None,
    ) -> dict[str, Any]:
        """
        Query a database.

        Args:
            database_id: The database ID.
            filter: Filter conditions.
            sorts: Sort conditions.
            start_cursor: Pagination cursor.
            page_size: Number of results per page (max 100).

        Returns:
            Query results with results array and pagination info.
        """
        body: dict[str, Any] = {}
        if filter:
            body["filter"] = filter
        if sorts:
            body["sorts"] = sorts
        if start_cursor:
            body["start_cursor"] = start_cursor
        if page_size:
            body["page_size"] = min(page_size, 100)

        return await self._request("POST", f"/databases/{database_id}/query", body)

    async def get_page(self, page_id: str) -> dict[str, Any]:
        """
        Retrieve a page by ID.

        Args:
            page_id: The page ID.

        Returns:
            Page object with properties.
        """
        return await self._request("GET", f"/pages/{page_id}")

    async def create_page(
        self,
        parent: dict[str, Any],
        properties: dict[str, Any],
        children: Optional[list[dict[str, Any]]] = None,
        icon: Optional[dict[str, Any]] = None,
        cover: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Create a new page.

        Args:
            parent: Parent object (database_id or page_id).
            properties: Page properties.
            children: Optional block children to add.
            icon: Optional icon.
            cover: Optional cover image.

        Returns:
            Created page object.
        """
        body: dict[str, Any] = {
            "parent": parent,
            "properties": properties,
        }
        if children:
            body["children"] = children
        if icon:
            body["icon"] = icon
        if cover:
            body["cover"] = cover

        return await self._request("POST", "/pages", body)

    async def update_page(
        self,
        page_id: str,
        properties: Optional[dict[str, Any]] = None,
        icon: Optional[dict[str, Any]] = None,
        cover: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Update a page's properties.

        Args:
            page_id: The page ID.
            properties: Properties to update.
            icon: Optional icon update.
            cover: Optional cover update.

        Returns:
            Updated page object.
        """
        body: dict[str, Any] = {}
        if properties:
            body["properties"] = properties
        if icon:
            body["icon"] = icon
        if cover:
            body["cover"] = cover

        return await self._request("PATCH", f"/pages/{page_id}", body)

    async def archive_page(
        self,
        page_id: str,
        archived: bool = True,
    ) -> dict[str, Any]:
        """
        Archive or restore a page.

        Args:
            page_id: The page ID.
            archived: True to archive, False to restore.

        Returns:
            Updated page object.
        """
        return await self._request(
            "PATCH",
            f"/pages/{page_id}",
            {"archived": archived},
        )

    async def get_block_children(
        self,
        block_id: str,
        start_cursor: Optional[str] = None,
        page_size: Optional[int] = None,
    ) -> dict[str, Any]:
        """
        Get children blocks of a block or page.

        Args:
            block_id: The block or page ID.
            start_cursor: Pagination cursor.
            page_size: Number of results per page (max 100).

        Returns:
            Block children with pagination info.
        """
        params = []
        if start_cursor:
            params.append(f"start_cursor={start_cursor}")
        if page_size:
            params.append(f"page_size={min(page_size, 100)}")

        endpoint = f"/blocks/{block_id}/children"
        if params:
            endpoint += "?" + "&".join(params)

        return await self._request("GET", endpoint)

    async def append_block_children(
        self,
        block_id: str,
        children: list[dict[str, Any]],
        after: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Append children blocks to a block or page.

        Args:
            block_id: The block or page ID.
            children: Block objects to append.
            after: Optional block ID to insert after.

        Returns:
            Appended block objects.
        """
        body: dict[str, Any] = {"children": children}
        if after:
            body["after"] = after

        return await self._request("PATCH", f"/blocks/{block_id}/children", body)

    async def search(
        self,
        query: Optional[str] = None,
        filter: Optional[dict[str, Any]] = None,
        sort: Optional[dict[str, Any]] = None,
        start_cursor: Optional[str] = None,
        page_size: Optional[int] = None,
    ) -> dict[str, Any]:
        """
        Search pages and databases.

        Args:
            query: Search query string.
            filter: Filter by object type (page or database).
            sort: Sort configuration.
            start_cursor: Pagination cursor.
            page_size: Number of results per page (max 100).

        Returns:
            Search results with pagination info.
        """
        body: dict[str, Any] = {}
        if query:
            body["query"] = query
        if filter:
            body["filter"] = filter
        if sort:
            body["sort"] = sort
        if start_cursor:
            body["start_cursor"] = start_cursor
        if page_size:
            body["page_size"] = min(page_size, 100)

        return await self._request("POST", "/search", body)

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()
