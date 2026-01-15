from typing import Any

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
    return {"result": 0}
    
  # Sort the numbers
  sorted_numbers = sorted(valid_numbers)
  
  # Find the median
  n = len(sorted_numbers)
  mid = n // 2
  
  if n % 2 == 0:
    # Even number of elements
    result = (sorted_numbers[mid - 1] + sorted_numbers[mid]) / 2
  else:
    # Odd number of elements
    result = sorted_numbers[mid]
    
  return {"result": result} 