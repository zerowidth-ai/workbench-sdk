from typing import Any

async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
  input1 = bool(inputs.get("input1"))
  input2 = bool(inputs.get("input2"))
  
  return {
    "value": not (input1 or input2)
  } 