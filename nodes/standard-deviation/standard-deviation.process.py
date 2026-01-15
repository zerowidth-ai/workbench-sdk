from typing import Any
import math

async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
  numbers = inputs.get("numbers", [])
  if not isinstance(numbers, list):
    numbers = [numbers]
    
  # Validate all inputs are numbers
  for n in numbers:
    try:
      float(n)
    except (ValueError, TypeError):
      raise ValueError("Input contains non-numeric values that cannot be processed")
  
  # Convert all values to numbers
  valid_numbers = [float(n) for n in numbers]
  
  if not valid_numbers:
    return {
      "result": 0,
      "variance": 0
    }
    
  # Calculate mean
  mean = sum(valid_numbers) / len(valid_numbers)
  
  # Calculate variance
  variance = sum((x - mean) ** 2 for x in valid_numbers) / len(valid_numbers)
  
  return {
    "result": math.sqrt(variance),
    "variance": variance
  } 