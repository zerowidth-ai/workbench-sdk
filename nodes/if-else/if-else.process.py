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
  
  # Return result based on condition, matching JS behavior
  result = inputs.get("if_true") if condition else inputs.get("if_false")

  if condition:
    return {
      "result": result,
      "true_path": True,
    }
  else:
    return {
      "result": result,
      "false_path": True,
    } 