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
  separator = str(inputs.get("separator", ","))
  
  return {
    "text": separator.join(str(x) for x in array)
  } 