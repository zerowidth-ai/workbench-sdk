"""
Pinecone Integration for the zv1 engine.

Provides vector query and upsert via the Pinecone REST API.
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


class PineconeIntegration:
    def __init__(self, config: dict[str, str] | str, timeout: float = 30.0) -> None:
        if not HAS_HTTPX:
            raise ImportError("httpx package is required for Pinecone integration.")
        if isinstance(config, dict):
            self.api_key = config.get("api_key") or config.get("key", "")
            self.host = config.get("host", "")
        else:
            self.api_key = config
            self.host = ""
        self.client = httpx.AsyncClient(
            timeout=timeout,
            headers={"Api-Key": self.api_key, "Content-Type": "application/json"},
        )

    async def _request(self, method: str, url: str, json_data: dict[str, Any] | None = None) -> dict[str, Any]:
        start_time = int(time.time() * 1000)
        request_headers = dict(self.client.headers)
        try:
            response = await self.client.request(method, url, json=json_data)
            await emit_api_call_event(getattr(self, "_engine_config", None), {
                "timestamp": start_time, "integration": "pinecone", "nodeId": None, "nodeType": None,
                "request": {"method": method, "url": url, "headers": request_headers, "body": json_data},
                "response": {"status": response.status_code, "statusText": response.reason_phrase or ""},
                "duration": int(time.time() * 1000) - start_time, "error": None,
            })
            if response.status_code >= 400:
                msg = response.text or response.reason_phrase
                raise Exception(f"Pinecone API error ({response.status_code}): {msg}")
            return response.json()
        except Exception as e:
            if "Pinecone API error" not in str(e):
                await emit_api_call_event(getattr(self, "_engine_config", None), {
                    "timestamp": start_time, "integration": "pinecone", "nodeId": None, "nodeType": None,
                    "request": {"method": method, "url": url, "headers": request_headers, "body": json_data},
                    "response": {"status": 0, "statusText": "Error"},
                    "duration": int(time.time() * 1000) - start_time, "error": str(e),
                })
            raise

    async def query(self, vector: list[float], top_k: int = 10, namespace: str | None = None,
                    filter: dict | None = None, include_metadata: bool = True, include_values: bool = False) -> dict[str, Any]:
        data: dict[str, Any] = {"vector": vector, "topK": top_k, "includeMetadata": include_metadata, "includeValues": include_values}
        if namespace:
            data["namespace"] = namespace
        if filter:
            data["filter"] = filter
        return await self._request("POST", f"{self.host}/query", json_data=data)

    async def upsert(self, vectors: list[dict], namespace: str | None = None) -> dict[str, Any]:
        data: dict[str, Any] = {"vectors": vectors}
        if namespace:
            data["namespace"] = namespace
        return await self._request("POST", f"{self.host}/vectors/upsert", json_data=data)

    async def close(self) -> None:
        await self.client.aclose()
