"""
Condition Check Node - Routes a value based on a boolean condition.
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
    Process function for the Condition Check node.
    """
    value = inputs.get("value")
    condition = inputs.get("condition")

    if condition:
        return {
            "passed": value,
            "blocked": None,
        }
    else:
        return {
            "passed": None,
            "blocked": value,
        }
