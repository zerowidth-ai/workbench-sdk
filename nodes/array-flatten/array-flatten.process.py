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
    
  max_depth = settings.get("depth", -1)
  skip_empty = settings.get("skip_empty", True)
  
  def flatten(arr, depth=0):
    if skip_empty and len(arr) == 0:
      return []
    
    if max_depth != -1 and depth >= max_depth:
      return arr.copy()
    
    result = []
    for item in arr:
      if isinstance(item, list):
        if skip_empty and len(item) == 0:
          continue
          
        if max_depth == -1 or depth < max_depth:
          flattened = flatten(item, depth + 1)
          result.extend(flattened)
        else:
          result.append(item)
      else:
        result.append(item)
        
    return result
  
  flattened = flatten(array)
  
  return {
    "array": flattened
  } 