from typing import Any
from datetime import datetime

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
    
  order = settings.get("order", "ascending")
  type_name = settings.get("type", "string")
  property_name = settings.get("property")
  case_sensitive = settings.get("case_sensitive", True)
  
  def get_value(item):
    value = item.get(property_name) if property_name and isinstance(item, dict) else item
    
    if value is None:
      return None
      
    if type_name == "number":
      try:
        return float(value)
      except (ValueError, TypeError):
        return 0
        
    elif type_name == "date":
      try:
        return datetime.fromisoformat(str(value)).timestamp()
      except (ValueError, TypeError):
        return 0
        
    else: # string
      value = str(value)
      return value if case_sensitive else value.lower()
  
  def compare(item):
    value = get_value(item)
    return (value is None, value)  # None values sort last
    
  reverse = order != "ascending"
  return {
    "array": sorted(array, key=compare, reverse=reverse)
  } 