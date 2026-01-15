"""
Temperature Node - Outputs a temperature value with validation.
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
    Process function for the Temperature node.
    """
    # Use input value if provided, otherwise use the setting value
    input_value = inputs.get("value")
    if input_value is not None:
        value = float(input_value)
    else:
        value = float(settings.get("value", 0))

    # Hard-code min to 0, max based on allow_experimental setting
    min_val = 0
    max_val = 2 if settings.get("allow_experimental") else 1

    # Clamp value to valid range
    value = max(min_val, min(max_val, value))

    return {"value": value}
