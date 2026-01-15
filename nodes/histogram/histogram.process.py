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
  
  # Check if all values are numeric
  valid_numbers = []
  for n in numbers:
    try:
      valid_numbers.append(float(n))
    except (ValueError, TypeError):
      # If we encounter a non-numeric value, throw an error
      raise ValueError("Input contains non-numeric values that cannot be processed")
  
  num_bins = max(1, int(inputs.get("bins", 10)))
  
  if not valid_numbers:
    return {
      "bins": [],
      "counts": []
    }
    
  # Calculate bin boundaries
  min_val = min(valid_numbers)
  max_val = max(valid_numbers)
  
  # Handle the case where all values are the same
  if min_val == max_val:
    # Create bins array with the same value repeated
    bins = [min_val] * (num_bins + 1)
    # Put all values in the first bin
    counts = [0] * num_bins
    counts[0] = len(valid_numbers)
    
    return {
      "bins": bins,
      "counts": counts
    }
  
  bin_width = (max_val - min_val) / num_bins
  
  # Create bin boundaries with fixed precision to avoid floating point errors
  bins = [round(min_val + (bin_width * i), 10) for i in range(num_bins + 1)]
  
  # Initialize counts array
  counts = [0] * num_bins
  
  # Count values in each bin
  for num in valid_numbers:
    # Handle edge case for maximum value
    if num == max_val:
      counts[-1] += 1
      continue
      
    bin_index = int((num - min_val) / bin_width)
    counts[bin_index] += 1
    
  return {
    "bins": bins,
    "counts": counts
  } 