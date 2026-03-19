"""
GitHub Integration for the zv1 engine.

Provides issue management via the GitHub REST API.
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


class GithubIntegration:
    def __init__(self, api_key: str, base_url: str = "https://api.github.com", timeout: float = 30.0) -> None:
        if not HAS_HTTPX:
            raise ImportError("httpx package is required for GitHub integration.")
        self.api_key = api_key
        self.base_url = base_url
        self.client = httpx.AsyncClient(
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "Content-Type": "application/json",
            },
        )

    async def _request(self, method: str, url: str, params: dict | None = None, json_data: dict | None = None) -> Any:
        start_time = int(time.time() * 1000)
        request_headers = dict(self.client.headers)
        try:
            response = await self.client.request(method, url, params=params, json=json_data)
            await emit_api_call_event(getattr(self, "_engine_config", None), {
                "timestamp": start_time, "integration": "github", "nodeId": None, "nodeType": None,
                "request": {"method": method, "url": url, "headers": request_headers, "body": json_data},
                "response": {"status": response.status_code, "statusText": response.reason_phrase or ""},
                "duration": int(time.time() * 1000) - start_time, "error": None,
            })
            if response.status_code >= 400:
                msg = response.json().get("message", response.reason_phrase) if response.content else response.reason_phrase
                raise Exception(f"GitHub API error ({response.status_code}): {msg}")
            return response.json()
        except Exception as e:
            if "GitHub API error" not in str(e):
                await emit_api_call_event(getattr(self, "_engine_config", None), {
                    "timestamp": start_time, "integration": "github", "nodeId": None, "nodeType": None,
                    "request": {"method": method, "url": url, "headers": request_headers, "body": json_data},
                    "response": {"status": 0, "statusText": "Error"},
                    "duration": int(time.time() * 1000) - start_time, "error": str(e),
                })
            raise

    async def create_issue(self, owner: str, repo: str, title: str, body: str | None = None,
                           labels: list[str] | None = None, assignees: list[str] | None = None) -> dict[str, Any]:
        data: dict[str, Any] = {"title": title}
        if body:
            data["body"] = body
        if labels:
            data["labels"] = labels
        if assignees:
            data["assignees"] = assignees
        return await self._request("POST", f"{self.base_url}/repos/{owner}/{repo}/issues", json_data=data)

    async def list_issues(self, owner: str, repo: str, state: str = "open", labels: str | None = None,
                          per_page: int = 30, page: int = 1) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"state": state, "per_page": per_page, "page": page}
        if labels:
            params["labels"] = labels
        return await self._request("GET", f"{self.base_url}/repos/{owner}/{repo}/issues", params=params)

    async def close(self) -> None:
        await self.client.aclose()
