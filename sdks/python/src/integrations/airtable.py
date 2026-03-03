"""
Airtable Integration for the zv1 engine.

Provides CRUD operations for Airtable bases and tables.
"""

from __future__ import annotations

import logging
import time
from typing import Any
from urllib.parse import quote

from src.utilities.sanitize_api_call import emit_api_call_event

try:
    import httpx

    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

logger = logging.getLogger(__name__)


class AirtableIntegration:
    """
    Integration with Airtable's REST API.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.airtable.com/v0",
        timeout: float = 30.0,
    ) -> None:
        """
        Initialize the Airtable integration.

        Args:
            api_key: Airtable Personal Access Token.
            base_url: Base URL for the API.
            timeout: Request timeout in seconds.
        """
        if not HAS_HTTPX:
            raise ImportError(
                "httpx package is required for Airtable integration. "
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

    def _build_url(self, base_id: str, table_name: str, record_id: str | None = None) -> str:
        """Build the API URL for a table or record."""
        # URL-encode the table name in case it has spaces/special chars
        encoded_table = quote(table_name, safe="")
        url = f"{self.base_url}/{base_id}/{encoded_table}"
        if record_id:
            url = f"{url}/{record_id}"
        return url

    async def _request(
        self,
        method: str,
        url: str,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Central request method with API call event emission."""
        start_time = int(time.time() * 1000)
        request_headers = dict(self.client.headers)

        try:
            response = await self.client.request(method, url, params=params, json=json_data)

            await emit_api_call_event(getattr(self, "_engine_config", None), {
                "timestamp": start_time, "integration": "airtable", "nodeId": None, "nodeType": None,
                "request": {"method": method, "url": url, "headers": request_headers, "body": json_data},
                "response": {"status": response.status_code, "statusText": response.reason_phrase or ""},
                "duration": int(time.time() * 1000) - start_time, "error": None,
            })

            self._check_response(response)
            return response.json()

        except Exception as e:
            if "Airtable API error" not in str(e):
                await emit_api_call_event(getattr(self, "_engine_config", None), {
                    "timestamp": start_time, "integration": "airtable", "nodeId": None, "nodeType": None,
                    "request": {"method": method, "url": url, "headers": request_headers, "body": json_data},
                    "response": {"status": 0, "statusText": "Error"},
                    "duration": int(time.time() * 1000) - start_time, "error": str(e),
                })
            raise

    async def list_records(
        self,
        base_id: str,
        table_name: str,
        filter_formula: str | None = None,
        sort_field: str | None = None,
        sort_direction: str | None = None,
        max_records: int | None = None,
        page_size: int | None = None,
        offset: str | None = None,
        fields: list[str] | None = None,
        view: str | None = None,
    ) -> dict[str, Any]:
        """
        List records from a table.

        Args:
            base_id: The Airtable base ID.
            table_name: The table name or ID.
            filter_formula: Airtable formula to filter records.
            sort_field: Field name to sort by.
            sort_direction: Sort direction ("asc" or "desc").
            max_records: Maximum number of records to return.
            page_size: Number of records per page (max 100).
            offset: Pagination offset from previous request.
            fields: List of field names to include.
            view: Name or ID of a view to use.

        Returns:
            Dict with 'records' array and optional 'offset' for pagination.
        """
        url = self._build_url(base_id, table_name)
        params: dict[str, Any] = {}

        if filter_formula:
            params["filterByFormula"] = filter_formula
        if sort_field:
            params["sort[0][field]"] = sort_field
            params["sort[0][direction]"] = sort_direction or "asc"
        if max_records:
            params["maxRecords"] = max_records
        if page_size:
            params["pageSize"] = min(page_size, 100)
        if offset:
            params["offset"] = offset
        if fields:
            for i, field in enumerate(fields):
                params[f"fields[{i}]"] = field
        if view:
            params["view"] = view

        return await self._request("GET", url, params=params)

    async def get_record(
        self,
        base_id: str,
        table_name: str,
        record_id: str,
    ) -> dict[str, Any]:
        """
        Get a single record by ID.

        Args:
            base_id: The Airtable base ID.
            table_name: The table name or ID.
            record_id: The record ID.

        Returns:
            The record object with id, fields, and createdTime.
        """
        url = self._build_url(base_id, table_name, record_id)
        return await self._request("GET", url)

    async def create_record(
        self,
        base_id: str,
        table_name: str,
        fields: dict[str, Any],
        typecast: bool = False,
    ) -> dict[str, Any]:
        """
        Create a new record.

        Args:
            base_id: The Airtable base ID.
            table_name: The table name or ID.
            fields: Field name/value pairs.
            typecast: If true, Airtable will try to convert string values.

        Returns:
            The created record.
        """
        url = self._build_url(base_id, table_name)
        data: dict[str, Any] = {"fields": fields}
        if typecast:
            data["typecast"] = True

        return await self._request("POST", url, json_data=data)

    async def update_record(
        self,
        base_id: str,
        table_name: str,
        record_id: str,
        fields: dict[str, Any],
        typecast: bool = False,
    ) -> dict[str, Any]:
        """
        Update an existing record (PATCH - partial update).

        Args:
            base_id: The Airtable base ID.
            table_name: The table name or ID.
            record_id: The record ID.
            fields: Field name/value pairs to update.
            typecast: If true, Airtable will try to convert string values.

        Returns:
            The updated record.
        """
        url = self._build_url(base_id, table_name, record_id)
        data: dict[str, Any] = {"fields": fields}
        if typecast:
            data["typecast"] = True

        return await self._request("PATCH", url, json_data=data)

    async def delete_record(
        self,
        base_id: str,
        table_name: str,
        record_id: str,
    ) -> dict[str, Any]:
        """
        Delete a record.

        Args:
            base_id: The Airtable base ID.
            table_name: The table name or ID.
            record_id: The record ID.

        Returns:
            Dict with 'deleted' boolean and 'id'.
        """
        url = self._build_url(base_id, table_name, record_id)
        return await self._request("DELETE", url)

    def _check_response(self, response: httpx.Response) -> None:
        """Check response for errors and raise if needed."""
        if response.status_code >= 400:
            try:
                error_data = response.json()
                error_info = error_data.get("error", {})
                error_type = error_info.get("type", "UNKNOWN_ERROR")
                error_message = error_info.get("message", response.reason_phrase)
                raise Exception(
                    f"Airtable API error ({response.status_code}): {error_type} - {error_message}"
                )
            except Exception as e:
                if "Airtable API error" in str(e):
                    raise
                raise Exception(
                    f"Airtable API error ({response.status_code}): {response.reason_phrase}"
                )

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()
