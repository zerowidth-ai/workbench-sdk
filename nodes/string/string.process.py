from typing import Any

async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    """
    Process function for the String node.
    Outputs a string value, either from the input or from the settings.
    """
    # If an input value is provided, use it; otherwise use the value from settings
    string_value = inputs.get("value") if "value" in inputs else settings.get("value", "Hello, world!")
    
    # Return the string value
    return {
        "value": string_value
    } 