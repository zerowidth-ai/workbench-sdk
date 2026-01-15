from typing import Any

async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    """
    Process function for the Greater Than node.
    Checks if the first number is greater than the second number.
    """
    # Convert inputs to numbers to ensure proper comparison
    a = float(inputs.get("a", 0))
    b = float(inputs.get("b", 0))

    # Check if A is greater than B
    result = a > b

    return {"result": result} 