"""
Filter Tools Node - Filter tools by name for dynamic tool selection.
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
    Filter an array of tools by name.

    Args:
        inputs: Contains 'tools' (array of tool definitions) and 'include' (array of tool names)

    Returns:
        Dict with 'tools' containing only tools whose names are in the include list.
    """
    tools = inputs.get("tools", [])
    include = inputs.get("include", [])

    if not include:
        return {"tools": []}

    include_set = set(include)
    filtered = [t for t in tools if t.get("name") in include_set]

    return {"tools": filtered}
