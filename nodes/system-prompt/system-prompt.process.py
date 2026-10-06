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
        key = match.group(1)
        # Look for a variable with the matching key
        for variable in variables:
            if isinstance(variable, dict) and key in variable:
                return _render_variable(variable[key])
        return match.group(0)  # Return original if no match

    def fill(text: str) -> str:
        return re.sub(r"\{\{(.*?)\}\}", replace_variable, text)

    # Values filled in can change from run to run (the time, memory, search
    # results); the text before the first of them doesn't. The message keeps
    # the two as separate blocks and marks the fixed one with cache_control,
    # so a model that caches on request can reuse the prompt up to there.
    # The model client removes the mark for models that don't take it.
    first_filled = -1
    for match in re.finditer(r"\{\{(.*?)\}\}", full_content):
        if any(isinstance(v, dict) and match.group(1) in v for v in variables):
            first_filled = match.start()
            break

    cache = {"type": "ephemeral"}
    if first_filled < 0:
        block = {"type": "text", "text": full_content}
        if full_content.strip():
            block["cache_control"] = cache
        blocks = [block]
    else:
        fixed = full_content[:first_filled]
        changing = fill(full_content[first_filled:])
        if fixed.strip():
            blocks = [{"type": "text", "text": fixed, "cache_control": cache}]
            if changing:
                blocks.append({"type": "text", "text": changing})
        else:
            blocks = [{"type": "text", "text": changing}]

    message = {"role": "system", "content": blocks}

    # Return the message and string prompt
    return {
        "message": message,
        "prompt": "".join(block["text"] for block in blocks),
    }
