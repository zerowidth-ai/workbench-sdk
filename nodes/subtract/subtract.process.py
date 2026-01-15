"""
Subtract Node - Subtracts one number from another.
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
    Process function for the Subtract node.

    Args:
        inputs: Node inputs containing 'a' and 'b' numbers.
        settings: Node settings (unused for this node).
        config: Engine configuration.
        node_config: Node configuration from config.json.

    Returns:
        Dictionary with 'result' containing a - b.
    """
    a = float(inputs.get("a") or 0)
    b = float(inputs.get("b") or 0)

    # Calculate the result
    result = a - b

    # Handle floating point precision issues
    result = float(format(result, '.10f'))

    return {"result": result} 