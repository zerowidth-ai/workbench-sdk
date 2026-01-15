from typing import Any
import re

async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
  text = str(inputs.get("text", ""))
  search = str(inputs.get("search", ""))
  replacement = str(inputs.get("replacement", ""))
  
  if settings.get("regex", False):
    flags = 0 if settings.get("case_sensitive", True) else re.IGNORECASE
    return {
      "text": re.sub(search, replacement, text, flags=flags)
    }
  
  if not settings.get("case_sensitive", True):
    search = re.escape(search)
    return {
      "text": re.sub(search, replacement, text, flags=re.IGNORECASE)
    }
    
  return {
    "text": text.replace(search, replacement)
  } 