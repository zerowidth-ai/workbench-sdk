from typing import Any

async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    """
    Process function for the Boolean Switch node.
    """
    retval = inputs.get("value", settings.get("value", False))

    # Ensure the value is a boolean
    retval = bool(retval)

    return {"value": retval}
