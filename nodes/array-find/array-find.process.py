from typing import Any
import re

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
    
  value = inputs.get("value")
  mode = settings.get("mode", "equals")
  case_sensitive = settings.get("case_sensitive", True)
  property_name = settings.get("property")
  
  def get_value(item):
    if property_name and isinstance(item, dict):
      return item.get(property_name)
    return item
  
  def compare(item):
    item_value = get_value(item)
    if item_value is None or value is None:
      return item_value == value
      
    str_value = str(value)
    str_item = str(item_value)
    
    if not case_sensitive:
      str_value = str_value.lower()
      str_item = str_item.lower()
      
    if mode == "contains":
      return str_value in str_item
      
    elif mode == "starts_with":
      return str_item.startswith(str_value)
      
    elif mode == "ends_with":
      return str_item.endswith(str_value)
      
    elif mode == "regex":
      try:
        flags = 0 if case_sensitive else re.IGNORECASE
        return bool(re.search(str_value, str_item, flags=flags))
      except:
        return False
        
    else: # equals
      return str_item == str_value
  
  for i, item in enumerate(array):
    if compare(item):
      return {
        "found": True,
        "item": item,
        "index": i
      }
  
  return {
    "found": False,
    "item": None,
    "index": -1
  } 