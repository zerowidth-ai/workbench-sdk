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
    
  property_name = inputs.get("property", "")
  
  def extract_property(item):
    if isinstance(item, dict):
      return item.get(property_name)
    return None
    
  return {
    "array": list(map(extract_property, array))
  } 