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
    
  reversed_array = array[::-1]
  indices = list(range(len(array) - 1, -1, -1))
  
  return {
    "array": reversed_array,
    "indices": indices
  } 