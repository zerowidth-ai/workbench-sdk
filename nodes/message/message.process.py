"""
Message Node - Manually create a single message.
"""

import json
import re
from typing import Any


def _render_variable(value: Any) -> str:
    """
    Render a variable value for injection into prompt text.
    Strings pass through untouched; everything else is JSON encoded so that
    nested objects and lists read as data instead of a Python repr.
    """
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, indent=2)
    except (TypeError, ValueError):
        # Anything JSON can't encode falls back to the default coercion
        # rather than failing the whole prompt.
        return str(value)


# A token's key and its fallback: `name`, or `name:"Unknown Name"` for the
# text to use when `name` is missing or empty. Same rules as the System
# Prompt node.
_TOKEN = re.compile(r'^\s*([A-Za-z_][A-Za-z0-9_]*)\s*(?::\s*"((?:[^"\\]|\\.)*)")?\s*$')


def _is_empty(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


def _resolve_token(variables: list, inner: str):
    """The text a {{...}} token becomes, or None to leave it as written."""
    for variable in variables:
        if isinstance(variable, dict) and inner in variable:
            return _render_variable(variable[inner])
    m = _TOKEN.match(inner)
    if not m:
        return None
    key = m.group(1)
    fallback = None if m.group(2) is None else re.sub(r"\\(.)", r"\1", m.group(2))
    found = next((v for v in variables if isinstance(v, dict) and key in v), None)
    value = found[key] if found is not None else None
    if not _is_empty(value):
        return _render_variable(value)
    if fallback is not None:
        return fallback
    return _render_variable(value) if found is not None else None


def _flatten_variables(variables: Any) -> list:
    """
    A single connection can deliver a list of key-value objects, so flatten
    one level and keep only dicts.
    """
    if variables is None:
        return []
    if not isinstance(variables, list):
        variables = [variables]
    flat = []
    for entry in variables:
        if isinstance(entry, list):
            flat.extend(item for item in entry if isinstance(item, dict))
        elif isinstance(entry, dict):
            flat.append(entry)
    return flat


async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    """
    Process function for the Message node.
    Outputs a message object, either from the input or from the settings.
    """
    # Build message from inputs (if provided) or settings
    message = {
        "role": inputs.get("role") if inputs.get("role") is not None else settings.get("role"),
        "content": inputs.get("content") if inputs.get("content") is not None else settings.get("content"),
    }

    # If content is a string, convert to content array format
    if isinstance(message.get("content"), str):
        message["content"] = [{"type": "text", "text": message["content"]}]

    # Initialize variables list if not provided
    variables = _flatten_variables(inputs.get("variables"))

    # If we have variables and text content, replace {{key}} with variable values
    if message.get("content") and isinstance(message["content"], list):
        text_content_index = next(
            (i for i, item in enumerate(message["content"])
             if isinstance(item, dict) and item.get("type") == "text"),
            -1
        )
        if text_content_index != -1:
            def replace_variable(match):
                resolved = _resolve_token(variables, match.group(1))
                return match.group(0) if resolved is None else resolved

            message["content"][text_content_index]["text"] = re.sub(
                r"\{\{(.*?)\}\}",
                replace_variable,
                message["content"][text_content_index]["text"]
            )

    return {
        "message": message,
    }
