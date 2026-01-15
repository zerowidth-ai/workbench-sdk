from typing import Any

async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
  array = inputs.get("array", [])
  if not isinstance(array, list):
    array = [array]
    
  start = int(inputs.get("start", 0))
  end = int(inputs.get("end")) if inputs.get("end") is not None else None
  
  return {
    "array": array[start:end]
  } 