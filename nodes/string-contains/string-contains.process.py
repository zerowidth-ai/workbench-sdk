from typing import Any

async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
  text = str(inputs.get("text", ""))
  search = str(inputs.get("search", ""))
  
  if not settings.get("case_sensitive", True):
    text = text.lower()
    search = search.lower()
    
  position = text.find(search)
  return {
    "contains": position != -1,
    "position": position
  } 