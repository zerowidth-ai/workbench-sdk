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
    Process function for the Random Error node.
    Randomly raises an exception based on probability, or passes through the value.
    """
    value = inputs.get("value")
    error_probability = float(inputs.get("errorProbability", 0.1))  # Default to 10% chance
    error_message = inputs.get("errorMessage", "Random error occurred")
    error_type = inputs.get("errorType", "RandomError")
    
    # Validate probability is between 0 and 1
    probability = max(0.0, min(1.0, error_probability))
    
    # Generate random number between 0 and 1
    random_val = random.random()
    
    # Raise error if random number is less than probability
    if random_val < probability:
        class RandomError(Exception):
            def __init__(self, message, probability, random_value):
                super().__init__(message)
                self.name = error_type
                self.probability = probability
                self.random_value = random_value
        
        raise RandomError(error_message, probability, random_val)
    
    # Otherwise, pass through the value
    return {"result": value} 