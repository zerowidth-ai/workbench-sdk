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
    
  value = inputs.get("value")
  condition = settings.get("condition", "equals")
  case_sensitive = settings.get("case_sensitive", True)
  
  def compare(item):
    if condition == "equals":
      if isinstance(item, str) and isinstance(value, str) and not case_sensitive:
        return item.lower() == value.lower()
      return item == value
      
    elif condition == "not_equals":
      if isinstance(item, str) and isinstance(value, str) and not case_sensitive:
        return item.lower() != value.lower()
      return item != value
      
    elif condition == "greater_than":
      return item > value
      
    elif condition == "less_than":
      return item < value
      
    elif condition == "contains":
      if isinstance(item, str) and isinstance(value, str):
        return value.lower() in item.lower() if not case_sensitive else value in item
      return False
      
    elif condition == "not_contains":
      if isinstance(item, str) and isinstance(value, str):
        return value.lower() not in item.lower() if not case_sensitive else value not in item
      return True
      
    elif condition == "exists":
      return item is not None
      
    elif condition == "not_exists":
      return item is None
      
    return True
  
  return {
    "array": list(filter(compare, array))
  } 