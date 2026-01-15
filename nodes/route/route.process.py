"""
Route Node - Routes value to true or false output based on condition.
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
    Process function for the Route node.
    """
    value = inputs.get("value")
    condition = inputs.get("condition")

    if condition:
        return {
            "true_output": value,
            "false_output": None,
        }
    else:
        return {
            "true_output": None,
            "false_output": value,
        }
