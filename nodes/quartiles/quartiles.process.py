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
    return {
      "q1": 0,
      "q2": 0,
      "q3": 0,
      "iqr": 0
    }
    
  sorted_nums = sorted(valid_numbers)
  length = len(sorted_nums)
  
  # Handle single value case
  if length == 1:
    return {
      "q1": sorted_nums[0],
      "q2": sorted_nums[0],
      "q3": sorted_nums[0],
      "iqr": 0
    }
  
  def get_median(arr):
    if not arr:
      return 0
    n = len(arr)
    mid = n // 2
    return arr[mid] if n % 2 else (arr[mid - 1] + arr[mid]) / 2
  
  mid = length // 2
  q2 = get_median(sorted_nums)
  
  # Calculate Q1 (median of lower half)
  lower_half = sorted_nums[:mid]
  q1 = get_median(lower_half)
  
  # Calculate Q3 (median of upper half)
  upper_half = sorted_nums[mid + 1:] if length % 2 else sorted_nums[mid:]
  q3 = get_median(upper_half)
  
  return {
    "q1": q1,
    "q2": q2,
    "q3": q3,
    "iqr": q3 - q1
  } 