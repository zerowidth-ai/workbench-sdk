"""
Array Index Selector Node - Selects an element from an array by index.
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
    Process function for the Array Index Selector node.
    """
    array = inputs.get("array", [])
    index = inputs.get("index", 0)

    index_to_use = index

    # Check if index is a number and round it
    if isinstance(index_to_use, (int, float)):
        index_to_use = round(index_to_use)

    # Check if index is in bounds
    if not isinstance(array, list) or index_to_use < 0 or index_to_use >= len(array):
        raise IndexError(f"Index {index_to_use} is out of bounds for array of length {len(array) if isinstance(array, list) else 0}")

    element = array[index_to_use]

    return {"element": element}
