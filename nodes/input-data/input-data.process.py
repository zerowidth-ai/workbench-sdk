"""
Input Data Node - Provides variable input from the user.
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
    Process function for the Variable Input node.
    Requests a variable from the user via the engine.

    Args:
        inputs: Node inputs (unused for input nodes).
        settings: Node settings containing key, value, type, etc.
        config: Engine configuration.
        node_config: Node configuration from config.json.

    Returns:
        Dictionary with 'value' and 'data' containing the input value.
    """
    # First check for an explicit value, then fall back to default_value
    value = settings.get("value")
    if value is None:
        value = settings.get("default_value")

    # If the type is select, we need to ensure the value is one of the options
    if settings.get("type") == "select" and settings.get("options"):
        options = settings["options"]
        # Handle both string and list formats for options
        if isinstance(options, str):
            options = [opt.strip() for opt in options.split(",")]
        elif isinstance(options, list):
            options = [str(opt).strip() for opt in options]

        if value not in options:
            raise ValueError(
                f"Invalid value for select variable {settings.get('key')}: {value}"
            )

    return {
        "value": value,
        "data": {settings.get("key"): value},
    }
