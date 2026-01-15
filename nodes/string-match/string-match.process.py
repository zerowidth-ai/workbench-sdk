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
  pattern = str(inputs.get("pattern", ""))
  
  try:
    flags = 0
    if not settings.get("case_sensitive", True):
      flags |= re.IGNORECASE
      
    if settings.get("global", False):
      matches = list(re.finditer(pattern, text, flags=flags))
      return {
        "matched": len(matches) > 0,
        "matches": [m.group(0) for m in matches],
        "groups": list(matches[0].groups()) if matches else []
      }
    else:
      match = re.search(pattern, text, flags=flags)
      return {
        "matched": match is not None,
        "matches": [match.group(0)] if match else [],
        "groups": list(match.groups()) if match else []
      }
  except:
    return {
      "matched": False,
      "matches": [],
      "groups": []
    } 