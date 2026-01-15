from typing import Any

async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
  # Convert various truthy/falsy values to boolean
  condition = False
  
  if isinstance(inputs.get("condition"), bool):
    condition = inputs.get("condition")
  elif isinstance(inputs.get("condition"), (int, float)):
    condition = inputs.get("condition") != 0
  elif isinstance(inputs.get("condition"), str):
    lowered = inputs.get("condition", "").lower().strip()
    condition = lowered != "" and \
                lowered != "false" and \
                lowered != "0" and \
                lowered != "no" and \
                lowered != "null" and \
                lowered != "undefined"
  else:
    condition = bool(inputs.get("condition"))
  
  # Initialize the output dictionary
  output = {}
  
  # Add result to output only if the corresponding input exists
  if condition:
    if "if_true" in inputs:
      output["result"] = inputs.get("if_true")
    output["true_path"] = True
  else:
    if "if_false" in inputs:
      output["result"] = inputs.get("if_false")
    output["false_path"] = True
  
  return output 