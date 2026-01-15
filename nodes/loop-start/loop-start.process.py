"""
Loop Start Node - Entry point for loops.
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
    Process function for the Loop Start node.
    Simply passes through the value - refiring behavior is handled by the engine.
    """
    return {
        "value": inputs.get("value"),
    }
