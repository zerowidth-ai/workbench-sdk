"""
Message Node - Manually create a single message.
"""

import re
from typing import Any


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
    variables = inputs.get("variables", [])
    if variables is None:
        variables = []

    # If we have variables and text content, replace {{key}} with variable values
    if message.get("content") and isinstance(message["content"], list):
        text_content_index = next(
            (i for i, item in enumerate(message["content"])
             if isinstance(item, dict) and item.get("type") == "text"),
            -1
        )
        if text_content_index != -1:
            def replace_variable(match):
                key = match.group(1)
                # Look for a variable with the matching key
                for variable in variables:
                    if isinstance(variable, dict) and key in variable:
                        return str(variable[key])
                return match.group(0)  # Return original if no match

            message["content"][text_content_index]["text"] = re.sub(
                r"\{\{(.*?)\}\}",
                replace_variable,
                message["content"][text_content_index]["text"]
            )

    return {
        "message": message,
    }
