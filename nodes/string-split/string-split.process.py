from typing import Any

async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
  text = str(inputs.get("text", ""))
  delimiter = settings.get("delimiter", " ")
  limit = int(settings.get("limit", -1))
  
  if limit > 0:
    parts = text.split(delimiter, limit)
    parts = parts[:limit]
  else:
    parts = text.split(delimiter)
    
  return {
    "parts": parts
  } 