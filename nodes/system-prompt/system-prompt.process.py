"""
System Prompt Node - Outputs a message object with the prompt text and system role.
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
# text to use when `name` is missing or empty. Inside the quotes, `\"` is a
# quote and `\\` a backslash. Spaces around the parts are allowed.
_TOKEN = re.compile(r'^\s*([A-Za-z_][A-Za-z0-9_]*)\s*(?::\s*"((?:[^"\\]|\\.)*)")?\s*$')


def _is_empty(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


def _resolve_token(variables: list, inner: str):
    """
    The text a {{...}} token becomes, or None to leave it as written: a
    variable's value, else the token's fallback when the value is missing or
    empty. A token naming nothing, with no fallback, stays in the text.
    """
    # An exact key first, so keys that aren't plain names keep working.
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
    Process function for the System Prompt node.
    Outputs a message object, containing the prompt text and system role.
    """
    # Initialize variables list if not provided
    variables = _flatten_variables(inputs.get("variables"))

    # Get the base content from settings
    base_content = settings.get("content", "")

    # Handle chain input if provided
    chained_content = ""
    chain = inputs.get("chain")
    if chain:
        if isinstance(chain, str):
            chained_content = chain
        elif isinstance(chain, dict) and chain.get("content"):
            # Handle message object format
            content = chain.get("content")
            if isinstance(content, list):
                # Extract text content from array format
                text_parts = [
                    item.get("text", "")
                    for item in content
                    if isinstance(item, dict) and item.get("type") == "text"
                ]
                chained_content = "\n".join(text_parts)
            elif isinstance(content, str):
                chained_content = content

    # Combine chained content with base content
    if chained_content:
        full_content = f"{chained_content}\n\n{base_content}"
    else:
        full_content = base_content

    # Process variables - replace {{key}} with variable value
    def replace_variable(match):
        resolved = _resolve_token(variables, match.group(1))
        return match.group(0) if resolved is None else resolved

    def fill(text: str) -> str:
        return re.sub(r"\{\{(.*?)\}\}", replace_variable, text)

    # Values filled in can change from run to run (the time, memory, search
    # results); the text before the first of them doesn't. The block records
    # that length as cache_prefix_length, so the model client can cache the
    # prompt up to there for a model that caches on request. The client
    # removes the hint before any model sees it.
    first_filled = -1
    for match in re.finditer(r"\{\{(.*?)\}\}", full_content):
        # A fallback is filled in too, so it ends the fixed part as a value does.
        if _resolve_token(variables, match.group(1)) is not None:
            first_filled = match.start()
            break

    if first_filled < 0:
        text, prefix = full_content, len(full_content)
    else:
        text = full_content[:first_filled] + fill(full_content[first_filled:])
        prefix = first_filled
    block: dict[str, Any] = {"type": "text", "text": text}
    if text[:prefix].strip():
        block["cache_prefix_length"] = prefix
    message = {"role": "system", "content": [block]}

    # Return the message and string prompt
    return {
        "message": message,
        "prompt": text,
    }
