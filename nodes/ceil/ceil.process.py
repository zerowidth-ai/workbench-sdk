from typing import Any
import math

async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
  number = float(inputs.get("number", 0))
  
  return {
    "result": math.ceil(number)
  } 