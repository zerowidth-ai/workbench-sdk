from typing import Any

async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
  text = str(inputs.get("text", ""))
  start = int(inputs.get("start", 0))
  end = int(inputs.get("end")) if inputs.get("end") is not None else None
  
  return {
    "text": text[start:end]
  } 