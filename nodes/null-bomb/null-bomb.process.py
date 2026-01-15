from typing import Any
import random

async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    """
    Process function for the Null Bomb node.
    Randomly returns None based on probability, or passes through the original value.
    """
    value = inputs.get("value")
    null_probability = float(inputs.get("nullProbability", 0.1))  # Default to 10% chance
    
    # Validate probability is between 0 and 1
    probability = max(0.0, min(1.0, null_probability))
    
    # Generate random number between 0 and 1
    random_val = random.random()
    
    # Return None if random number is less than probability
    if random_val < probability:
        return {"result": None}
    
    # Otherwise, pass through the original value
    return {"result": value} 