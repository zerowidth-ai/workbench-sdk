"""
Output Data Node - Outputs data from the flow.
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
    Process function for the Output Data node.

    Args:
        inputs: Node inputs containing 'value' to output.
        settings: Node settings (unused for this node).
        config: Engine configuration.
        node_config: Node configuration from config.json.

    Returns:
        Dictionary with 'value' containing the output value.
    """
    return {"value": inputs.get("value")} 