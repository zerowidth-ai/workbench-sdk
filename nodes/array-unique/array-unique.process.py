from typing import Any
import json

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
    
  mode = settings.get("mode", "value")
  property_name = settings.get("property")
  case_sensitive = settings.get("case_sensitive", True)
  
  def get_compare_value(item):
    value = item
    
    if mode == "property" and property_name:
      if isinstance(item, dict):
        value = item.get(property_name)
      else:
        value = None
        
    if mode == "json":
      try:
        return json.dumps(item, sort_keys=True)
      except:
        return str(item)
        
    if isinstance(value, str) and not case_sensitive:
      return value.lower()
      
    return value
    
  seen = {}
  duplicates = []
  indices = []
  
  for i, item in enumerate(array):
    compare_value = get_compare_value(item)
    # Use repr for non-string keys to handle unhashable types
    key = compare_value if isinstance(compare_value, (str, int, float, bool)) else repr(compare_value)
    
    if key not in seen:
      seen[key] = (item, i)
    else:
      duplicates.append(item)
      
  unique = []
  for item, index in seen.values():
    unique.append(item)
    indices.append(index)
    
  return {
    "array": unique,
    "count": len(unique),
    "duplicates": duplicates,
    "indices": indices
  } 