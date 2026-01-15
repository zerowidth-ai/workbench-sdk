from typing import Any

async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
  array = inputs.get("array", [])
  mode = settings.get("mode", "size")
  size = int(settings.get("size", 2))
  
  # Handle count with special care for 0
  count_setting = settings.get("count")
  if count_setting is None:
    count = 2
  else:
    count = int(count_setting)
  
  chunks = []
  
  if mode == "size":
    # Split into chunks of specified size
    for i in range(0, len(array), size):
      chunks.append(array[i:i + size])
  
  elif mode == "count":
    # Split into specified number of chunks
    if count <= 0:
      chunks = [array[:]]  # Return the entire array as a single chunk
    else:
      chunk_size = (len(array) + count - 1) // count  # Ceiling division
      for i in range(0, len(array), chunk_size):
        chunks.append(array[i:i + chunk_size])
  
  return {
    "chunks": chunks
  } 