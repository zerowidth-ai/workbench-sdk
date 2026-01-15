"""
Input Prompt Node - Accepts a text prompt as input to the flow.
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
    Process function for the Input Prompt node.
    """
    return {
        "prompt": settings.get("prompt", ""),
    }
