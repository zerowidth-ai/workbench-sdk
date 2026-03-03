"""
MCP (Model Context Protocol) utilities for the zv1 engine.

Provides functions for calling remote MCP tools and fetching tool schemas.
MCP is a protocol for exposing tools/functions from remote servers.
"""

from __future__ import annotations

import uuid
from typing import Any, Optional

import httpx


# Module-level cache for MCP schemas
_mcp_schema_cache: dict[str, list[dict[str, Any]]] = {}


async def call_mcp_tool(
    args: dict[str, Any],
    *,
    url: str,
    token: Optional[str] = None,
) -> Any:
    """
    Call an MCP tool.

    Args:
        args: The arguments to pass to the tool (must include 'name').
        url: The MCP server URL.
        token: Optional bearer token for authentication.

    Returns:
        The result from the MCP tool call.

    Raises:
        RuntimeError: If the call fails.
    """
    if not url:
        raise RuntimeError("No MCP URL provided")

    tool_name = args.get("name")
    if not tool_name:
        raise RuntimeError("No tool name provided for MCP call")

    # Separate name from the rest of the args
    tool_args = {k: v for k, v in args.items() if k != "name"}

    request_id = str(uuid.uuid4())

    payload = {
        "id": request_id,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": tool_args,
        },
    }

    headers: dict[str, str] = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            return data.get("result")

    except httpx.HTTPError as e:
        raise RuntimeError(f"Failed to call MCP tool \"{tool_name}\" at {url}: {e}") from e
    except Exception as e:
        raise RuntimeError(f"Failed to call MCP tool \"{tool_name}\" at {url}: {e}") from e


async def fetch_mcp_tools(
    url: str,
    token: Optional[str] = None,
    *,
    use_cache: bool = True,
) -> list[dict[str, Any]]:
    """
    Fetch all available tools from an MCP endpoint.

    Args:
        url: The MCP server URL.
        token: Optional bearer token for authentication.
        use_cache: Whether to use cached schemas (default True).

    Returns:
        List of tool schemas, each with name, description, and parameters.

    Raises:
        RuntimeError: If fetching fails.
    """
    if not url:
        raise RuntimeError("No MCP URL provided")

    # Check cache
    if use_cache and url in _mcp_schema_cache:
        return _mcp_schema_cache[url]

    request_id = str(uuid.uuid4())

    payload = {
        "id": request_id,
        "method": "tools/list",
        "params": {},
    }

    headers: dict[str, str] = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

            tools_data = data.get("result", {}).get("tools", [])

            schemas: list[dict[str, Any]] = []
            for tool in tools_data:
                schema = {
                    "name": tool.get("name", ""),
                    "description": tool.get("description", ""),
                    "parameters": tool.get("inputSchema", {
                        "type": "object",
                        "properties": {},
                        "required": [],
                    }),
                }
                schemas.append(schema)

            # Cache the result
            _mcp_schema_cache[url] = schemas

            return schemas

    except httpx.HTTPError as e:
        raise RuntimeError(f"Failed to fetch MCP tools from {url}: {e}") from e
    except Exception as e:
        raise RuntimeError(f"Failed to fetch MCP tools from {url}: {e}") from e


def clear_mcp_cache() -> None:
    """Clear the MCP schema cache."""
    _mcp_schema_cache.clear()


def is_remote_mcp_tool(node: dict[str, Any]) -> bool:
    """
    Check if a node is a remote MCP tool.

    Args:
        node: The node to check.

    Returns:
        True if the node is a remote MCP tool.
    """
    return node.get("type") == "remote-mcp-tool"
