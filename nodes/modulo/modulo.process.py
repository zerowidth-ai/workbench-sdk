from typing import Any

async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
  # Validate inputs are numbers
  dividend = inputs.get("dividend")
  divisor = inputs.get("divisor")
  
  try:
    num_dividend = float(dividend)
  except (ValueError, TypeError):
    raise ValueError("Dividend must be a number")
    
  try:
    num_divisor = float(divisor)
  except (ValueError, TypeError):
    raise ValueError("Divisor must be a number")
    
  if num_divisor == 0:
    raise ValueError("Division by zero")
    
  # JavaScript-like modulo implementation
  # In JavaScript, the sign of the result matches the sign of the dividend
  # regardless of the sign of the divisor
  
  # Calculate absolute values
  abs_dividend = abs(num_dividend)
  abs_divisor = abs(num_divisor)
  
  # Calculate modulo with absolute values
  abs_result = abs_dividend % abs_divisor
  
  # Apply the sign of the dividend to the result
  if num_dividend < 0 and abs_result != 0:
    result = -abs_result
  else:
    result = abs_result
  
  # Round to 10 decimal places to match JavaScript implementation
  result = round(result, 10)
  
  return {
    "result": result
  } 