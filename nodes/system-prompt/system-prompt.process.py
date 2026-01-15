"""
System Prompt Node - Outputs a message object with the prompt text and system role.
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
    Process function for the System Prompt node.
    Outputs a message object, containing the prompt text and system role.
    """
    # Initialize variables list if not provided
    variables = inputs.get("variables", [])
    if variables is None:
        variables = []

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

    # Create message object
    message = {
        "role": "system",
        "content": [
            {
                "type": "text",
                "text": full_content,
            }
        ],
    }

    # Process variables - replace {{key}} with variable value
    def replace_variable(match):
        key = match.group(1)
        # Look for a variable with the matching key
        for variable in variables:
            if isinstance(variable, dict) and key in variable:
                return str(variable[key])
        return match.group(0)  # Return original if no match

    message["content"][0]["text"] = re.sub(
        r"\{\{(.*?)\}\}",
        replace_variable,
        message["content"][0]["text"]
    )

    # Return the message and string prompt
    return {
        "message": message,
        "prompt": message["content"][0]["text"],
    }
