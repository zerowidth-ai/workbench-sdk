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
    
  valid_numbers = []
  for n in numbers:
    try:
      num = float(n)
      if not isinstance(num, complex) and not isinstance(n, bool):
        valid_numbers.append(num)
    except (ValueError, TypeError):
      continue
  
  if not valid_numbers:
    return {
      "min": 0,
      "max": 0,
      "range": 0
    }
    
  min_val = min(valid_numbers)
  max_val = max(valid_numbers)
  
  return {
    "min": min_val,
    "max": max_val,
    "range": max_val - min_val
  } 