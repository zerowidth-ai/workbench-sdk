from typing import Any

async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
  base = float(inputs.get("base", 0))
  exponent = float(inputs.get("exponent", 0))
  
  return {
    "result": base ** exponent
  } 