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

  try:
    start = int(inputs.get("start", 0))
  except (ValueError, TypeError):
    raise ValueError("array-slice: 'start' must be a valid number")

  try:
    end = int(inputs.get("end")) if inputs.get("end") is not None else None
  except (ValueError, TypeError):
    raise ValueError("array-slice: 'end' must be a valid number")
  
  return {
    "array": array[start:end]
  } 