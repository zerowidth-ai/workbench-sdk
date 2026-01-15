"""
AND Gate Node - Logical AND of two boolean inputs.
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
    Process function for the AND Gate node.
    """
    input1 = bool(inputs.get("input1"))
    input2 = bool(inputs.get("input2"))

    # AND logic
    result = input1 and input2

    return {"value": result}
