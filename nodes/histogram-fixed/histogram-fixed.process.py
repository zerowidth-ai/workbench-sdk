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
    
  # Fix the validation to match the JavaScript implementation
  valid_numbers = []
  for n in numbers:
    try:
      num = float(n)
      if not isinstance(num, complex) and not isinstance(n, bool):
        valid_numbers.append(num)
    except (ValueError, TypeError):
      continue
    
  start = float(inputs.get("start", 0))
  bin_size = max(0.000001, float(inputs.get("bin_size", 1)))
  bin_count = max(1, int(inputs.get("bin_count", 10)))
  
  # Create bin boundaries - convert to integers if they are whole numbers
  bins = []
  for i in range(bin_count + 1):
    value = start + (bin_size * i)
    # Convert to integer if it's a whole number to match JavaScript output
    if value.is_integer():
      bins.append(int(value))
    else:
      bins.append(value)
  
  # Initialize counts
  counts = [0] * bin_count
  overflow = 0
  underflow = 0
  
  # If we have valid numbers, count them in bins
  if valid_numbers:
    # Count values in each bin
    for num in valid_numbers:
      if num < start:
        underflow += 1
        continue
        
      bin_index = int((num - start) / bin_size)
      if bin_index >= bin_count:
        overflow += 1
      else:
        counts[bin_index] += 1
        
  return {
    "bins": bins,
    "counts": counts,
    "overflow": overflow,
    "underflow": underflow
  } 