"""
Output Chat Node - Outputs a chat message to the user.
"""

from typing import Any


async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    """
    Process function for the Output Chat node.
    """
    result = []

    if inputs.get("message"):
        message = inputs.get("message")
        if isinstance(message, list):
            result.extend(message)
        else:
            result.append(message)
    elif inputs.get("content"):
        result.append({
            "content": inputs.get("content"),
            "role": inputs.get("role") or "assistant",
        })

    return {
        "chat": result,
    }
