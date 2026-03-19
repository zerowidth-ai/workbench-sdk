"""
Jira Integration for the zv1 engine.

Provides issue management via the Jira REST API v3.
"""

from __future__ import annotations

import base64
import time
from typing import Any

from src.utilities.sanitize_api_call import emit_api_call_event

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False


class JiraIntegration:
    def __init__(self, config: dict[str, str] | str, timeout: float = 30.0) -> None:
        if not HAS_HTTPX:
            raise ImportError("httpx package is required for Jira integration.")
        if isinstance(config, dict):
            self.email = config["email"]
            self.api_token = config["api_token"]
            self.domain = config["domain"]
        else:
            raise Exception("Jira integration requires an object with email, api_token, and domain")

        auth = base64.b64encode(f"{self.email}:{self.api_token}".encode()).decode()
        self.base_url = f"https://{self.domain}/rest/api/3"
        self.client = httpx.AsyncClient(
            timeout=timeout,
            headers={
                "Authorization": f"Basic {auth}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )

    async def _request(self, method: str, url: str, params: dict | None = None,
                       json_data: dict | None = None) -> Any:
        start_time = int(time.time() * 1000)
        request_headers = dict(self.client.headers)
        try:
            response = await self.client.request(method, url, params=params, json=json_data)
            await emit_api_call_event(getattr(self, "_engine_config", None), {
                "timestamp": start_time, "integration": "jira", "nodeId": None, "nodeType": None,
                "request": {"method": method, "url": url, "headers": request_headers, "body": json_data},
                "response": {"status": response.status_code, "statusText": response.reason_phrase or ""},
                "duration": int(time.time() * 1000) - start_time, "error": None,
            })
            if response.status_code >= 400:
                error_data = response.json() if response.content else {}
                error_msgs = error_data.get("errorMessages", [])
                field_errors = error_data.get("errors", {})
                if error_msgs:
                    msg = "; ".join(error_msgs)
                elif field_errors:
                    msg = "; ".join(f"{k}: {v}" for k, v in field_errors.items())
                else:
                    msg = response.reason_phrase or "Unknown error"
                raise Exception(f"Jira API error ({response.status_code}): {msg}")
            return response.json() if response.content else None
        except Exception as e:
            if "Jira API error" not in str(e):
                await emit_api_call_event(getattr(self, "_engine_config", None), {
                    "timestamp": start_time, "integration": "jira", "nodeId": None, "nodeType": None,
                    "request": {"method": method, "url": url, "headers": request_headers, "body": json_data},
                    "response": {"status": 0, "statusText": "Error"},
                    "duration": int(time.time() * 1000) - start_time, "error": str(e),
                })
            raise

    async def create_issue(self, project_key: str, summary: str, issue_type: str = "Task",
                           description: str | None = None, assignee_id: str | None = None,
                           priority: str | None = None, labels: list[str] | None = None,
                           parent_key: str | None = None) -> dict[str, Any]:
        fields: dict[str, Any] = {
            "project": {"key": project_key},
            "summary": summary,
            "issuetype": {"name": issue_type},
        }
        if description:
            fields["description"] = {
                "type": "doc", "version": 1,
                "content": [{"type": "paragraph", "content": [{"type": "text", "text": description}]}],
            }
        if assignee_id:
            fields["assignee"] = {"accountId": assignee_id}
        if priority:
            fields["priority"] = {"name": priority}
        if labels:
            fields["labels"] = labels
        if parent_key:
            fields["parent"] = {"key": parent_key}

        return await self._request("POST", f"{self.base_url}/issue", json_data={"fields": fields})

    async def list_issues(self, jql: str, max_results: int = 25, start_at: int = 0,
                          fields: list[str] | None = None) -> dict[str, Any]:
        data: dict[str, Any] = {
            "jql": jql,
            "maxResults": max_results,
            "startAt": start_at,
            "fields": fields or ["summary", "status", "assignee", "priority", "created", "updated", "issuetype"],
        }
        return await self._request("POST", f"{self.base_url}/search", json_data=data)

    async def update_issue(self, issue_key: str, fields: dict[str, Any]) -> None:
        await self._request("PUT", f"{self.base_url}/issue/{issue_key}", json_data={"fields": fields})

    async def close(self) -> None:
        await self.client.aclose()
