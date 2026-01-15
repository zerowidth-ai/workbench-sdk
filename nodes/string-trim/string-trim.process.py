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
  chars = inputs.get("chars")
  mode = settings.get("mode", "both")
  
  if chars:
    pattern = ""
    if mode in ["both", "start"]:
      pattern += f"^[{re.escape(chars)}]+"
    if mode in ["both", "end"]:
      if pattern:
        pattern += "|"
      pattern += f"[{re.escape(chars)}]+$"
    return {
      "text": re.sub(pattern, "", text)
    }
  
  if mode == "start":
    return {"text": text.lstrip()}
  elif mode == "end":
    return {"text": text.rstrip()}
  else:
    return {"text": text.strip()} 