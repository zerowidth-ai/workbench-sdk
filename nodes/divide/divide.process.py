from typing import Any

async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:

  # avoid division by zero 
  if inputs.get("b") == 0:
    return {
      "result": None
    }

  a = float(inputs.get("a", 0))
  b = float(inputs.get("b", 1))  # Avoid division by zero
  
  return {
    "result": a / b
  } 