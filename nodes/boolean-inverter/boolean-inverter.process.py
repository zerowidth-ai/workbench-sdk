from typing import Any

async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    """
    Process function for the Boolean Inverter node.
    """
    input_value = inputs.get("input")

    if not isinstance(input_value, bool):
        raise ValueError("Input must be a boolean value.")

    # Invert the boolean value
    output = not input_value

    return {"output": output}
