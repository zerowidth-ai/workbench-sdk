from typing import Any

async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    """
    Process function for the Array Builder node.
    """
    items = inputs.get("items")

    if items is None:
        return {"array": []}

    array = items if isinstance(items, list) else [items]

    return {"array": array}
