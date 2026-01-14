"""
Helper utilities for the zv1 engine.

This module provides various utility functions used throughout the engine.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def create_safe_tool_name(name: str) -> str:
    """
    Create a safe tool name that matches the pattern ^[a-zA-Z0-9_-]+$.

    Args:
        name: The name to make safe.

    Returns:
        A sanitized name containing only alphanumeric characters,
        underscores, and hyphens, truncated to 64 characters.
    """
    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "", name)
    return safe_name[:64]


def is_remote_mcp_tool(node: dict[str, Any]) -> bool:
    """
    Check if a node is a remote MCP tool.

    Args:
        node: The node dict to check.

    Returns:
        True if the node is a remote MCP tool.
    """
    return node.get("type") == "remote-mcp-tool"


def is_manual_tool_node(node: dict[str, Any]) -> bool:
    """
    Check if a node is a manual tool node.

    Args:
        node: The node dict to check.

    Returns:
        True if the node is a manual tool node.
    """
    return node.get("type") == "tool"


def map_type_to_json_schema(type_str: str | None) -> str:
    """
    Map node semantic input types to JSON Schema types for tool parameters.

    Args:
        type_str: The type string to map.

    Returns:
        The corresponding JSON Schema type.
    """
    if not type_str:
        return "string"

    t = type_str.lower()

    if t in ("number", "integer"):
        return "number"
    if t == "boolean":
        return "boolean"
    if t.startswith("array"):
        return "array"
    if t == "object":
        return "object"

    return "string"


def get_src_dir() -> Path:
    """
    Get the src directory path.

    Returns:
        Path to the src directory.
    """
    return Path(__file__).parent


def get_nodes_dir() -> Path:
    """
    Get the nodes directory path.

    Returns:
        Path to the nodes directory (relative to SDK root).
    """
    return Path(__file__).parent.parent / "nodes"


def get_types_dir() -> Path:
    """
    Get the types directory path.

    Returns:
        Path to the types directory (relative to SDK root).
    """
    return Path(__file__).parent.parent / "types"


def extract_text_from_content(content: str | list[Any] | None) -> str:
    """
    Extract text content from a message's content field.

    Handles both string and array content formats.

    Args:
        content: The content field from a message. Can be a string,
                 a list of content items, or None.

    Returns:
        Extracted text content as a string.
    """
    if isinstance(content, str):
        return content

    if content is None:
        return ""

    if isinstance(content, list):
        text_parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                # Extract text from content items with type 'text'
                if item.get("type") == "text" and item.get("text"):
                    text_parts.append(str(item["text"]))
        return "".join(text_parts)

    return str(content) if content else ""


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """
    Deep merge two dictionaries.

    Values from override take precedence. Nested dicts are merged recursively.

    Args:
        base: The base dictionary.
        override: The dictionary to merge on top.

    Returns:
        A new merged dictionary.
    """
    result = base.copy()

    for key, value in override.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value

    return result


def normalize_messages(
    messages: str | dict[str, Any] | list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """
    Normalize messages input to a list of message dicts.

    Args:
        messages: Can be a string (converted to user message),
                  a single message dict, or a list of messages.

    Returns:
        A list of message dictionaries.
    """
    if isinstance(messages, str):
        return [{"role": "user", "content": messages}]

    if isinstance(messages, dict):
        return [messages]

    if isinstance(messages, list):
        return messages

    return []


def ensure_list(value: Any) -> list[Any]:
    """
    Ensure a value is a list.

    Args:
        value: Any value.

    Returns:
        The value wrapped in a list if not already a list.
    """
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def safe_get(obj: dict[str, Any] | None, *keys: str, default: Any = None) -> Any:
    """
    Safely get a nested value from a dictionary.

    Args:
        obj: The dictionary to get from.
        *keys: The keys to traverse.
        default: Default value if key not found.

    Returns:
        The value at the nested key path, or default.
    """
    if obj is None:
        return default

    current = obj
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default

    return current
