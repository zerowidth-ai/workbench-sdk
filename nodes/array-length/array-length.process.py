from typing import Any

async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    """
    Process function for the Array Length node.
    """
    array = inputs.get("array", [])

    # Default length to 0 if not an array
    length = 0

    # Check if the input is an array and calculate its length
    if isinstance(array, list):
        length = len(array)

    return {"length": length}
