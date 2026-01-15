from typing import Any

async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
  value = inputs.get("value")
  cases = inputs.get("cases", []) if isinstance(inputs.get("cases"), list) else []
  outputs = inputs.get("outputs", []) if isinstance(inputs.get("outputs"), list) else []
  
  # Find matching case
  match_index = -1
  for i, case_value in enumerate(cases):
    # Handle different types of equality
    if isinstance(value, (int, float)) or isinstance(case_value, (int, float)):
      try:
        if float(value) == float(case_value):
          match_index = i
          break
      except (ValueError, TypeError):
        pass
    
    if isinstance(value, str) or isinstance(case_value, str):
      try:
        if str(value) == str(case_value):
          match_index = i
          break
      except (ValueError, TypeError):
        pass
    
    # Default to Python equality
    if value == case_value:
      match_index = i
      break
  
  # Prepare result object
  result = {
    "case_index": match_index,
    "matched": match_index >= 0
  }
  
  if match_index >= 0:
    # Case matched
    result["result"] = outputs[match_index] if match_index < len(outputs) else value
    
    # Add dynamic output for the matched case
    result[f"case_{match_index}"] = True
  else:
    # No match, use default
    result["result"] = inputs.get("default_output")
  
  return result 