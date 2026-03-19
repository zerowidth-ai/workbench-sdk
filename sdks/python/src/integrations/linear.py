"""
Linear Integration for the zv1 engine.

Provides issue management via the Linear GraphQL API.
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


class LinearIntegration:
    def __init__(self, api_key: str, base_url: str = "https://api.linear.app", timeout: float = 30.0) -> None:
        if not HAS_HTTPX:
            raise ImportError("httpx package is required for Linear integration.")
        self.api_key = api_key
        self.base_url = base_url
        self.client = httpx.AsyncClient(
            timeout=timeout,
            headers={"Authorization": api_key, "Content-Type": "application/json"},
        )

    async def _graphql(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        start_time = int(time.time() * 1000)
        request_headers = dict(self.client.headers)
        json_data = {"query": query, "variables": variables or {}}
        url = f"{self.base_url}/graphql"
        try:
            response = await self.client.post(url, json=json_data)
            await emit_api_call_event(getattr(self, "_engine_config", None), {
                "timestamp": start_time, "integration": "linear", "nodeId": None, "nodeType": None,
                "request": {"method": "POST", "url": url, "headers": request_headers, "body": json_data},
                "response": {"status": response.status_code, "statusText": response.reason_phrase or ""},
                "duration": int(time.time() * 1000) - start_time, "error": None,
            })
            data = response.json()
            if data.get("errors"):
                msgs = "; ".join(e.get("message", "") for e in data["errors"])
                raise Exception(f"Linear API error: {msgs}")
            return data.get("data", {})
        except Exception as e:
            if "Linear API error" not in str(e):
                await emit_api_call_event(getattr(self, "_engine_config", None), {
                    "timestamp": start_time, "integration": "linear", "nodeId": None, "nodeType": None,
                    "request": {"method": "POST", "url": url, "headers": request_headers, "body": json_data},
                    "response": {"status": 0, "statusText": "Error"},
                    "duration": int(time.time() * 1000) - start_time, "error": str(e),
                })
            raise

    async def create_issue(self, team_id: str, title: str, description: str | None = None,
                           priority: int | None = None, assignee_id: str | None = None,
                           label_ids: list[str] | None = None) -> dict[str, Any]:
        mutation = """
            mutation IssueCreate($input: IssueCreateInput!) {
                issueCreate(input: $input) {
                    success
                    issue { id identifier title url state { name } priority createdAt }
                }
            }
        """
        input_data: dict[str, Any] = {"teamId": team_id, "title": title}
        if description:
            input_data["description"] = description
        if priority is not None:
            input_data["priority"] = priority
        if assignee_id:
            input_data["assigneeId"] = assignee_id
        if label_ids:
            input_data["labelIds"] = label_ids
        result = await self._graphql(mutation, {"input": input_data})
        return result.get("issueCreate", {})

    async def list_issues(self, first: int | None = None, after: str | None = None,
                          filter: dict[str, Any] | None = None) -> dict[str, Any]:
        query = """
            query Issues($filter: IssueFilter, $first: Int, $after: String) {
                issues(filter: $filter, first: $first, after: $after) {
                    nodes {
                        id identifier title url
                        state { name }
                        priority
                        assignee { name email }
                        createdAt updatedAt
                    }
                    pageInfo { hasNextPage endCursor }
                }
            }
        """
        variables: dict[str, Any] = {}
        if first is not None:
            variables["first"] = first
        if after:
            variables["after"] = after
        if filter:
            variables["filter"] = filter
        result = await self._graphql(query, variables)
        return result.get("issues", {})

    async def update_issue(self, issue_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        mutation = """
            mutation IssueUpdate($id: String!, $input: IssueUpdateInput!) {
                issueUpdate(id: $id, input: $input) {
                    success
                    issue { id identifier title url state { name } priority updatedAt }
                }
            }
        """
        result = await self._graphql(mutation, {"id": issue_id, "input": updates})
        return result.get("issueUpdate", {})

    async def close(self) -> None:
        await self.client.aclose()
